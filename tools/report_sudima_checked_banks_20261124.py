"""Produce a concise local client-action report from private migration receipts."""
import html
import json
import sys
from pathlib import Path

root, target = map(Path, sys.argv[1:3])
plan = json.loads((root / 'plan.json').read_text())
receipt = json.loads((root / 'applied.json').read_text())
assert receipt['committed'] and receipt['database'] == 'sudima'
esc = html.escape
waiting = [r for r in plan['rows'] if r['status'] == 'waiting_registration' and r['code'] != '039']
assert len(waiting) == 28
rows = ''.join('<tr><td>' + esc(r['code']) + '</td><td>' + esc(r['name']) + '</td><td>' +
               ('Created' if not r['employee_id'] else 'Existing; name corrected') + '</td></tr>' for r in waiting)
counts = receipt['counts']
content = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sudima — November roster and bank update</title><style>
body{font:15px/1.5 system-ui,sans-serif;color:#172b44;background:#f4f7fa;margin:0;padding:28px}
main{max-width:1180px;margin:auto;background:white;padding:28px;border-radius:12px}h1{font-size:26px;margin:0 0 8px}
.status{background:#e9f5ef;padding:14px;border-left:4px solid #26734d}.muted{color:#52667b;font-size:13px}
table{border-collapse:collapse;width:100%;margin:14px 0}th,td{text-align:left;vertical-align:top;padding:12px;border:1px solid #d9e2eb}
th{background:#edf3f9}details{margin-top:18px;border:1px solid #d9e2eb;border-radius:8px;padding:14px}summary{cursor:pointer;font-weight:650}
.scroll{overflow:auto}@media(max-width:700px){body{padding:8px}main{padding:14px}table{min-width:680px}}@media print{body{background:white;padding:0}main{padding:0}details{break-inside:avoid}}
</style><main><h1>Sudima — November roster and bank update</h1>
<p class="muted">Updated 24 November 2026 · Production: sudima.payobook.com · Checked client workbook dated 6 November 2026</p>
<p class="status"><b>Saved:</b> 27 new HR profiles, 233 employee-name corrections and 246 bank-field corrections.
All 576 complete bank records now agree with their linked payment accounts. New profiles have no contract, salary, bank account or login added.</p>
<h2>Information still needed</h2><div class="scroll"><table><thead><tr><th>Employee / item</th><th>Client provided</th><th>Saved / not updated</th><th>What to confirm / recommendation</th></tr></thead><tbody>
<tr><td><b>029 — LÊ THỊ DIỆU QUỚI</b></td><td>Account number and holder; bank name blank.</td><td>Name corrected. Bank details left unset.</td><td>Please provide the bank name. Then save the supplied account; do not guess the bank from its number.</td></tr>
<tr><td><b>039 — THÁI HỒ TUYẾT MAI</b></td><td>“Wait for bank account registration.”</td><td>An older account is still saved; it was not replaced by the placeholder.</td><td>Please confirm whether the old account is valid, or provide the new bank details. Verify this account before making a payment.</td></tr>
<tr><td><b>28 employees listed below</b></td><td>“Wait for bank account registration.”</td><td>27 profiles created; employee 1276 already existed and its name was corrected. No bank details added.</td><td>Provide bank name, account number and account holder once registration is complete.</td></tr>
<tr><td><b>1264 / 12641</b></td><td>The extra final “1” on a five-digit code means probation. Neither record appears in the latest roster.</td><td>1264 = THẠCH QUANG.<br>12641 = ĐẶNG VĂN HỒ.<br>Both left unchanged.</td><td>Please confirm the correct employee name/code for each. The names differ, so these records must not be merged automatically.</td></tr>
</tbody></table></div>
<details><summary>28 employees awaiting bank registration</summary><div class="scroll"><table><thead><tr><th>Code</th><th>Name</th><th>HR profile</th></tr></thead><tbody>''' + rows + '''</tbody></table></div></details>
<details><summary>Completed work and verification</summary>
<p>Matched 579 existing employees by employee code and joining date; created the 27 authorized missing profiles. Source codes, including leading zeroes, were retained. The 233 corrected names had matching codes and joining dates in the saved records; their contact names were corrected too.</p>
<p>576 complete bank records verified: 246 employee bank-field corrections, 181 linked-account corrections and 168 account-link corrections. These counts overlap. Thirteen blank bank names were retained from a matching saved account; only 029 could not be resolved. Previous bank records and native bank-change audit history were preserved.</p>
<p>All 27 new profiles have Country of Work set to Vietnam. New profiles use existing departments: Factory 1 → Xưởng 1; Factory 2/3/4 → Xưởng 2/3/4 + Office 2/3/4; New Office → Office VPM.</p>
<p>Contracts, payroll amounts and formulas, attendance, leave and users were unchanged. Obsolete pending bank import RD00185 was cancelled through the normal workflow: its proposed changes exactly matched RD00189, already applied on 7 November. This clears the stale bank-approval warning and prevents that old proposal being applied later. No email was sent. A permanent database backup and full before/after receipt are retained on the server.</p>
<p><b>Probation codes:</b> this workbook contains only 3- and 4-digit base codes. No new five-digit profiles were created. Eight older five-digit records remain separate and unchanged; the inconsistent 1264/12641 pair is listed above. This bank repair does not change future timesheet/payroll import matching.</p>
<p>Applied repair: <code>8b93b285f</code>; country setup: <code>64df6b50d</code>. Data target: <code>sudima</code>. The joining-date display fix (<code>7b4d349d9</code>, guarded deployment <code>465faa09f</code>) was deployed across all five active databases with a brief shared-service restart; no schema change or database upgrade was needed. Combined deployed custom modules and installed versions checked across payobook, payobook_template, p0clone, rize and sudima. ABM untouched.</p><p>Checks passed: full rollback rehearsal, 576 bank records, 606 saved names and joining dates, all 27 new profiles, zero-change repeat, five joining-date regression tests, and 207 deployed custom-module trees/installed versions across all five databases. Chrome confirmed the corrected joining date, new profile, saved bank/holder/account, removal of the stale approval warning, and report readability.</p>
</details><p class="muted">Source: Danh sách CNV tới 06-11-2026 Sudima_check.xlsx · Source SHA-256: ''' + esc(plan['source_sha256']) + '''</p></main></html>'''
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(content)
print(target)
