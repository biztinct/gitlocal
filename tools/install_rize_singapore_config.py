"""Install the reviewed demo Singapore configuration into Rize, atomically.

Run through the Rize Odoo shell. Default is a read-only plan; set
SG_INSTALL_APPLY=1 only after a database backup. Uses ORM creation and Studio
mapping/check APIs, translates related records by business keys, and never
copies employees, payroll transactions, approvals, or numeric database IDs.
"""
import base64
import hashlib
import io
import json
import math
import os

import openpyxl
from odoo.modules.registry import Registry

assert env.cr.dbname == 'rize'
company = env['res.company'].search([('name', '=', 'Rize Farms')])
assert len(company) == 1
target = env(context=dict(env.context, allowed_company_ids=company.ids))
code = 'RIZE_SINGAPORE_PAYROLL'
assert not target['hr.formula.config'].with_context(active_test=False).search([('code', '=', code)])


def business_counts():
    return {m: target[m].with_context(active_test=False).search_count([])
            for m in ('hr.employee', 'hr.contract', 'hr.payslip', 'hr.payslip.run')}


def scalar_copy(record):
    return {k: v for k, v in record.copy_data()[0].items()
            if k in target[record._name]._fields
            and record._fields[k].type not in ('many2one', 'one2many', 'many2many')}


before = business_counts()
with Registry('payobook').cursor() as source_cr:
    source_env = type(env)(source_cr, env.uid, {})
    source = source_env['hr.formula.config'].browse(613).exists()
    assert len(source) == 1 and source.country_code == 'SG' and source.state == 'draft'
    assert len(source.rule_ids) == 41 and len(source.sample_data_ids.filtered('active')) == 8
    assert source.currency_id.name == 'SGD'
    # Fail closed if this reviewed source acquires a new integration/account link.
    allowed_links = {'company_id', 'proration_component_ids'}
    for k, v in source.copy_data()[0].items():
        f = source._fields[k]
        if f.type == 'many2one' and k not in allowed_links:
            assert not v, ('Unreviewed configuration relation', k)
        if f.type == 'many2many':
            assert not source[k], ('Unreviewed configuration relation', k)
    assert not source.rate_table_ids
    tables = source.rule_ids.mapped('tax_table_id')
    assert len(tables) == 1 and tables.code == 'RIZESGSDL' and tables.state == 'draft'
    attachments = source_env['ir.attachment'].search([
        ('res_model', '=', source._name), ('res_id', '=', source.id),
        ('name', 'in', ['Rize_Singapore_Payroll_Configuration_Aug2026.xlsx',
                        'Rize_Singapore_Monthly_Inputs.xlsx'])])
    assert len(attachments) == 2
    artifact_hashes = {a.name: hashlib.sha256(base64.b64decode(a.datas)).hexdigest()
                       for a in attachments}
    assert set(artifact_hashes.values()) == {
        '94ce15333aff042cb26417ac49c2ae240bcfc45ac2eb35ad84be49156e4c9240',
        '45d35b020dab37a73e1d7d79892a9777f6d6a050ae6dc68bd7e042aa90419a66'}
    print('SG_PLAN', json.dumps({'source': source.id, 'target': env.cr.dbname,
        'company': company.name, 'components': len(source.rule_ids),
        'active_samples': 8, 'files': artifact_hashes}, sort_keys=True))
    if os.environ.get('SG_INSTALL_APPLY') != '1':
        source_cr.rollback()
    else:
        vals = scalar_copy(source)
        vals.update(name='Rize Singapore Payroll', code=code, company_id=company.id,
                    state='draft')
        if 'is_demo' in target['hr.formula.config']._fields:
            vals['is_demo'] = False
        config = target['hr.formula.config'].create(vals)
        table_vals = scalar_copy(tables)
        table_vals.update(company_id=company.id, state='draft', parameter_ids=[
            (0, 0, scalar_copy(p)) for p in tables.parameter_ids])
        assert not tables.slab_ids
        table = target['hr.payroll.tax.table'].create(table_vals)
        table._validate_edition()
        rules = {}
        for source_rule in source.rule_ids:
            for k, f in source_rule._fields.items():
                if f.type == 'many2one' and f.store and not f.compute and k not in {
                    'config_id', 'category_id', 'payslip_identifier', 'tax_table_id',
                    'create_uid', 'write_uid'}:
                    assert not source_rule[k], ('Unreviewed rule relation', k)
            rv = scalar_copy(source_rule)
            rv.update(config_id=config.id)
            if 'is_demo' in target['hr.formula.rule']._fields:
                rv['is_demo'] = False
            if source_rule.category_id:
                category = target['hr.salary.rule.category'].search([
                    ('code', '=', source_rule.category_id.code),
                    ('name', '=', source_rule.category_id.name),
                    ('company_id', 'in', [False, company.id])])
                if not category:
                    assert not source_rule.category_id.parent_id
                    category = target['hr.salary.rule.category'].create({
                        'code': source_rule.category_id.code,
                        'name': source_rule.category_id.name, 'company_id': company.id})
                assert len(category) == 1, ('Ambiguous category', source_rule.category_id.code)
                rv['category_id'] = category.id
            if source_rule.payslip_identifier:
                ident = source_rule.payslip_identifier
                rv['payslip_identifier'] = target['hr.payslip.config'].create({
                    'identifier': ident.identifier, 'label': ident.label,
                    'salary_structure_id': config.id}).id
            if source_rule.tax_table_id:
                rv['tax_table_id'] = table.id
            rule = target['hr.formula.rule'].create(rv)
            rules[source_rule.id] = rule
            for binding in source_rule.source_ids:
                assert binding.kind == 'excel'
                rule.set_source_binding(binding.kind, binding.key, origin='import')
        config.col_letter_hwm = source.col_letter_hwm
        studio = target['pb.formula.studio']
        mappings = source_env['hr.payslip.import.mapping'].search([
            ('salary_structure_id', '=', source.id)])
        for mapping in mappings:
            if mapping.destination_type == 'bank_account':
                spec = 'b:' + mapping.bank_role
            else:
                spec = 'f:%s:%s' % (mapping.target_model_id.model, mapping.target_field_id.name)
            result = studio.employee_mapping_create(config.id, '', rules[mapping.component_id.id].id, spec)
            assert result.get('ok'), result
        for sample in source.sample_data_ids.filtered('active'):
            assert not sample.source_employee_id and not sample.source_payslip_id
            sv = scalar_copy(sample)
            sv.update(config_id=config.id, active=True)
            target['hr.formula.sample.data'].create(sv)
        for attachment in attachments:
            target['ir.attachment'].create({'name': attachment.name, 'type': 'binary',
                'res_model': config._name, 'res_id': config.id, 'datas': attachment.datas,
                'mimetype': attachment.mimetype, 'company_id': company.id})
        # Setup preferences contain no copied approvals or old readiness evidence.
        source_bp = source_env['pb.formula.blueprint'].search([('config_id', '=', source.id)])
        blueprint = target['pb.blueprint.studio']
        assert blueprint.bp_adopt(config.id).get('ok')
        dest_bp = target['pb.formula.blueprint'].search([('config_id', '=', config.id)])
        assert len(source_bp) == len(dest_bp) == 1 and not source_bp.pack_id
        prefs = ('effective_from', 'calendar_json', 'tax_json', 'situations_json')
        dest_bp.write({k: source_bp[k] for k in prefs})
        for task in ('mapping', 'payslip'):
            assert blueprint.bp_task_set(config.id, task, 'configured').get('ok')
        checks = blueprint.bp_run_checks(config.id)
        assert checks.get('ok'), checks
        assert blueprint.bp_finish(config.id).get('ok')
        # Independently re-evaluate every expected output in the destination engine.
        comparisons = 0
        for sample in config.sample_data_ids.filtered('active'):
            errors = {}
            actual = sample._evaluate_rules_with_dependencies(
                json.loads(sample.input_values_json), readonly=True, errors=errors)
            assert not errors, errors
            for key, expected in json.loads(sample.expected_values_json).items():
                assert isinstance(actual.get(key), (int, float))
                assert math.isclose(actual[key], expected, rel_tol=0, abs_tol=1e-7), (sample.name, key)
                comparisons += 1
            assert math.isclose(actual['GROSS'] - actual['EEDED'], actual['NET'], abs_tol=1e-7)
        tests = config.run_sample_tests()
        assert tests['passed'] == 8 and not tests['failed'], tests
        reviewed = ('code', 'name', 'column_type', 'excel_formula', 'constant_value',
                    'forced_column_letter', 'net_role', 'net_role_detail', 'net_role_source',
                    'value_kind', 'value_kind_source', 'column_role', 'column_role_source',
                    'appears_on_payslip', 'is_contract_component', 'period_key')
        for original in source.rule_ids:
            copied = rules[original.id]
            for key in reviewed:
                assert copied[key] == original[key], (original.code, key, copied[key], original[key])
        board = config.value_kind_board()
        assert board['review_count'] == board['role_conflict_count'] == 0
        assert all(config.rule_ids.filtered('tax_table_id').mapped('tax_aligned'))
        health = studio.get_problems(config.id)
        assert health['counts']['error'] == 0, health
        workspace = target['pb.payroll.templates'].workspace(config.id, '2026-10')
        # Compare the configuration workbook's cached numerical examples as well.
        workbook_attachment = attachments.filtered(lambda a: 'Configuration' in a.name)
        book = openpyxl.load_workbook(io.BytesIO(base64.b64decode(workbook_attachment.datas)), data_only=True)
        assert book['Payroll']['A13'].value == '000001'
        assert len(config.rule_ids.filtered(lambda r: r.column_type == 'input')) == 25
        assert before == business_counts()
        assert config.state == table.state == 'draft'
        report = {'database': env.cr.dbname, 'config_id': config.id, 'name': config.name,
            'company': company.name, 'state': config.state, 'currency': config.currency_id.name,
            'components': len(config.rule_ids), 'inputs': 25, 'statutory_bindings': 3,
            'mappings': len(mappings), 'scenario_tests': tests, 'output_comparisons': comparisons,
            'health': health['counts'], 'treatment_review': board['review_count'],
            'type_conflicts': board['role_conflict_count'], 'eligible_employees': workspace['people'],
            'business_counts_unchanged': before, 'files': artifact_hashes}
        env.cr.commit()
        print('SG_INSTALLED', json.dumps(report, sort_keys=True, default=str))
    # The source is always read only, even when destination changes commit.
    source_cr.rollback()
