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
Req = env['pb.bank.change.request'].sudo()
fmt = 'pb_bank_format' in Req._fields
waiting = Req.search([('state', 'in', ('draft', 'hr_review', 'finance_review'))])
print('PROBE ready per company (people, bank on record, payroll-ready):', out,
      '| totals', tuple(sum(v[i] for v in out.values()) for i in range(3)),
      '| waiting bank changes', len(waiting),
      '| with a country', len(waiting.filtered('pb_bank_format')) if fmt else 'no field')
env.cr.rollback()
