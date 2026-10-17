# -*- coding: utf-8 -*-
"""The "Connect an HR system" flow — a facade over the existing wizard.

IA Cycle 3, flow doctrine 1: a stock Odoo modal becomes a full-screen stepped
flow. What it must NOT become is a second implementation. Every decision here is
still made by `hr.integration.onboarding.wizard` — the transient that already
knows how to create a connector, apply a vendor field template, test a payload
and promote a suggested mapping. This model writes its fields, calls its buttons,
DISCARDS the `act_window` dicts they return (they exist to re-open the modal this
cycle is replacing), and re-reads the transient's state.

That is the same discard-and-re-read orchestration the Import cockpit uses over
`hr.integration.connector`, and it is what keeps one behaviour in one place: a
fix to the wizard's template logic reaches this flow without anybody remembering
that this flow exists.

Two things it deliberately does differently from the modal:

  * **it never returns a credential.** The wizard stores `api_key`,
    `client_secret` and `client_id`; the flow reports only WHETHER each is set.
    A full-screen surface is screenshotted, pasted into tickets and left open on
    a shared monitor in a way a modal is not, and there is no step in this flow
    that needs to read a secret back.
  * **it validates before it delegates.** `action_to_auth` raises through
    `models.ValidationError`, which does not exist in Odoo 19 (`odoo/models/
    __init__.py` exports no exceptions) — so the wizard's own empty-vendor guard
    would answer with an AttributeError traceback instead of a message. The
    facade asks the question first, in its own words. See the module docstring
    of the report for the defect; it is pre-existing and not patched here.

Rights: the caller's own, throughout. This flow adds no privilege the modal did
not have — the one `sudo()` in the file reads a formula rule's CODE for the
preview table, which is what the wizard's own `_build_summary` already does for
the same string on the same screen (those rules are company-scoped by record
rule and an integration user may legitimately not read them). Every WRITE goes
through the wizard's own buttons as the real user.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

WIZ = 'hr.integration.onboarding.wizard'

# The four steps, in order. Named here because the flow's stepper has to render
# them and because `action_back` walks this same order inside the wizard — two
# copies of a sequence is how a Back button ends up one step out of phase.
STEPS = ['vendor', 'auth', 'mappings', 'activate']

# Only these wizard fields may be written from the browser. An allow-list, not a
# deny-list: the transient carries readonly result fields (`applied_count`,
# `summary_html`) that a forged call could otherwise use to write a plausible
# outcome onto a step it never ran.
WRITABLE = {
    'connector_type', 'config_id', 'name', 'api_endpoint',
    'auth_type', 'api_key', 'client_id', 'client_secret',
}


class PbIntegrationOnboarding(models.AbstractModel):
    _name = 'pb.integration.onboarding'
    _description = 'Connect an HR system — stepped flow'

    # ------------------------------------------------------------------ state
    @api.model
    def _wizard(self, wizard_id):
        w = self.env[WIZ].browse(int(wizard_id))
        if not w.exists():
            # A transient is vacuumed after a while, and a flow left open over
            # lunch is the normal way to meet that. Say so — "Object does not
            # exist" would send someone looking for a bug.
            raise UserError(_("This connection setup has expired. Start it again."))
        return w

    @api.model
    def _state(self, w):
        """Everything the flow renders, and nothing it must not see."""
        sel = dict(self.env[WIZ]._fields['connector_type'].selection or [])
        maps = w.connector_id.field_mapping_ids if w.connector_id else \
            self.env['hr.integration.field.mapping'].browse()
        return {
            'wizard_id': w.id,
            'step': w.step or 'vendor',
            'step_index': STEPS.index(w.step) if w.step in STEPS else 0,
            'connector_type': w.connector_type or '',
            'connector_label': sel.get(w.connector_type, ''),
            'config_id': w.config_id.id or False,
            'config_name': w.config_id.name or '',
            'name': w.name or '',
            'api_endpoint': w.api_endpoint or '',
            'auth_type': w.auth_type or '',
            # Whether, never what.
            'has_api_key': bool(w.api_key),
            'has_client_id': bool(w.client_id),
            'has_client_secret': bool(w.client_secret),
            'connection_status': w.connection_status or '',
            'connector_id': w.connector_id.id or False,
            'connector_name': w.connector_id.name or '',
            'applied_count': w.applied_count or 0,
            'suggested_count': w.suggested_count or 0,
            'guide': w.guide_display or '',
            'badge': w.badge_display or '',
            'mappings': [{
                'id': m.id,
                'source': m.source_field or '',
                'target': (m.target_rule_id.sudo().code or ''),
                'state': m.active_state or 'active',
            } for m in maps[:60]],
            'mapping_total': len(maps),
        }

    # ------------------------------------------------------------------ setup
    @api.model
    def start(self):
        """A fresh flow. The ONE method that creates a wizard.

        Called from `onWillStart`, which is a mount hook — and a mount hook that
        writes is exactly what cost P1a 591 junk records (W21). It is safe here
        for the reason that rule allows: the record it creates is a TRANSIENT
        with no side effect outside itself (no connector is created until the
        user presses a button), and Odoo vacuums it. The connector-creating
        steps below are every one of them a click.
        """
        w = self.env[WIZ].create({})
        d = self._state(w)
        d['vendors'] = [
            {'id': k, 'label': v}
            for k, v in (self.env[WIZ]._fields['connector_type'].selection or [])
        ]
        d['configs'] = [
            {'id': c.id, 'name': c.name}
            for c in self.env['hr.formula.config'].search(
                [('active', '=', True)], order='name', limit=200)
        ]
        d['auth_types'] = [
            {'id': k, 'label': v}
            for k, v in (self.env[WIZ]._fields['auth_type'].selection or [])
        ]
        return d

    @api.model
    def get_state(self, wizard_id):
        """A pure READ, safe to run any number of times.

        The flow's mount asks this rather than re-running a step, so an OWL
        remount (which restarts an in-flight `onWillStart`, W21.1) can never
        repeat a create.
        """
        return self._state(self._wizard(wizard_id))

    @api.model
    def _write(self, w, vals):
        clean = {k: v for k, v in (vals or {}).items() if k in WRITABLE}
        if clean:
            w.write(clean)
        return w

    # ------------------------------------------------------------------ steps
    @api.model
    def choose_vendor(self, wizard_id, vals):
        """Step 1 → 2. Validated HERE, in words a user can act on."""
        w = self._wizard(wizard_id)
        self._write(w, vals)
        if not w.connector_type:
            raise UserError(_("Choose the HR system you are connecting to."))
        w.action_to_auth()                 # discard the reopen action
        return self._state(w)

    @api.model
    def back(self, wizard_id):
        w = self._wizard(wizard_id)
        w.action_back()
        return self._state(w)

    @api.model
    def save_auth(self, wizard_id, vals):
        """Step 2, without moving. Lets the flow keep typed values server-side
        so a Back-then-Next round trip does not lose them."""
        w = self._wizard(wizard_id)
        self._write(w, vals)
        return self._state(w)

    @api.model
    def test_connection(self, wizard_id, vals):
        """Step 2's probe. Creates or updates the connector, then tests it.

        The wizard's own `action_test_connection` calls `_ensure_connector`
        first, so the connector exists from this point on — which is why the
        client blocks every step button while one is in flight. Two of these in
        parallel would both see an empty `connector_id` and both create one, in
        separate transactions, where no uniqueness guard can see the other
        (W21.1: a uniqueness guard cannot fix a concurrency problem).
        """
        w = self._wizard(wizard_id)
        self._write(w, vals)
        err = None
        try:
            w.action_test_connection()
        except Exception as e:
            # Reported to the caller, never swallowed into "nothing happened"
            # (W40). A failed connection test is a normal outcome of this step
            # and the message is the whole point of pressing the button.
            err = str(getattr(e, 'name', None) or e) or _("Connection test failed.")
            _logger.info("Onboarding test_connection failed: %s", e)
        d = self._state(w)
        d['error'] = err
        return d

    @api.model
    def apply_template(self, wizard_id, vals):
        """Step 2 → 3. Loads the vendor field template onto the connector."""
        w = self._wizard(wizard_id)
        self._write(w, vals)
        w.action_apply_template()
        return self._state(w)

    @api.model
    def test_mappings(self, wizard_id):
        """Step 3's probe — the only path from 'suggested' to 'active'."""
        w = self._wizard(wizard_id)
        w.action_test_mappings()
        return self._state(w)

    @api.model
    def to_activate(self, wizard_id):
        w = self._wizard(wizard_id)
        w.action_to_activate()
        return self._state(w)

    @api.model
    def finish(self, wizard_id):
        """Step 4. Activates the connector and hands back its id.

        `action_finish` returns an `act_window` onto the native connector form.
        That return value is DISCARDED: the flow's terminal card lands the user
        on the Payobook connector cockpit instead, which is the surface this
        product actually maintains — sending them to the native form would undo
        the whole point of the cycle at the last click.
        """
        w = self._wizard(wizard_id)
        w.action_finish()
        d = self._state(w)
        d['done'] = True
        return d
