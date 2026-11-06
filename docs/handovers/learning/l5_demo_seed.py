# -*- coding: utf-8 -*-
"""LEARNING L5 — demo outside courses, course requests, a new course version,
a drawn test, feedback, follow-ups and skills on payobook (handover §6).
Idempotent.

Run with the service stopped, on payobook ONLY:

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < l5_demo_seed.py

(Locally the environment variables L5_SEED_COMPANY, L5_SEED_COURSE,
L5_SEED_MANAGER, L5_SEED_HR, L5_SEED_FIELD and L5_SEED_LOGIN_LIKE override the
payobook defaults.)

What it does (every new record named "DEMO …" and put on the demo register
when that module is installed):
  1. A training allowance for the demo company this year, only when none is
     set (10,000,000 in the company currency) — the requests need one.
  2. Three outside courses: DEMO Pesticide applicator licence (3,000,000, 8 h,
     an exam with a certificate valid 24 months, good for the agronomist
     jobs), DEMO Soil science online (free, 6 h), DEMO First aid at work
     (1,200,000, 7 h, classroom).
  3. Skills: two skill types with levels (DEMO Field skills: Basic / Good /
     Expert; DEMO Leadership: Basic / Good). Course 27 gives "DEMO Field
     safety · Basic", the licence gives "DEMO Spraying · Good". The
     agronomist job and DEMO Line leader require two skills each; a few demo
     people get a skill below the level so the SKILLS board shows gaps.
  4. Two course requests: the field demo login asks for DEMO Soil science
     online (waiting on their manager); the training team puts another demo
     person on the licence (agreed, 3,000,000 set aside).
  5. A small course of its own, "DEMO Safe chemical storage" (online, on
     no learning path), finished by three demo people and published as
     version 2 — they get a re-read. NOT course 27: it is a step of the L3
     learning paths and a re-read would reopen that step (coordinator).
  6. A test "DEMO Field safety quiz" that draws 5 of 8 questions.
  7. Six feedback answers on course 27 and two manager follow-ups answered.
  8. NO EMAIL: only demo logins ("@example.com") are used; everything this
     run queued (re-read mails, request mails, approval notices) is
     cancelled at the end, never deleted (the L3 lesson). payobook also holds
     real sign-up accounts.
Nothing here contains a password or a real person's data.
"""
import json
import os
from datetime import timedelta

from odoo import fields

COMPANY_ID = int(os.environ.get('L5_SEED_COMPANY') or 5)
COURSE_ID = int(os.environ.get('L5_SEED_COURSE') or 27)
MANAGER = os.environ.get('L5_SEED_MANAGER') or 'lam.ngo@example.com'
HR_LEAD = os.environ.get('L5_SEED_HR') or 'demo.hr@example.com'
FIELD = os.environ.get('L5_SEED_FIELD') or 'demo.field@example.com'
DEMO_LOGIN = os.environ.get('L5_SEED_LOGIN_LIKE') or '%@example.com'
LABEL = 'DEMO Learning L5 courses, requests, skills'


def say(msg, *args):
    print('L5 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
seed = env.get('pb.demo.seed')
company = env['res.company'].browse(COMPANY_ID).exists() or env.company
env = env(context=dict(env.context, allowed_company_ids=[company.id],
                       lang='en_US', tz='Asia/Ho_Chi_Minh'))
Emp = env['hr.employee'].sudo()
Users = env['res.users'].sudo()
new_records = []
mails_last = env['mail.mail'].sudo().search(
    [], order='id desc', limit=1).id or 0
today = fields.Date.today()
say('company %s "%s"', company.id, company.name)

hr_user = Users.search([('login', '=', HR_LEAD)], limit=1)
field_user = Users.search([('login', '=', FIELD)], limit=1)
manager_user = Users.search([('login', '=', MANAGER)], limit=1)
course = env['slide.channel'].sudo().browse(COURSE_ID).exists()
say('HR lead %s, field login %s, manager %s, course %s "%s"', hr_user.id,
    field_user.id, manager_user.id, course.id, course.name or '')
demo_users = Users.search([('login', '=like', DEMO_LOGIN),
                           ('company_ids', 'in', company.ids)])
pool = Emp.search([('company_id', '=', company.id), ('active', '=', True),
                   ('user_id', 'in', demo_users.ids)], order='id')
say('demo people with a demo login in the company: %s', len(pool))

# ------------------------------------------------------------- 1. allowance
Allowance = env['pb.training.allowance'].sudo()
if not Allowance.search([('company_id', '=', company.id),
                         ('employee_id', '=', False),
                         ('year', '=', today.year)], limit=1):
    alw = Allowance.create({'company_id': company.id, 'year': today.year,
                            'amount': 10000000.0,
                            'currency_id': company.currency_id.id})
    new_records.append(alw)
    say('allowance set for %s: 10,000,000 %s', today.year,
        company.currency_id.name)
else:
    say('allowance for %s already set — left alone', today.year)

# ------------------------------------------------------------- 2. outside
Outside = env['pb.training.outside.course'].sudo()


def outside(name, **vals):
    rec = Outside.with_context(active_test=False).search(
        [('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if rec:
        return rec
    vals.update({'name': name, 'company_id': company.id,
                 'currency_id': company.currency_id.id})
    rec = Outside.create(vals)
    new_records.append(rec)
    return rec


# A DEMO job first (payobook also has a tester's own "… Agronomist").
agro_job = env['hr.job'].sudo().search([
    ('name', '=ilike', 'DEMO%agronomist%'),
    ('company_id', 'in', [company.id, False])], order='id', limit=1) or \
    env['hr.job'].sudo().search([
        ('name', 'ilike', 'agronomist'),
        ('company_id', 'in', [company.id, False])], order='id', limit=1)
licence = outside(
    'DEMO Pesticide applicator licence', provider='DEMO Southern Ag College',
    url='https://example.com/pesticide-licence', cost=3000000.0, hours=8.0,
    kind='exam', issues_certificate=True, validity_months=24,
    blurb='One day in the classroom and the state exam. Required before '
          'anybody signs off a spray plan.',
    job_ids=[(6, 0, agro_job.ids)])
soil = outside(
    'DEMO Soil science online', provider='DEMO Open Agronomy School',
    url='https://example.com/soil-science', cost=0.0, hours=6.0,
    kind='online', blurb='Six short video units on soil structure, testing '
                         'and what the numbers mean.')
first_aid = outside(
    'DEMO First aid at work', provider='DEMO Red Cross Training Centre',
    url='https://example.com/first-aid', cost=1200000.0, hours=7.0,
    kind='classroom', issues_certificate=True, validity_months=36,
    blurb='The one-day first-aid course for site first-aiders.')
say('outside courses: %s, %s, %s', licence.id, soil.id, first_aid.id)

# ------------------------------------------------------------- 3. skills
SkillType = env['hr.skill.type'].sudo()


def skill_type(name, levels, skills):
    rec = SkillType.search([('name', '=', name)], limit=1)
    if not rec:
        rec = SkillType.create({
            'name': name,
            'skill_level_ids': [(0, 0, {'name': n, 'level_progress': p})
                                for n, p in levels],
            'skill_ids': [(0, 0, {'name': s}) for s in skills]})
        new_records.append(rec)
    return rec


field_t = skill_type('DEMO Field skills',
                     [('DEMO Basic', 25), ('DEMO Good', 60),
                      ('DEMO Expert', 100)],
                     ['DEMO Field safety', 'DEMO Spraying', 'DEMO Soil testing'])
lead_t = skill_type('DEMO Leadership', [('DEMO Basic', 30), ('DEMO Good', 70)],
                    ['DEMO Running a shift', 'DEMO Coaching'])


def sk(stype, name):
    return stype.skill_ids.filtered(lambda s: s.name == name)[:1]


def lv(stype, name):
    return stype.skill_level_ids.filtered(lambda x: x.name == name)[:1]


safety, spraying, soil_t = (sk(field_t, 'DEMO Field safety'),
                            sk(field_t, 'DEMO Spraying'),
                            sk(field_t, 'DEMO Soil testing'))
shift, coaching = sk(lead_t, 'DEMO Running a shift'), sk(lead_t, 'DEMO Coaching')
Grant = env['pb.training.skill.grant'].sudo()


def grant(skill, level, **where):
    key = [(k, '=', v.id) for k, v in where.items()]
    if not Grant.search(key + [('skill_id', '=', skill.id)], limit=1):
        vals = {k: v.id for k, v in where.items()}
        vals.update({'skill_id': skill.id, 'skill_level_id': level.id,
                     'company_id': company.id})
        new_records.append(Grant.create(vals))


if course:
    grant(safety, lv(field_t, 'DEMO Basic'), channel_id=course)
grant(spraying, lv(field_t, 'DEMO Good'), outside_course_id=licence)
grant(soil_t, lv(field_t, 'DEMO Basic'), outside_course_id=soil)

# Only a DEMO job is given required skills; a missing one is made.
line_job = env['hr.job'].sudo().search([
    ('name', '=ilike', 'DEMO%line leader%'),
    ('company_id', 'in', [company.id, False])], limit=1)
if not line_job:
    line_job = env['hr.job'].sudo().create({'name': 'DEMO Line leader',
                                            'company_id': company.id})
    new_records.append(line_job)
JobSkill = env['hr.job.skill'].sudo()


def need(job, stype, skill, level):
    if job and not JobSkill.search([('job_id', '=', job.id),
                                    ('skill_id', '=', skill.id)], limit=1):
        new_records.append(JobSkill.create({
            'job_id': job.id, 'skill_id': skill.id,
            'skill_level_id': level.id, 'skill_type_id': stype.id}))


need(agro_job, field_t, safety, lv(field_t, 'DEMO Good'))
need(agro_job, field_t, spraying, lv(field_t, 'DEMO Basic'))
need(line_job, lead_t, shift, lv(lead_t, 'DEMO Good'))
need(line_job, lead_t, coaching, lv(lead_t, 'DEMO Basic'))
# People on those jobs: only people who have NO job yet are given one.
agro_people = pool.filtered(lambda e: e.job_id == agro_job) if agro_job \
    else Emp.browse()
spare = pool.filtered(lambda e: not e.job_id)
if agro_job and len(agro_people) < 4:
    for emp in spare[:4 - len(agro_people)]:
        emp.job_id = agro_job
    spare = pool.filtered(lambda e: not e.job_id)
    agro_people = pool.filtered(lambda e: e.job_id == agro_job)
line_people = pool.filtered(lambda e: e.job_id == line_job)
if len(line_people) < 2:
    for emp in spare[:2 - len(line_people)]:
        emp.job_id = line_job
    line_people = pool.filtered(lambda e: e.job_id == line_job)
EmpSkill = env['hr.employee.skill'].sudo()
for emp, skill, stype, level in (
        (agro_people[:1], safety, field_t, lv(field_t, 'DEMO Good')),
        (agro_people[1:2], safety, field_t, lv(field_t, 'DEMO Basic')),
        (line_people[:1], shift, lead_t, lv(lead_t, 'DEMO Basic'))):
    if emp and not emp.current_employee_skill_ids.filtered(
            lambda s, k=skill: s.skill_id == k):
        new_records.append(EmpSkill.create({
            'employee_id': emp.id, 'skill_id': skill.id,
            'skill_level_id': level.id, 'skill_type_id': stype.id,
            'valid_from': today - timedelta(days=60)}))
say('skills: agronomist job %s (%s people), line leader job %s (%s people)',
    agro_job.id, len(agro_people), line_job.id, len(line_people))

# ------------------------------------------------------------- 4. requests
Request = env['pb.training.request'].sudo()
field_emp = Emp.search([('user_id', '=', field_user.id)], limit=1) \
    if field_user else Emp.browse()
if field_emp and not Request.search([('employee_id', '=', field_emp.id),
                                     ('outside_course_id', '=', soil.id)]):
    res = env['pb.my.training'].with_user(field_user).with_context(
        allowed_company_ids=[company.id]).ask_course({
            'kind': 'outside', 'outside_course_id': soil.id,
            'when_words': 'DEMO next month, after the harvest',
            'why': 'DEMO I want to read the soil test results myself '
                   'instead of waiting for the lab.'})
    rec = Request.browse(res['id'])
    new_records.append(rec)
    say('request waiting: %s (%s) — %s', rec.id, rec.state, res['message'])
put_on = (pool - field_emp)[:1]
if hr_user and put_on and not Request.search(
        [('employee_id', '=', put_on.id),
         ('outside_course_id', '=', licence.id)]):
    board = env['pb.training'].with_user(hr_user).with_context(
        allowed_company_ids=[company.id])
    try:
        res = board.put_on_outside({
            'outside_course_id': licence.id, 'employee_ids': put_on.ids,
            'why': 'DEMO the licence is needed before the spraying season.'})
        rec = Request.search([('employee_id', '=', put_on.id),
                              ('outside_course_id', '=', licence.id)],
                             limit=1)
        new_records.append(rec)
        say('request agreed by the training team: %s (%s) — %s', rec.id,
            rec.state, res['message'])
    except Exception as err:            # noqa: BLE001 — say it, carry on
        say('putting %s on the licence failed: %s', put_on.name, err)

# ------------------------------------------------------------- 5. version
# NOT course 27 (coordinator, 2026-10-22): every online course with
# finishers on payobook is a step of an L3 learning path, and a re-read
# would reopen that step for the people on the path. So a small course of
# its own — "DEMO Safe chemical storage", online, on no path, no session —
# is made here, three demo people finish it, and it is published as v2.
Channel = env['slide.channel'].sudo()
storage = Channel.search([('name', '=', 'DEMO Safe chemical storage')],
                         limit=1)
if not storage:
    storage = Channel.create({
        'name': 'DEMO Safe chemical storage', 'channel_type': 'training',
        'visibility': 'members', 'enroll': 'invite',
        'completed_template_id': False, 'is_published': True,
        'user_id': hr_user.id or env.uid})
    for i, (title, body) in enumerate((
            ('DEMO The store room rules', 'Locked, labelled, ventilated.'),
            ('DEMO Spills and first steps', 'Kit, gloves, tell the lead.'))):
        env['slide.slide'].sudo().create({
            'name': title, 'channel_id': storage.id,
            'slide_category': 'article', 'is_published': True,
            'html_content': '<p>%s</p>' % body, 'sequence': i + 1,
            'completion_time': 0.25})
    new_records.append(storage)
    if hr_user and hr_user.partner_id:
        storage._remove_membership(hr_user.partner_id.ids)   # LN46
storage.pb_requestable = True
on_path = env['pb.training.path.step'].sudo().search_count(
    [('channel_id', '=', storage.id)])
say('version course %s "%s" (on %s path steps, delivery %s)', storage.id,
    storage.name, on_path, storage.delivery)
if (storage.pb_version or 1) < 2:
    Assignment = env['pb.training.assignment'].sudo().with_context(
        pb_training_no_announce=True)
    finishers = pool.filtered(lambda e: e.user_id)[:3]
    for emp in finishers:
        if not Assignment.search_count([('channel_id', '=', storage.id),
                                        ('employee_id', '=', emp.id)]):
            row = Assignment.create({'channel_id': storage.id,
                                     'employee_id': emp.id,
                                     'reason': 'adhoc',
                                     'company_id': company.id})
            new_records.append(row)
        me = env['pb.my.training'].with_user(emp.user_id).with_context(
            allowed_company_ids=[company.id])
        for slide in storage._pb_lessons():
            me.mark_done(storage.id, slide.id)
    Assignment.search([('channel_id', '=', storage.id)])._refresh()
    done = Assignment.search_count([('channel_id', '=', storage.id),
                                    ('state', '=', 'done')])
    say('course %s: %s demo people finished it', storage.id, done)
    if hr_user:
        res = env['pb.training'].with_user(hr_user).with_context(
            allowed_company_ids=[company.id]).publish_version(
                storage.id, 'DEMO the store room now needs a second '
                            'extinguisher by the door.', 14)
        say('course %s: %s', storage.id, res['message'])
        new_records += list(Assignment.search(
            [('channel_id', '=', storage.id), ('reason', '=', 'reread')]))
else:
    say('course %s already at version %s — left alone', storage.id,
        storage.pb_version)

# ------------------------------------------------------------- 6. drawn test
Survey = env['survey.survey'].sudo()
quiz = Survey.search([('title', '=', 'DEMO Field safety quiz')], limit=1)
if not quiz and hr_user:
    res = env['pb.training'].with_user(hr_user).create_test(
        {'name': 'DEMO Field safety quiz', 'pass_mark': 60, 'attempts': 3,
         'draw': 5})
    quiz = Survey.browse(res['id'])
    page = quiz.page_ids[:1]
    questions = [
        ('Where is the spill kit kept on a spray rig?', 'In the cab box',
         'At the depot'),
        ('How far is the buffer from a water course?', '10 metres',
         '1 metre'),
        ('What do you wear to mix concentrate?', 'Gloves, apron, face shield',
         'Overalls only'),
        ('When do you stop spraying?', 'Wind above 15 km/h', 'At lunch'),
        ('Who signs off a spray plan?', 'A licensed applicator',
         'Anybody on site'),
        ('Where do empty containers go?', 'The triple-rinse station',
         'The general bin'),
        ('What is re-entry time?', 'The wait before people go back in',
         'The drive back to the depot'),
        ('Who do you tell about a splash?', 'The site first-aider',
         'Nobody'),
    ]
    for i, (title, right, wrong) in enumerate(questions):
        env['survey.question'].sudo().create({
            'survey_id': quiz.id, 'title': 'DEMO ' + title,
            'sequence': (page.sequence or 1) + 1 + i,
            'question_type': 'simple_choice',
            'suggested_answer_ids': [
                (0, 0, {'value': right, 'is_correct': True,
                        'answer_score': 1}),
                (0, 0, {'value': wrong, 'answer_score': 0})]})
    new_records.append(quiz)
say('test %s: %s', quiz.id, env['pb.training'].sudo()._pool_words(quiz)
    if quiz else '-')

# ------------------------------------------------------------- 7. feedback
Feedback = env['pb.feedback.request'].sudo()
if course:
    have = Feedback.search_count([('kind', '=', 'training'),
                                  ('channel_id', '=', course.id),
                                  ('state', '=', 'submitted')])
    answers = [(5, 5, 'DEMO More pictures of the real rigs, please.'),
               (4, 4, 'DEMO The soil section was the most useful.'),
               (4, 5, ''), (5, 5, 'DEMO Shorter videos would help on a phone.'),
               (3, 3, 'DEMO Too much reading for a field course.'),
               (4, 4, '')]
    for emp, (useful, rec_, text) in zip(pool[:6], answers[have:]):
        req = Feedback.create({
            'subject_employee_id': emp.id, 'respondent_user_id': emp.user_id.id,
            'respondent_email': emp.user_id.email or '', 'kind': 'training',
            'window_end': today + timedelta(days=14),
            'questions_json': json.dumps([
                {'key': 'useful', 'label': 'Was it useful?', 'type': 'rating'},
                {'key': 'recommend', 'label': 'Would you recommend it?',
                 'type': 'rating'},
                {'key': 'change', 'label': 'What would you change?',
                 'type': 'text'}]),
            'channel_id': course.id, 'company_id': company.id})
        req.submit_answers({'useful': {'value': str(useful)},
                            'recommend': {'value': str(rec_)},
                            'change': {'value': text}})
        new_records.append(req)
    manager_emp = Emp.search([('user_id', '=', manager_user.id)], limit=1) \
        if manager_user else Emp.browse()
    Followup = env['pb.training.followup'].sudo()
    done_fu = Followup.search_count([('channel_id', '=', course.id),
                                     ('state', '=', 'answered')])
    reports = pool.filtered(lambda e: e.parent_id == manager_emp)[:2] \
        if manager_emp else Emp.browse()
    for emp, (effect, used) in list(zip(reports, [(4, 'Yes'),
                                                  (3, 'Partly')]))[done_fu:]:
        fu = Followup.create({
            'channel_id': course.id, 'employee_id': emp.id,
            'manager_id': manager_emp.id, 'due_date': today,
            'state': 'sent', 'company_id': company.id})
        req = Feedback.create({
            'subject_employee_id': emp.id,
            'respondent_user_id': manager_user.id,
            'respondent_email': manager_user.email or '',
            'kind': 'training_followup', 'window_end': today + timedelta(
                days=14),
            'questions_json': json.dumps([
                {'key': 'effect', 'label': 'Has their work changed since the '
                 'course?', 'type': 'rating'},
                {'key': 'used', 'label': 'Did they use what they learned?',
                 'type': 'choice', 'options': ['Yes', 'Partly', 'No']},
                {'key': 'note', 'label': 'Anything to add?', 'type': 'text'}]),
            'channel_id': course.id, 'followup_id': fu.id,
            'company_id': company.id})
        fu.feedback_request_id = req.id
        req.submit_answers({'effect': {'value': str(effect)},
                            'used': {'value': used},
                            'note': {'value': 'DEMO fewer spray-plan '
                                              'mistakes since.'}})
        new_records += [fu, req]
    extras = env['pb.training'].sudo().course_extras(course.id)
    say('course %s ratings: %s · follow-ups answered %s, work changed %s/5',
        course.id, extras['rating_words'],
        extras['ratings']['followups_answered'],
        extras['ratings']['effect_avg'])

# ------------------------------------------------------------- register, mail
if seed is not None:
    for rec in new_records:
        try:
            seed.register(rec, LABEL)
        except Exception as err:        # noqa: BLE001 — say it, carry on
            say('could not register %s: %s', rec, err)
    say('registered %s record(s) on the demo register', len(new_records))
board = env['pb.training'].sudo()
skills = board.with_user(hr_user).with_context(
    allowed_company_ids=[company.id]).skills_board({}) if hr_user else {}
say('skills board: %s', skills.get('headline', '-'))
say('requests board: %s', board.with_user(hr_user).with_context(
    allowed_company_ids=[company.id]).requests_board({}).get('headline')
    if hr_user else '-')
with env.cr.savepoint(flush=True) as sp:
    Auto = env['pb.training.automation']
    say('morning legs (rolled back): %s re-read(s), %s follow-up(s) sent',
        Auto._rereads(), Auto._send_followups(today))
    sp.rollback()
queued = env['mail.mail'].sudo().search([('state', '=', 'outgoing')],
                                        order='id desc', limit=500).filtered(
    lambda m: m.id > mails_last)
queued.write({'state': 'cancel'})
say('mail queued by this run and cancelled: %s', len(queued))
env.cr.commit()
say('done')
