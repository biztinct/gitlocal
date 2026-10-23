# -*- coding: utf-8 -*-
"""LEARNING L4 — demo sessions and a toolbox talk on payobook (handover §6,
minus the practical sign-off: owner decision LD5). Idempotent.

Run with the service stopped, on payobook ONLY:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < l4_demo_seed.py

(Locally the environment variables L4_SEED_COMPANY, L4_SEED_MANAGER,
L4_SEED_HR and L4_SEED_LOGIN_LIKE override the payobook defaults.)

What it does (every new record named "DEMO …" and put on the demo register
when that module is installed):
  1. Course "DEMO Site safety walk": taught in a room or on site, 2 hours,
     attending files a certificate valid 12 months, people may book a seat
     themselves.
  2. A session NEXT WEEK (09:00 local, Hall A): 14 seats, 16 people booked →
     14 booked and 2 waiting for a seat; marked "Invitations sent" WITHOUT
     sending any (the quiet diary entry is made; it never mails anybody).
     (The handover's "20 seats, 14 booked, 2 waiting" cannot happen — people
     only wait when the seats are full — so the seats are 14.)
  3. A session LAST WEEK: 10 booked, 9 attended, closed → 1 did not come; the
     9 get the course marked finished, 2 hours and a certificate each.
  4. A toolbox talk "DEMO Lifting safely" logged YESTERDAY by the manager
     (lam.ngo) for up to 8 of the people under him.
  5. Runs the morning job's two session legs inside a rolled-back savepoint
     and prints what they would do.
  6. NO EMAIL: only demo logins ending "@example.com" (or people with no login
     at all) are picked, the booking path sends nothing, and anything this run
     queued is cancelled at the end (the L3 lesson). payobook also holds real
     sign-up accounts.
Nothing here contains a password or a real person's data.
"""
import os
from datetime import datetime, timedelta

import pytz

from odoo import fields

COMPANY_ID = int(os.environ.get('L4_SEED_COMPANY') or 5)
MANAGER = os.environ.get('L4_SEED_MANAGER') or 'lam.ngo@example.com'
HR_LEAD = os.environ.get('L4_SEED_HR') or 'demo.hr@example.com'
DEMO_LOGIN = os.environ.get('L4_SEED_LOGIN_LIKE') or '%@example.com'
LABEL = 'DEMO Learning L4 sessions'
TZ = 'Asia/Ho_Chi_Minh'


def say(msg, *args):
    print('L4 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
seed = env.get('pb.demo.seed')
company = env['res.company'].browse(COMPANY_ID).exists() or env.company
env = env(context=dict(env.context, allowed_company_ids=[company.id],
                       lang='en_US', tz=TZ))
Channel = env['slide.channel'].sudo()
Session = env['pb.training.session'].sudo()
Emp = env['hr.employee'].sudo()
Users = env['res.users'].sudo()
new_records = []
mails_last = env['mail.mail'].sudo().search(
    [], order='id desc', limit=1).id or 0
say('company %s "%s"', company.id, company.name)


def utc_at(day, hour, minute=0):
    """A local wall-clock time on `day` as the naive UTC the ORM stores."""
    local = pytz.timezone(TZ).localize(datetime(day.year, day.month, day.day,
                                                hour, minute))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


# ------------------------------------------------------------- people
demo_users = Users.search([('login', '=like', DEMO_LOGIN),
                           ('company_ids', 'in', company.ids)])
pool = Emp.search([('company_id', '=', company.id), ('active', '=', True),
                   ('user_id', 'in', demo_users.ids)], order='id')
nologin = Emp.search([('company_id', '=', company.id), ('active', '=', True),
                      ('user_id', '=', False)], order='id', limit=40)
people = (pool | nologin)
say('people to pick from: %s with a demo login, %s with no login',
    len(pool), len(nologin))
hr_user = Users.search([('login', '=', HR_LEAD)], limit=1)
hr_emp = Emp.search([('user_id', '=', hr_user.id)], limit=1) if hr_user \
    else Emp.browse()
manager_user = Users.search([('login', '=', MANAGER)], limit=1)
manager_emp = Emp.search([('user_id', '=', manager_user.id),
                          ('company_id', '=', company.id)], limit=1) \
    if manager_user else Emp.browse()

# ------------------------------------------------------------- 1. course
course = Channel.search([('name', '=', 'DEMO Site safety walk')], limit=1)
if not course:
    course = Channel.create({
        'name': 'DEMO Site safety walk', 'channel_type': 'training',
        'visibility': 'members', 'enroll': 'invite',
        'completed_template_id': False, 'is_published': True,
        'delivery': 'session', 'session_hours': 2.0, 'pb_hours': 2.0,
        'session_certificate': True, 'session_validity_months': 12,
        'self_booking': True,
        'description_short': 'Walk the site with the safety officer: '
                             'exits, PPE, hazards and what to do if.'})
    new_records.append(course)
say('course %s "%s"', course.id, course.name)
today = fields.Date.today()
existing = Session.search([('channel_id', '=', course.id)])
trainer = {'trainer_id': hr_emp.id} if hr_emp else \
    {'trainer_name': 'DEMO Safety officer'}

if existing:
    say('sessions already there (%s) — steps 2 and 3 skipped', len(existing))
else:
    # ------------------------------------------------------------- 2. next week
    nxt = Session.create(dict(trainer, **{
        'channel_id': course.id, 'kind': 'onsite',
        'start': utc_at(today + timedelta(days=7), 9), 'minutes': 120,
        'place': 'DEMO Hall A, main gate', 'seats': 14,
        'company_id': company.id}))
    new_records.append(nxt)
    nxt._book(people[:16], send=False)
    nxt.write({'state': 'open'})
    nxt.attendance_ids.filtered(lambda a: a.state == 'booked').write(
        {'invited': True})
    nxt._sync_event()
    say('next week: session %s — %s', nxt.id, nxt._seats_words())
    # ------------------------------------------------------------- 3. last week
    last = Session.create(dict(trainer, **{
        'channel_id': course.id, 'kind': 'onsite',
        'start': utc_at(today - timedelta(days=7), 9), 'minutes': 120,
        'place': 'DEMO Hall A, main gate', 'seats': 12,
        'company_id': company.id}))
    new_records.append(last)
    group = people[16:26] or people[:10]
    last._book(group, send=False)
    last.write({'state': 'held'})
    for att in last.attendance_ids[:9]:
        att._mark('attended', 'qr')
    last.action_close()
    say('last week: session %s — %s attended, %s did not come', last.id,
        last.attended_count, last.no_show_count)

# ------------------------------------------------------------- 4. toolbox talk
talk = Session.search([('kind', '=', 'toolbox'),
                       ('channel_id.name', '=', 'DEMO Lifting safely')],
                      limit=1)
if talk:
    say('toolbox talk already there (%s) — step 4 skipped', talk.id)
elif not manager_emp:
    say('manager %s not found — step 4 skipped', MANAGER)
else:
    reports = Emp.search([('parent_id', 'child_of', manager_emp.id),
                          ('id', '!=', manager_emp.id),
                          ('active', '=', True),
                          '|', ('user_id', '=', False),
                          ('user_id', 'in', demo_users.ids)], limit=8)
    if not reports:
        say('nobody reports to %s — step 4 skipped', MANAGER)
    else:
        board = env['pb.training'].with_user(manager_user).with_context(
            allowed_company_ids=[company.id])
        res = board.log_toolbox({
            'new_course': 'DEMO Lifting safely', 'minutes': 15,
            'place': 'DEMO Warehouse B, loading bay',
            'start': fields.Datetime.to_string(
                utc_at(today - timedelta(days=1), 7, 30)),
            'notes': '<p>Bend the knees, test the weight, ask for a hand '
                     'over 25 kg.</p>',
            'employee_ids': reports.ids})
        talk = Session.browse(res['id'])
        new_records += [talk, talk.channel_id]
        say('toolbox talk: %s', res['message'])

# ------------------------------------------------------------- register, job
if seed is not None:
    for rec in new_records:
        seed.register(rec, LABEL)
    say('registered %s record(s) on the demo register', len(new_records))
with env.cr.savepoint(flush=True) as sp:
    Auto = env['pb.training.automation']
    say('morning legs (rolled back): %s reminder(s), %s session(s) closed '
        'by themselves', Auto._session_reminders(fields.Datetime.now(), {}),
        Auto._sessions_autoclose())
    sp.rollback()
queued = env['mail.mail'].sudo().search([('state', '=', 'outgoing')],
                                        order='id desc', limit=300).filtered(
    lambda m: m.id > mails_last)
queued.write({'state': 'cancel'})
say('mail queued by this run and cancelled: %s', len(queued))
env.cr.commit()
say('done')
