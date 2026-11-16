# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shared words and numbers of Employee voice (WDGAP S9-C).

The floor (owner ruling P4): results AND written comments appear only for
groups of at least ``FLOOR`` answers. A round may raise it, never lower it.
"""
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

#: Owner ruling P4. The server refuses anything below it.
FLOOR = 5

#: Question kinds. A rating is the five agreement words; the recommend
#: question is 0-10 (eNPS); a choice is one of HR's options; a comment is
#: free text (HR only, groups of 5 or more).
KINDS = [
    ('scale', 'Agree or disagree (5 steps)'),
    ('enps', 'Would recommend (0 to 10)'),
    ('choice', 'Pick one option'),
    ('text', 'Written comment'),
]

#: What a result is grouped under on the results page.
THEMES = [
    ('engagement', 'Feeling about working here'),
    ('manager', 'Your manager'),
    ('growth', 'Learning and growth'),
    ('wellbeing', 'Wellbeing and workload'),
    ('recognition', 'Recognition'),
    ('communication', 'Communication'),
    ('teamwork', 'Teamwork'),
    ('values', 'Our values'),
    ('other', 'Other'),
]

#: The five agreement words, 1..5 (same words on the form and the results).
SCALE_WORDS = [
    _lt('Strongly disagree'),
    _lt('Disagree'),
    _lt('Neither agree nor disagree'),
    _lt('Agree'),
    _lt('Strongly agree'),
]

ROUND_STATES = [
    ('draft', 'Being set up'),
    ('open', 'Open for answers'),
    ('closed', 'Closed'),
]

#: What happened to the answers when the round closed.
RESULT_STATES = [
    ('none', 'Not closed yet'),
    ('kept', 'Results ready'),
    ('too_few', 'Too few answers, nothing kept'),
]

ACTION_STATES = [
    ('open', 'To do'),
    ('doing', 'Under way'),
    ('done', 'Done'),
]

#: The longest comment kept (characters).
MAX_COMMENT = 1000

#: The most questions a round may hold (keeps the form a few minutes long).
MAX_QUESTIONS = 30

#: Who runs surveys and reads results (and comments): HR, and system
#: administrators. Managers see only their own card on My Payobook.
VOICE_GATE = ('hr.group_hr_user', 'base.group_system')
