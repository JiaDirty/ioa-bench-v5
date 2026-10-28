"""Interim GOAL_PROGRESS refresh after the v1.2b/v1.2c re-audit rounds (zero calls)."""
import json
from pathlib import Path

run = Path('artifacts/v5/tree_factory/tf-20261024-r1')
summary = json.loads((run / 'ab/RUN_SUMMARY.json').read_text(encoding='utf-8'))
cost = json.loads((run / 'ab/COST_AND_YIELD.json').read_text(encoding='utf-8'))
accepted_rows = [row for row in summary['rows'] if row.get('admission') == 'DEV_ACCEPTED']
by_suite = {}
for row in accepted_rows:
    by_suite.setdefault(row['task'][:4], []).append(f"{row['task']}/{row['route'][:9]}")
progress = json.loads((run / 'GOAL_PROGRESS.json').read_text(encoding='utf-8'))
progress['iteration'] = 6
progress['stages']['M5'] = {
    'status': 'IN_PROGRESS_T321_ONLY',
    'evidence': ['ab/RUN_SUMMARY.json', 'ab/AB_RESULTS.csv', 'ab/COST_AND_YIELD.json',
                 'ab/FAILURE_FUNNEL.csv', 'STOP_RESOLUTION_7.json', 'STOP_RESOLUTION_8.json',
                 'STOP_RESOLUTION_9.json', 'STOP_RESOLUTION_10.json'],
    'notes': 'frozen A/B fully executed (18/18); v1.2b re-audit delivered 7 DEV_ACCEPTED '
             'pairs (T331 x3, T362 x4); T321 0/6 spent (1 honest dedup rejection, 2 v12b '
             'compliance quarantines superseded by the v1.2c contract optimization, 1 honest '
             'two-effort disagreement, 2 transport cuts) and 3 v12c candidates remain blocked '
             'by gateway stream cuts (STOP_RESOLUTION_11 pending)',
}
progress['goal_conditions']['G5_real_dev_closed_loop'] = (
    'PARTIAL: 7 real new DEV_ACCEPTED pairs with all hard gates+replay+full-history novelty '
    '(T331 ok, T362 ok); T321 minimum unmet pending gateway window')
progress['goal_conditions']['G6_fair_quantification'] = (
    'PASS_OFFLINE_DELIVERABLES_PLUS_LIVE_FUNNEL: structure cells, cost bounds, frozen '
    'denominators and the executed 18-unit funnel recorded; live per-route comparison '
    'complete for generation+audit legs')
progress['new_accepted_pairs'] = len(accepted_rows)
progress['new_accepted_by_suite'] = by_suite
progress['paid_completions_with_receipt'] = cost['paid_completions_with_receipt']
progress['upper_usd_bound'] = cost['upper_usd_bound_known_receipts']
progress['request_unknown_count'] = 9  # real transport unknowns; all ids forbidden-forever
progress['requests_401_403'] = 0
progress['goal_status'] = 'IN_PROGRESS_T321_GATEWAY_WINDOW'
progress['resume_instructions'] = (
    'when the gateway stabilizes: write STOP_RESOLUTION_11 for audit-high-8eb9562657d138d0 '
    '(09:06 stream cut), then run scratch/_tmp_reaudit_t321.py (fresh -v12c ids) for '
    'T321-t1-B/T321-t2-B/T321-t3-B; afterwards rerun scripts/v5/tf_m7_closeout.py and commit')
(run / 'GOAL_PROGRESS.json').write_text(json.dumps(progress, ensure_ascii=False, indent=1),
                                        encoding='utf-8')
print(json.dumps({'accepted': len(accepted_rows), 'by_suite': {k: len(v) for k, v in by_suite.items()},
                  'paid': cost['paid_completions_with_receipt'],
                  'upper_usd': cost['upper_usd_bound_known_receipts']}, ensure_ascii=False))
