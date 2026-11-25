# NEWHIRE P7 (odoo-bin shell, read-only, rolled back): handover §2.3 / B4 - payroll-ready is unchanged for
# the people already on record. Bank on record (the field Payroll-ready reads) and payroll-ready (running
# contract + bank) per company, plus every bank change waiting and whether it names a country.
Emp = env['hr.employee'].sudo().with_context(active_test=True)
out = {}
for c in env['res.company'].sudo().search([], order='id'):
    people = Emp.search([('company_id', '=', c.id)])
    if not people:
        continue
    bank = people.filtered('pb_bank_on_record')
    ready = bank.filtered(lambda e: e.contract_id and e.contract_id.state == 'open')
    out[c.id] = (len(people), len(bank), len(ready))
# plain SQL for the change requests: on a rehearsal copy the STAGED code may already know the new column
# while the database (not yet upgraded) does not have it
env.cr.execute("select count(*) from pb_bank_change_request where state in ('draft','hr_review','finance_review')")
waiting = env.cr.fetchone()[0]
env.cr.execute("select count(*) from information_schema.columns where table_name='pb_bank_change_request' "
               "and column_name='pb_bank_format'")
if env.cr.fetchone()[0]:
    env.cr.execute("select count(*) from pb_bank_change_request where state in ('draft','hr_review','finance_review') "
                   "and pb_bank_format is not null")
    with_country = env.cr.fetchone()[0]
else:
    with_country = 'no field'
print('PROBE ready per company (people, bank on record, payroll-ready):', out,
      '| totals', tuple(sum(v[i] for v in out.values()) for i in range(3)),
      '| waiting bank changes', waiting, '| with a country', with_country)
env.cr.rollback()
