# WFSETUP P5b (odoo-bin shell on the REHEARSAL COPY only, after the walk confirmed the rules): make a
# PAST day published (yesterday's drafts of the company, pointed at the active rule set) and run the
# 15-minute calculation job ONCE by hand; count what it made. Committed on the copy (dropped after).
import time
from datetime import timedelta
from odoo import fields
assert env.cr.dbname.startswith('wfs_rh_'), 'rehearsal copy only'
u = env['res.users'].search([('login', '=', 'wfs-rh-manager')])
cid = u.company_id.id
R = env['hr.shift.planning'].sudo()
pol = env['pb.attendance.policy'].sudo().search([('company_id', '=', cid), ('state', '=', 'active')], limit=1)
print('PROBE active rule set', pol.id, pol.name)
today = fields.Date.context_today(R.with_context(tz=pol.tz or 'Asia/Ho_Chi_Minh'))
day = today - timedelta(days=1)
rows = R.search([('company_id', '=', cid), ('date', '=', day), ('state', '=', 'draft')])
print('PROBE past day', day, 'drafts', len(rows), 'already published that day', R.search_count([('company_id', '=', cid), ('date', '=', day), ('state', '=', 'published')]))
rows.with_context(tracking_disable=True, mail_notrack=True).write({'pb_policy_id': pol.id})
ctx = dict(tracking_disable=True, mail_notrack=True, mail_create_nolog=True)
if hasattr(rows, 'action_publish'):
    rows.with_context(**ctx).action_publish()
else:
    rows.with_context(**ctx).write({'state': 'published'})
env.flush_all()
pub = rows.filtered(lambda r: r.state == 'published')
print('PROBE published for the test', len(pub), 'ended', len(pub.filtered(lambda r: r.end_datetime < fields.Datetime.now())))
A = env['hr.attendance'].sudo()
a0 = A.search_count([('pb_policy_roster_id', 'in', pub.ids)])
t = time.time()
R._cron_policy_calculate()
env.flush_all()
dt = time.time() - t
a1 = A.search_count([('pb_policy_roster_id', 'in', pub.ids)])
st = {}
for r in pub:
    k = (r.pb_calculation_status or '-')[:60]
    st[k] = st.get(k, 0) + 1
print('PROBE job ran in %.1f s' % dt, 'attendance rows for the day: before', a0, 'after', a1)
print('PROBE rows with an attendance', len(pub.filtered('pb_attendance_id')), 'statuses', sorted(st.items(), key=lambda x: -x[1])[:8])
print('PROBE hours: normal %.1f overtime %.1f deduction %.1f' % (sum(pub.mapped('pb_normal_hours')), sum(pub.mapped('pb_overtime_hours')), sum(pub.mapped('pb_deduction_hours'))))
env.cr.commit()
