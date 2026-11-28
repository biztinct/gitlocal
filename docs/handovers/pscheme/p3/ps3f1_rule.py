# PSCHEME F1 (odoo-bin shell, rize ONLY; owner-ordered 27 Nov 2026): the Vietnam scheme's fallback rule
# follows Country of work, like the India / Singapore / Indonesia rules beside it.
#   PS3_MODE=dry    everything below, ROLLED BACK (writes nothing)
#   PS3_MODE=apply  committed; <out>/rize_vn_rule_undo.txt names the created line and how to remove it
# The new line copies the shape of the existing by-country rules exactly (company scoping, kind of run,
# sequence, source) through the map line model's own create (its constraints and the "Paid by needs working
# out again" marking run). The Mapping screen has no way to create a rule line (only team / division lines),
# and no approval kind exists for one; that is reported as an open item.
# Checks (before -> after, every active person): WITH the person rule, main + advance identical; WITHOUT it
# (pb_scheme_skip_person), the only differences allowed are Vietnamese-country people who were answered
# "nobody" and now get the Vietnam scheme; the people with no Country of work unchanged; a throwaway new
# person with Country of work Vietnam and no row of their own is answered by the Vietnam scheme (rolled back).
import json, os
from odoo.addons.pb_scheme_map.models.pb_scheme_map import MAIN_QUESTION, SKIP_PERSON
assert env.cr.dbname == 'rize', 'rize only'
mode = os.environ.get('PS3_MODE', 'dry')
out = os.environ['PS3_OUT']
company = env['res.company'].browse(1)
Assign = env['hr.formula.scheme.assignment'].sudo()
Config = env['hr.formula.config'].sudo()
Emp = env['hr.employee'].sudo()
Map = env['pb.scheme.map'].sudo().with_company(company).with_context(allowed_company_ids=[company.id])
main_kind = Emp._pb_main_cycle(company.id)
rules = Assign.search([('active', '=', True), ('company_id', '=', company.id), ('domain', '!=', False),
                       ('department_id', '=', False), ('division_id', '=', False)], order='sequence, id')
by_country = [r for r in rules if "('payroll_country', '=', " in (r.domain or '')]
shapes = {(r.cycle_type, r.sequence, r.source, r.config_id.cycle_type) for r in by_country}
assert len(shapes) == 1, ('the by-country rules differ in shape', shapes)
cycle_type, sequence, source, kind = shapes.pop()
vn = Config.search([('state', '=', 'active'), ('company_id', '=', company.id), ('country_code', '=', 'VN'),
                    ('cycle_type', '=', kind)])
assert len(vn) == 1, ('not exactly one active Vietnam scheme of that kind', vn.ids)
assert not [r for r in by_country if r.config_id == vn], 'a Vietnam by-country rule already exists'
code_lists = [r for r in rules if r.config_id == vn and "('barcode', 'in'" in (r.domain or '')]
domain = "[('company_id', '=', %s), ('payroll_country', '=', 'VN')]" % company.id
people = Emp.with_context(active_test=True).search([('company_id', '=', company.id)])


def answers():
    res = {}
    for label, ctx in (('with', {}), ('without', {SKIP_PERSON: True})):
        M = Map.with_context(**ctx)
        main = M.with_context(**{MAIN_QUESTION: True}).resolve_many(people.ids, main_kind)
        adv = M.resolve_many(people.ids, 'mid_cycle')
        res[label] = {str(e): [(main.get(e) or {}).get('config_id') or 0, (adv.get(e) or {}).get('config_id') or 0]
                      for e in people.ids}
    return res


before = answers()
# code-list rules that would answer differently from the new rule for somebody: a person on a Vietnam code
# list whose Country of work is not Vietnam (the code list pays them by Vietnam; the new rule would not)
code_people = Emp.browse()
for r in code_lists:
    code_people |= Emp.search([('id', 'in', people.ids)] + r._employee_domain())
code_not_vn = code_people.filtered(lambda e: e.payroll_country != 'VN')
vn_people = people.filtered(lambda e: e.payroll_country == 'VN')
no_country = people.filtered(lambda e: not e.payroll_country)
line = Assign.with_context(pb_schememap_approved_write=True).create({
    'config_id': vn.id, 'domain': domain, 'cycle_type': cycle_type, 'sequence': sequence, 'source': source,
    'note': 'Vietnam follows Country of work, like the other countries (owner, 27 Nov 2026)'})
env.flush_all()
after = answers()
with_changed = [e for e in before['with'] if before['with'][e] != after['with'][e]]
without_changed = [e for e in before['without'] if before['without'][e] != after['without'][e]]
allowed = [e for e in without_changed if int(e) in vn_people.ids and before['without'][e][0] == 0
           and after['without'][e][0] == vn.id and before['without'][e][1] == after['without'][e][1]]
not_allowed = [e for e in without_changed if e not in allowed]
nc_changed = [e for e in without_changed + with_changed if int(e) in no_country.ids]
# a throwaway NEW person (Country of work Vietnam, a team of the company, no row of their own)
sp = env.cr.savepoint()
dept = env['hr.department'].sudo().search([('company_id', '=', company.id)], limit=1)
newbie = Emp.create({'name': 'PSCHEME F1 check (rolled back)', 'company_id': company.id,
                     'department_id': dept.id, 'payroll_country': 'VN'})
nb = Map.with_context(**{MAIN_QUESTION: True}).resolve_many(newbie.ids, main_kind).get(newbie.id) or {}
sp.close(rollback=True)
result = {
    'mode': mode, 'line_id': line.id, 'vn_scheme': 'the Vietnam scheme (id %s)' % vn.id,
    'shape': {'cycle_type': cycle_type, 'sequence': sequence, 'source': source}, 'domain': domain,
    'people': len(people), 'vn_country_people': len(vn_people), 'no_country_people': len(no_country),
    'code_list_rules': [r.id for r in code_lists], 'code_list_people': len(code_people),
    'code_list_people_not_vn_country': len(code_not_vn),
    'with_person_rule_changed': len(with_changed),
    'without_person_rule_changed': len(without_changed), 'allowed_nobody_to_vn': len(allowed),
    'not_allowed_changes': len(not_allowed), 'no_country_changed': len(nc_changed),
    'new_vn_person_answer': {'config_id': nb.get('config_id'), 'rung': nb.get('rung'),
                             'is_vn_scheme': nb.get('config_id') == vn.id},
}
result['ok'] = (not with_changed and not not_allowed and not nc_changed and result['new_vn_person_answer']['is_vn_scheme'])
os.makedirs(out, exist_ok=True)
json.dump(result, open(os.path.join(out, 'rize_vn_rule_%s.json' % mode), 'w'), indent=1, default=str)
if mode == 'apply' and result['ok']:
    with open(os.path.join(out, 'rize_vn_rule_undo.txt'), 'w') as fh:
        fh.write('Created map line id %s: %s -> the Vietnam scheme (id %s), kind of run %s, sequence %s.\n'
                 'Undo (odoo-bin shell on rize): env["pb.scheme.board"].with_context(pb_schememap_approved_write=True)'
                 '.detach(%s, 1); env.cr.commit()  - or env["hr.formula.scheme.assignment"].browse(%s).unlink()\n'
                 'Then Mapping > Who is paid by what > Work it out again. The Mapping screen shows no rule lines, so '
                 'there is no on-screen remove for this line today.\n'
                 % (line.id, domain, vn.id, cycle_type, sequence, line.id, line.id))
    env.cr.commit()
    print('PROBE committed line', line.id)
else:
    env.cr.rollback()
    print('PROBE rolled back (mode %s, ok %s)' % (mode, result['ok']))
print('PROBE', json.dumps({k: v for k, v in result.items() if k not in ('domain',)}, default=str))
