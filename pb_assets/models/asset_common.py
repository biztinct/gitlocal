# -*- coding: utf-8 -*-
"""The words the asset register uses, in exactly one place.

Everything else in the module imports from here, so a label that changes on a
screen changes on every screen at once.
"""

from odoo import _

# --------------------------------------------------------------- the two kinds
#: A thing you can drop, and a thing you can only switch off. The whole module
#: branches on this one distinction: a laptop comes back, an email account is
#: closed.
ASSET_KINDS = [
    ('tangible', 'Physical'),
    ('digital', 'Digital'),
]
ASSET_KIND_LABEL = dict(ASSET_KINDS)

# ------------------------------------------------------------------- the states
#: ONE selection carries both kinds — the constraint below is what keeps a
#: laptop out of "Switched off" and an email account out of "Under repair".
#: Two selections would have meant two state fields, two filters and two sets of
#: reports that never quite agree.
ASSET_STATES = [
    ('spare', 'Spare'),
    ('assigned', 'Assigned'),
    ('repair', 'Under repair'),
    ('to_scrap', 'To scrap'),
    ('scrapped', 'Scrapped'),
    ('deactivated', 'Switched off'),
]
ASSET_STATE_LABEL = dict(ASSET_STATES)

TANGIBLE_STATES = ('spare', 'assigned', 'repair', 'to_scrap', 'scrapped')
DIGITAL_STATES = ('spare', 'assigned', 'deactivated')

#: A digital item is never "spare in the cupboard" and never "assigned to a
#: desk" — it is available, or it is live on somebody's name.
DIGITAL_STATE_LABEL = {
    'spare': 'Available',
    'assigned': 'Active',
    'deactivated': 'Switched off',
}


def state_label(kind, state):
    """The word this kind of item uses for this state."""
    if kind == 'digital' and state in DIGITAL_STATE_LABEL:
        return _(DIGITAL_STATE_LABEL[state])
    return _(ASSET_STATE_LABEL.get(state, state or ''))


def states_for(kind):
    return DIGITAL_STATES if kind == 'digital' else TANGIBLE_STATES


# -------------------------------------------------------------- an assignment
ASSIGNMENT_STATES = [
    ('open', 'With employee'),
    ('returned', 'Returned'),
]
ASSIGNMENT_STATE_LABEL = dict(ASSIGNMENT_STATES)

# ----------------------------------------------------------------- a request
REQUEST_STATES = [
    ('draft', 'Draft'),
    ('submitted', 'Waiting for the manager'),
    ('manager_approved', 'Manager approved'),
    ('approved', 'Approved'),
    ('refused', 'Turned down'),
    ('cancelled', 'Cancelled'),
]
REQUEST_STATE_LABEL = dict(REQUEST_STATES)

FULFILMENTS = [
    ('todo', 'To arrange'),
    ('spare', 'Assign from spares'),
    ('buy', 'Buy new'),
    ('ready', 'Ready'),
    ('delivered', 'Delivered'),
    ('confirmed', 'Confirmed by employee'),
]
FULFILMENT_LABEL = dict(FULFILMENTS)

# ------------------------------------------------------------------ the gates
GROUP_USER = 'pb_assets.group_assets_user'
GROUP_MANAGER = 'pb_assets.group_assets_manager'

#: Who may approve the second tier of a request when no line manager answers.
MANAGER_GROUPS = ('hr.group_hr_user', 'hr.group_hr_manager')
