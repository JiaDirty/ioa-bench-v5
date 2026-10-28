"""Read-only, credential-free S1 diagnostics; never sends a completion."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import time
from urllib.parse import urlsplit


HOSTS = ("aihubmix.com", "api.inferera.com")  # Local official quick-start.md.


def utc():
    return datetime.now(timezone.utc).isoformat()


def proxy_description(value):
    if not value:
        return {"set": False}
    # Never persist userinfo, bypass lists, query strings or PAC credentials.
    parsed = urlsplit(value if "://" in value else "http://" + value)
    try:
        port = parsed.port
    except ValueError:
        port = None
    return {"set": True, "scheme": parsed.scheme, "host": parsed.hostname,
            "port": port, "has_credentials": parsed.username is not None}


def scrub(text):
    text = re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", text)
    return re.sub(r"(?i)(bearer\s+|api[_-]?key[=: ]+)[^\s]+", r"\1[REDACTED]", text)


def proxy_context():
    env = {key: proxy_description(os.environ.get(key)) for key in
           ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")}
    env["NO_PROXY"] = {"set": bool(os.environ.get("NO_PROXY"))}
    result = {"environment": env, "wininet": {}, "winhttp": "UNKNOWN"}
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            def read(name, default=None):
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    return default
            server = read("ProxyServer", "")
            result["wininet"] = {"enabled": bool(read("ProxyEnable", 0)),
                                 "server": proxy_description(server),
                                 "auto_config_set": bool(read("AutoConfigURL")),
                                 "bypass_set": bool(read("ProxyOverride"))}
        command = subprocess.run(["netsh", "winhttp", "show", "proxy"],
                                 capture_output=True, text=True, errors="replace", check=False)
        result["winhttp"] = {"exit_code": command.returncode, "output": scrub(command.stdout)}
    return result


def probe_host(host):
    row = {"host": host, "at_utc": utc(), "addresses": []}
    try:
        addresses = sorted({(family, addr[0]) for family, _, _, _, addr in
                            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    except OSError as exc:
        return {**row, "dns": "FAIL", "error": scrub(str(exc))}
    row["dns"] = "PASS"
    for family, address in addresses:
        started = time.monotonic()
        item = {"family": "IPv6" if family == socket.AF_INET6 else "IPv4", "ip": address}
        try:
            with socket.socket(family, socket.SOCK_STREAM) as stream:
                stream.settimeout(5)
                stream.connect((address, 443))
                item.update(tcp="PASS", tcp_ms=round((time.monotonic() - started) * 1000, 2))
                with ssl.create_default_context().wrap_socket(stream, server_hostname=host) as secure:
                    cert = secure.getpeercert()
                    item.update(tls="PASS", tls_version=secure.version(), cipher=secure.cipher()[0],
                                certificate_not_after=cert.get("notAfter"),
                                certificate_issuer=cert.get("issuer"))
        except OSError as exc:
            item.update(tcp=item.get("tcp", "FAIL"), tls="FAIL" if item.get("tcp") == "PASS" else "NOT_RUN",
                        error_type=type(exc).__name__, error=scrub(str(exc)))
        item["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
        row["addresses"].append(item)
    return row


def classify_http(code, returncode, metrics=None):
    if code:
        if code in (401, 403):
            return "AUTH_OR_PERMISSION"
        if code == 429:
            return "RATE_LIMIT"
        if code >= 500:
            return "UPSTREAM"
        if code in (400, 422):
            return "SCHEMA"
        return "HTTP_REACHED"
    if returncode == 28 and metrics:
        if not metrics.get("time_connect"):
            return "NETWORK_CONNECT"
        if not metrics.get("time_appconnect"):
            return "TLS"
        return "NETWORK_READ_TIMEOUT"
    return {5: "DNS", 6: "DNS", 7: "NETWORK_CONNECT", 35: "TLS", 60: "TLS"}.get(
        returncode, "UNRESOLVED_EXTERNAL")


def probe_http(url, directory, name, mode="current", ipv=None):
    """Only GET/HEAD and no credentials. Current means curl's existing env policy."""
    body, headers = directory / (name + ".body"), directory / (name + ".headers")
    command = [shutil.which("curl.exe") or "curl", "--silent", "--show-error",
               "--connect-timeout", "6", "--max-time", "15", "--http1.1",
               "--output", str(body), "--dump-header", str(headers), "--write-out", "%{json}"]
    if mode == "direct":
        command += ["--noproxy", "*"]
    elif mode == "configured-wininet":
        proxy = proxy_context()["wininet"]
        server = proxy.get("server", {})
        if not proxy.get("enabled") or server.get("has_credentials") or not server.get("host"):
            raise ValueError("no existing credential-free WinINET proxy configured")
        command += ["--proxy", f"{server['scheme']}://{server['host']}:{server['port']}", "--noproxy", ""]
    if ipv:
        command += ["-" + str(ipv)]
    command.append(url)
    started = utc()
    completed = subprocess.run(command, capture_output=True, text=True, errors="replace", check=False,
                               timeout=20)
    try:
        metrics = json.loads(completed.stdout)
    except ValueError:
        metrics = {}
    code = int(metrics.get("http_code") or 0)
    # Curl's full JSON includes certificate data and environment-dependent proxy URLs.
    allowed = ("http_code", "remote_ip", "local_ip", "remote_port", "num_connects", "size_download",
               "time_namelookup", "time_connect", "time_appconnect", "time_starttransfer", "time_total",
               "ssl_verify_result", "exitcode", "errormsg", "http_connect")
    saved_headers = {}
    if headers.exists():
        for line in headers.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                if key.lower() in {"date", "server", "content-type", "x-request-id", "x-aihubmix-model", "retry-after"}:
                    saved_headers[key.lower()] = value.strip()
        headers.unlink()
    row = {"at_utc": started, "url": url, "method": "GET", "credentials_sent": False,
           "path_mode": mode, "ipv": ipv or "default", "curl_returncode": completed.returncode,
           "http_status": code or None, "metrics": {k: metrics[k] for k in allowed if k in metrics},
           "headers": saved_headers, "stderr": scrub(completed.stderr),
           "category": classify_http(code, completed.returncode, metrics), "command": command}
    if body.exists():
        row.update(body_sha256=hashlib.sha256(body.read_bytes()).hexdigest(), body_bytes=body.stat().st_size)
    (directory / (name + ".json")).write_text(json.dumps(row, indent=2), encoding="utf-8")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    context = proxy_context()
    version = subprocess.run([shutil.which("curl.exe") or "curl", "--version"],
                             capture_output=True, text=True, check=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        hosts = list(pool.map(probe_host, HOSTS))
    jobs = []
    for host in HOSTS:
        jobs += [(f"https://{host}/model-data/index.json", host + "-direct", "direct", 4),
                 (f"https://{host}/v1/models", host + "-current", "current", None)]
    if any(item.get("set") for key, item in context["environment"].items() if key != "NO_PROXY"):
        jobs.append(("https://aihubmix.com/model-data/index.json", "aihubmix-current-index", "current", None))
    with ThreadPoolExecutor(max_workers=2) as pool:
        http = list(pool.map(lambda job: probe_http(job[0], args.out, *job[1:]), jobs))
    result = {"at_utc": utc(), "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "mode": "READ_ONLY_NO_COMPLETION_NO_CREDENTIALS", "proxy": context, "dns_tcp_tls": hosts,
              "http": http, "curl_version": version.stdout, "ssl_default_paths": str(ssl.get_default_verify_paths()),
              "system_time_utc": utc(), "local_timezone": str(datetime.now().astimezone().tzinfo),
              "s1_gate": "NOT_ESTABLISHED_NO_COMPLETION", "global_settings_modified": False}
    (args.out / "NETWORK_PATH_DIAGNOSIS.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"hosts": hosts, "http": [{k: r[k] for k in ("url", "path_mode", "http_status", "curl_returncode", "category")} for r in http], "proxy": context}, ensure_ascii=False))


if __name__ == "__main__":
    main()
