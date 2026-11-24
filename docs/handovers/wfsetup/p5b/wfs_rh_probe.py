# WFSETUP P5b (odoo-bin shell on the REHEARSAL COPY only): server-side numbers as the throwaway manager.
# PHASE=before (read-only, rolled back): people, working weeks, clocks, rules, the 12-week plan + time.
# PHASE=after (read-only): what the walk's Confirm + Publish left behind - published rows per company,
# duplicates per person/day, rows with the rule set, other companies untouched since the walk started.
import os, time, json
from datetime import timedelta
assert env.cr.dbname.startswith('wfs_rh_'), 'rehearsal copy only'
phase = os.environ.get('PHASE', 'before')
u = env['res.users'].search([('login', '=', 'wfs-rh-manager')])
cid = u.company_id.id
F = env['pb.workforce.setup'].with_user(u).with_company(cid).with_context(allowed_company_ids=[cid])
R = env['hr.shift.planning'].sudo()
def p(*a):
    print('PROBE', *a)
p('company', cid, u.company_id.name, 'companies', env['res.company'].search_count([]))
if phase == 'before':
    t = time.time(); people = F.people(); tp = time.time() - t
    rows = people.get('rows') or people.get('people') or []
    p('people() %.2f s' % tp, 'keys', sorted(people)[:12], 'rows', len(rows))
    t = time.time(); ld = F.load(); p('load() %.2f s' % (time.time() - t), 'keys', sorted(ld)[:15])
    for k in ('weeks', 'patterns', 'shifts', 'steps'):
        if k in ld:
            v = ld[k]; p('load', k, len(v) if hasattr(v, '__len__') else v)
    t = time.time(); ck = F.clocks(); p('clocks() %.2f s' % (time.time() - t), 'keys', sorted(ck)[:10],
        {k: len(v) for k, v in ck.items() if isinstance(v, list)})
    t = time.time(); ru = F.rules(); p('rules() %.2f s' % (time.time() - t), 'state', ru.get('state'), 'keys', sorted(ru)[:14])
    t = time.time(); pl = F.live_plan(); tl = time.time() - t
    w = pl['weeks']
    p('live_plan() %.2f s' % tl, 'weeks', len(w), 'week1', json.dumps(w[0])[:300])
    p('live_plan 2 weeks: new', sum(x['new_shifts'] for x in w[:2]), 'already planned', sum(x['already_planned'] for x in w[:2]),
      'people', sum(x['people'] for x in w[:2]), 'removed', sum(x['removed'] for x in w[:2]), 'skipped', sum(x['skipped_total'] for x in w[:2]))
    p('live_plan 12 weeks: new', sum(x['new_shifts'] for x in w), 'already planned', sum(x['already_planned'] for x in w),
      'people', sum(x['people'] for x in w))
    p('roster now: drafts', R.search_count([('company_id', '=', cid), ('state', '=', 'draft')]),
      'published', R.search_count([('company_id', '=', cid), ('state', '=', 'published')]),
      'other companies', R.search_count([('company_id', '!=', cid)]))
    env.cr.rollback()
else:
    since = os.environ.get('SINCE')
    pub = R.search([('company_id', '=', cid), ('state', '=', 'published')])
    p('published rows', len(pub), 'people', len(pub.mapped('employee_id')), 'dates', min(pub.mapped('date')) if pub else '-', max(pub.mapped('date')) if pub else '-')
    env.cr.execute("""select count(*) from (select employee_id, date from hr_shift_planning where company_id=%s and state='published'
                      group by 1,2 having count(*)>1) s""", [cid])
    p('published duplicates per person/day', env.cr.fetchone()[0])
    env.cr.execute("""select count(*) from (select employee_id, date, start_datetime from hr_shift_planning where company_id=%s
                      group by 1,2,3 having count(*)>1) s""", [cid])
    p('any-state duplicates per person/day/start', env.cr.fetchone()[0])
    p('published with the active rule set', R.search_count([('company_id', '=', cid), ('state', '=', 'published'), ('pb_policy_id.state', '=', 'active')]))
    p('day kinds published', dict((k, R.search_count([('company_id', '=', cid), ('state', '=', 'published'), ('pb_day_kind', '=', k)])) for k in ('normal', 'holiday', 'rest_day', 'weekend')))
    if since:
        p('other companies written since', since, R.search_count([('company_id', '!=', cid), ('write_date', '>=', since)]),
          'employees of other companies written', env['hr.employee'].sudo().search_count([('company_id', '!=', cid), ('write_date', '>=', since)]))
    pol = env['pb.attendance.policy'].sudo().search([('company_id', '=', cid)])
    p('rule sets', [(x.id, x.state) for x in pol], 'people on the active one', env['hr.employee'].sudo().search_count([('company_id', '=', cid), ('pb_attendance_policy_id.state', '=', 'active')]))
    co = env['res.company'].browse(cid)
    p('company setup', co.pb_wfs_holidays_year, co.pb_wfs_clocks_ok, co.pb_wfs_live_on, co.pb_wfs_live_to)
    p('days off 2027', env['resource.calendar.leaves'].sudo().search_count([('company_id', '=', cid), ('resource_id', '=', False), ('date_from', '>=', '2026-12-31'), ('date_to', '<=', '2028-01-01')]))
    p('mail queue outgoing', env['mail.mail'].sudo().search_count([('state', '=', 'outgoing')]))
    env.cr.rollback()
