# -*- coding: utf-8 -*-
"""The Settings hub's only server call: does this action exist here?

The hub itself is chrome — it owns no data, writes nothing, and every card on it
is a door to something that already exists. The one question it cannot answer in
the browser is whether an ACTION XMLID resolves on this database: a client action
can be probed against the JS registry (a module that is not installed did not
ship its JS), but an `ir.actions.act_window` leaves no trace in the browser at
all.

That question matters because of W79: a resolver with a swallowing fallback makes
a DEAD entry indistinguishable from an ABSENT one. A card pointing at a deleted
or never-installed action renders normally, answers a click with nothing, and
logs nothing — five of exactly that shape survived in `hr.flow.wizard` until P7
went looking. So the hub asks, and hides what is not there.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# The descriptor in settings_hub.js names 6 action xmlids today. The cap is a
# bound on a list a caller controls, not a guess at the descriptor's size — a
# forged call may not turn one RPC into an unbounded ir.model.data walk.
_MAX_PROBE = 50


class PbSettings(models.AbstractModel):
    _name = 'pb.settings'
    _description = 'Payobook settings hub'

    @api.model
    def resolve_actions(self, xmlids):
        """`{xmlid: bool}` — which of these action xmlids exist here.

        Read-only by construction: `env.ref` with `raise_if_not_found=False` is
        the whole method. No sudo (there is nothing to escalate — existence of an
        xmlid is not a permission), no create, no write, no unlink. Whether the
        CALLER may open what it names is the action's own question and stays
        with the action; this one only stops the hub from offering a door that
        was never built.

        Anything that is not a string is skipped rather than raising: the caller
        is a template descriptor, and one malformed entry must not take the whole
        Settings hub down with it.
        """
        out = {}
        for xmlid in (xmlids or [])[:_MAX_PROBE]:
            if not isinstance(xmlid, str) or '.' not in xmlid:
                continue
            out[xmlid] = bool(self.env.ref(xmlid, raise_if_not_found=False))
        return out
