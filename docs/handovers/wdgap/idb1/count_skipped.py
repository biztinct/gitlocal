# WDGAP IDB1 — READ-ONLY count for the deploy agent, one database at a time:
#   odoo-bin shell -c /etc/odoo-server.conf -d <db> --no-http < count_skipped.py
# Writes nothing (rolls back at the end). Prints counts only — no names, no
# account numbers. Works before AND after the IDB1 upgrade (it reads only the
# Vietnamese bank file's own row check and the employees' bank accounts).
#
# Question answered: of the active employees, how many would the Vietnamese
# bank file leave out for their bank details, and of those how many have an
# approved bank account on record (so the payment list (any bank) can pay them)?
from collections import Counter

from odoo.addons.pb_bank_ocr.models import vn_bank_dictionary as vnd

Emp = env['hr.employee'].sudo()
registry = env['pb.bank.registry']
by_company = {}
for emp in Emp.search([('active', '=', True)]):
    reasons = []
    if not vnd.account_ok(emp.vietnam_bank_account_number or ''):
        reasons.append('invalid account')
    if not (emp.vietnam_bank_account_name or emp.name or '').strip():
        reasons.append('missing account holder')
    if not registry.match(emp.vietnam_bank_name or ''):
        reasons.append('unknown bank')
    if not reasons:
        continue
    row = by_company.setdefault(emp.company_id.name or '-', Counter())
    row['left out of the Vietnamese file'] += 1
    if emp.bank_account_ids[:1]:
        row['has an approved account (payment list can pay)'] += 1
        bank = (emp.bank_account_ids[:1].bank_id.name or '').strip() or '(no bank name)'
        row['bank: ' + bank] += 1
    else:
        row['no account at all'] += 1
print('IDB1 COUNT db=%s' % env.cr.dbname)
for company, row in sorted(by_company.items()):
    print('  %s: %s' % (company, dict(row.most_common())))
env.cr.rollback()
