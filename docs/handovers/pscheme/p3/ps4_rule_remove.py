# PSCHEME P4 follow-up (odoo-bin shell, rize ONLY; owner decision 27 Nov 2026): take off the Vietnam
# named-people rule(s) now redundant beside the Vietnam country line - through the Mapping screen's own
# "Other rules > Remove" server method (pb.scheme.board.other_rule_remove: approval route, fast lane on rize,
# refused when it would leave anybody uncaught). Only rules shown under "Other rules" today (in force today).
#   PS3_MODE=dry    everything, ROLLED BACK
#   PS3_MODE=apply  committed; <out>/rize_vn_rule_remove_undo.txt holds every removed line's values
# Checks, every active person, with AND without the person rule (main + advance): identical before / after.
import json, os
from odoo.addons.pb_scheme_map.models.pb_scheme_map import MAIN_QUESTION, SKIP_PERSON
from odoo.addons.pb_scheme_map.models.pb_country_lines import line_country
assert env.cr.dbname == 'rize', 'rize only'
mode = os.environ.get('PS3_MODE', 'dry')
out = os.environ['PS3_OUT']
company = env['res.company'].browse(1)
Board = env['pb.scheme.board'].with_company(company).with_context(allowed_company_ids=[company.id])
Map = env['pb.scheme.map'].sudo().with_company(company).with_context(allowed_company_ids=[company.id])
Emp = env['hr.employee'].sudo()
people = Emp.with_context(active_test=True).search([('company_id', '=', company.id)])
main_kind = Emp._pb_main_cycle(company.id)


def answers():
    res = {}
    for label, ctx in (('with', {}), ('without', {SKIP_PERSON: True})):
        M = Map.with_context(**ctx)
        main = M.with_context(**{MAIN_QUESTION: True}).resolve_many(people.ids, main_kind)
        adv = M.resolve_many(people.ids, 'mid_cycle')
        res[label] = {str(e): [(main.get(e) or {}).get('config_id') or 0,
                               (adv.get(e) or {}).get('config_id') or 0] for e in people.ids}
    return res


country_rows, other_rows = Board._map_rules(company.id)
vn_line = (country_rows.get('VN') or [None])[0]
assert vn_line, 'no Vietnam country line'
candidates = [r for r in other_rows if r.config_id == vn_line.config_id and "('barcode', 'in'" in (r.domain or '')]
# every Vietnam code-list rule on the map, in force today or not (to report what is left and why)
Assign = env['hr.formula.scheme.assignment'].sudo().with_context(active_test=False)
all_vn_lists = Assign.search([('company_id', '=', company.id), ('active', '=', True),
                              ('config_id', '=', vn_line.config_id.id), ('domain', 'like', "('barcode', 'in'")])
before = answers()
facts = Board._country_facts(company.id)
infos = Board._other_rules(company.id, candidates, country_rows, facts)
removed, kept = [], []
for row, info in zip(candidates, infos):
    values = {'id': row.id, 'config_id': row.config_id.id, 'company_id': row.company_id.id,
              'domain': row.domain, 'cycle_type': row.cycle_type, 'sequence': row.sequence,
              'source': row.source, 'date_from': str(row.date_from or ''), 'date_to': str(row.date_to or ''),
              'note': row.note or '', 'reaches': info['reaches'], 'removable': info['removable']}
    if not info['removable']:
        kept.append(dict(values, why=info['why_not']))
        continue
    answer = Board.other_rule_remove(row.id, company.id)
    values['answer'] = {k: answer.get(k) for k in ('saved', 'pending', 'message', 'reference')}
    removed.append(values)
env.flush_all()
for row in all_vn_lists:
    if row.id not in [r.id for r in candidates]:
        kept.append({'id': row.id, 'date_from': str(row.date_from or ''), 'date_to': str(row.date_to or ''),
                     'why': 'not in force today (outside its dates), so not shown and not reaching anybody'})
after = answers()
changed = {v: [e for e in before[v] if before[v][e] != after[v][e]] for v in ('with', 'without')}
section = Board.country_lines(company.id)
result = {
    'mode': mode, 'removed': removed, 'kept': kept,
    'changed_with_person_rule': len(changed['with']), 'changed_without_person_rule': len(changed['without']),
    'section': {'set': section['set'], 'countries': len(section['rows']), 'holes': section['holes'],
                'other_rules': len(section['others'])},
    'people': len(people),
}
result['ok'] = bool(removed) and not changed['with'] and not changed['without'] and section['holes'] == 0
os.makedirs(out, exist_ok=True)
json.dump(result, open(os.path.join(out, 'rize_vn_rule_remove_%s.json' % mode), 'w'), indent=1, default=str)
if mode == 'apply' and result['ok']:
    with open(os.path.join(out, 'rize_vn_rule_remove_undo.txt'), 'w') as fh:
        for v in removed:
            fh.write('Removed (archived) map line id %(id)s: domain %(domain)s -> pay scheme id %(config_id)s, '
                     'kind of run %(cycle_type)s, sequence %(sequence)s, source %(source)s, dates %(date_from)s..%(date_to)s.\n' % v)
            fh.write('Undo (odoo-bin shell on rize): env["hr.formula.scheme.assignment"].sudo().with_context('
                     'active_test=False).browse(%s).active = True; env.cr.commit()  - then Mapping > Work it out again.\n'
                     % v['id'])
    env.cr.commit()
    print('PROBE committed')
else:
    env.cr.rollback()
    print('PROBE rolled back (mode %s, ok %s)' % (mode, result['ok']))
print('PROBE', json.dumps({k: v for k, v in result.items() if k not in ('removed', 'kept')}, default=str))
print('PROBE removed', [(r['id'], r['reaches'], (r.get('answer') or {}).get('message')) for r in removed])
print('PROBE kept', [(k['id'], k.get('why')) for k in kept])
