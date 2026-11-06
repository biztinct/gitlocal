# -*- coding: utf-8 -*-
"""Three stories in flight: a joiner, a trial period, a performance plan.

MID-FLIGHT IS THE WHOLE POINT. A finished workflow shows a screen; a running one
shows a decision somebody has to make. So the laptop is approved and not yet
handed over, two of four colleagues have answered and two have not, and one
objective on the performance plan is at risk while the rest are on track. Every
one of those is a place the person giving the demo can click.

THE DATES ARE RELATIVE TO THE DAY IT IS LOADED. A demo loaded in March and shown
in June with "trial period ends 14 March" in it is worse than no demo. Nothing
here carries a fixed date.

WHERE THE PRODUCT HAS AN ACTION, THE ACTION IS CALLED. Opening a journey
generates its checklist from the template; writing the tasks by hand here would
produce a checklist that does not match the one a real joiner gets, and the
difference would only surface in front of a customer.
"""

import json
import logging
from datetime import timedelta

from odoo import fields

_logger = logging.getLogger(__name__)


def build(ctx):
    _onboarding(ctx)
    _probation(ctx)
    _pip(ctx)


# ======================================================================
#  Day three
# ======================================================================
def _onboarding(ctx):
    people = ctx.get('people', {})
    joiner = people.get('joiner')
    manager = people.get('manager')
    buddy = people.get('pip')          # two years in, out of probation, eligible
    if not joiner:
        return

    joined = ctx.days(-3)
    template = _template(ctx, 'onboarding')

    # OPENING THE CHECKLIST IS NOT JUST OPENING THE CHECKLIST. `action_open()`
    # generates the steps AND assigns the HR partner, puts the 30-60-90
    # conversations in the diary, enrols the joiner in the next welcome session,
    # schedules the three one-tap checks and raises the asset requests the
    # checklist's own steps call for.
    #
    # WE LET IT. Writing those by hand here would produce a joiner whose journey
    # differs from a real one's in ways nobody would notice until a customer
    # asked why. It would also fight the product: the pulses carry a uniqueness
    # rule on (person, day, checklist), and the first version of this file
    # created a duplicate and stopped the load dead.
    #
    # What it costs is that the records are made by the product and not by
    # `ctx.create`, so they are not in the register. `mark` + `adopt_since` is
    # the answer: take an id watermark first, adopt whatever appeared after.
    marks = ctx.mark('pb.employee.checkin', 'pb.newhire.pulse',
                     'pb.orientation.batch', 'pb.asset.request')

    case = ctx.create('pb.journey.case', {
        'employee_id': joiner.id,
        'case_type': 'onboarding',
        'template_id': template.id if template else False,
        'anchor_date': joined,
        'state': 'draft',
        'source': 'manual',
        'note': 'Demo joining checklist.',
    }, label='Joining checklist — %s' % joiner.name)
    if template:
        case.sudo().action_open()
    else:
        case.sudo().state = 'active'

    for model_name in ('pb.employee.checkin', 'pb.newhire.pulse',
                       'pb.orientation.batch', 'pb.asset.request'):
        ctx.adopt_since(marks, model_name)

    _close_the_first_few_steps(ctx, case)
    _the_seven_day_check_has_gone_out(ctx, case)
    _the_laptop_is_halfway(ctx, case, joiner, manager)

    if buddy:
        ctx.create('pb.buddy.nomination', {
            'employee_id': joiner.id,
            'case_id': case.id,
            'manager_user_id': ctx.env.user.id,
            'candidate_ids': [(6, 0, [p.id for k, p in people.items()
                                      if k in ('pip', 'probation')])],
            'chosen_id': buddy.id,
            'state': 'confirmed',
            'eligibility_json': json.dumps({
                'tenure_months_ok': True, 'not_contractor': True,
                'out_of_probation': True, 'same_location': True,
            }),
        }, label='Buddy for %s' % joiner.name)
        if 'buddy_id' in joiner._fields:
            joiner.sudo().buddy_id = buddy.id
    if 'hrbp_user_id' in joiner._fields and not joiner.hrbp_user_id:
        joiner.sudo().hrbp_user_id = ctx.env.user.id
    if 'onboarding_case_id' in joiner._fields:
        joiner.sudo().onboarding_case_id = case.id

    # A buddy connect that has already happened, so the buddy story has a
    # history and not only a plan.
    ctx.create('pb.employee.checkin', {
        'employee_id': joiner.id,
        'case_id': case.id,
        'kind': 'buddy',
        'owner_user_id': ctx.env.user.id,
        'scheduled_date': ctx.days(-1),
        'state': 'done',
        'notes': 'First buddy call. Settling in, knows where everything is, '
                 'waiting on the laptop.',
    }, label='Buddy connect — %s' % joiner.name)

    # Trial period. Two months is the Vietnam policy on this database.
    _start_trial(ctx, joiner, ctx.days(57))

    # The training the requirements sheet gates probation clearance on.
    _agronomist_training(ctx, joiner)

    if manager:
        ctx.create('pb.employee.checkin', {
            'employee_id': joiner.id,
            'case_id': case.id,
            'kind': 'other',
            'owner_user_id': ctx.env.user.id,
            'scheduled_date': joined,
            'state': 'done',
            'notes': 'Day-one call with the manager. Introductions, first '
                     'fortnight, who to ask for what.',
        }, label='Day-one call — %s' % joiner.name)


def _the_seven_day_check_has_gone_out(ctx, case):
    """Three days in, the first one-tap check is already with them.

    The product plans all three as "planned". Moving the first one to "sent"
    is the difference between a screen that shows a plan and a screen that
    shows something happening.
    """
    for pulse in ctx.env['pb.newhire.pulse'].sudo().search(
            [('case_id', '=', case.id), ('day_mark', '=', '7')]):
        pulse.sudo().write({'state': 'sent',
                            'sent_at': fields.Datetime.now()})


def _the_laptop_is_halfway(ctx, case, joiner, manager):
    """Spare found, manager has agreed, nothing handed over yet.

    This is the step the asset requirements make the most of — check the
    spares BEFORE buying — so the demo stops exactly there, with a spare
    proposed and a button that hands it over.
    """
    laptop = ctx.env.ref('pb_assets.cat_laptop', raise_if_not_found=False)
    requests = ctx.env['pb.asset.request'].sudo().search(
        [('employee_id', '=', joiner.id)])
    spare = ctx.env['pb.asset'].sudo().search([
        ('state', '=', 'spare'),
        ('category_id', '=', laptop.id if laptop else -1),
    ], limit=1)
    for request in requests:
        values = {'manager_id': manager.id if manager else False,
                  'needed_by': ctx.days(4)}
        if laptop and request.category_id == laptop:
            values.update({
                'state': 'manager_approved',
                'fulfilment': 'spare',
                'justification': 'Laptop for a new agronomist. Field work, so '
                                 'the rugged model if one is spare.',
            })
            if spare:
                values['spare_asset_id'] = spare.id
        request.sudo().write(values)


def _close_the_first_few_steps(ctx, case):
    """Three days in, the first steps are done and the rest are not.

    Done by DATE rather than by counting: whatever the template contains, the
    steps whose day has already passed are the ones that should be closed, and
    a template that grows a step tomorrow still produces a sensible picture.
    """
    for task in case.sudo().task_ids:
        if task.due_date and task.due_date < ctx.today:
            task.sudo().write({
                'state': 'done',
                'done_by': ctx.env.user.id,
                'done_at': fields.Datetime.now(),
            })


# ======================================================================
#  Eighteen days to go
# ======================================================================
def _probation(ctx):
    people = ctx.get('people', {})
    subject = people.get('probation')
    manager = people.get('manager')
    if not subject:
        return

    trial_end = ctx.days(18)
    _start_trial(ctx, subject, trial_end)

    policy = ctx.env['pb.probation.policy'].sudo().search(
        [('country_id', '=', ctx.company.country_id.id)], limit=1)
    if not policy:
        policy = ctx.env['pb.probation.policy'].sudo().search(
            [('country_id', '=', False)], limit=1)

    peers = [p for key, p in people.items()
             if key not in ('probation',)][:4]
    review = ctx.create('pb.probation.review', {
        'employee_id': subject.id,
        'kind': 'probation',
        'round': 1,
        'trial_end': trial_end,
        'manager_user_id': ctx.env.user.id,
        'hrbp_user_id': ctx.env.user.id,
        'policy_id': policy.id if policy else False,
        'state': 'feedback',
        'nominee_ids': [(6, 0, [p.id for p in peers])],
        # Two days left. Close enough that the "answers are due" nudge is the
        # honest state of it, far enough that it is not already overdue.
        'feedback_deadline': ctx.days(2),
    }, label='Probation review — %s' % subject.name)

    answers = [
        {'quality': 4, 'reliability': 4, 'teamwork': 5, 'learning': 4,
         'strengths': 'Runs the morning briefing well and the crews listen to '
                      'him. Good with the seasonal casuals.',
         'improve': 'Paperwork. Timesheets come in late most weeks.'},
        {'quality': 4, 'reliability': 3, 'teamwork': 4, 'learning': 5,
         'strengths': 'Picked up the spray schedule faster than anybody '
                      'expected and now trains others on it.',
         'improve': 'Would like him to flag problems earlier rather than '
                    'trying to fix everything himself first.'},
    ]
    from odoo.addons.pb_probation.models.probation_common import PEER_QUESTIONS
    questions = json.dumps(PEER_QUESTIONS)
    for index, peer in enumerate(peers):
        answered = index < len(answers)
        ctx.create('pb.feedback.request', {
            'subject_employee_id': subject.id,
            'respondent_user_id': ctx.env.user.id,
            'kind': 'probation_peer',
            'probation_review_id': review.id,
            'window_end': ctx.days(2),
            'state': 'submitted' if answered else 'sent',
            'questions_json': questions,
            'answers_json': json.dumps(answers[index]) if answered else False,
            'submitted_at': fields.Datetime.now() if answered else False,
        }, label='Peer feedback on %s — from %s' % (subject.name, peer.name))

    if manager:
        ctx.create('pb.employee.checkin', {
            'employee_id': subject.id,
            'kind': 'probation',
            'owner_user_id': ctx.env.user.id,
            'scheduled_date': ctx.days(6),
            'state': 'scheduled',
            'notes': 'Confirmation conversation once the colleagues have '
                     'answered.',
        }, label='Probation 1:1 — %s' % subject.name)


# ======================================================================
#  Week five of six
# ======================================================================
def _pip(ctx):
    people = ctx.get('people', {})
    subject = people.get('pip')
    manager = people.get('manager')
    if not subject:
        return

    template = ctx.env['pb.pip.template'].sudo().search([], limit=1)
    start = ctx.days(-28)
    case = ctx.create('pb.pip.case', {
        'employee_id': subject.id,
        'requested_by_user_id': ctx.env.user.id,
        'hr_owner_user_id': ctx.env.user.id,
        'template_id': template.id if template else False,
        'reason_text': 'Three quarters below target and two accounts lost at '
                       'renewal. The manager asked for support rather than a '
                       'conversation about leaving.',
        'state': 'active',
        'coaching_note': 'Two coaching sessions before the plan started. Agreed '
                         'the problem is pipeline discipline rather than '
                         'product knowledge: deals are worked late and renewals '
                         'are left until the month they fall due.',
        'coaching_start': ctx.days(-42),
        'coaching_end': ctx.days(-30),
        'weeks': 6,
        'checkin_freq': 'weekly',
        'start_date': start,
        'end_date': ctx.days(14),
        'employee_ack': True,
        'ack_at': fields.Datetime.now(),
    }, label='Performance plan — %s' % subject.name)

    objectives = [
        ('Build and keep a pipeline worth three times the quarterly target',
         'Pipeline value on the last working day of each week', '3x target',
         2, 'on_track'),
        ('Start every renewal conversation ninety days before the date',
         'Renewals with a logged conversation before the ninety-day mark',
         '100%', 2, 'at_risk'),
        ('Log every customer visit the same day',
         'Visits logged within twenty-four hours', '95%', 1, 'met'),
    ]
    for sequence, (name, metric, target, weight, status) in enumerate(objectives):
        ctx.create('pb.pip.objective', {
            'case_id': case.id,
            'employee_id': subject.id,
            'name': name,
            'metric': metric,
            'target': target,
            'weight': weight,
            'status': status,
            'sequence': (sequence + 1) * 10,
        }, label='Objective — %s' % name[:60])

    # Four weeks of check-ins behind, two ahead.
    for week in range(1, 7):
        held = week <= 4
        ctx.create('pb.employee.checkin', {
            'employee_id': subject.id,
            'kind': 'pip',
            'pip_case_id': case.id,
            'owner_user_id': ctx.env.user.id,
            'scheduled_date': start + _weeks(week),
            'state': 'done' if held else 'scheduled',
            'notes': _PIP_NOTES.get(week) if held else False,
            'red_flag': week == 3,
            'red_flag_note': ('Renewals still being started inside ninety days.'
                              if week == 3 else False),
        }, label='Plan check-in week %s — %s' % (week, subject.name))

    if manager:
        ctx.create('pb.feedback.request', {
            'subject_employee_id': subject.id,
            'respondent_user_id': ctx.env.user.id,
            'kind': 'pip',
            'pip_case_id': case.id,
            'window_end': ctx.days(19),
            'state': 'sent',
        }, label='Plan evaluation — %s' % subject.name)


_PIP_NOTES = {
    1: 'Plan walked through line by line. She agrees with the pipeline point '
       'and pushed back on the visit logging, fairly.',
    2: 'Pipeline up by a third. Renewals untouched.',
    3: 'Two renewals inside ninety days again. Flagged.',
    4: 'Both outstanding renewals now have a date in the diary. Visit logging '
       'has held all month.',
}


# ======================================================================
#  Shared
# ======================================================================
def _weeks(count):
    return timedelta(days=7 * count)


def _next_weekday(day):
    """Push a Saturday or Sunday forward to the Monday."""
    while day.weekday() >= 5:
        day = day + timedelta(days=1)
    return day


def _template(ctx, case_type):
    """The richest checklist of this kind on the database.

    Richest rather than first: a demo wants the full welcome, and picking by
    step count means it keeps working if somebody renames the templates.
    """
    templates = ctx.env['pb.journey.template'].sudo().search(
        [('case_type', '=', case_type)])
    if not templates:
        return None
    return max(templates, key=lambda t: len(t.step_ids))


def _start_trial(ctx, employee, ends_on):
    """Put somebody in their trial period, on the fields the product reads."""
    values = {}
    if 'trial_date_end' in employee._fields:
        values['trial_date_end'] = ends_on
    if 'pb_probation_state' in employee._fields:
        values['pb_probation_state'] = 'in_probation'
    if values:
        employee.sudo().write(values)


def _agronomist_training(ctx, employee):
    """The course that has to be finished before a trial period can be closed.

    The track and its items are the customer's configuration, not ours, so only
    the per-person STATUS rows are created — and only those are removed later.
    """
    track = ctx.env['pb.training.track'].sudo().search([], limit=1)
    if not track or not track.item_ids:
        return
    for index, item in enumerate(track.item_ids):
        done = index == 0
        ctx.create('pb.training.status', {
            'employee_id': employee.id,
            'item_id': item.id,
            'state': 'done' if done else 'todo',
            'score': 82.0 if done else 0.0,
            'done_at': ctx.days(-1) if done else False,
        }, label='Training — %s' % (item.name or '')[:60])
