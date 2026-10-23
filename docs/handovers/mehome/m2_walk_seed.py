# MEHOME M2 walk seed for "Linh Tran" on p0clone ONLY (odoo shell script).
from datetime import date, datetime, time, timedelta

import pytz

EMP_ID = 5842
emp = env['hr.employee'].sudo().browse(EMP_ID)
user = emp.user_id
assert emp.name == 'Linh Tran' and env.cr.dbname == 'p0clone', (emp.name, env.cr.dbname)
TZ = 'Asia/Ho_Chi_Minh'
user.partner_id.tz = TZ
emp.tz = TZ         # the schedule facade draws hours on the employee's clock
tz = pytz.timezone(TZ)
today = datetime.now(pytz.utc).astimezone(tz).date()
monday = today - timedelta(days=today.weekday())
print('WALK today', today, 'monday', monday)


def utc(d, hh, mm=0):
    return tz.localize(datetime.combine(d, time(hh, mm))).astimezone(pytz.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- payslips
Slip = env['hr.payslip'].sudo()
vnd = env.ref('base.VND')
if not vnd.active:
    vnd.active = True
aug = Slip.browse(3470)
sep = Slip.browse(3471)
jul = Slip.search([('employee_id', '=', EMP_ID), ('date_to', '=', date(2026, 7, 31))], limit=1)
if not jul:
    jul = Slip.create({'name': 'Salary July 2026', 'employee_id': EMP_ID,
                       'contract_id': aug.contract_id.id, 'company_id': aug.company_id.id,
                       'date_from': date(2026, 7, 1), 'date_to': date(2026, 7, 31)})
    aug_net = aug.line_ids.filtered(lambda l: l.code == 'NET')[:1]
    vals = {'slip_id': jul.id, 'name': aug_net.name, 'code': 'NET', 'amount': 1.0,
            'quantity': 1.0, 'rate': 100.0, 'employee_id': EMP_ID,
            'contract_id': aug.contract_id.id, 'salary_rule_id': aug_net.salary_rule_id.id,
            'category_id': aug_net.category_id.id}
    if 'pay_role' in aug_net._fields:
        vals['pay_role'] = 'net'
    env['hr.payslip.line'].sudo().create(vals)
env.flush_all()
for slip, net in ((jul, 27250000.0), (aug, 28450000.0), (sep, 26100000.0)):
    env.cr.execute("UPDATE hr_payslip_line SET amount=%s, total=%s, quantity=1, rate=100 "
                   "WHERE slip_id=%s AND (code='NET' OR pay_role='net')", (net, net, slip.id))
    env.cr.execute("UPDATE hr_payslip SET state='done' WHERE id=%s", (slip.id,))
# one pay run per month in đ, so the card shows the employee's own currency
Run = env['hr.payslip.run'].sudo()
for slip in (jul, aug, sep):
    if slip.payslip_run_id:
        run = slip.payslip_run_id
    else:
        run = Run.create({'name': 'MEHOME walk %s' % slip.date_to.strftime('%B %Y'),
                          'date_start': slip.date_from, 'date_end': slip.date_to})
        env.cr.execute('UPDATE hr_payslip SET payslip_run_id=%s WHERE id=%s', (run.id, slip.id))
    if 'pb_currency_id' in run._fields:
        env.flush_all()
        env.cr.execute('UPDATE hr_payslip_run SET pb_currency_id=%s WHERE id=%s', (vnd.id, run.id))
env.invalidate_all()

# ------------------------------------------------------------------- leave
Alloc = env['hr.leave.allocation'].sudo()
Leave = env['hr.leave'].sudo().with_context(leave_skip_date_check=True, mail_create_nolog=True,
                                            tracking_disable=True)
pto = env['hr.leave.type'].browse(1)        # Paid Time Off (needs an allocation)
unpaid = env['hr.leave.type'].browse(4)     # Unpaid (no allocation)
alloc = Alloc.search([('employee_id', '=', EMP_ID), ('holiday_status_id', '=', pto.id)], limit=1)
if not alloc:
    alloc = Alloc.create({'name': 'MEHOME walk allocation', 'employee_id': EMP_ID,
                          'holiday_status_id': pto.id, 'number_of_days': 20,
                          'allocation_type': 'regular', 'date_from': date(2026, 1, 1)})
if alloc.state != 'validate':
    try:
        alloc.action_approve()
    except Exception as e:  # noqa: BLE001
        print('WALK alloc approve', e)
    if alloc.state != 'validate':
        env.cr.execute("UPDATE hr_leave_allocation SET state='validate' WHERE id=%s", (alloc.id,))


def leave(ltype, d_from, d_to, label):
    lv = Leave.search([('employee_id', '=', EMP_ID), ('holiday_status_id', '=', ltype.id),
                       ('request_date_from', '=', d_from)], limit=1)
    if not lv:
        lv = Leave.create({'name': label, 'employee_id': EMP_ID, 'holiday_status_id': ltype.id,
                           'request_date_from': d_from, 'request_date_to': d_to})
    if lv.state != 'validate':
        try:
            lv.action_approve()
            if lv.state != 'validate':
                lv.action_validate()
        except Exception as e:  # noqa: BLE001
            print('WALK leave approve', label, e)
        if lv.state != 'validate':
            env.cr.execute("UPDATE hr_leave SET state='validate' WHERE id=%s", (lv.id,))
    return lv


taken = leave(pto, date(2026, 9, 21), date(2026, 9, 22), 'MEHOME walk two days off')
friday = monday + timedelta(days=4)
week_leave = leave(unpaid, friday, friday, 'MEHOME walk day off')
env.invalidate_all()
print('WALK leave', taken.number_of_days, taken.state, week_leave.state)

# ------------------------------------------------------------------ shifts
Shift = env['hr.shift.planning'].sudo()
Shift.search([('employee_id', '=', EMP_ID), ('date', '>=', monday),
              ('date', '<=', monday + timedelta(days=6))]).unlink()
plan = [  # (day offset, start, end, acked)
    (0, (9, 0), (17, 0), True),
    (1, (9, 0), (17, 0), True),
    (2, (22, 0), (23, 30), False),      # today, still ahead → can be confirmed
    (3, (9, 0), (17, 0), False),
    (5, (9, 0), (13, 0), False),
]
now = datetime.utcnow()
for off, (sh, sm), (eh, em), acked in plan:
    d = monday + timedelta(days=off)
    s = Shift.create({'employee_id': EMP_ID, 'date': d, 'shift_template_id': 3 if sh >= 20 else 4,
                      'start_datetime': utc(d, sh, sm), 'end_datetime': utc(d, eh, em),
                      'company_id': emp.company_id.id})
    s.write({'state': 'published'})
    ack = {'ack_state': 'acked' if acked else 'pending'}
    if acked:
        ack['acked_at'] = now
    s._ess_ack_env().write(ack)
    print('WALK shift', d, s.planned_hours, s.state, s.ack_state)

# -------------------------------------------------------------- attendance
Att = env['hr.attendance'].sudo()
Att.search([('employee_id', '=', EMP_ID), ('check_in', '>=', utc(monday, 0)),
            ('check_in', '<', utc(monday + timedelta(days=1), 0))]).unlink()
Att.create({'employee_id': EMP_ID, 'check_in': utc(monday, 9), 'check_out': utc(monday, 17)})

env.cr.commit()
env.invalidate_all()
home = env['pb.me.home'].with_user(user).get_home_data(emp.with_user(user))
print('WALK pay', {k: home['pay'].get(k) for k in ('count', 'previous_net', 'next_pay_date')},
      home['pay']['last']['net'], home['pay']['last']['currency'].name,
      [t['net'] for t in home['pay']['trend']])
print('WALK leave', home['leave'])
wk = home['week']
print('WALK week', wk['pending'], wk['scheduled_h'], wk['worked_h'],
      [(d['state'], d['shift_short'], d['is_today']) for d in wk['days']])
print('WALK needs', [(n['key'], n['n']) for n in home['needs_you']])
