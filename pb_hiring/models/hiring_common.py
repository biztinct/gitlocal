# -*- coding: utf-8 -*-
"""The words, the dials and the two helpers every file here needs.

WHY A COMMON FILE AT ALL. Six models, a facade, a portal controller and a
daily job all need the same three things: the group names, the switches with
their defaults, and the two helpers that stop a sentence reading like a
machine wrote it. Copied around they drift; a plural that says "1 role(s)"
in one place and "1 role" in another is worse than either on its own (R46).
"""

import logging
import unicodedata

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------- the tiers
GROUP_USER = 'pb_hiring.group_hiring_user'
GROUP_MANAGER = 'pb_hiring.group_hiring_manager'
GROUP_ADMIN = 'pb_hiring.group_hiring_admin'
ALL_GROUPS = (GROUP_USER, GROUP_MANAGER, GROUP_ADMIN)

# --------------------------------------------------------------- the dials
#: Every switch defaults IN CODE. A `noupdate="1"` record for a switch freezes
#: whatever value a test run happened to leave behind, because the next
#: upgrade never corrects it (the reason P3-P5 all kept their switches out of
#: the data file). The data file ships only the NUMBERS, which are dials
#: somebody tunes rather than switches somebody flips.
P_PLATFORM_MAIL = 'pb_hiring.platform_mail'
P_REFERRAL_AUTO = 'pb_hiring.referral_auto'
P_NOTIFY_MAIL = 'pb_hiring.notify_mail'
P_REFERRAL_MAIL = 'pb_hiring.referral_mail'
P_JD_REMINDER_DAYS = 'pb_hiring.jd_reminder_days'
P_RECRUITER_NUDGE_DAYS = 'pb_hiring.recruiter_nudge_days'

# ------------------------------------------------- A2, the interview loop
P_REMINDERS = 'pb_hiring.reminders'
P_CANDIDATE_MAIL = 'pb_hiring.candidate_mail'
P_FEEDBACK_HOURS = 'pb_hiring.feedback_hours'
P_URGENT_AFTER_HOURS = 'pb_hiring.urgent_after_hours'
P_INTERVIEW_DURATION = 'pb_hiring.interview_duration'
P_REMINDER_CAP = 'pb_hiring.reminder_cap'

# --------------------------------------------- A3, the offer and the closure
P_DOC_DEADLINE_DAYS = 'pb_hiring.doc_deadline_days'
P_DOC_REMINDER_DAYS = 'pb_hiring.doc_reminder_days'
P_OFFER_MAIL = 'pb_hiring.offer_mail'
P_CLOSURE_MAIL = 'pb_hiring.closure_mail'
P_CREATE_CONTRACT = 'pb_hiring.create_contract'

DEFAULTS = {
    # OFF. An advert that leaves the building the first time somebody presses
    # a button is an advert nobody agreed to send. The pack is built either
    # way and a human pushes it.
    P_PLATFORM_MAIL: '0',
    P_REFERRAL_AUTO: '1',
    P_NOTIFY_MAIL: '1',
    P_REFERRAL_MAIL: '1',
    P_JD_REMINDER_DAYS: '3',
    P_RECRUITER_NUDGE_DAYS: '3',
    # ON. A candidate who is not told where to be at ten o'clock is a
    # candidate who does not come, and the whole point of an invitation is
    # that it leaves the building.
    P_REMINDERS: '1',
    P_CANDIDATE_MAIL: '1',
    P_FEEDBACK_HOURS: '24',
    # Zero: the nudge goes at the moment the opinion is late, not a day
    # after it. A panel member who is asked a week later has forgotten.
    P_URGENT_AFTER_HOURS: '0',
    P_INTERVIEW_DURATION: '45',
    # A cap that is right for a SCREEN is a bug in a CRON (R76), so the jobs
    # carry their own and it is a dial rather than a literal.
    P_REMINDER_CAP: '400',
    # A3. Two days is what the sheet asks for, and it is counted in WORKING
    # days on the company's own calendar for the same reason the feedback
    # window is (R149): a request sent on a Friday afternoon that wanted an
    # answer by Sunday would be a deadline nobody could meet.
    P_DOC_DEADLINE_DAYS: '2',
    P_DOC_REMINDER_DAYS: '1',
    # ON. An offer that is agreed and never sent is the single most expensive
    # thing that can go wrong here, so the mail leaves by default and the
    # switch exists for a business that sends offers by hand.
    P_OFFER_MAIL: '1',
    P_CLOSURE_MAIL: '1',
    # ON. The contract is what gives a joiner a joining date, and without one
    # they have no anniversary, no probation clock and no row in the joiner
    # digest. Off, the closure still makes the employee and says in the log
    # and on the record that the contract was not written.
    P_CREATE_CONTRACT: '1',
}

# ------------------------------------------------------------- the choices
ROLE_TYPES = [
    ('new_role', 'A role that did not exist before'),
    ('growth', 'One more of a role we already have'),
    ('replacement', 'Replacing somebody who has left'),
    ('sensitive_replacement', 'Replacing somebody quietly'),
]

#: The one role type that must never open itself to referrals: the person
#: being replaced is usually still at their desk.
SENSITIVE_TYPES = ('sensitive_replacement',)

REQUISITION_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Sent in'),
    ('manager_ok', 'Manager agreed'),
    ('hr_ok', 'HR agreed'),
    ('open', 'Open for candidates'),
    ('filled', 'Filled'),
    ('closed', 'Closed'),
    ('refused', 'Not approved'),
]

#: The statuses after which nothing is still being asked for.
REQUISITION_LIVE = ('draft', 'submitted', 'manager_ok', 'hr_ok', 'open')

BUDGET_STATUS = [
    ('unknown', 'No budget set'),
    ('within', 'Within budget'),
    ('over', 'Over budget'),
]

JD_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Sent for agreement'),
    ('approved', 'Agreed'),
    ('refused', 'Not agreed'),
]

STEP_KINDS = [
    ('screen', 'A first look at the CV'),
    ('call', 'A phone call'),
    ('interview', 'An interview'),
    ('test', 'A test or an exercise'),
    ('panel', 'A panel'),
    ('final', 'The final conversation'),
    ('other', 'Something else'),
]

REFERRAL_STATES = [
    ('received', 'Received'),
    ('in_progress', 'Being looked at'),
    ('hired', 'Joined us'),
    ('not_this_time', 'Not this time'),
]

POSTING_STATES = [
    ('ready', 'Ready to send'),
    ('sent', 'Sent'),
]

SCREEN_TAGS = [
    ('shortlisted', 'Shortlisted'),
    ('rejected', 'Not this time'),
    ('future_fit', 'Worth keeping in touch with'),
    ('other_role', 'Better suited to another role'),
]

# ==========================================================================
#  A2 — the interview loop
# ==========================================================================
INTERVIEW_STATES = [
    ('scheduled', 'Arranged'),
    ('done', 'Done'),
    ('no_show', 'Nobody came'),
    ('cancelled', 'Called off'),
    ('rescheduled', 'Moved'),
]

#: The statuses in which an interview is still going to happen.
INTERVIEW_LIVE = ('scheduled',)

INTERVIEW_MODES = [
    ('in_person', 'In person'),
    ('video', 'On a video call'),
    ('phone', 'On the phone'),
]

NO_SHOW_BY = [
    ('candidate', 'The candidate did not come'),
    ('interviewer', 'Somebody on our side did not come'),
]

#: Whose fault a move is. It is not a blame column — it is the only way a
#: company can ever answer "are we the reason our hiring takes eleven weeks".
DELAY_KINDS = [
    ('internal', 'Our side moved it'),
    ('external', 'The candidate moved it'),
]

FEEDBACK_STATES = [
    ('pending', 'Waiting'),
    ('submitted', 'In'),
    ('expired', 'Closed'),
]

#: Ordered worst to best, so a mean of the stored numbers is meaningful.
RECOMMENDATIONS = [
    ('strong_no', 'Strong no'),
    ('no', 'No'),
    ('yes', 'Yes'),
    ('strong_yes', 'Strong yes'),
]

RECOMMENDATION_SCORE = {'strong_no': 1, 'no': 2, 'yes': 3, 'strong_yes': 4}

DEBRIEF_DECISIONS = [
    ('select', 'We want them'),
    ('hold', 'Keep them warm'),
    ('reject', 'Not this time'),
]

#: The kinds of stage after which a debrief and a decision make sense. A
#: debrief on round one is a decision taken before the process has run.
FINAL_KINDS = ('final', 'panel')


# ==========================================================================
#  A3 — the background check, the documents, the offer, the cover
# ==========================================================================
BGV_STATES = [
    ('open', 'Being checked'),
    ('complete', 'All clear'),
    ('flagged', 'Something came back'),
]

#: A result is an ANSWER and `pending` is the absence of one. "Does not
#: apply" is a real answer and is deliberately separate from "clear": a
#: candidate with no previous employer has not been checked and cleared, and
#: a checklist that pretended otherwise would be a checklist nobody trusts.
BGV_RESULTS = [
    ('pending', 'Not looked at yet'),
    ('ok', 'Clear'),
    ('flag', 'Came back with something'),
    ('na', 'Does not apply'),
]

DOCREQ_STATES = [
    ('sent', 'Asked for'),
    ('partial', 'Some are in'),
    ('complete', 'Everything is in'),
    ('expired', 'Past the date'),
]

#: draft → submitted → manager_ok → hr_ok → sent → accepted|declined →
#: signed → closed, plus the route's own dead end.
OFFER_STATES = [
    ('draft', 'Being prepared'),
    ('submitted', 'Sent for sign-off'),
    ('manager_ok', 'Hiring manager agreed'),
    ('hr_ok', 'Agreed'),
    ('sent', 'With the candidate'),
    ('accepted', 'Accepted'),
    ('declined', 'Turned down'),
    ('signed', 'Signed'),
    ('closed', 'They have joined'),
    ('refused', 'Not approved'),
]

#: The statuses in which an offer is still a live piece of work.
OFFER_LIVE = ('draft', 'submitted', 'manager_ok', 'hr_ok', 'sent', 'accepted',
              'signed')

CANDIDATE_DECISIONS = [
    ('pending', 'Waiting to hear'),
    ('accepted', 'Accepted'),
    ('declined', 'Turned it down'),
]

#: What a line of an offer IS. The same five words the pay package uses, so
#: the package the offer becomes at closure reads as the same document.
OFFER_KINDS = [
    ('earning', 'Pay'),
    ('statutory', 'Statutory contribution'),
    ('benefit', 'Benefit'),
    ('perquisite', 'Perk'),
    ('bonus', 'Variable'),
]

OFFER_PERIODS = [
    ('monthly', 'Every month'),
    ('yearly', 'Once a year'),
    ('one_time', 'One-off'),
]

#: WHAT ONE YEAR OF A LINE IS WORTH, and it is deliberately NOT the pay
#: package's table. `pb.employee.comp` scores a one-off at ZERO, which is
#: right for "what is this person paid every year" and wrong for an offer: a
#: sign-on bonus is real money in the first year and it is the number a
#: candidate weighs the offer on. So a one-off counts once here, and the
#: package the closure creates keeps comp's own arithmetic — the two answer
#: different questions and both are honest about which.
OFFER_PERIOD_YEAR = {'monthly': 12.0, 'yearly': 1.0, 'one_time': 1.0}

#: What ONE MONTH of a line is worth. Only a monthly line has a monthly
#: figure: dividing a yearly bonus by twelve would put money on a payslip
#: that is not paid in that month.
OFFER_PERIOD_MONTH = {'monthly': 1.0, 'yearly': 0.0, 'one_time': 0.0}

COVER_STATES = [
    ('draft', 'Being written'),
    ('submitted', 'Sent in'),
    ('approved', 'Agreed'),
    ('active', 'Covering now'),
    ('ended', 'Finished'),
    ('refused', 'Not agreed'),
]

#: A cover that is agreed or running is one that can stand in for somebody.
COVER_LIVE = ('approved', 'active')

#: The letter type this module adds to the shared letter library.
OFFER_LETTER_TYPE = 'offer'

#: What the candidate may send us, and nothing else. A public upload form is
#: the widest door in the product and it takes documents and pictures only.
UPLOAD_MIME_OK = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
}

#: Five megabytes. A phone photograph of a passport is about two.
UPLOAD_MAX_BYTES = 5 * 1024 * 1024


# ------------------------------------------------------------- the helpers
def leg(env, label, fn):
    """One piece of paperwork, inside its own SAVEPOINT (R131).

    The record-scoped twin of `pb.hiring.requisition._leg`, for the models
    and the jobs that are not a requisition. A try/except IS NOT ENOUGH when
    the thing that failed reached the database: Postgres aborts the whole
    transaction and every statement after it fails too, including the write
    that the paperwork was about.
    """
    try:
        with env.cr.savepoint():
            return fn()
    except Exception:                   # noqa: BLE001 — paperwork never fails
        _logger.warning('pb_hiring: %s failed', label, exc_info=True)
        return False
def flag(env, key, default=None):
    """A switch, read as a switch and never as a truthy string."""
    raw = env['ir.config_parameter'].sudo().get_param(
        key, DEFAULTS.get(key) if default is None else default)
    return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')


def number(env, key, default=0):
    raw = env['ir.config_parameter'].sudo().get_param(
        key, DEFAULTS.get(key, default))
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return int(default)


def counted(count, one, many):
    """"1 role" and "3 roles", never "1 role(s)" (R46).

    Both words are passed in whole so a translator gets a sentence rather
    than a frame with a hole in it (R117).
    """
    return one if count == 1 else many


def fold(text):
    """Accent-blind text for a search box.

    Postgres on this build has no `unaccent` extension (R78) and most people
    on this database have an accent in their name, so the folding happens in
    Python. `đ` carries no combining mark, so NFKD leaves it and it is mapped
    by hand (R28).
    """
    if not text:
        return ''
    out = unicodedata.normalize('NFKD', str(text))
    out = ''.join(ch for ch in out if not unicodedata.combining(ch))
    return out.replace('đ', 'd').replace('Đ', 'D').lower()


def slug_filename(text, fallback='file'):
    """A file name a person can still read, with the accents FOLDED.

    A plain `[^A-Za-z0-9]` pass turns "Bùi Hữu Dũng" into `B_i_H_u_D_ng`,
    which nobody can read and which collides with every other name of the
    same shape (R28). `fold` does the NFKD pass and the hand map for `đ`;
    this only tidies what is left, keeps the extension and never lets a
    candidate's own file name decide where a file is written.
    """
    import os
    import re
    raw = (text or '').strip()
    if not raw:
        return fallback
    stem, ext = os.path.splitext(os.path.basename(raw))
    stem = re.sub(r'[^a-z0-9]+', '-', fold(stem)).strip('-')
    ext = re.sub(r'[^a-z0-9.]+', '', fold(ext))[:8]
    return (stem or fallback)[:80] + (ext or '')


def as_id(value):
    """A record argument arrives over the wire as a plain integer (R43).

    Every public method that takes "a record" coerces at the door, so an RPC
    caller and an in-process caller reach the same code.
    """
    if not value:
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(value.id)
    except (AttributeError, TypeError, ValueError):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def excerpt(text, limit=240):
    text = (text or '').strip()
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + '…'
