# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
"""A defensive guard on `hr_timesheet`'s `session_info` override (W100).

THE BUG, AND WHY IT IS NOT OURS
-------------------------------
`hr_timesheet/models/ir_http.py:19` (Odoo 19 CE) decorates every company the
user belongs to with the timesheet UoM the `timesheet_uom` widget needs::

    for company in self.env.user.company_ids:
        result["user_companies"]["allowed_companies"][company.id].update({...})

but `allowed_companies` is NOT built from `company_ids`. `web`'s own
`session_info` builds it from `res.users._get_company_ids()`
(`base/models/res_users.py:726`), which is
`@tools.ormcache('self.id')`-decorated and is invalidated ONLY from
`res.users.write()` (`_get_invalidation_fields`). Link a company to a user from
the COMPANY side — `res.company.write({'user_ids': …})`, the Users tab of the
company form, a data file, SQL — and nothing clears that cache: the live
`company_ids` then holds an id the cached `allowed_companies` does not, and the
loop above raises `KeyError: <company id>` inside `session_info`, which is
called by `webclient_rendering_context()`. **Every backend page load answers
500 for that user and only for that user** — the shape recorded as W100 in
`docs/WORKFORCE_REDESIGN_CONVENTIONS.md` and observed on this server on
2026-08-19 (`KeyError: 1` at 03:38 and 04:05, `KeyError: 5` at 13:47-13:52,
both of them ACTIVE companies, which is the fingerprint of this path).

Measured on this build (IA Cycle 7), so the two directions are not confused:
`c.write({'user_ids': [(4, uid)]})` leaves `company_ids = [2, 7, 8]` against a
cached `_get_company_ids() = [2, 7]`. ARCHIVING a company does NOT produce the
mirror-image bug, because reading the `company_ids` many2many applies
`active_test` and drops the archived id from BOTH sides.

So this file ships two things: the guard below (the symptom — every user whose
session is already divergent, on every database, without a data migration) and
`ResCompany.write` (the cause — one `clear_cache()` on the write core forgot).

WHY A PATCH AND NOT AN `_inherit`
---------------------------------
An `ir.http` override in another module cannot help: model inheritance makes
our method the OUTERMOST one, so the crash happens inside our own `super()`
call and there is nothing left to guard. Making the fix an inherit would
require loading BEFORE `hr_timesheet`, which no dependency can express (nothing
may depend on us) and which module load order must never be relied on. So the
crash site itself is replaced, with a copy of upstream's body whose only
difference is the missing-key branch. `biz_deroute/tests/test_session_guard.py`
pins upstream's shape: the day Odoo fixes this, that test fails and this file
should be deleted rather than quietly kept.

The patch is behaviour-preserving by construction. For every user whose
`company_ids` is a subset of `allowed_companies` — i.e. everybody the bug does
not hit — the loop writes exactly the same keys with exactly the same values,
and `uom_ids` is computed by the same unmodified `get_timesheet_uoms()`. The
only observable difference for an AFFECTED user is a rendered page and one
WARNING naming the divergent ids, instead of a 500 with no user in it.

WHEN THE PATCH IS APPLIED, AND WHY NOT AT IMPORT TIME
-----------------------------------------------------
The first version of this file did
`from odoo.addons.hr_timesheet.models.ir_http import IrHttp` at module level,
and that took the LOGIN PAGE of every database on the server down (500 on
`/web/login`, `ValueError: Expected singleton: res.users()` while rendering
`website.layout` with an empty `env.user`). `biz_deroute` depends on `web`
alone and is `auto_install`, so it is imported very early; importing an addon
this module does not DEPEND on drags that addon's `ir.http` class — and the
whole dependency chain behind it — into the class registry ahead of its place
in the module graph, and the `ir.http` composed from that order no longer runs
`website`'s dispatch hook that gives an anonymous request its public user.
Isolated by running the same database on a private port with only this file
reverted: 500 with the import, 200 without it, 200 with the rest of the module
and the import removed.

So the patch is applied from `_register_hook()`, which runs after the registry
is built: by then `hr_timesheet` has been imported by the graph if it is
installed, the import here is a `sys.modules` lookup that changes no ordering,
and if it is NOT installed nothing is imported at all. Idempotent, because
`_register_hook` runs on every registry load of every database.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Set by `_install_session_guard()` once the registry is up. Never imported at
# module level — see the header.
_TimesheetIrHttp = None


def _guarded_session_info(self):
    """`hr_timesheet.IrHttp.session_info`, with the crash site guarded."""
    result = super(_TimesheetIrHttp, self).session_info()
    if self.env.user._is_internal():
        allowed = result["user_companies"]["allowed_companies"]
        divergent = []
        for company in self.env.user.company_ids:
            entry = allowed.get(company.id)
            if entry is None:
                # The company is on the user but not in the session's allowed
                # set (archived, or a stale `_get_company_ids` cache). Upstream
                # raises KeyError here and takes the whole webclient with it.
                divergent.append(company.id)
                continue
            entry.update({
                "timesheet_uom_id": company.timesheet_encode_uom_id.id,
                "timesheet_uom_factor": company.project_time_mode_id._compute_quantity(
                    1.0,
                    company.timesheet_encode_uom_id,
                    round=False
                ),
            })
        if divergent:
            _logger.warning(
                "biz_deroute session guard: user %s (id %s) has compan%s %s in "
                "company_ids that the session's allowed_companies does not "
                "carry (archived company, or a stale res.users._get_company_ids "
                "ormcache). Upstream hr_timesheet would have answered 500 here; "
                "the timesheet UoM decoration is skipped for those companies. "
                "See W100.",
                self.env.user.login, self.env.user.id,
                'y' if len(divergent) == 1 else 'ies', divergent,
            )
        result["uom_ids"] = self.get_timesheet_uoms()
    return result


def _install_session_guard():
    """Bind the guard onto `hr_timesheet`'s class, once, after registry load.

    Called from `_register_hook`. Returns True when the guard is (already)
    bound, False when `hr_timesheet` is not part of this deployment at all —
    the tests read that answer rather than re-deriving it.
    """
    global _TimesheetIrHttp
    try:
        from odoo.addons.hr_timesheet.models.ir_http import IrHttp
    except ImportError:
        # hr_timesheet is not installed on any database this process serves,
        # so there is no crash site to guard. (Importing it here to find that
        # out is exactly what the header forbids at module level; by
        # `_register_hook` time the graph has already imported whatever is
        # installed, so this raises instead of loading anything new.)
        return False
    _TimesheetIrHttp = IrHttp
    if IrHttp.session_info is not _guarded_session_info:
        IrHttp.session_info = _guarded_session_info
        _logger.info("biz_deroute: hr_timesheet session_info guard installed (W100)")
    return True


class ResCompany(models.Model):
    """The CAUSE, one level below the guard.

    `res.users.write()` clears the registry cache when it touches one of
    `_get_invalidation_fields()` — `company_ids` among them. The inverse write
    does not: `res.company.write({'user_ids': …})` updates the same relation
    table from the other end and clears nothing, so `_get_company_ids()` keeps
    answering the set the user had BEFORE the company was linked, for the life
    of the registry. That single missing invalidation is what makes
    `allowed_companies` disagree with `company_ids` at all.

    Clearing here is cheap (linking users to a company is an administrative
    action, not a hot path) and it is the same call, on the same registry, that
    the other half of the relation already makes.
    """
    _inherit = 'res.company'

    def write(self, vals):
        res = super().write(vals)
        if 'user_ids' in vals:
            self.env.registry.clear_cache()
        return res

    def _register_hook(self):
        # The guard is bound HERE and not at import time. `res.company` is only
        # the carrier: this module has to own some model for the hook to fire,
        # and inheriting `ir.http` for the purpose would put this module's class
        # into the very MRO whose ordering the header is about.
        super()._register_hook()
        _install_session_guard()
