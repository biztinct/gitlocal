"""Run in an Odoo shell. Import source-approved dependent details idempotently.

Private extracted source JSON is supplied through VN_DEPENDENTS_SOURCE_JSON.
Dry-run is the default. VN_DEPENDENTS_APPLY=1 commits; creating the five absent
inactive Employee profiles additionally requires VN_DEPENDENTS_ARCHIVE=1.
No contract, payroll assignment or eligibility dates are inferred. The owner
explicitly approved using the imported count for both dependent payroll inputs.
"""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata


def normalized(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', str(value or ''))).strip().casefold()


def folded(value):
    return ''.join(c for c in unicodedata.normalize('NFD', normalized(value).replace('đ', 'd'))
                   if unicodedata.category(c) != 'Mn')


apply = os.getenv('VN_DEPENDENTS_APPLY') == '1'
archive = os.getenv('VN_DEPENDENTS_ARCHIVE') == '1'
source = json.loads(Path(os.environ['VN_DEPENDENTS_SOURCE_JSON']).read_text())
assert env.cr.dbname == 'rize' or env.cr.dbname.startswith('codex_vn_records_')
cfg = env['hr.formula.config'].browse(4639)
assert cfg.code == 'RIZE_VIETNAM_HC_202610' and cfg.state == 'draft'
company = cfg.company_id
Employee = env['hr.employee'].with_context(active_test=False)
Dependent = env['vietnam.employee.dependent']
people = Employee.search([('company_id', '=', company.id)])
settings = cfg.rule_ids.filtered(lambda r: r.code in {
    'VNTAXMODE','VNREGISTER','VNINSBASE','VNSIJOIN','VNHIJOIN','VNUIJOIN',
    'VNUIREGCAP','VNTUJOIN','VNTRANSPORT','VNPHONE','VNOTHERFIX'})
baseline_settings = sorted((r.code, s.key) for r in settings for s in r.source_ids if s.kind == 'excel')
baseline_contracts = env['hr.contract'].with_context(active_test=False).search_count([])
baseline_assignments = env['hr.contract'].with_context(active_test=False).search_count([('formula_config_id','=',cfg.id)]) if 'formula_config_id' in env['hr.contract']._fields else None
rows = [r for r in source['dependent_rows'] if not (
    r['employee_name'] == 'Column1' and r['dependent_name'] == 'Column2')]
counts = collections.Counter(folded(r['employee_name']) for r in rows)
created, existing, pending, new_people, decisions = [], [], [], [], []
relation = {'cha': 'parent', 'me': 'parent', 'cha/me': 'parent', 'con': 'child'}
for row in rows:
    hits = people.filtered(lambda e: normalized(e.name) == normalized(row['employee_name']))
    method = 'normalized employee name'
    if not hits:
        hits = people.filtered(lambda e: folded(e.name) == folded(row['employee_name']))
        method = 'accent-insensitive employee name'
    hc = [p for p in source['hc'] if folded(p['name']) == folded(row['employee_name'])]
    if len(hits) > 1:
        # Use the owner's HC-count check, then the IDs on that same HC row.
        relevant = [p for p in hc if p['count'] == counts[folded(row['employee_name'])]]
        keys = {normalized(p[k]) for p in relevant for k in ('key','employee_id') if p.get(k)}
        hits = hits.filtered(lambda e: normalized(e.barcode) in keys or normalized(e.employee_id) in keys)
        method = 'duplicate name resolved against VN dependent count and identity'
    if not hits and archive and len(hc) == 1 and hc[0]['status'] == 'Inactive':
        person = hc[0]
        keys = {normalized(person[k]) for k in ('key','employee_id') if person.get(k)}
        conflicts = people.filtered(lambda e: normalized(e.barcode) == normalized(person['key']))
        if conflicts:
            pending.append({'row': row['row'], 'reason': 'HC identity already belongs to a different employee name'})
            continue
        vals = {'name': person['name'], 'company_id': company.id, 'active': False,
                'barcode': str(person['key'] or '').strip()}
        if (person.get('employee_id') and not str(person['employee_id']).startswith('#')
                and not people.filtered(lambda e: normalized(e.employee_id) == normalized(person['employee_id']))):
            vals['employee_id'] = str(person['employee_id']).strip()
        hits = Employee.create(vals)
        people |= hits
        new_people.append(hits.id)
        method = 'new archived profile from unique Inactive VN identity'
    if len(hits) != 1:
        pending.append({'row': row['row'], 'employee_name': row['employee_name'],
                        'reason': 'No unique existing Employee match'})
        continue
    employee = hits
    dependent_name = str(row['dependent_name'] or '').strip()
    if not dependent_name:
        pending.append({'row': row['row'], 'reason': 'Missing dependent name'})
        continue
    relationship = relation.get(folded(row['relationship']), 'other')
    matches = Dependent.search([('employee_id', '=', employee.id)]).filtered(
        lambda d: normalized(d.name) == normalized(dependent_name) and d.relationship == relationship)
    if len(matches) > 1:
        pending.append({'row': row['row'], 'reason': 'Multiple existing dependent records match'})
        continue
    if matches:
        existing.append(matches.id)
    else:
        note = ('Imported from VN_HC_TemplateVietnam_updated_07Oct2026.xlsx, Dependent row %s. '
                'Employee matched by %s. Original relationship: %s. '
                'Eligibility dates, tax registration and allowance were not provided; pending verification.') % (
                    row['row'], method, row['relationship'] or 'not supplied')
        dependent = Dependent.create({'employee_id': employee.id, 'name': dependent_name,
            'relationship': relationship, 'status': 'pending', 'effective_from': False,
            'effective_to': False, 'tax_allowance': 0, 'notes': note})
        created.append(dependent.id)
    decisions.append({'row': row['row'], 'employee_id': employee.id, 'method': method,
                      'relationship': relationship})

Connector = env['hr.integration.connector']
connector = cfg.connector_id
if not connector:
    connector = Connector.create({'name': 'Rize Vietnam saved employee dependents',
        'connector_type': 'excel', 'company_id': company.id, 'sync_interval': 0})
    cfg.connector_id = connector
Rule = env['hr.api.transformation.rule']
transform = Rule.search([('connector_id', '=', connector.id), ('output_key', '=', 'VNDEPCOUNT')], limit=1)
if not transform:
    transform = Rule.create({'connector_id': connector.id, 'name': 'Dependents count',
        'output_key': 'VNDEPCOUNT', 'source_data_type': 'dependent', 'rule_type': 'count',
        'builder_mode': 'guided', 'record_source': 'records', 'employee_record_source': 'vn_dependent_ids',
        'description': 'Count all dependent details saved on Employee. Owner-approved input for both Dependent/Children and Registered tax dependents; record eligibility dates remain unverified.'})
assert transform.employee_record_source == 'vn_dependent_ids'
targets = cfg.rule_ids.filtered(lambda r: r.code in ('VNHCQ', 'VNREGISTER'))
assert len(targets) == 2
Mapping = env['hr.payslip.import.mapping']
field = env['ir.model.fields'].search([('model','=','hr.employee'),('name','=','vn_dependent_record_count')], limit=1)
assert field
for target in targets:
    if target.code == 'VNHCQ':
        target.clear_source_binding('excel')
    # Retain VNREGISTER's recurring-settings Excel placeholder as requested.
    target.set_source_binding('rule', transform.output_key, origin='board')
    target.write({'column_role': 'payroll', 'column_role_source': 'user',
                  'is_contract_component': False, 'is_text_component': False})
    mapped = Mapping.search([('salary_structure_id','=',cfg.id),('component_id','=',target.id)])
    vals = {'salary_structure_id':cfg.id,'component_id':target.id,'destination_type':'field',
            'target_model_id':env['ir.model']._get('hr.employee').id,'target_field_id':field.id}
    if mapped:
        mapped.write(vals)
    else:
        Mapping.create(vals)
# Keep the owner's reviewed roster separate from live payroll assignment.
preview_ids, missing_roster = [], []
for p in source['hc']:
    if p['status'] not in ('Active','Notice Period'):
        continue
    hits = people.filtered(lambda e: folded(e.name)==folded(p['name']))
    if not hits:
        hits = people.filtered(lambda e: str(e.barcode or '').strip()==str(p['key'] or '').strip())
    if len(hits)==1:
        preview_ids.append(hits.id)
    else:
        missing_roster.append({'source_row':p['row'],'name':p['name'],'key':p['key']})
Layout = env['pb.payroll.template.layout'].sudo()
layout = Layout.search([('config_id','=',cfg.id),('company_id','=',company.id)],limit=1)
if not layout:
    layout = Layout.create({'config_id':cfg.id,'company_id':company.id,'payload':{}})
layout.payload = dict(layout.payload or {}, preview_employee_ids=sorted(set(preview_ids)),
                      preview_expected_count=70)
assert baseline_settings == sorted((r.code, s.key) for r in settings for s in r.source_ids if s.kind == 'excel')
assert env['hr.contract'].with_context(active_test=False).search_count([]) == baseline_contracts
if baseline_assignments is not None:
    assert env['hr.contract'].with_context(active_test=False).search_count([('formula_config_id','=',cfg.id)]) == baseline_assignments
for emp_id in {d['employee_id'] for d in decisions}:
    employee = Employee.browse(emp_id)
    assert transform._employee_record_value(employee) == employee.vn_dependent_record_count
result = {'database':env.cr.dbname,'applied':apply,'created_dependents':len(created),
          'existing_dependents':len(existing),'archived_profiles_created':len(new_people),
          'pending_rows':pending,'matched_decisions':decisions,'transformation_id':transform.id,
          'target_codes':targets.mapped('code'),'recurring_settings_preserved':len(settings),
          'review_roster':len(set(preview_ids)),'missing_review_roster':missing_roster}
receipt = Path(os.environ.get('VN_DEPENDENTS_RECEIPT','/tmp/vn-dependent-records-20261018/import-receipt.json'))
receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2));receipt.chmod(0o600)
print('DEPENDENT_IMPORT',json.dumps({k:v for k,v in result.items() if k not in ('matched_decisions','pending_rows','missing_review_roster')},ensure_ascii=False))
if apply:env.cr.commit()
else:env.cr.rollback()
