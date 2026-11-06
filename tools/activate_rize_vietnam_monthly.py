"""Activate the reviewed Vietnam definition and its approved review population.

Uses the existing advanced employee-domain assignment model, as the
administrator (VN_MONTHLY_USER_ID, default 2). No department-wide population,
contract or payroll changes. Default rollback; VN_MONTHLY_ACTIVATE=1 persists.
"""
import json
import os

assert env.cr.dbname == 'rize'
e = env(user=int(os.getenv('VN_MONTHLY_USER_ID', '2')),
        context=dict(env.context, allowed_company_ids=[1]))
cfg = e['hr.formula.config'].browse(4760).exists()
assert cfg.code == 'RIZE_VIETNAM_MASTER_V3' and cfg.company_id.id == 1
assert len(cfg.rule_ids) == 181
assert cfg.rule_ids.filtered(lambda r: r.code == 'VNTECH').column_type == 'input'
api = e['pb.payroll.templates']
api._lock(cfg)
saved = e['pb.payroll.template.layout'].sudo().search([
    ('config_id', '=', cfg.id), ('company_id', '=', 1)], limit=1)
people = e['hr.employee'].browse(saved.payload['preview_employee_ids']).exists()
assert len(people) == 70 and all(p.company_id == cfg.company_id for p in people)
contracts = e['pb.records.desk']._io_contracts(people)
ready = people.filtered(lambda p: contracts.get(p.id)
                        and contracts[p.id].state == 'open' and contracts[p.id].wage > 0)
pending = people - ready
assert len(ready) == 63 and len(pending) == 7
assert all(contracts[p.id].state == 'draft' and not contracts[p.id].wage for p in pending)
codes = sorted(str(p.barcode or '').strip() for p in people)
assert len(set(codes)) == 70 and all(code.startswith('RIZ') for code in codes)
assert not e['hr.formula.scheme.assignment'].search_count([('config_id', '=', cfg.id)])
assert cfg.state == 'draft'
cfg.action_validate_formulas()
assert not cfg.has_errors and not cfg.has_circular_refs
cfg.action_activate()
# A whole department would also admit seven August leavers whose old contracts
# remain open. Restrict this initial population to the owner's approved 70 RIZ
# identities. The normal open-contract eligibility excludes the seven pending
# profiles without altering their records or closing another person's contract.
assignment = e['hr.formula.scheme.assignment'].create({
    'config_id': cfg.id, 'cycle_type': cfg.cycle_type or 'regular',
    'domain': repr([('company_id', '=', cfg.company_id.id), ('barcode', 'in', codes)]),
    'source': 'manual', 'confidence': 1,
    'note': 'Owner-approved 70-person Vietnam review roster. Payroll uses the 63 open, salaried contracts; seven Draft contracts remain pending. Review population when adding or leaving employees.'})
assert set(api._roster(cfg, '2026-10').ids) == set(ready.ids)
assert set(e['pb.payrun.wizard']._eligible_employees(
    formula_config_id=cfg.id, date_start='2026-10-01', date_end='2026-10-31')) == set(ready.ids)
report = dict(config_id=cfg.id, state=cfg.state, assignment_id=assignment.id,
              expected_ready=63, pending_records=7,
              actual_roster=len(api._roster(cfg, '2026-10')),
              committed=os.getenv('VN_MONTHLY_ACTIVATE') == '1')
if report['committed']:
    env.cr.commit()
else:
    env.cr.rollback()
print('VN_POPULATION_RESULT ' + json.dumps(report, ensure_ascii=False, default=str))
