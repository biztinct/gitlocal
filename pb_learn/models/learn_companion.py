# -*- coding: utf-8 -*-
"""Companion settings — the one screen that can switch the composer on.

WHY THERE IS A SCREEN AT ALL, AND WHY IT IS THIS SMALL
------------------------------------------------------
Phase D shipped the composer OFF behind `ir.config_parameter` and said, in the
ledger, that there was no UI on purpose: "turning on a path that lets a model
write to a learner is a decision worth making at the parameter table". That was
right about the WEIGHT of the decision and wrong about who ends up making it.
On a DB-per-tenant SaaS the person who owns that decision is a tenant
administrator, and the parameter table is a place nobody visits and nothing
explains.

So the screen exists and it deliberately does almost nothing:

  * it shows the two facts that decide whether anything happens — is the flag
    on, and is a provider configured FOR THIS COMPANY — because the flag alone
    changes nothing and a tenant who flips it and sees no difference will
    conclude the feature is broken;
  * it names what switching on means, in the same words the Coach uses;
  * it writes one parameter, and logs who did it.

STILL OFF BY DEFAULT, EVERYWHERE. Nothing here runs at install, nothing
defaults to true, and an upgraded tenant is in exactly the state it was in.

TWO GATES, AND THE SERVER RE-ASKS BOTH. The menu and the action are gated on
`group_learn_author`; `apply()` re-asks for that AND for `base.group_system`,
because a menu is a hint and a method is reachable by RPC from anything holding
a session. Same ruling as `learn.question.create` in Phase D2: put the gate on
the method, then ask what else can reach it.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .learn_intent import COMPOSE_FLAG

_logger = logging.getLogger(__name__)

# Both are required to change the flag. The author group is about owning the
# learning content; system is about owning the database. Switching on a path
# that sends this tenant's own tutorial text to a third-party provider is
# both kinds of decision at once, so it needs both hats.
APPLY_GROUPS = ('pb_learn.group_learn_author', 'base.group_system')


class LearnCompanionSettings(models.TransientModel):
    """A wizard, not a settings page.

    `res.config.settings` would have been the obvious home and is the wrong
    one: that screen is company-wide Odoo configuration with a Save button
    that writes dozens of unrelated fields, and this is one switch whose whole
    point is that somebody stopped and read a sentence before pressing it.
    """
    _name = 'learn.companion.settings'
    _description = 'Payobook Coach — companion settings'

    company_id = fields.Many2one(
        'res.company', string='Company', readonly=True,
        default=lambda self: self.env.company)

    compose_enabled = fields.Boolean(
        string='Let the Coach compose answers',
        default=lambda self: self.env['learn.intent']._compose_enabled(),
        help="When this is off — which is the shipped state everywhere — the "
             "Coach answers only from written content, and nothing it says "
             "has ever left this server. When it is on, a question no written "
             "answer covers may be answered by the configured AI provider, "
             "using this module's own tutorial text as its only material. "
             "Those answers are badged so the reader can tell.")

    provider_ready = fields.Boolean(
        string='AI provider configured', readonly=True,
        compute='_compute_provider', help="Read from PayAI's own active "
                                          "configuration for this company.")
    provider_note = fields.Char(readonly=True, compute='_compute_provider')

    # The flag is a DATABASE parameter and the provider is a per-company
    # record, so the two are not scoped the same way. Saying so is the point of
    # this field: a multi-company tenant that switches the flag on has switched
    # it on for every company, and only the ones with a provider will notice.
    scope_note = fields.Char(readonly=True, compute='_compute_provider')

    @api.depends('company_id')
    def _compute_provider(self):
        for record in self:
            config = None
            if 'payroll.ai.config' in self.env:
                try:
                    config = self.env['payroll.ai.config'].sudo() \
                        .get_active_config()
                except Exception:                             # noqa: BLE001
                    _logger.info("Companion settings: cannot read the PayAI "
                                 "configuration", exc_info=True)
            record.provider_ready = bool(config)
            if not config:
                record.provider_note = _(
                    "No AI provider is configured. With the switch on and no "
                    "provider, the Coach behaves exactly as it does with the "
                    "switch off.")
            else:
                record.provider_note = _(
                    "Provider: %(provider)s. Questions the written content "
                    "does not cover may be sent to it, with this module's "
                    "tutorial text as the only material.",
                    provider=config.provider_type or config.display_name)
            record.scope_note = _(
                "The switch applies to this whole database. The provider is "
                "configured per company, and this is the one active for "
                "%(company)s.", company=record.company_id.display_name or '-')

    def _check_may_apply(self):
        """Re-asked on the server, for every group the menu implies.

        A menu is a hint. This method is reachable over RPC by anything
        holding a session, which is the whole reason Phase D2 moved the
        question-mining gates out of `record()` and into `create()`.
        """
        missing = [g for g in APPLY_GROUPS if not self.env.user.has_group(g)]
        if missing:
            raise AccessError(_(
                "Changing this needs both the Learning content author role and "
                "system administration rights. Yours is missing: %(groups)s",
                groups=', '.join(missing)))

    def apply(self):
        """Write the parameter, and say in the log who did it.

        Logged at WARNING rather than INFO deliberately: this is the one
        control in the module that changes what a learner can be shown by
        something no author wrote, and a line nobody would find at INFO is a
        line that is not really a record of the decision.
        """
        self.ensure_one()
        self._check_may_apply()
        Param = self.env['ir.config_parameter'].sudo()
        before = self.env['learn.intent']._compose_enabled()
        Param.set_param(COMPOSE_FLAG, 'True' if self.compose_enabled else 'False')
        after = self.env['learn.intent']._compose_enabled()
        if before != after:
            _logger.warning(
                "pb_learn: the Coach composer was switched %s by %s (uid %s) "
                "on company %s. Parameter %s is now %r.",
                'ON' if after else 'OFF', self.env.user.login, self.env.uid,
                self.env.company.display_name, COMPOSE_FLAG, after)
        return {'type': 'ir.actions.act_window_close'}
