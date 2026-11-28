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
    # one team per country (the team most people of that country work in): what step 2 and the payslip
    # example say for a new person there (team ids only, no names, no amounts)
    Emp = env['hr.employee'].sudo()
    for code, _label in nh._countries():
        groups = Emp._read_group([('company_id', '=', company.id), ('active', '=', True),
                                  ('payroll_country', '=', code), ('department_id', '!=', False)],
                                 ['department_id'], ['__count'], order='__count desc', limit=1)
        if not groups:
            continue
        team = groups[0][0]
        d = nh.decides(team.id, code, '2026-12-07')
        s = d.get('scheme') or {}
        ex = nh.payslip_example({'name': 'DEMO P8 Look', 'date_start': '2026-12-07', 'department_id': team.id,
                                 'job_title': 'DEMO', 'payroll_country': code, 'wage': 1000,
                                 'contract_kind': 'permanent'})
        print('PROBE team-look company %s %s team %s: scheme %s rung %s honoured %s problem %s | example ok %s lines %s %s' % (
            company.id, code, team.id, s.get('id'), s.get('rung'), s.get('honoured'), bool(d.get('problem')),
            ex.get('ok'), len(ex.get('lines') or []), (ex.get('error') or '')[:80]))
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
