"""Owner-authorized Sudima roster/bank correction, run in Odoo shell.

SUDIMA_BANK_DIR holds the private, source-hashed plan and permanent backup.
Default is rollback. SUDIMA_BANK_APPLY=1 commits atomically. Native manual
bank-change history is retained; no approval is impersonated or bypassed.
Existing contracts, pay, attendance, users and probation variants are preserved.
"""
import collections
import json
import os
import re
import unicodedata
from pathlib import Path

assert env.cr.dbname == 'sudima'
root = Path(os.environ['SUDIMA_BANK_DIR'])
apply = os.getenv('SUDIMA_BANK_APPLY') == '1'
plan = json.loads((root / 'plan.json').read_text())
assert plan['source_sha256'] == '74f194f6dceb8bbba678955839c0619a76b8809215b86235676685bedcb5b5a6'
assert plan['new_profiles_authorized'] and len(plan['rows']) == 606
if apply:
    assert (root / 'sudima-before.dump').stat().st_size > 1000000
e = env(user=2500, context=dict(env.context, allowed_company_ids=[1], lang='en_US',
                              mail_create_nosubscribe=True, mail_notrack=True,
                              tracking_disable=True, mail_notify_force_send=False))
assert e.user.login == 'ash@biztinct.com'
assert e.company.name == 'Sudima Panels Vietnam'
Emp = e['hr.employee'].sudo().with_context(active_test=False)
Account = e['res.partner.bank'].sudo().with_context(active_test=False)
History = e['pb.employee.bank.history'].sudo()
bank_fields = ['vietnam_bank_name', 'vietnam_bank_branch',
               'vietnam_bank_account_name', 'vietnam_bank_account_number']
departments = {'FACTORY 1': (289, 'Xưởng 1'), 'FACTORY 2': (303, 'Xưởng 2 + Office 2'),
               'FACTORY 3': (304, 'Xưởng 3 + Office 3'), 'FACTORY 4': (305, 'Xưởng 4 + Office 4'),
               'NEW OFFICE': (301, 'Office VPM')}
for ident, name in departments.values():
    dep = e['hr.department'].browse(ident)
    assert dep.name == name and dep.company_id.id == 1 and dep.active


def norm(v):
    return re.sub('[^a-z0-9]', '', ''.join(c for c in unicodedata.normalize('NFD', str(v or ''))
                                        if unicodedata.category(c) != 'Mn').lower().replace('đ', 'd'))


def digest(table):
    e.cr.execute('SELECT md5(coalesce(string_agg(md5(to_jsonb(t)::text),chr(10) ORDER BY id),\'\')) FROM ' + table + ' t')
    return e.cr.fetchone()[0]


# Serialize this repair and reject concurrent employee/bank edits until commit.
e.cr.execute("SELECT pg_advisory_xact_lock(hashtext('sudima-checked-banks-20261124'))")
e.cr.execute('LOCK TABLE hr_employee, res_partner_bank IN SHARE ROW EXCLUSIVE MODE')
protected = ['hr_contract', 'hr_payslip', 'hr_payslip_line', 'hr_payslip_run',
             'hr_attendance', 'hr_formula_config', 'hr_formula_rule', 'res_users',
             'pb_bank_change_request', 'mail_mail', 'hr_leave', 'hr_leave_allocation']
protected = [t for t in protected if e.cr.execute('SELECT to_regclass(%s)', (t,)) is None and e.cr.fetchone()[0]]
before = {t: digest(t) for t in protected}
history_before = History.search_count([])
counts = collections.Counter()
details = []
bank_changes = 0
for row in plan['rows']:
    emp = Emp.search([('company_id', '=', 1), ('employee_id', '=', row['code'])])
    assert len(emp) <= 1, (row['code'], 'duplicate base code')
    if row['employee_id']:
        assert emp.id == row['employee_id'] and emp.active
        assert emp.barcode == row['code'] and str(emp.date_of_joining) == row['join']
        assert emp.name in (row['old_name'], row['name']), (row['code'], 'name changed since review')
    elif not emp:
        emp = Emp.create({'name': row['name'], 'legal_name': row['name'], 'employee_id': row['code'],
                          'barcode': row['code'], 'date_of_joining': row['join'], 'sex': row['sex'],
                          'company_id': 1, 'payroll_country': 'VN',
                          'department_id': departments[row['source_department']][0]})
        counts['profiles_created'] += 1
    else:
        assert emp.name == row['name'] and str(emp.date_of_joining) == row['join']
        assert emp.department_id.id == departments[row['source_department']][0]
        assert not emp.user_id and not emp.pb_portal_user_id
        assert emp.payroll_country in (False, 'VN')
        if not emp.payroll_country:
            # These are the Vietnam factory/office roster's newly created profiles.
            emp.write({'payroll_country': 'VN'})
            counts['new_profile_work_countries_set'] += 1
    record = {'code': row['code'], 'employee_id': emp.id, 'name': row['name'], 'status': row['status']}
    if row['name_correction']:
        values = {}
        if emp.name != row['name']:
            values['name'] = row['name']
        if not emp.legal_name or norm(emp.legal_name) == norm(row['old_name']):
            if emp.legal_name != row['name']:
                values['legal_name'] = row['name']
        partner = emp.work_contact_id
        if partner and partner.name == row['old_name']:
            assert not Emp.search_count([('work_contact_id', '=', partner.id), ('id', '!=', emp.id)])
            partner.write({'name': row['name']})
            counts['contact_names_corrected'] += 1
        if values:
            emp.write(values)
            counts['employee_names_corrected'] += 1
    if row['status'] != 'ready':
        # A blank bank or placeholder must never overwrite existing payment data.
        if row['employee_id']:
            assert {f: emp[f] for f in bank_fields} == row['before_bank']
            assert set(emp.bank_account_ids.ids) == set(row['before_account_ids'])
        else:
            assert not emp.bank_account_ids and not any(emp[f] for f in bank_fields)
            assert not e['hr.contract'].sudo().search_count([('employee_id', '=', emp.id)])
        details.append(record)
        continue
    expected = {'vietnam_bank_name': row['bank'], 'vietnam_bank_account_name': row['holder'],
                'vietnam_bank_account_number': row['account']}
    current = {f: emp[f] for f in bank_fields}
    assert all((current[f] or '') in ((row['before_bank'][f] or ''), (expected.get(f, current[f]) or ''))
               for f in bank_fields), (row['code'], 'bank details changed since review')
    # A branch from a different old account/bank is not supported by this workbook.
    if (current['vietnam_bank_account_number'] or '') != row['account'] or (current['vietnam_bank_name'] or '') != row['bank']:
        expected['vietnam_bank_branch'] = False
    values = {f: v for f, v in expected.items() if (emp[f] or '') != (v or '')}
    if values:
        record['before_bank'] = current
        emp.write(values)
        bank_changes += 1
        counts['bank_master_corrected'] += 1
    partner = emp.work_contact_id
    if not partner:
        partner = e['res.partner'].sudo().create({'name': emp.name, 'company_id': 1, 'type': 'private'})
        emp.work_contact_id = partner
    bank = e['res.bank'].sudo().search([('name', '=', row['bank'])])
    assert len(bank) == 1
    account = Account.search([('partner_id', '=', partner.id)]).filtered(
        lambda a: re.sub(r'\D', '', a.acc_number or '') == row['account'])
    assert len(account) <= 1, (row['code'], 'duplicate contact account')
    vals = {'acc_holder_name': row['holder'], 'bank_id': bank.id, 'active': True}
    if not account:
        account = Account.create(dict(vals, acc_number=row['account'], partner_id=partner.id, company_id=1))
        counts['payment_accounts_created'] += 1
    else:
        assert not Emp.search_count([('bank_account_ids', 'in', account.ids), ('id', '!=', emp.id)])
        changes = {k: v for k, v in vals.items() if (account[k].id if k == 'bank_id' else account[k]) != v}
        if changes:
            account.write(changes)
            counts['payment_accounts_corrected'] += 1
    if emp.bank_account_ids.ids != account.ids:
        record['previous_account_links'] = emp.bank_account_ids.ids
        # Preserve old account records and financial history; detach incorrect live links.
        emp.write({'bank_account_ids': [(6, 0, account.ids)]})
        counts['payment_account_links_corrected'] += 1
    assert emp.bank_account_ids == account and account.partner_id == partner
    assert emp.vietnam_bank_account_number == account.acc_number == row['account']
    assert emp.vietnam_bank_account_name == account.acc_holder_name == row['holder']
    assert emp.vietnam_bank_name == account.bank_id.name == row['bank']
    assert norm(emp.name) == norm(account.acc_holder_name)
    counts['bank_records_verified'] += 1
    details.append(record)
e.flush_all()
assert {t: digest(t) for t in protected} == before, 'Protected business records changed'
assert History.search_count([]) == history_before + bank_changes
for variant in plan['probation_records']:
    emp = Emp.browse(variant['id'])
    assert emp.active and emp.employee_id == variant['code'] and emp.name == variant['name']
assert len(details) == 606 and counts['bank_records_verified'] == 576
receipt = {'database': 'sudima', 'committed': apply, 'counts': dict(counts), 'records': details,
           'source_sha256': plan['source_sha256'], 'protected_tables': before,
           'probation_variants_preserved': plan['probation_records'], 'actor': e.user.login}
if apply:
    e.cr.commit()
else:
    e.cr.rollback()
target = root / ('applied.json' if apply else 'rehearsal.json')
target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)); target.chmod(0o600)
print('SUDIMA_BANK_RESULT', json.dumps({'committed': apply, 'counts': dict(counts), 'protected': protected}))
