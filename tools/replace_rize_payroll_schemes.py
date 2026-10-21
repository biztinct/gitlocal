"""Create focused Rize replacements, preserving history and formula addresses.

Run inside Odoo shell after module upgrade. Default is rollback rehearsal.
RIZE_FOCUSED_PLAN: reviewed JSON; RIZE_FOCUSED_APPLY=1 commits only on rize.
RIZE_FOCUSED_RECEIPT: private JSON receipt. No employee values in the receipt.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path

assert env.su
assert env.cr.dbname in ('rize', 'p0clone', 'codex_rize_app_20261021a')
plan_path = Path(os.environ.get('RIZE_FOCUSED_PLAN', '/tmp/rize_focused_payroll_plan.json'))
plan = json.loads(plan_path.read_text())
apply = os.environ.get('RIZE_FOCUSED_APPLY') == '1'
assert not apply or env.cr.dbname == 'rize'
receipt = {'database': env.cr.dbname, 'apply': apply,
           'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(), 'schemes': []}
Config = env['hr.formula.config'].with_context(tracking_disable=True, mail_notrack=True, mail_create_nolog=True)
Mapping = env['hr.payslip.import.mapping']



def focus_layout(cfg):
    # The data-source mode is supplied by Pay Run, not entered each month.
    # Preserve the engine component but leave it off ordinary input worksheets.
    api = env['pb.payroll.templates']
    catalog = api._catalog(cfg)
    layout = api._layout(cfg, catalog)
    controls = {'rule:%s' % r.id for r in cfg.rule_ids
                if r.application_source_key == 'application.mode'}
    controls &= {c['id'] for c in catalog}
    if any(fid in layout[lane] for fid in controls for lane in ('time', 'adjustments', 'records')):
        for lane in layout:
            layout[lane] = [fid for fid in layout[lane] if fid not in controls]
        layout['available'].extend(sorted(controls))
        api.save_layout(cfg.id, layout)


def replace_one(old, spec, seal=True):
    code = 'RIZE_%s_FOCUSED_2026' % spec['country']
    existing = Config.search([('code', '=', code), ('company_id', '=', old.company_id.id)])
    if existing:
        assert existing.focused_payroll_inputs and old.state == 'archived', 'Partial migration found'
        focus_layout(existing)
        return {'old_id': old.id, 'new_id': existing.id, 'idempotent': True}
    keep = {r['code'] for r in spec['rules'] if r['keep']}
    assert set(old.rule_ids.mapped('code')) == {r['code'] for r in spec['rules']}, 'Schema changed since audit'
    protected_ids = set()
    for name, field in old._fields.items():
        if getattr(field, 'comodel_name', None) == 'hr.formula.rule' and field.type in ('many2one', 'many2many'):
            protected_ids.update(old[name].ids)
        if field.type == 'html' and old[name]:
            protected_ids.update(int(m.group(1)) for m in old._payslip_component_token_re.finditer(str(old[name])))
    for page in (old.payslip_document or {}).get('pages', []):
        for item in page.get('fields', []):
            protected_ids.update(i for i in (item.get('rule_id'), item.get('rate_rule_id')) if i)
    keep.update(old.rule_ids.filtered(lambda r: r.id in protected_ids).mapped('code'))
    retained = old.rule_ids.filtered(lambda r: r.code in keep)
    removed = old.rule_ids - retained
    used = set(','.join(old.rule_ids.mapped('formula_dependencies')).split(','))
    assert all(r.column_type == 'input' and not r.appears_on_payslip
               and r.code not in used and r.column_letter not in used for r in removed)
    old_letters = {r.code: r.column_letter for r in old.rule_ids}
    baseline = []
    for sample in old.sample_data_ids.filtered('active'):
        inputs = json.loads(sample.input_values_json or '{}')
        errors = {}
        result = sample._evaluate_rules_with_dependencies(inputs, readonly=True, errors=errors)
        baseline.append((sample, inputs, result, errors))
    new = old.copy({'name': old.name + ' — focused payroll', 'code': code,
                    'state': 'draft', 'rule_ids': [], 'payslip_document': False,
                    'focused_payroll_inputs': True, 'parent_branch_id': False,
                    'master_config_id': False})
    by_old = {}
    for rule in retained:
        by_old[rule.id] = rule.copy({'config_id': new.id,
            'forced_column_letter': old_letters[rule.code],
            'source_ids': [(0, 0, s.copy_data()[0]) for s in rule.source_ids]})
    # Config-owned rule references must follow the copy, never the retired rules.
    for name, field in old._fields.items():
        if getattr(field, 'comodel_name', None) != 'hr.formula.rule' or field.type not in ('many2one', 'many2many'):
            continue
        assert set(old[name].ids) <= set(by_old), ('Referenced rule cannot be removed', name)
        new[name] = by_old[old[name].id].id if field.type == 'many2one' and old[name] else (
            [(6, 0, [by_old[r.id].id for r in old[name]])] if field.type == 'many2many' else False)
    for name, field in old._fields.items():
        if field.type == 'html' and old[name]:
            new[name] = old._payslip_component_token_re.sub(
                lambda m: '{{pb_component:%s:%s}}' % (by_old[int(m.group(1))].id, m.group(2)), str(old[name]))
    if old.payslip_document:
        document = copy.deepcopy(old.payslip_document)
        for page in document['pages']:
            for item in page['fields']:
                for key in ('rule_id', 'rate_rule_id'):
                    if item.get(key):
                        item[key] = by_old[item[key]].id
        new.payslip_document = document
    for mapping in Mapping.search([('salary_structure_id', '=', old.id)]):
        if mapping.component_id.id in by_old:
            mapping.copy({'salary_structure_id': new.id, 'component_id': by_old[mapping.component_id.id].id})
    # Direct application readers get matching native write destinations, so
    # optional monthly edits use the same reviewed Records Desk writer.
    mapped = set(Mapping.search([('salary_structure_id', '=', new.id)]).mapped('component_id').ids)
    for rule in new.rule_ids.filtered(lambda r: r.column_type == 'input'):
        key = rule.application_source_key or ''
        if rule.id in mapped or not key.startswith(('employee.', 'contract.')):
            continue
        prefix, field_name = key.split('.', 1)
        model = 'hr.' + prefix
        field = env[model]._fields.get(field_name)
        if field and not field.readonly and field.type in ('char', 'text', 'date', 'datetime', 'float', 'monetary', 'integer', 'boolean', 'selection', 'many2one'):
            Mapping.create({'salary_structure_id': new.id, 'component_id': rule.id,
                'destination_type': 'field', 'target_model_id': env['ir.model']._get(model).id,
                'target_field_id': env['ir.model.fields']._get(model, field_name).id})
    # Preserve declared source discovery. The uploaded source workbook stays
    # on the archived scheme; the replacement only advertises retained keys.
    cols = json.loads(old.import_sample_columns_json or '[]')
    keys = {s.key for r in new.rule_ids for s in r.source_ids if s.kind == 'excel'}
    if isinstance(cols, list):
        new.import_sample_columns_json = json.dumps([c for c in cols if (c if isinstance(c, str) else c.get('key')) in keys])
    checks = 0
    for sample, inputs, expected, prior_errors in baseline:
        clean_inputs = {k: v for k, v in inputs.items() if k in keep}
        copied = env['hr.formula.sample.data'].create({'config_id': new.id,
            'name': sample.name, 'source_type': 'manual',
            'input_values_json': json.dumps(clean_inputs)})
        errors = {}
        values = copied._evaluate_rules_with_dependencies(clean_inputs, readonly=True, errors=errors)
        assert errors == prior_errors, (old.code, 'Formula errors changed', errors, prior_errors)
        for key in keep:
            a, b = expected.get(key), values.get(key)
            assert (math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-6)
                    if isinstance(a, (int, float)) and isinstance(b, (int, float)) else a == b), (old.code, key, 'Sample result changed')
            checks += 1
    assert all(r.column_letter == old_letters[r.code] for r in new.rule_ids)
    assert all(r.excel_formula == old.rule_ids.filtered(lambda x: x.code == r.code).excel_formula for r in new.rule_ids)
    for assignment in env['hr.formula.scheme.assignment'].search([('config_id', '=', old.id)]):
        assignment.active = False
        assignment.copy({'config_id': new.id, 'active': True})
    # These are current assignment caches, not payslip history.
    for field in ('pb_paid_by_id', 'pb_paid_by_advance_id'):
        env['hr.employee'].with_context(active_test=False).search([(field, '=', old.id)]).write({field: new.id})
    # Existing monthly uploads, runs and samples remain attached to the archived
    # configuration. The user confirmed that none of these schemes is operational.
    new.state = 'active'
    release = env['pb.formula.studio'].release_approve(new.id,
        narrative='Owner-approved focused payroll: preserve calculations and payslip contributions; maintain unrelated HR data independently in Records Desk.') if seal else {'ok': True, 'rehearsal_only': True}
    if seal and release.get('reason') == 'no_changes':
        # A new copy has no outgoing edit versions. release_approve has already
        # checked the normal release gate; seal an honest initial snapshot,
        # rather than manufacturing an edit to an unchanged formula.
        studio = env['pb.formula.studio']
        milestone = studio._seal_milestone(new, 'Initial focused payroll release')
        released = env['hr.formula.release'].create({
            'name': 'Release v1', 'config_id': new.id,
            'to_milestone_id': milestone.id, 'change_count': len(new.rule_ids),
            'narrative': 'Initial owner-approved focused scheme copied from %s (%s). Calculations and payslip contributions preserved; unrelated HR fields maintained in Master records.' % (old.name, old.code),
        })
        release = {'ok': True, 'release_id': released.id}
    assert release.get('ok'), ('Release could not be sealed', release)
    old.write({'state': 'archived', 'name': old.name + ' — archived master-data scheme'})
    focus_layout(new)
    catalog = env['pb.payroll.templates']._catalog(new)
    assert all(c['id'].startswith('rule:') for c in catalog)
    assert not any(r.code not in keep for r in new.rule_ids)
    return {'old_id': old.id, 'new_id': new.id, 'code': new.code,
            'before': len(old.rule_ids), 'after': len(new.rule_ids),
            'inputs': len(new.rule_ids.filtered(lambda r: r.column_type == 'input')),
            'removed': len(removed), 'sample_checks': checks,
            'baseline_sample_error_count': sum(len(b[3]) for b in baseline),
            'spreadsheet_bindings': sum(len(r.source_ids.filtered(lambda s: s.kind == 'excel')) for r in new.rule_ids),
            'editable_records': sum(bool(c.get('record_editable')) for c in catalog)}


def history_fingerprint():
    env.cr.execute("SELECT md5(string_agg(row_to_json(t)::text, '' ORDER BY id)) FROM hr_payslip t")
    return env.cr.fetchone()[0]

if not globals().get('FOCUSED_LIBRARY_ONLY'):
    env.cr.execute('SELECT pg_advisory_xact_lock(%s)', [202610215])
    before = history_fingerprint()
    for spec in plan:
        old = Config.browse(spec['old_id']).exists()
        assert old and old.country_code == spec['country']
        receipt['schemes'].append(replace_one(old, spec))
    env.flush_all()
    assert history_fingerprint() == before, 'Historical payslips changed'
    for spec in plan:
        assert replace_one(Config.browse(spec['old_id']), spec)['idempotent']
    out = Path(os.environ.get('RIZE_FOCUSED_RECEIPT', '/tmp/rize_focused_receipt.json'))
    out.write_text(json.dumps(receipt, indent=2)); out.chmod(0o600)
    if apply:
        env.cr.commit()
    else:
        env.cr.rollback()
    print('FOCUSED_RECEIPT', json.dumps(receipt))
