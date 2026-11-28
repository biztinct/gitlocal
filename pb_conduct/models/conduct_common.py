# -*- coding: utf-8 -*-
"""The words, groups and small helpers `pb_conduct` shares.

WDGAP S9-B (owner ruling P3): conduct cases are seen ONLY by the people HR
names on the Access screen. This module ships its own two groups, with NO
implied_ids from any HR, lifecycle, payroll or administrator group, and every
read path re-checks them. A system administrator is NOT let in by default
(unlike growth plans): they can name themselves on the Access screen, and
that grant is recorded like any other.
"""

GROUP_USER = 'pb_conduct.group_conduct_user'
GROUP_HEAD = 'pb_conduct.group_conduct_head'

#: The vault category a finished letter is filed under. Its CODE is what the
#: global document rule reads (a rule domain cannot `ref()` an xmlid).
VAULT_CODE = 'pb_conduct'

#: The steps of a case, in order. Generic on purpose: the legal steps differ
#: by country and are an owner/adviser item (country notes HR can edit).
STATES = [
    ('concern', 'Concern'),
    ('hearing', 'Hearing'),
    ('decision', 'Decision'),
    ('letter', 'Letter'),
    ('signoff', 'Second sign-off'),
    ('closed', 'Closed'),
]
OPEN_STATES = ('concern', 'hearing', 'decision', 'letter', 'signoff')

#: What was decided. Country words (SP1-SP3, ...) go in the country notes.
OUTCOMES = [
    ('none', 'No action'),
    ('verbal', 'Verbal warning'),
    ('written', 'Written warning'),
    ('final', 'Final written warning'),
    ('dismissal', 'Dismissal'),
]
WARNING_OUTCOMES = ('verbal', 'written', 'final')

#: Owner ruling CD1 (2026-11-17): every decision whose letter tells the
#: employee of a consequence — a warning of any kind, or a dismissal — is
#: confirmed by a SECOND named person before the letter is finished and
#: before the employee can see anything. "No action" has no consequence and
#: needs no second sign-off. No formal appeal step (owner).
SIGNOFF_OUTCOMES = ('verbal', 'written', 'final', 'dismissal')

#: Where the second sign-off of one decision stands.
SIGNOFF_STATES = [
    ('waiting', 'Waiting for a second sign-off'),
    ('sent_back', 'Sent back'),
    ('confirmed', 'Confirmed'),
]

#: How long a warning stays live by default, in months. HR changes the date
#: on each decision; these are only where the date starts.
DEFAULT_VALID_MONTHS = {'verbal': 6, 'written': 12, 'final': 12}

LETTER_KINDS = [
    ('invite', 'Invitation to a hearing'),
    ('none', 'No further action'),
    ('verbal', 'Verbal warning confirmed'),
    ('written', 'Written warning'),
    ('final', 'Final written warning'),
    ('dismissal', 'Dismissal'),
]

NOTE_KINDS = [
    ('investigation', 'Investigation note'),
    ('minutes', 'Hearing minutes'),
    ('meeting', 'Meeting note'),
    ('other', 'Other note'),
]

#: The step a country note belongs to.
NOTE_STEPS = [
    ('concern', 'Concern'),
    ('hearing', 'Hearing'),
    ('decision', 'Decision'),
    ('letter', 'Letter'),
]


def initials(name):
    parts = [p for p in (name or '').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def is_reader(env):
    """May this user see conduct cases at all? Named people only."""
    user = env.user
    return bool(env.su or user.has_group(GROUP_USER)
                or user.has_group(GROUP_HEAD))


def is_head(env):
    return bool(env.su or env.user.has_group(GROUP_HEAD))


def named_users(env, company):
    """The people named for conduct cases (either group — the head's group
    implies the other) who work in `company`: active internal logins only."""
    group = env.ref(GROUP_USER, raise_if_not_found=False)
    if not group:
        return env['res.users'].browse()
    return group.sudo().all_user_ids.filtered(
        lambda u: u.active and not u.share and company in u.company_ids)
