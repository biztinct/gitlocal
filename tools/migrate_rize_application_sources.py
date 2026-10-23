"""Reviewed Rize application-source migration; execute inside an Odoo shell.

Default: apply every operation in one transaction, verify, then ROLLBACK.
Set RIZE_APP_APPLY=1 after backup to commit. RIZE_APP_PLAN points at the reviewed
metadata plan. RIZE_APP_RECEIPT is a private absolute JSON path (chmod 0600).
RIZE_APP_EFFECTIVE_FROM explicitly overrides the plan's next-period cutover.

Only rize and the four named active mainline schemes are in scope. No employee
identity, asset, resignation, leave approval, or historical payroll is invented.
Unresolved metadata is preserved and reported. Existing spreadsheet arithmetic
is tested before/after and retained behind an explicit application-mode branch.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
from datetime import date

from odoo import fields


assert env.cr.dbname == 'rize', 'Client mappings may only be applied to rize.'
assert env.su, 'Run the controlled migration as the maintenance administrator.'
root = Path(os.environ.get('RIZE_APP_PLAN', '/tmp/rize_application_source_plan.json'))
plan = json.loads(root.read_text())
assert plan['version'] == '2026-10-21' and plan['reviewed_input_count'] == 480
apply = os.environ.get('RIZE_APP_APPLY') == '1'
effective = fields.Date.to_date(os.environ.get('RIZE_APP_EFFECTIVE_FROM') or plan['effective_from'])
receipt_path = Path(os.environ.get('RIZE_APP_RECEIPT', '/tmp/rize_application_source_receipt.json'))
assert receipt_path.is_absolute()
receipt = dict(database='rize', plan_sha256=hashlib.sha256(root.read_bytes()).hexdigest(),
               apply=apply, effective_from=str(effective), schemes=[], field_changes=[],
               native_mappings_created=[], unresolved=[], retained_controls=[], formula_changes=[], created_rules=[],
               ownership_summary=plan.get('ownership_summary', {}))
Config, Rule = env['hr.formula.config'], env['hr.formula.rule']
Mapping = env['hr.payslip.import.mapping']
Studio = env['pb.formula.studio']
settings = ['payroll_basis', 'standard_day_basis', 'fixed_standard_days',
            'application_data_enabled', 'application_effective_from']
rfields = ['application_source_key', 'application_source_required', 'application_source_note',
           'application_source_owner', 'application_source_owner_model',
           'application_zero_allowed', 'application_settlement_kind',
           'is_contract_component', 'is_text_component']
assert all(n in Config._fields for n in settings)
assert all(n in Rule._fields for n in rfields)
env.cr.execute('SELECT pg_advisory_xact_lock(%s)', [202610214])


def saved(value):
    if hasattr(value, 'ids'):
        return value.id or False
    if isinstance(value, (date,)):
        return str(value)
    return value


def snapshot(record, names):
    return {name: saved(record[name]) for name in names}


def write_changed(record, values):
    changes = {key: value for key, value in values.items() if saved(record[key]) != saved(value)}
    if changes:
        record.write(changes)


def frozen_business():
    result = {}
    for table in ('hr_payslip', 'hr_payslip_run', 'hr_leave', 'hr_leave_allocation',
                  'hr_overtime_request', 'pb_asset', 'pb_asset_assignment', 'pb_resignation'):
        env.cr.execute('SELECT count(*),md5(coalesce(string_agg(row_to_json(t)::text, chr(10) ORDER BY id),\'\')) FROM '+table+' t')
        result[table] = env.cr.fetchone()
    return result


before_business = frozen_business()


def normalize(value):
    return ' '.join(str(value or '').strip().casefold().split())


def converted(record, field_name, value):
    field = record._fields[field_name]
    if field.type in ('char', 'text'):
        return str(value).strip()
    if field.type == 'date':
        # No locale guesses such as 03/04/26. Preserve unresolved strings.
        text = str(value).strip()
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
            raise ValueError('date_not_iso')
        return str(fields.Date.to_date(text))
    if field.type == 'selection':
        pairs = field._description_selection(env)
        wanted = normalize(value)
        aliases = {'m':'male','f':'female','nett':'net'} if field_name in ('sex','pb_salary_basis') else {}
        wanted = aliases.get(wanted, wanted)
        matches = [k for k, label in pairs if wanted in (normalize(k), normalize(label))]
        if len(matches) != 1:
            raise ValueError('selection_not_unique')
        return matches[0]
    if field.type == 'many2one':
        Model = env[field.comodel_name]
        matches = Model.search([('name', '=ilike', str(value).strip())], limit=2)
        if field.comodel_name == 'res.country' and not matches:
            matches = Model.search([('code', '=ilike', str(value).strip())], limit=2)
        if len(matches) != 1:
            raise ValueError('relation_not_unique')
        return matches.id
    raise ValueError('unsupported_native_type')


def rehome_native(cfg, rule, target, people):
    model_name, field_name = target
    Model = env[model_name]
    if field_name not in Model._fields:
        raise AssertionError('Required native field is not installed: '+'.'.join(target))
    mapped = Mapping.search([('salary_structure_id', '=', cfg.id), ('component_id', '=', rule.id)])
    if mapped:
        assert len(mapped) == 1 and mapped.destination_type == 'field'
        assert (mapped.target_model_id.model, mapped.target_field_id.name) == tuple(target)
    else:
        field = env['ir.model.fields']._get(model_name, field_name)
        created = Mapping.create(dict(salary_structure_id=cfg.id, component_id=rule.id,
                                      destination_type='field', target_model_id=field.model_id.id,
                                      target_field_id=field.id))
        receipt['native_mappings_created'].append(created.id)
    for employee in people:
        contracts = env['hr.contract'].with_context(active_test=False).search([
            ('employee_id', '=', employee.id), ('company_id', '=', cfg.company_id.id),
            ('state', '=', 'open'), ('date_start', '<=', effective),
            '|', ('date_end', '=', False), ('date_end', '>=', effective),
        ])
        if len(contracts) != 1:
            receipt['unresolved'].append(dict(scheme=cfg.code, code=rule.code,
                employee_id=employee.id, reason='unique_effective_contract_required_for_legacy_copy'))
            continue
        contract = contracts[0]
        lines = contract.advantages_ids.filtered(lambda a:
            (a.advantage_template_code or a.advantage_template_id.code) == rule.code)
        values = {str(a.text_value).strip() for a in lines if a.text_value and str(a.text_value).strip()}
        if not values:
            continue
        if len(values) != 1:
            receipt['unresolved'].append(dict(scheme=cfg.code,code=rule.code,employee_id=employee.id,
                                              reason='multiple_legacy_values_preserved'))
            continue
        target_record = employee if model_name == 'hr.employee' else contract
        env.cr.execute('SELECT id FROM '+target_record._table+' WHERE id=%s FOR UPDATE', [target_record.id])
        target_record.invalidate_recordset([field_name])
        try:
            value = converted(target_record, field_name, next(iter(values)))
        except (ValueError, TypeError) as exc:
            receipt['unresolved'].append(dict(scheme=cfg.code,code=rule.code,employee_id=employee.id,
                                              reason='legacy_value_not_converted:'+str(exc)))
            continue
        old = saved(target_record[field_name])
        if old and old != value:
            receipt['unresolved'].append(dict(scheme=cfg.code,code=rule.code,employee_id=employee.id,
                                              reason='canonical_conflict_preserved'))
            continue
        if old != value:
            receipt['field_changes'].append(dict(model=model_name,id=target_record.id,field=field_name,
                                                before=old,after=value,legacy_line_ids=lines.ids))
            target_record.with_context(tracking_disable=True, mail_notrack=True,
                mail_create_nolog=True, mail_auto_subscribe_no_notify=True).write({field_name:value})


def sample_values(cfg):
    controls = []
    for sample in cfg.sample_data_ids.filtered('active'):
        inputs = json.loads(sample.input_values_json or '{}')
        errors = {}
        values = sample._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)
        assert not errors, (cfg.code, 'baseline_sample_errors', sample.id, errors)
        controls.append((sample.id, inputs, values))
    return controls


def compare_samples(cfg, controls):
    checks = 0
    for sample_id, inputs, expected in controls:
        errors = {}
        values = env['hr.formula.sample.data'].browse(sample_id)._evaluate_rules_with_dependencies(
            dict(inputs, PBAPPDATA=0), readonly=True, errors=errors)
        assert not errors, (cfg.code, 'post_sample_errors', sample_id, errors)
        for code, old in expected.items():
            new = values.get(code)
            if isinstance(old,(int,float)) and not isinstance(old,bool):
                assert isinstance(new,(int,float)) and math.isclose(old,new,rel_tol=1e-10,abs_tol=.000001), (cfg.code,code,'spreadsheet_changed')
            else:
                assert old == new, (cfg.code,code,'spreadsheet_changed')
            checks += 1
    return checks


def add_input(cfg, code, name, kind, key, settlement='none'):
    current = cfg.rule_ids.filtered(lambda r:r.code==code)
    if current:
        assert len(current)==1 and current.column_type=='input' and current.application_source_key==key
        return current
    cfg._require_proposal('activate')
    record = Rule.create(dict(config_id=cfg.id,code=code,name=name,column_type='input',
        value_kind=kind,value_kind_source='user',column_role='payroll',net_role='info',
        net_role_source='user',sequence=max(cfg.rule_ids.mapped('sequence') or [0])+10,
        application_source_key=key,application_source_required=False,default_value=0,
        application_zero_allowed=settlement!='none',application_settlement_kind=settlement,
        application_source_note='Owner-approved 2026-10-21 application-data branch. Spreadsheet default stays zero.',
        appears_on_payslip=False,report_visible=False))
    receipt['created_rules'].append(record.id)
    return record


def branch_formulas(cfg, changes):
    if not changes:
        return None
    route, unused = cfg._scheme_route()
    if route == 'steps':
        raise AssertionError('Published scheme approval route requires its configured reviewers before this migration: '+cfg.code)
    result = Studio.branch_create(cfg.id,name=cfg.name+' — application sources 2026-10-21',
        note='Owner-approved application payroll and literal Rize policy. Preserve spreadsheet behavior.')
    assert result.get('ok'), result
    branch = Config.browse(result['branch_id'])
    by = {r.code:r for r in branch.rule_ids}
    for code, new_formula in changes.items():
        old = cfg.rule_ids.filtered(lambda r:r.code==code).excel_formula
        receipt['formula_changes'].append(dict(config_id=cfg.id,code=code,before=old,after=new_formula))
        by[code].with_context(formula_version_reason='edit',
            formula_version_note='Owner-approved application-only branch; spreadsheet formula retained').write({'excel_formula':new_formula})
    diff = Studio.branch_diff(branch.id)
    assert diff.get('ok') and not diff.get('conflicts'), diff
    merged = Studio.branch_merge(branch.id,narrative='Owner-approved 2026-10-21: application paid days and policy-approved gross/30 leave cash-out. Existing spreadsheet formulas retained in the else branch. New input defaults are zero; application preflight requires approved sources or explicit permitted no-activity certification.')
    assert merged.get('ok') and merged.get('release_id'), merged
    return dict(branch_id=branch.id,release_id=merged['release_id'],changed=len(changes))


# Lock the complete mainline scope before a long sample-equivalence rehearsal.
# Locking only the config rows leaves stored dependency/diagnostic fields on
# rules exposed to concurrent writes and can fail the final flush after minutes
# of successful checks. Readers remain available; writers wait for this bounded
# migration transaction. Acquire every row in a consistent order.
scope_configs = Config.browse()
for spec in plan['schemes']:
    candidate = Config.search([('code', '=', spec['code']), ('active', '=', True),
        ('state', '=', 'active'), ('parent_branch_id', '=', False)])
    assert len(candidate) == 1 and candidate.country_code == spec['country_code'], spec
    scope_configs |= candidate
env.cr.execute('SELECT id FROM hr_formula_config WHERE id = ANY(%s) ORDER BY id FOR UPDATE',
               [scope_configs.ids])
env.cr.execute('SELECT id FROM hr_formula_rule WHERE config_id = ANY(%s) ORDER BY id FOR UPDATE',
               [scope_configs.ids])
scope_configs.invalidate_recordset()
scope_configs.mapped('rule_ids').invalidate_recordset()

for spec in plan['schemes']:
    cfg = Config.search([('code','=',spec['code']),('active','=',True),('state','=','active'),('parent_branch_id','=',False)])
    assert len(cfg)==1 and cfg.country_code==spec['country_code'], spec
    env.cr.execute('SELECT id FROM hr_formula_config WHERE id=%s FOR UPDATE',[cfg.id])
    cfg.invalidate_recordset()
    expected = [r for r in plan['inputs'] if r['scheme_code']==cfg.code]
    current = {r.code:r for r in cfg.rule_ids if r.column_type=='input'}
    assert {r['code'] for r in expected}.issubset(current), ('reviewed_inputs_missing',cfg.code)
    for row in expected:
        assert current[row['code']].name==row['name'], ('reviewed_label_changed',cfg.code,row['code'])
    before = snapshot(cfg,settings)
    assert not cfg.use_proration, ('salary_history_proration_needs_review', cfg.code)
    before_rules = {r.code:snapshot(r,rfields) for r in cfg.rule_ids if r.column_type=='input'}
    source_order = cfg.source_priority
    controls = []
    people = env['hr.employee'].with_context(active_test=False).search([('company_id','=',cfg.company_id.id)])
    people = people.filtered(lambda e: cfg in Config.schemes_for_employee(e))
    catalogue = cfg._application_source_catalogue()
    mapped = 0
    for row in expected:
        rule = current[row['code']]
        key = row['source_key']
        if not key:
            if row.get('migration_outcome') in ('retained_recurring_contract_term', 'retained_reviewed_contract_payroll_control'):
                receipt['retained_controls'].append(dict(scheme=cfg.code,code=rule.code,
                    outcome=row['migration_outcome'],canonical_owner=row.get('canonical_owner'),note=row['note']))
            elif not row['spreadsheet_only']:
                receipt['unresolved'].append(dict(scheme=cfg.code,code=rule.code,reason='retained_current_source_pending_ownership_review',note=row['note']))
            continue
        if rule.application_source_key and rule.application_source_key!=key:
            previous = row.get('previous_source_key')
            assert (previous == 'pending.domain.' + rule.code
                    and rule.application_source_key == previous
                    and key in catalogue and not key.startswith('pending.domain.')), (
                'concurrent_source_mapping_preserved', cfg.code, rule.code)
        owner_values = dict(application_source_owner=row.get('canonical_owner') or False,
                            application_source_owner_model=row.get('owner_model') or False)
        if key.startswith('pending.domain.'):
            assert key == 'pending.domain.'+rule.code
            write_changed(rule, dict(owner_values, application_source_key=key, application_source_note=row['note']))
            catalogue = cfg._application_source_catalogue()
        assert key in catalogue, ('provider_not_registered',cfg.code,rule.code,key)
        if row['native_target']:
            rehome_native(cfg,rule,row['native_target'],people)
        values = dict(application_source_key=key,application_source_note=row['note'],
                      application_zero_allowed=row['zero_allowed'], **owner_values)
        if row['remove_contract_flag']:
            values.update(is_contract_component=False,is_text_component=False)
        write_changed(rule, values)
        mapped += 1
    mode = add_input(cfg,'PBAPPDATA','Application data mode','quantity','application.mode')
    changes = {}
    by = {r.code:r for r in cfg.rule_ids}
    if cfg.country_code == 'VN':
        weekday = add_input(cfg, 'VNAPPWDOT', 'Application weekday overtime hours (150%)',
                            'quantity', 'period.ot.weekday.approved_hours')
        holiday = add_input(cfg, 'VNAPPHOT', 'Application public holiday overtime hours (300%)',
                            'quantity', 'period.ot.holiday.approved_hours')
        original = by['VNOVERTIME'].excel_formula
        if mode.column_letter not in re.findall(r'([A-Z]+)\d+', original):
            # Preserve this scheme's existing normal hourly wage basis and its
            # downstream tax routing; add only the document's missing OT rates.
            old_term = by['VNWEEKHRS'].column_letter + '2*AT2/BY2/8*200%'
            assert original.count(old_term) == 1, ('review_overtime_hourly_basis', cfg.code)
            new_term = '(%s2*150%%+%s2*200%%+%s2*300%%)*AT2/BY2/8' % (
                weekday.column_letter, by['VNWEEKHRS'].column_letter, holiday.column_letter)
            app = original.lstrip('=').replace(old_term, new_term)
            changes['VNOVERTIME'] = '=IF(%s2=1,%s,%s)' % (mode.column_letter, app, original.lstrip('='))
    if cfg.country_code=='SG':
        paid = add_input(cfg,'SGAPPAID','Application paid day equivalents','quantity','period.paid_day_equivalents')
        original = by['SGACTIWORKDAYS'].excel_formula
        if mode.column_letter not in re.findall(r'([A-Z]+)\d+', original):
            changes['SGACTIWORKDAYS']='=IF(%s2=1,%s2+%s2,%s)'%(mode.column_letter,paid.column_letter,by['SGARREARDAYS'].column_letter,original.lstrip('='))
    else:
        cashout = add_input(cfg,'PBAPPCASHOUT','Approved policy leave cash-out amount','money',
                             'period.input.PBAPPCASHOUT','cashout_amount')
        output = {'VN':'VNLEAVEPAY','IN':'INLEAVE','ID':'IDLEAVBALAPAID'}[cfg.country_code]
        original = by[output].excel_formula
        if mode.column_letter not in re.findall(r'([A-Z]+)\d+', original):
            changes[output]='=IF(%s2=1,%s2,%s)'%(mode.column_letter,cashout.column_letter,original.lstrip('='))
        readycode = {'VN':'VNREADY','ID':'IDREADY'}.get(cfg.country_code)
        if readycode:
            original = by[readycode].excel_formula
            if mode.column_letter not in re.findall(r'([A-Z]+)\d+', original):
                if cfg.country_code=='VN':
                    a,b=by['VNLEAVEWD'].column_letter,by['VNLEAVESTD'].column_letter
                    pattern=r'%s(\d+)<0,AND\(%s\1>0,%s\1<=0\)'%(a,a,b)
                else:
                    a=by['IDLEAVBALADAYS'].column_letter
                    pattern=r'%s\d+<0'%a
                app,count=re.subn(pattern,cashout.column_letter+'2<0',original.lstrip('='))
                assert count==1, ('readiness_formula_changed',cfg.code)
                changes[readycode]='=IF(%s2=1,%s,%s)'%(mode.column_letter,app,original.lstrip('='))
    # Repeated runs with no formula changes do not need to reevaluate every
    # historical sample. A real formula migration still checks every sample
    # before and after its audited branch merge.
    controls = sample_values(cfg) if changes else []
    release = branch_formulas(cfg,changes)
    checks = compare_samples(cfg,controls)
    if cfg.country_code == 'VN':
        by_column = {r.column_letter: r.code for r in cfg.rule_ids}
        values = {'VNREADY': 'Ready', 'PBAPPDATA': 1, 'VNAPPWDOT': 1,
                  'VNWEEKHRS': 1, 'VNAPPHOT': 1, by_column['AT']: 1600, by_column['BY']: 20}
        ot_rule = cfg.rule_ids.filtered(lambda r: r.code == 'VNOVERTIME')
        assert ot_rule._run_formula(values, ot_rule.excel_formula, write_diagnostics=False) == 65
        values['PBAPPDATA'] = 0
        assert ot_rule._run_formula(values, ot_rule.excel_formula, write_diagnostics=False) == 20
        checks += 2
    write_changed(cfg, dict(payroll_basis='contractual',standard_day_basis='calendar',
                   application_data_enabled=True,application_effective_from=effective))
    assert cfg.source_priority==source_order, 'Existing source precedence must not change.'
    after_catalogue = cfg._application_source_catalogue()
    assert all(r.application_source_key in after_catalogue for r in cfg.rule_ids if r.application_source_key)
    receipt['schemes'].append(dict(id=cfg.id,code=cfg.code,mapped_inputs=mapped,
        before_settings=before,after_settings=snapshot(cfg,settings),before_rules=before_rules,
        after_rules={r.code:snapshot(r,rfields) for r in cfg.rule_ids if r.column_type=='input'},
        employee_scope_count=len(people),sample_checks=checks,release=release,
        source_priority=source_order,content_hash=cfg._content_hash()))

# Neither a mapping migration nor a dry run can change an already posted result
# or manufacture approvals/assignment history in a source domain.
env.flush_all()
assert before_business==frozen_business(), 'Business transaction evidence changed unexpectedly.'
receipt['business_invariants']='unchanged'
receipt['status']='committed' if apply else 'rolled_back_dry_run'
receipt_path.parent.mkdir(parents=True,exist_ok=True)
fd=os.open(str(receipt_path),os.O_CREAT|os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW,0o600)
os.fchmod(fd,0o600)
with os.fdopen(fd,'w') as output:
    json.dump(receipt,output,indent=2,ensure_ascii=False,default=str)
os.chmod(receipt_path,0o600)
if apply:
    env.cr.commit()
else:
    env.cr.rollback()
print('RIZE_APPLICATION_SOURCE_MIGRATION',json.dumps(dict(status=receipt['status'],receipt=str(receipt_path),
    schemes=[{k:r[k] for k in ('id','code','mapped_inputs','sample_checks','employee_scope_count','release')} for r in receipt['schemes']],
    native_field_changes=len(receipt['field_changes']),new_native_mappings=len(receipt['native_mappings_created']),
    unresolved=len(receipt['unresolved']),formula_changes=len(receipt['formula_changes']),
    ownership_summary=receipt['ownership_summary'],retained_controls=len(receipt['retained_controls']),
    business_invariants=receipt['business_invariants']),default=str))
