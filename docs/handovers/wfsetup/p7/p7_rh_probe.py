# WFSETUP P7 (odoo-bin shell on the REHEARSAL COPY only; trimmed clone of ../p5b/wfs_rh_probe.py):
# read-only, rolled back. As the throwaway manager: people(), load(), clocks(), rules(), live_plan();
# then the rules module's 15-minute calculation job run ONCE by hand: rows it would pick, what it wrote.
import time, json
assert env.cr.dbname.startswith('wfs_rh7_'), 'rehearsal copy only'
u = env['res.users'].search([('login', '=', 'wfs-rh-manager')])
cid = u.company_id.id
F = env['pb.workforce.setup'].with_user(u).with_company(cid).with_context(allowed_company_ids=[cid])
R = env['hr.shift.planning'].sudo()
def p(*a):
    print('PROBE', *a)
p('company', cid, u.company_id.name, 'companies', env['res.company'].search_count([]))
t = time.time(); people = F.people(); tp = time.time() - t
rows = people.get('rows') or people.get('people') or []
p('people() %.2f s' % tp, 'rows', len(rows), 'active employees of the company', env['hr.employee'].sudo().search_count([('company_id', '=', cid)]))
t = time.time(); ld = F.load(); p('load() %.2f s' % (time.time() - t), 'keys', sorted(ld)[:15])
t = time.time(); ck = F.clocks(); p('clocks() %.2f s' % (time.time() - t), {k: len(v) for k, v in ck.items() if isinstance(v, list)})
t = time.time(); ru = F.rules(); p('rules() %.2f s' % (time.time() - t), 'state', ru.get('state'))
t = time.time(); pl = F.live_plan(); w = pl.get('weeks') or []
p('live_plan() %.2f s' % (time.time() - t), 'weeks', len(w), 'new shifts 12 weeks', sum(x.get('new_shifts', 0) for x in w))
env.cr.rollback()
# the calculation job, once, as the job runs it (superuser), on this copy
Pol = env['pb.attendance.policy'].sudo()
p('rule sets', Pol.search_count([]), 'active', Pol.search_count([('state', '=', 'active')]),
  'people with a rule set', env['hr.employee'].sudo().with_context(active_test=False).search_count([('pb_attendance_policy_id', '!=', False)]),
  'roster rows with a rule set', R.search_count([('pb_policy_id', '!=', False)]),
  'roster rows', R.search_count([]), 'published', R.search_count([('state', '=', 'published')]))
cron = env.ref('pb_attendance_policy.cron_calculate')
p('job', cron.id, cron.cron_name, 'every', cron.interval_number, cron.interval_type, 'active', cron.active)
def snap():
    env.cr.execute("select count(*), coalesce(max(write_date)::text,'') from hr_attendance"); a = env.cr.fetchone()
    env.cr.execute("select count(*), coalesce(max(write_date)::text,'') from hr_shift_planning"); s = env.cr.fetchone()
    env.cr.execute("select count(*), coalesce(max(write_date)::text,'') from hr_overtime_request"); o = env.cr.fetchone()
    return a, s, o
b = snap()
from odoo import fields
from datetime import timedelta
picked = R.search_count([('state', '=', 'published'), ('pb_policy_id.state', '=', 'active'),
                         ('end_datetime', '<', fields.Datetime.now()), ('date', '>=', fields.Date.today() - timedelta(days=35))])
t = time.time(); R._cron_policy_calculate(); env.flush_all(); dt = time.time() - t
a = snap()
p('job ran in %.2f s' % dt, 'rows it picks', picked, 'attendance/roster/overtime before', b, 'after', a, 'unchanged', a == b)
env.cr.rollback()
