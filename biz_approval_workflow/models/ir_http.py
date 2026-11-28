# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The approval switches cannot be set from outside.

Every proposal in this product marks "this write IS the approved change" with
a context key — `pb_contract_approved_write`, `pb_bands_approved_write`,
`pb_unlock_approved_write` and nine more — so the adapter's apply step can
pass the gate it put in front of everybody else. Those keys are plain strings
read with ``context.get(KEY)``, and a client sends its context with every
call. A request body carrying one of them would therefore have walked
straight past the route and written the change unapproved, with the ordinary
write right as the only thing left in the way.

Pay runs (`pb_chain_state_write`) and imports (`pb_import_apply`) already use
an ``object()`` token that no JSON can spell. The older switches get the same
protection here, at the one door every client call comes through: a guarded
key arriving in a request's parameters is dropped before the endpoint runs,
and the attempt is logged with the user who made it. Server-side callers are
untouched — they never go through a request.

PAYAI P0 (2026-10-12). Converting each switch to an ``object()`` token is the
longer repair and is on the ledger; this closes the door today in one place.
"""
import logging

from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)

#: Any context key ending like this is an approval switch.
GUARDED_SUFFIXES = ('_approved_write',)
#: Exact names that are tokens already, kept out of client reach all the same.
GUARDED_KEYS = frozenset({'pb_chain_state_write', 'pb_import_apply'})

_MAX_DEPTH = 8


def is_guarded_key(key):
    return isinstance(key, str) and (
        key in GUARDED_KEYS or key.endswith(GUARDED_SUFFIXES))


def scrub_params(params, _depth=0):
    """Drop guarded keys from `params`, in place. Returns the names dropped.

    Looks inside every dict (a `context` under `kwargs`, a positional context
    dict in an `execute` call, a nested `vals`) and every list, to a bounded
    depth. Nothing else is changed.
    """
    dropped = []
    if _depth > _MAX_DEPTH:
        return dropped
    if isinstance(params, dict):
        for key in [k for k in params if is_guarded_key(k)]:
            params.pop(key, None)
            dropped.append(key)
        for value in list(params.values()):
            dropped += scrub_params(value, _depth + 1)
    elif isinstance(params, (list, tuple)):
        for value in params:
            dropped += scrub_params(value, _depth + 1)
    return dropped


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _dispatch(cls, endpoint):
        # `request.params` is set by the dispatcher just before this hook and
        # is the very dict the endpoint is called with (`endpoint(**params)`),
        # so scrubbing it here is scrubbing what the method will see.
        try:
            params = getattr(request, 'params', None)
            dropped = scrub_params(params) if params else []
        except Exception as exc:                    # noqa: BLE001
            dropped = []
            _logger.error("biz_approval_workflow: could not inspect the "
                          "request parameters (%r); the request proceeds.", exc)
        if dropped:
            session = getattr(request, 'session', None)
            _logger.warning(
                "biz_approval_workflow: dropped approval switch(es) %s from a "
                "request by uid %s to %s — these keys are never accepted from "
                "a client.", sorted(set(dropped)),
                getattr(session, 'uid', None),
                getattr(getattr(request, 'httprequest', None), 'path', '?'))
        return super()._dispatch(endpoint)
