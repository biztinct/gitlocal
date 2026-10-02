# -*- coding: utf-8 -*-
"""Learning settings — every learning switch on one card (LEARN v3).

WHY THIS EXISTS
---------------
Five learning features were built and shipped OFF: the next-step suggestion,
streaks and badge levels, answers composed from the guide, voice, and keeping
people's questions. Only one of them (composing) had a screen, and that screen
needed a role nobody holds. The rest could only be changed at the system
parameter table. The owner's ruling (2026-09-24): an administrator decides,
on one card, in plain words, without a developer.

WHAT IT CHANGES, AND WHAT IT DOES NOT
-------------------------------------
It writes the same five `ir.config_parameter` rows the features already read,
through the same truthy reader (`_flag_on`). No feature changes behaviour; the
card only makes the switches reachable. The per-person consents are untouched:
voice still asks each person once before recording, and keeping questions
still needs each person's own yes in the helper.

WHO CAN
-------
`base.group_system` — the tenant administrator — asked again on the server for
every read and every write, because a menu or a lens is a hint and these
methods are reachable over RPC by anything holding a session. This is a
deliberate relaxation of the composer's older two-role gate
(`learn.companion.settings`, which also required `group_learn_author`); that
wizard still exists and still asks both.

Every change is logged at WARNING with who made it, the same as the composer
wizard: three of these switches decide whether text or audio leaves the
server, and a record nobody would find at INFO is not a record.
"""
import logging

from odoo import api, models
from odoo.exceptions import AccessError

from .learn_intent import COMPOSE_FLAG
from .learn_question import COLLECT_FLAG, _flag_on
from .learn_runtime import NEXT_BEST_FLAG, SKILL_TREE_FLAG

_logger = logging.getLogger(__name__)

# PayAI's flag, spelled here rather than imported: pb_learn does not depend on
# pb_payroll_ai_insights, and the switch is only offered when that module is
# installed (see `_payai_installed`).
VOICE_FLAG = 'payai.voice_enabled'

# The card's order is the order a tenant would think about them in: the two
# that never leave the server first, then the three that can.
SWITCHES = (
    ('next_best', NEXT_BEST_FLAG),
    ('skill_tree', SKILL_TREE_FLAG),
    ('compose', COMPOSE_FLAG),
    ('voice', VOICE_FLAG),
    ('collect', COLLECT_FLAG),
)
SWITCH_PARAM = dict(SWITCHES)


class LearnSettings(models.AbstractModel):
    _name = 'learn.settings'
    _description = 'Payobook Learn — learning settings'

    # ------------------------------------------------------------ the gate
    @api.model
    def _check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(self.env._(
                "Only an administrator can change learning settings."))

    @api.model
    def can_manage(self):
        """For the lens: draw the card or not. The methods below re-ask."""
        return self.env.user.has_group('base.group_system')

    # ------------------------------------------------------ what is ready
    @api.model
    def _payai_installed(self):
        return 'payroll.ai.config' in self.env

    @api.model
    def _ai_ready(self):
        if not self._payai_installed():
            return False
        try:
            return bool(self.env['payroll.ai.config'].sudo().get_active_config())
        except Exception:                                          # noqa: BLE001
            _logger.info("Learning settings: cannot read the AI configuration",
                         exc_info=True)
            return False

    @api.model
    def _speech_ready(self):
        if 'payroll.ai.conversation' not in self.env:
            return False
        try:
            return self.env['payroll.ai.conversation'].sudo()._speech_provider() \
                is not None
        except Exception:                                          # noqa: BLE001
            _logger.info("Learning settings: cannot read the speech provider",
                         exc_info=True)
            return False

    # ------------------------------------------------------------- the API
    @api.model
    def get_switches(self):
        """`[{key, on, ready, leaves}]` in card order.

        `ready` False means the switch can be turned on but changes nothing
        until a provider is set up — the card says so rather than letting a
        tenant conclude the feature is broken. `leaves` names what, if
        anything, goes outside Payobook; the words are the card's own.
        Voice is left out entirely when PayAI is not installed: there is no
        microphone for it to switch on.
        """
        self._check_admin()
        ai_ready = self._ai_ready()
        out = []
        for key, param in SWITCHES:
            if key == 'voice' and not self._payai_installed():
                continue
            ready = True
            if key == 'compose':
                ready = ai_ready
            elif key == 'voice':
                ready = self._speech_ready()
            out.append({
                'key': key,
                'on': _flag_on(self.env, param),
                'ready': ready,
                'leaves': key in ('compose', 'voice'),
            })
        return out

    @api.model
    def set_switch(self, key, on):
        """Write one switch and return the whole card, re-read."""
        self._check_admin()
        param = SWITCH_PARAM.get(key)
        if not param or (key == 'voice' and not self._payai_installed()):
            raise AccessError(self.env._("That is not a learning setting."))
        before = _flag_on(self.env, param)
        self.env['ir.config_parameter'].sudo().set_param(
            param, 'True' if on else 'False')
        after = _flag_on(self.env, param)
        if before != after:
            _logger.warning(
                "pb_learn: learning setting %s switched %s by %s (uid %s). "
                "Parameter %s is now %r.", key, 'ON' if after else 'OFF',
                self.env.user.login, self.env.uid, param, after)
        return self.get_switches()
