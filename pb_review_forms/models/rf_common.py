# -*- coding: utf-8 -*-
"""The words and the limits every file in this module shares (WDGAP S9-A).

ONE FORM PER GOAL YEAR (owner ruling P1). The form holds three parts that are
mixed into one overall result by the shares HR sets (P2):

  * the goals score the year already works out (`pb.goal.set.score`, 0–5);
  * a few skills or company values, rated on the SAME five words the goals
    use for key results and self-ratings ("Well below" … "Well above",
    `pb_goals.models.goals_common.RATINGS`), so the employee's words and the
    manager's words are the same words;
  * up to eight questions HR writes (rating, text or a pick from a list).

THE ORDER IS FIXED: the employee gives their own view first, then the manager
answers and writes the overall comment, then the employee reads it (when HR
says it may be shown) and says they have read it.
"""

from odoo.addons.pb_goals.models.goals_common import RATINGS

#: The five rating words, shared with Goals on purpose.
RATING_KEYS = tuple(key for key, _label in RATINGS)
RATING_LABEL = dict(RATINGS)

#: "A few skills or values" and "up to about eight questions" (P1).
MAX_SKILLS = 8
MAX_QUESTIONS = 8
MAX_CHOICES = 8

SECTIONS = [
    ('skill', 'Skill or value'),
    ('question', 'Question'),
]

QUESTION_TYPES = [
    ('rating', 'Rated from Well below to Well above'),
    ('text', 'Written answer'),
    ('choice', 'Pick one from a list'),
]

WHO_ANSWERS = [
    ('both', 'The employee and the manager'),
    ('employee', 'The employee only'),
    ('manager', 'The manager only'),
]

FORM_STATES = [
    ('draft', 'Being written'),
    ('published', 'In use'),
]

#: When the employee may read the manager's part.
REVEAL_MODES = [
    ('manager_done', 'As soon as the manager finishes'),
    ('date', 'From a date HR chooses'),
]

SELF_STATES = [
    ('todo', 'Not started'),
    ('draft', 'Started'),
    ('sent', 'Sent'),
]

MANAGER_STATES = [
    ('todo', 'Not started'),
    ('draft', 'Started'),
    ('done', 'Finished'),
]

ACK_STATES = [
    ('none', 'Not yet'),
    ('read', 'Has read it'),
    ('talk', 'Wants to talk about it'),
]

#: The groups. A line manager holds none of them (pb_goals' ladder): they are
#: let in by being the person's manager, checked on every call.
GROUP_USER = 'pb_goals.group_goals_user'
GROUP_MANAGER = 'pb_goals.group_goals_manager'

#: The review moment the form is used at. The half-way review keeps the
#: manager's written note exactly as before.
FORM_KIND = 'year_end'

#: How many reviews one run of the daily job may share (savepoint each).
RELEASE_CAP = 500


def rating_options(env):
    """The five words, in the reader's language (the answer model's own
    selection carries this module's translations)."""
    labels = dict(env['pb.review.answer']._fields['rating']
                  ._description_selection(env))
    return [{'key': key, 'label': labels.get(key, label)}
            for key, label in RATINGS]


def tidy(value):
    """3.6 and 4, never 4.0 — and None stays None."""
    if value is None or value is False:
        return None
    number = round(float(value), 2)
    return int(number) if number == int(number) else number
