"""Apply the owner's confirmed August VND salary baseline through Records Desk.

Rize only. Default is a dry-run plan. VN_SALARY_APPLY=1 creates the audited
records proposal; its published approval route remains authoritative. Does not
approve payroll, alter formulas, or copy August time/variable payments.
"""
import hashlib
import json
import os

assert env.cr.dbname == 'rize'
cfg = env['hr.formula.config'].browse(3942).exists()
run = env['hr.payslip.run'].browse(685).exists()
previous = env['hr.payslip.run'].browse(681).exists()
assert cfg.country_code == 'VN' and cfg.currency_id.name == 'VND'
assert run.pb_formula_config_id == previous.pb_formula_config_id == cfg
assert run.state == 'draft' and len(run.slip_ids) == 70
assert all(s.state == 'draft' for s in run.slip_ids)
target = env(context=dict(env.context, allowed_company_ids=cfg.company_id.ids))
facade = target['pb.payroll.templates']
desk = target['pb.records.desk']
people = facade._roster(cfg, '2026-10')
assert set(people.ids) == set(run.slip_ids.employee_id.ids)
contracts = desk._io_contracts(people)
source = {s.employee_id.id: json.loads(s.formula_input_values or '{}').get('LUONGHOPVND')
          for s in previous.slip_ids}
assert len(contracts) == len(people) == 70
assert all(isinstance(source.get(e.id), (int, float)) and source[e.id] > 0 for e in people)
assert sum(source[e.id] for e in people) == 1814978020
assert all(c.wage == 0 for c in contracts.values()), 'A wage changed; prepare a fresh comparison.'
baseline = [{'employee_id': e.id, 'contract_id': contracts[e.id].id,
             'old': contracts[e.id].wage, 'new': source[e.id]} for e in people]
print('VN_SALARY_PLAN', json.dumps({'employees': len(people), 'source_run': previous.id,
    'destination_run': run.id, 'old_salary_total': 0, 'new_salary_total': sum(r['new'] for r in baseline),
    'baseline_sha256': hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()}))
if os.environ.get('VN_SALARY_APPLY') == '1':
    rule = cfg.rule_ids.filtered(lambda r: r.code == 'LUONGHOPVND')
    assert len(rule) == 1 and rule.column_type == 'input'
    result = target['pb.formula.studio'].employee_mapping_create(
        cfg.id, '', rule.id, 'f:hr.contract:wage')
    assert result.get('ok'), result
    changes = [{'emp_id': e.id, 'emp_name': e.name, 'field_id': 'f:hr.contract:wage',
                'field_label': rule.name, 'old': contracts[e.id].wage,
                'value': source[e.id]} for e in people]
    preview = desk.preview_changes(cfg.id, changes) if hasattr(desk, 'preview_changes') else None
    result = desk.apply_changes(cfg.id, changes,
        note='Owner confirmed: use the August client-import VND salaries as October baseline. '
             'Repair missing recurring salary only; preserve all October time and variable inputs.',
        source='import')
    assert result.get('ok') and not result.get('refused'), result
    if not result.get('pending'):
        assert result['written'] == 70
        assert all(contracts[e.id].wage == source[e.id] for e in people)
    env.cr.commit()
    print('VN_SALARY_RESULT', json.dumps({k: v for k, v in result.items()
        if k not in ('items', 'refused')}, default=str))
else:
    env.cr.rollback()
