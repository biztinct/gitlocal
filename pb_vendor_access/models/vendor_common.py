# -*- coding: utf-8 -*-
"""The words, the caps and the switches the VENDOR half of this module shares.

One module, one vocabulary. A vendor TYPE is spelled the same on the model, on
the board, in the spreadsheet and in the mail, because three spellings of one
idea is how a filter quietly matches nothing (R27/R80).

ACCESS MANAGEMENT LIVES IN `biz_access` NOW (ACCESS P6). Everything about roles,
abilities and hand-overs — the models, the home, the constants and the small
helpers — was extracted into a product-agnostic module so it can be reused in
another application. This file keeps the vendor register's own words and
re-exports the shared helpers so the vendor files that use them read exactly as
they did.

THE TWO REGISTRATIONS AT THE BOTTOM are how this product tells the generic
module about itself: the areas its roles are grouped under, and the fact that a
lifecycle administrator here may also manage somebody's access. They are made at
IMPORT time, so they are in place before any record is read.

Two rules from the ledger are wired in here rather than repeated in six files:

  * **R76 — a cap that is right for a SCREEN is a bug in a CRON.** Every cap
    below is a DEFAULT, every reader takes it as a PARAMETER, and the jobs pass
    `None`.
  * **R92 — a swallowed exception logged at DEBUG is invisible on a live
    server.** `safe()` returns its default and says so at WARNING with the
    traceback.
"""

import logging

from odoo.addons.biz_access.models.access_common import (  # noqa: F401
    FORBIDDEN_GROUP_XMLIDS, HOLDER_CAP, PICKER_CAP, area_label, counted, fold,
    forbidden_group_ids, forbidden_in_closure, implied_closure, profile_areas,
    register_areas, register_manager_groups, safe)
from odoo.addons.biz_access.models import access_common

_logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ the words
#: What kind of outside party this is. The blueprint's list, verbatim.
VENDOR_TYPES = [
    ('recruitment', 'Recruitment'),
    ('learning', 'Learning & training'),
    ('assessment', 'Assessments & tests'),
    ('benefits', 'Benefits & insurance'),
    ('it', 'IT & software'),
    ('services', 'Services'),
    ('committee', 'Committee / statutory'),
    ('other', 'Other'),
]
VENDOR_TYPE_KEYS = tuple(k for k, _l in VENDOR_TYPES)

#: Where an agreement is in its life. Computed from the dates and the renewal
#: flag — never typed, so it can never disagree with the calendar.
AGREEMENT_STATES = [
    ('draft', 'Not started'),
    ('running', 'Running'),
    ('expiring', 'Ending soon'),
    ('expired', 'Ended'),
    ('renewed', 'Replaced by a newer one'),
]

# =============================================================================
# THE AREAS THIS PRODUCT GROUPS ITS ROLES UNDER.
#
# They are the words on the rail, not the names of modules — which is exactly
# why they belong to the product and not to the generic access module. The
# generic module ships one neutral area and this registration replaces it.
# =============================================================================
PROFILE_AREAS = [
    ('payroll', 'Payroll'),
    ('people', 'People'),
    ('lifecycle', 'Lifecycle'),
    ('money', 'Money & budgets'),
    ('system', 'System'),
]
register_areas(PROFILE_AREAS, default='people')

# =============================================================================
# WHO ELSE MAY MANAGE ACCESS ON THIS PRODUCT.
#
# The generic module ships its own access-team permission. On this product a
# lifecycle administrator also gives and takes roles, so that permission is
# registered rather than hard-coded anywhere in the generic layer.
# =============================================================================
register_manager_groups('pb_lifecycle.group_lifecycle_admin')

# ------------------------------------------------------------------- the caps
VENDOR_ROW_CAP = 800
AGREEMENT_ROW_CAP = 2000

# --------------------------------------------------------------- the switches
#: Defaults live in CODE, never in a `noupdate="1"` record — a shipped record
#: freezes whatever value a test run left behind, because the next upgrade
#: never corrects it (the call P3-P10 all made).
DEFAULTS = {
    #: How many days before an agreement ends we start saying so.
    'pb_vendor_access.renewal_horizon_days': '45',
    #: Are the nightly agreement mails switched on? Shipped ON: unlike a job
    #: that opens a review on somebody, this one only ever tells the person who
    #: already owns the contract that it is about to run out (R54's shape, the
    #: gentler side of it).
    'pb_vendor_access.alerts_enabled': '1',
    #: How many mails one run of a job may send. A burst cap, not a filter:
    #: whatever is left is reported and picked up on the next run.
    'pb_vendor_access.mail_burst': '80',
}


def param(env, key, default=None):
    """A config parameter, with this module's own default behind it."""
    return access_common.param(env, key, default, DEFAULTS)


def param_int(env, key, default=0):
    return access_common.param_int(env, key, default, DEFAULTS)


def flag(env, key):
    return access_common.flag(env, key, DEFAULTS)


def type_label(key, env=None):
    """The word for a vendor type, translated where there is an env to ask.

    Module-level `_()` has no language to work in and logs "no translation
    language detected" on every call, so the environment is passed rather than
    assumed — `env._()` is Odoo 19's own form for exactly this.
    """
    for k, lbl in VENDOR_TYPES:
        if k == key:
            return env._(lbl) if env is not None else lbl
    return key or ''


def state_label(key, env=None):
    for k, lbl in AGREEMENT_STATES:
        if k == key:
            return env._(lbl) if env is not None else lbl
    return key or ''
