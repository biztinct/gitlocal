# -*- coding: utf-8 -*-
"""THE GATE — PA-R1, no back door.

An Action is allowed for a person only when BOTH halves say yes:

  1. the Access-home half — the Action's screen (a `pb.sidebar.item`) is
     'on' for the person in `pb.sidebar.item.visibility_for(user)`, which is
     the one rule the left menu AND the Access home's person passport are
     drawn from (lent roles arrive as groups, so they are honoured there);
  2. the method half — the Action's own right (group / ACL), judged with
     `with_user(user)` so a test's superuser env cannot say yes for somebody
     else (ledger PA12).

Neither alone. A screen that is locked or hidden refuses even when the ACL
would allow the method; a right without the screen refuses too.
"""
import logging

from odoo.tools.translate import LazyTranslate

from .i18n import T

from .registry import TIER_SWITCH

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

#: The Access home's ⌘K row — the door every "no right" refusal offers.
ACCESS_DOOR = 'va_access'


def tier_on(env, tier):
    """Is this tier switched on for the current company?"""
    field = TIER_SWITCH.get(tier)
    if not field:
        return False
    company = env.company
    return bool(company[field]) if field in company._fields else False


def screen_item(env, action):
    """The Action's screen: the first ACTIVE sidebar item it names, or None."""
    for xmlid in action.screen_keys:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec and rec._name == 'pb.sidebar.item' and rec.sudo().active:
            return rec
    return None


def screen_state(env, user, action):
    """'on' | 'locked' | 'hidden' | 'none' (the Action declares no screen).

    An Action that declares screens but none of them is on this database is
    'hidden': the screen does not exist here, so nobody can stand on it.
    """
    if not action.screen_keys:
        return 'none'
    item = screen_item(env, action)
    if item is None:
        return 'hidden'
    vis = env['pb.sidebar.item'].visibility_for(user)
    return (vis.get('items') or {}).get(item.id, 'hidden')


def method_ok(env, user, action):
    try:
        return bool(action.method_gate(env, user))
    except Exception:                                   # noqa: BLE001
        _logger.info("PayAI gate: method check for %s raised; refusing",
                     action.key, exc_info=True)
        return False


def allowed(env, user, action):
    """(ok, reason) — reason in 'tier_off' | 'no_right' | 'screen_off' | ''.

    Order of the reasons is the order of usefulness to the person reading the
    refusal: a switched-off tier is the company's decision, a missing right is
    the most actionable, a locked screen is the Access home's.
    """
    if action.tier == 'never':
        return False, 'never'
    if not tier_on(env, action.tier):
        return False, 'tier_off'
    if not user._is_internal():
        return False, 'no_right'
    m_ok = method_ok(env, user, action)
    s_state = screen_state(env, user, action)
    s_ok = s_state in ('on', 'none')
    if not m_ok:
        return False, 'no_right'
    if not s_ok:
        return False, 'screen_off'
    return True, ''


def prefilter(env, user, action):
    """The gate without the tier switch: may this person EVER do it here?

    Used to decide what to offer the model and what to list under "What can
    you do?". The tier switch is still checked at run time by `allowed`.
    """
    if action.tier == 'never':
        return False, 'never'
    if not tier_on(env, 'look'):
        return False, 'tier_off'
    if not user._is_internal():
        return False, 'no_right'
    if not method_ok(env, user, action):
        return False, 'no_right'
    if screen_state(env, user, action) not in ('on', 'none'):
        return False, 'screen_off'
    return True, ''


def refusal_text(action, reason):
    """The plain sentence for a refusal. Never a code word."""
    if reason == 'tier_off':
        return T(_lt(
            "PayAI can look, but is not allowed to do this here yet. An "
            "administrator can switch it on under Settings › PayAI can act."))
    if reason == 'screen_off':
        return T(_lt(
            "That screen is not switched on for you, so I cannot do this for "
            "you. An administrator can change it under Settings › Access and "
            "delegations."))
    if reason == 'never':
        return T(_lt("I do not do this, even when asked clearly. You can do "
                       "it yourself on the screen if you have the right."))
    subject = T(action.right_subject or action.title)
    right = T(action.right_label or action.title)
    return T(_lt(
        "%(subject)s is for payroll staff. Your sign-in does not have the "
        "%(right)s right; ask your administrator under Settings › Access and "
        "delegations.")) % {'subject': subject, 'right': right}
