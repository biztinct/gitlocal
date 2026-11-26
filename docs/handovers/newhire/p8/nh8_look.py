# NEWHIRE P8 (odoo-bin shell, read-only, rolled back; rehearsal copy or live): what this release shows on
# this database - per Country of work the pay scheme tile (one / several / none); "Suggest who pays each
# team" counts; the two new roles and who holds them by implication; the page builder gate. Counts only.
import time
assert not env.cr.dbname.startswith('abm') and env.cr.dbname != '_test_sudima_policy_20261119', 'never this database'
NH = env['pb.new.hire']
for company in env['res.company'].sudo().search([], order='id'):
    people = env['hr.employee'].sudo().search_count([('company_id', '=', company.id), ('active', '=', True)])
    if not people:
        continue
    nh = NH.with_company(company).with_context(allowed_company_ids=[company.id]).sudo()
    line = ['company %s (%s people)' % (company.id, people)]
    for code, _label in nh._countries():
        t0 = time.perf_counter()
        d = nh.decides(False, code)
        ms = (time.perf_counter() - t0) * 1000
        s = d.get('scheme') or {}
        line.append('%s %s%s %.0f ms' % (code, 'several(%s)' % len(d['schemes']) if d['schemes'] else
                                          ('one' if s else 'none'), ' id=%s' % s.get('id') if s else '', ms))
    try:
        sug = env['pb.scheme.map'].sudo().suggest_by_country(company.id)
        line.append('suggest %s mapped %s' % (dict(sug['counts']), sug['mapped']))
    except Exception as e:      # noqa: BLE001
        line.append('suggest ERROR %s' % type(e).__name__)
    print('PROBE', ' | '.join(line))
for xmlid in ('pb_new_hire.group_joiners_board', 'pb_form_studio_portal.group_page_builder'):
    g = env.ref(xmlid, raise_if_not_found=False)
    if g:
        users = env['res.users'].sudo().search([('all_group_ids', 'in', g.id), ('share', '=', False), ('active', '=', True)])
        print('PROBE role', xmlid, 'internal users holding it', len(users),
              'implied by HR manager', env.ref('hr.group_hr_manager') in g.implied_by_ids)
    else:
        print('PROBE role', xmlid, 'MISSING')
env.cr.rollback()
