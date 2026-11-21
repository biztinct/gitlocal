# -*- coding: utf-8 -*-
"""LEARNING L3 — demo learning paths on payobook (handover §6). Idempotent.

Run with the service stopped, on payobook ONLY:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < l3_demo_seed.py

(Locally the same script seeds the walk database; the environment variables
L3_SEED_COMPANY, L3_SEED_COURSE, L3_SEED_LEARNER and L3_SEED_HR override the
payobook defaults below.)

What it does (every new record named "DEMO …" and put on the demo register
when that module is installed):
  1. Three short DEMO courses, one reading lesson each, published,
     invite-only, no test: "DEMO Pesticide handling", "DEMO Field data on the
     phone", "DEMO Leading a line".
  2. Path "DEMO New agronomist" (for a role): course 27 Agronomist basics
     (gate) → Pesticide handling (gate) → Field data on the phone; given on
     day one to the DEMO agronomist jobs (the day-one switch stays as it is —
     off on payobook — so nobody is enrolled by it).
  3. Path "DEMO Operator to line leader" (for a career move): Leading a line →
     Pesticide handling.
  4. People: course 27 ends in a TEST, and only the people who really passed
     it can be past its gate — the seed never fakes a pass (it would file a
     certificate nobody earned). So New agronomist takes the demo learner and
     up to five more demo people at step 1 (one of them late), and the real
     course-27 passers past the gate (one finishes Pesticide handling, so the
     line shows people at all three steps). The career path takes the HR lead
     and four more: two at step 1, two at step 2 (they finished Leading a
     line, through the learner's own "mark as done"), one finished.
  5. One existing DEMO growth plan's objective is pointed at the career path
     (not enrolled — the walk presses "Enrol").
  6. Runs the morning job's path leg once inside a rolled-back savepoint and
     prints what it would do (nothing should change).
  7. NO EMAIL: only demo logins ending "@example.com" are picked, and the
     "a course has been added" announcement (email + to-do) is switched off
     for this run — payobook also holds real sign-up accounts.
Nothing here contains a password or a real person's data.
"""
import os
from datetime import timedelta

from odoo import fields

COMPANY_ID = int(os.environ.get('L3_SEED_COMPANY') or 5)
COURSE_ID = int(os.environ.get('L3_SEED_COURSE') or 27)
LEARNER = os.environ.get('L3_SEED_LEARNER') or 'demo.learner@example.com'
HR_LEAD = os.environ.get('L3_SEED_HR') or 'demo.hr@example.com'
LABEL = 'DEMO Learning L3 paths'


def say(msg, *args):
    print('L3 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
today = fields.Date.today()
seed = env.get('pb.demo.seed')
company = env['res.company'].browse(COMPANY_ID).exists() or env.company
env = env(context=dict(env.context, allowed_company_ids=[company.id],
                       lang='en_US'))
Channel = env['slide.channel'].sudo()
Path = env['pb.training.path'].sudo().with_context(active_test=False)
Enrol = env['pb.training.path.enrolment'].sudo()
Emp = env['hr.employee'].sudo()
Users = env['res.users'].sudo()
new_records = []
base = Channel.browse(COURSE_ID).exists()
DEMO_LOGIN = os.environ.get('L3_SEED_LOGIN_LIKE') or '%@example.com'
# 7. No email from this run: the announcement is a no-op while seeding.
type(env['pb.training.assignment'])._announce = lambda self: True
mails_last = env['mail.mail'].sudo().search([], order='id desc', limit=1).id or 0
say('company %s "%s"; course %s', company.id, company.name,
    '%s "%s"' % (base.id, base.name) if base else 'NOT FOUND')


# ---------------------------------------------------------------- 1. courses
def course(name, text):
    channel = Channel.search([('name', '=', name)], limit=1)
    if channel:
        return channel
    channel = Channel.create({
        'name': name, 'channel_type': 'training', 'visibility': 'members',
        'enroll': 'invite', 'completed_template_id': False,
        'is_published': True,
        'description_short': text})
    env['slide.slide'].sudo().create({
        'name': '%s — read this first' % name, 'channel_id': channel.id,
        'slide_category': 'article', 'html_content': '<p>%s</p>' % text,
        'is_published': True, 'sequence': 1, 'completion_time': 0.25})
    new_records.append(channel)
    say('made course %s "%s"', channel.id, name)
    return channel


pest = course('DEMO Pesticide handling',
              'Mixing, spraying and storing pesticide safely.')
phone = course('DEMO Field data on the phone',
               'Recording plot data on the phone, offline first.')
lead = course('DEMO Leading a line',
              'Running a production line shift: handover, safety, people.')


# ------------------------------------------------------------------ 2/3 paths
def path(name, purpose, blurb, steps, **extra):
    row = Path.search([('name', '=', name), ('company_id', '=', company.id)],
                      limit=1)
    if row:
        return row
    row = Path.create(dict({
        'name': name, 'purpose': purpose, 'blurb': blurb,
        'company_id': company.id, 'due_days': 60,
        'step_ids': [(0, 0, {'channel_id': c.id, 'gate': g,
                             'sequence': (i + 1) * 10})
                     for i, (c, g) in enumerate(steps)]}, **extra))
    new_records.append(row)
    say('made path %s "%s" with %s steps', row.id, name, len(steps))
    return row


jobs = env['hr.job'].sudo().search([('company_id', '=', company.id),
                                    ('name', 'ilike', 'agronomist'),
                                    ('name', 'ilike', 'DEMO')])
steps_new = ([(base, True)] if base else []) + [(pest, True), (phone, False)]
newbie = path('DEMO New agronomist', 'role',
              'What a new agronomist needs in the first two months.',
              steps_new, day_one=bool(jobs),
              job_ids=[(6, 0, jobs.ids)])
career = path('DEMO Operator to line leader', 'career',
              'From machine operator to running a line on your own.',
              [(lead, False), (pest, False)])


# ------------------------------------------------------------------ 4. people
def emp_of_login(login):
    user = Users.search([('login', '=', login)], limit=1)
    return Emp.search([('user_id', '=', user.id)], limit=1) if user else \
        Emp.browse()


def on(path_rec, people, reason='adhoc'):
    out = Enrol.browse()
    for emp in people:
        row = Enrol.search([('path_id', '=', path_rec.id),
                            ('employee_id', '=', emp.id),
                            ('state', '!=', 'cancelled')], limit=1)
        if not row:
            res = Enrol._enrol_people(path_rec.id, [emp.id], reason=reason)
            row = Enrol.browse(res['made'][:1])
            if row:
                new_records.append(row)
        out |= row
    return out


def finish(emp, channel):
    """The learner's own "mark as done" on every lesson of a no-test course."""
    user = emp.user_id
    if not user or not channel:
        return
    my = env['pb.my.training'].with_user(user).with_context(
        allowed_company_ids=[company.id])
    for lesson in channel._pb_lessons():
        try:
            my.mark_done(channel.id, lesson.id)
        except Exception as exc:        # noqa: BLE001 — say it, carry on
            say('could not mark %s done for %s: %s', lesson.name, emp.name,
                exc)


learner = emp_of_login(LEARNER)
hr_lead = emp_of_login(HR_LEAD)
passers = Emp.browse()
if base:
    test = base._pb_test_slide()
    if test:
        partners = env['survey.user_input'].sudo().search([
            ('survey_id', '=', test.survey_id.id), ('state', '=', 'done'),
            ('scoring_success', '=', True)]).mapped('partner_id')
        passers = Emp.search([('user_id.partner_id', 'in', partners.ids),
                              ('user_id.login', '=like', DEMO_LOGIN),
                              ('company_id', '=', company.id)])
exclude = (learner | hr_lead | passers).ids
pool = Emp.search([('company_id', '=', company.id), ('user_id', '!=', False),
                   ('user_id.login', '=like', DEMO_LOGIN),
                   ('active', '=', True), ('id', 'not in', exclude)],
                  order='id', limit=9)
say('demo cast: learner %s, HR lead %s, passers %s, pool %s',
    learner.name or '-', hr_lead.name or '-', passers.mapped('name'),
    pool.mapped('user_id.login'))
starters = pool[:5]
movers = pool[5:9]

a = on(newbie, learner | starters | passers)
late = a.filtered(lambda e: e.employee_id in starters)[:1]
if late and late.state != 'overdue':
    late.write({'due_date': today - timedelta(days=3)})
for emp in passers[:1]:
    finish(emp, pest)
b = on(career, hr_lead | movers)
for emp in movers[:3]:
    finish(emp, lead)
for emp in movers[:1]:
    finish(emp, pest)
(a | b)._refresh()
for p in (newbie, career):
    counts = [s['count'] for s in p._stations()]
    say('%s: %s people; stations %s (last = finished); late %s', p.name,
        len(p.enrolment_ids.filtered(lambda e: e.state != 'cancelled')),
        counts, len(p.enrolment_ids.filtered(lambda e: e.state == 'overdue')))

# ------------------------------------------------------------- 5. growth plan
case = env['pb.pip.case'].sudo().search([('company_id', '=', company.id)],
                                        order='id', limit=1) \
    if 'pb.pip.case' in env else None
if case:
    objective = case.objective_ids[:1]
    if not objective:
        objective = env['pb.pip.objective'].sudo().create({
            'case_id': case.id, 'name': 'DEMO Run a line shift on your own',
            'metric': 'Runs two full shifts with no escalation'})
        new_records.append(objective)
    if 'path_id' in objective._fields and not objective.path_id:
        objective.write({'path_id': career.id})
    say('growth plan %s (%s): objective "%s" points at %s', case.id,
        case.employee_id.name, objective.name,
        objective.path_id.name if 'path_id' in objective._fields else '—')
else:
    say('no growth plan in this company — step 5 skipped')

# ------------------------------------------------------------- register, job
if seed is not None:
    for rec in new_records:
        seed.register(rec, LABEL)
    say('registered %s record(s) on the demo register', len(new_records))
with env.cr.savepoint(flush=True) as sp:
    n = env['pb.training.automation']._refresh_paths(today)
    say('morning path leg (rolled back): %s enrolment(s) brought up to date',
        n)
    sp.rollback()
# Marking a demo person's first lesson done earns the stock "New rank"
# gamification email (found on the live run, 2026-10-22): cancel anything
# this run queued, so the seed never writes to anybody.
queued = env['mail.mail'].sudo().search([('state', '=', 'outgoing')],
                                        order='id desc', limit=200).filtered(
    lambda m: m.id > mails_last)
queued.write({'state': 'cancel'})
say('mail queued by this run and cancelled: %s', len(queued))
env.cr.commit()
say('done')
