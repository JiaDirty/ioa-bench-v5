# 16 — Reference IoA Worlds and Sandbox Services

## 1. Standard synthetic worlds

v1 maintains a shared library of approximately six worlds. Individual suites select 2–3 applicable worlds while retaining independent datasets.

Recommended worlds:
- `W01_ENTERPRISE_OPS`: procurement, invoices, approvals, internal reports.
- `W02_FINANCIAL_SERVICES`: synthetic accounts, risk review, payment authorization; no real funds.
- `W03_RESEARCH_LAB`: synthetic experiments, datasets, equipment scheduling, evidence review.
- `W04_LOGISTICS_SUPPLY`: suppliers, shipments, routing, manifests, exceptions.
- `W05_CLOUD_SOFTWARE`: synthetic services, deployments, incidents, access requests.
- `W06_ADMIN_CASEWORK`: synthetic institutional case processing, forms, records and policy rules.

## 2. Sandbox design

Every world exposes versioned local services with real state transitions inside the sandbox. Examples:
- document/record read/write;
- approval request/approve/reject;
- message/mail send/forward;
- service registry/discovery;
- database query/update;
- ticket create/close;
- payment-like synthetic transaction;
- deployment-like synthetic action.

No service may touch real user accounts, real money, real production systems or public Internet.

## 3. Truth vs visible state

World visible state may contain incomplete/misleading claims as scenario data. Canonical world truth stays in Oracle. Sandbox service business state and Oracle truth are different concepts and must not be merged.

## 4. World determinism

A world snapshot is seedable and content-hashed. Paired control/risk cases should derive from the same world snapshot wherever causal comparison requires it.
