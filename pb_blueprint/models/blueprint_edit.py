# -*- coding: utf-8 -*-
"""Edit mode — the guided journey opened on a configuration that already exists.

The studio's Settings tab used to be a panel of its own: five sub-tabs of bare
fields sitting beside the components grid. Everything it edited now lives in the
journey, on the step where the decision belongs, so there is ONE screen that
describes a payroll configuration instead of two that can disagree.

Three rules hold this together.

**One settings contract, never two.** Edit mode reads and writes through the
studio's own ``get_config_settings`` / ``save_config_settings``. This module
adds no second whitelist: a field the studio does not carry is a field edit mode
cannot write, and that is deliberate.

**Settings are not pay logic.** BLUEPRINT rule 8 ("the draft is the working copy
and an active configuration is never edited as one") protects the RULES — the
formulas, the bands, the calendar, the components. Identity, accounting,
connections, export options, part-month pay, back-pay and the source lanes are
not rules, and they have ALWAYS been written straight to a live configuration
through the studio's Settings panel. Edit mode keeps exactly that contract and
adds nothing to it. Recorded as rule **8a**.

**A read never writes** (BP53). Entering edit mode is one explicit call,
``bp_adopt``. ``bp_load`` on a configuration the journey has never seen answers
``needs_adopt`` and writes nothing at all.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class PbBlueprintStudioEdit(models.AbstractModel):
    """Everything edit mode adds to the journey's one service model.

    Loaded after `blueprint_finish`, so the overrides below resolve first and
    hand the ordinary create-mode journey straight on to `super()`.
    """
    _inherit = 'pb.blueprint.studio'

    # ==================================================================
    # What may still be changed
    # ==================================================================
    def _edit_locks(self, config, blueprint=None):
        """The two locks, answered by the engine and never by the client.

        * ``country`` — the country decides the currency, the statutory rules
          and how people are matched. Once a configuration has paid somebody,
          changing it would rewrite the meaning of money that has already been
          handed over.
        * ``pay_logic`` — the same condition the tax and calendar steps have
          always enforced: a configuration that is no longer a draft, or that
          has paid somebody, has its rules changed in the components grid,
          where every change is versioned.
        """
        has_payslips = self._has_payslips(config)
        return {
            'country': bool(has_payslips),
            'pay_logic': bool(config.state != 'draft' or has_payslips),
            'has_payslips': bool(has_payslips),
        }

    def _pay_logic_reason(self, config):
        """Why the rules are read-only, in the words the tax step already uses.

        Deliberately the SAME two sentences as `_tax_readonly_reason`: two
        screens refusing the same thing for the same reason in two different
        wordings is how a person concludes that one of them is a bug.
        """
        if self._has_payslips(config):
            return _("This configuration has already paid people. Its pay "
                     "rules are changed in the components grid, where every "
                     "change is versioned.")
        return _("This configuration is no longer a draft. Its pay rules are "
                 "changed in the components grid, where every change is "
                 "versioned.")

    def _pay_logic_door(self, config):
        """No dead ends: the refusal names the screen that CAN do it."""
        return {'label': _("Open the components grid"), 'config_id': config.id}

    def _pay_logic_block(self, config_id):
        """A refusal dict when pay logic may not be written here, else None.

        Returns None whenever the configuration cannot be resolved or belongs
        to another company — those are refusals the endpoint's own `_guard`
        words better, and answering them twice would be answering them
        differently.

        This gate applies in BOTH modes. Create mode never reached it before
        because the journey only ever built drafts, but `bp_component_save`,
        `bp_component_exclude`, `bp_component_include`,
        `bp_component_restore_guided` and `bp_regenerate` had no such gate at
        all, so a hand-made RPC could rewrite the rules of a live
        configuration. Owner ruling 2026-09-19: close it in both modes.
        """
        try:
            config = self._config(config_id)
            if not config:
                return None
            company = config.company_id
        except AccessError:
            return None
        if company and company.id not in self._reachable_company_ids():
            return None
        if not self._edit_locks(config)['pay_logic']:
            return None
        return {
            'ok': False,
            'locked': True,
            'reason': self._pay_logic_reason(config),
            'door': self._pay_logic_door(config),
        }

    def _edit_mode_block(self, config_id, reason):
        """A refusal dict when this configuration is open in EDIT mode."""
        try:
            config = self._config(config_id)
            if not config:
                return None
            company = config.company_id
        except AccessError:
            return None
        if company and company.id not in self._reachable_company_ids():
            return None
        blueprint = self._blueprint(config)
        if not blueprint or blueprint.state != 'editing':
            return None
        return {'ok': False, 'locked': True, 'reason': reason,
                'door': self._pay_logic_door(config)}

    # ==================================================================
    # Entering edit mode — the ONE write that does it
    # ==================================================================
    @api.model
    def bp_adopt(self, config_id):
        """Open an existing configuration in the journey, in edit mode.

        Idempotent, and it never touches pay logic: the components, the rate
        tables and the samples are not read here, let alone written. All this
        does is give the configuration the row the journey needs in order to
        remember which step somebody is on.

        A configuration that is still a DRAFT of the journey's own making is
        left exactly as it is and answers ``mode: 'create'`` — it opens as the
        ordinary six-step build, because that is what it is.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err

        if blueprint:
            if blueprint.state == 'draft':
                return {'ok': True, 'mode': 'create', 'created': False,
                        'config_id': config.id}
            if blueprint.state != 'editing':
                blueprint.write({'state': 'editing',
                                 'revision': blueprint.revision + 1})
            return {'ok': True, 'mode': 'edit', 'created': False,
                    'config_id': config.id}

        vals = {
            'config_id': config.id,
            'token': 'edit-%s' % config.id,
            'state': 'editing',
            'step': 'start',
            # There was no starter: this configuration was not built here. The
            # Start step says where it DID come from instead of naming a
            # starting point nobody chose.
            'template_key': False,
            'template_name': False,
            'effective_from': self._edit_effective_from(config),
        }
        try:
            with self.env.cr.savepoint():
                blueprint = self.env['pb.formula.blueprint'].create(vals)
        except Exception as exc:        # noqa: BLE001 — two presses at once
            # `unique(config_id)`: somebody else's press won the race. Theirs
            # is as good as ours, so take it rather than failing a click.
            blueprint = self._blueprint(config)
            if not blueprint:
                _logger.warning("Guided setup: could not open %s for editing: %s",
                                config.id, exc, exc_info=True)
                return {'ok': False, 'reason': self._plain(exc)}
        return {'ok': True, 'mode': 'edit', 'created': True,
                'config_id': config.id}

    def _edit_effective_from(self, config):
        """The first period this configuration is known to have been meant for.

        The earliest period it has actually paid, when it has paid anything —
        that is a fact rather than a guess. Otherwise the start of this month,
        which is what a person filling the field in by hand would type.
        """
        Payslip = self.env.get('hr.payslip')
        if (Payslip is not None and 'formula_config_id' in Payslip._fields
                and 'date_from' in Payslip._fields):
            slip = Payslip.sudo().search(
                [('formula_config_id', '=', config.id),
                 ('date_from', '!=', False)],
                order='date_from asc', limit=1)
            if slip and slip.date_from:
                return slip.date_from
        return fields.Date.context_today(self).replace(day=1)

    def _built_from(self, config, blueprint):
        """"Vietnam · Complete", or where this configuration actually came from.

        Replaces the starter cards in edit mode: the starting point of a
        configuration that already exists is history, not a choice, and a grid
        of pressable cards over a live payroll is an invitation to destroy it.
        """
        if blueprint and blueprint.template_name:
            return blueprint.template_name
        Batch = self.env.get('hr.payroll.import.batch')
        if Batch is not None and 'formula_config_id' in Batch._fields:
            try:
                if Batch.sudo().search_count(
                        [('formula_config_id', '=', config.id)]):
                    return _("Imported from a workbook")
            except Exception:           # noqa: BLE001 — a label, never a block
                pass
        return _("Built in the components grid")

    # ==================================================================
    # Reading it back
    # ==================================================================
    @api.model
    def bp_load(self, config_id):
        """As before — plus `needs_adopt` instead of a dead end, and no write.

        BP53: a read RPC that writes is a read RPC a person who may only LOOK
        at payroll setup cannot call. Answering "this has not been opened for
        editing yet" costs one extra round trip and keeps the read a read.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        if not blueprint:
            return {
                'ok': False,
                'needs_adopt': True,
                'config_id': config.id,
                'reason': _("This configuration was not created with the "
                            "guided setup. Open it for editing to carry on."),
            }
        return self._load_payload(config, blueprint)

    def _load_payload(self, config, blueprint):
        """The journey's payload, with everything edit mode needs on top."""
        payload = super()._load_payload(config, blueprint)
        if not payload.get('ok'):
            return payload
        locks = self._edit_locks(config, blueprint)
        state_labels = dict(config._fields['state'].selection)
        payload.update({
            'mode': 'edit' if blueprint.state == 'editing' else 'create',
            'locks': locks,
            'lock_reason': self._pay_logic_reason(config) if locks['pay_logic'] else '',
            'country_lock_reason': _(
                "This configuration has already paid people, so its country "
                "cannot be changed. The country decides the currency and the "
                "statutory rules.") if locks['country'] else '',
            'built_from': self._built_from(config, blueprint),
            'scheme_state': config.state,
            'scheme_state_label': state_labels.get(config.state, ''),
        })
        return payload

    # ==================================================================
    # The settings themselves — one contract, two screens
    # ==================================================================
    @api.model
    def bp_settings(self, config_id):
        """Everything the old Settings panel read, for the journey's cards."""
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        data = self.env['pb.formula.studio'].get_config_settings(config.id)
        if not data or not data.get('ok'):
            return {'ok': False, 'reason': _(
                "This configuration's settings could not be read. Reload the "
                "page to try again.")}
        values = dict(data.get('values') or {})
        # BP-R11 — the company is read-only everywhere in this journey, and a
        # value the screen cannot change has no business travelling to it.
        values.pop('company_id', None)
        meta = dict(data.get('meta') or {})
        meta.pop('companies', None)
        return {
            'ok': True,
            'values': values,
            'meta': meta,
            'status': data.get('status') or {},
            'approvals': data.get('approvals') or {},
            'locks': self._edit_locks(config, blueprint),
            'revision': blueprint.revision if blueprint else 0,
        }

    @api.model
    def bp_save_settings(self, config_id, values, revision=None):
        """Write settings to the live configuration, as the studio always has.

        Rule 8a. Nothing here touches a rule, a band, a calendar or a
        component; the pay-logic endpoints are gated separately and refuse.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        if blueprint and revision is not None and int(revision) != blueprint.revision:
            return {'ok': False, 'conflict': True, 'reason': _(
                "Someone else changed this configuration while you were "
                "editing. Reload to see their version.")}

        Studio = self.env['pb.formula.studio']
        locks = self._edit_locks(config, blueprint)
        values = dict(values or {})
        values.pop('company_id', None)

        if 'country_code' in values:
            wanted = (values.get('country_code') or '').upper()
            if not wanted or wanted == (config.country_code or '').upper():
                # Not a change at all — the client sends the whole card back.
                values.pop('country_code', None)
            elif locks['country']:
                return {'ok': False, 'reason': _(
                    "This configuration has already paid people, so its "
                    "country cannot be changed. The country decides the "
                    "currency and the statutory rules.")}

        allowed = set(Studio._CFG_FIELDS)
        values = {k: v for k, v in values.items() if k in allowed}
        if not values:
            return {'ok': True, 'saved': [], 'values': {},
                    'revision': blueprint.revision if blueprint else 0,
                    'name': config.name or '', 'code': config.code or ''}

        res = Studio.save_config_settings(config.id, values)
        if not res or not res.get('ok'):
            return {'ok': False, 'reason': (res or {}).get('msg') or _(
                "Those settings could not be saved.")}

        if blueprint:
            blueprint.revision += 1
        return {
            'ok': True,
            'saved': sorted(values.keys()),
            # Read back from the record, not echoed from the request: a value
            # the database normalised (a cleared many2one, a rounded number)
            # has to reach the screen as the database holds it.
            'values': self._settings_echo(config, values.keys()),
            'status': res.get('status') or {},
            'revision': blueprint.revision if blueprint else 0,
            'name': config.name or '',
            'code': config.code or '',
            'currency': config.currency_id.name or '',
            'country_code': config.country_code or '',
        }

    def _settings_echo(self, config, fieldnames):
        Studio = self.env['pb.formula.studio']
        out = {}
        for name in fieldnames:
            if name in Studio._CFG_M2O:
                out[name] = config[name].id or False
            elif name in Studio._CFG_M2M:
                out[name] = config[name].ids
            else:
                out[name] = config[name] if config[name] is not False else False
        return out

    # ==================================================================
    # Finishing a sitting
    # ==================================================================
    @api.model
    def bp_finish(self, config_id):
        """In edit mode this is "Save changes" — and it generates nothing.

        Every setting was already written as its card was committed, so this
        closes the sitting and hands back the door to the components grid. It
        does NOT activate, validate, regenerate or change the configuration's
        own state: an Active configuration is still Active afterwards.
        """
        config, blueprint, err = self._guard(config_id, require_blueprint=False)
        if err:
            return err
        if blueprint and blueprint.state == 'editing':
            blueprint.write({'state': 'finished', 'step': 'finish',
                             'revision': blueprint.revision + 1})
            door = self.bp_studio_action(config.id)
            return {'ok': True, 'mode': 'edit', 'config_id': config.id,
                    'already': False,
                    'action': door.get('action') if door.get('ok') else False}
        return super().bp_finish(config_id)

    # ==================================================================
    # The things edit mode must never do
    # ==================================================================
    @api.model
    def bp_restart(self, config_id, template_key):
        block = self._edit_mode_block(config_id, _(
            "This configuration already exists, so its components cannot be "
            "replaced from here. Change them in the components grid, where "
            "every change is versioned."))
        return block or super().bp_restart(config_id, template_key)

    @api.model
    def bp_discard(self, config_id):
        block = self._edit_mode_block(config_id, _(
            "This configuration exists in its own right, so there is nothing "
            "to discard. Retire it from the components grid instead."))
        return block or super().bp_discard(config_id)

    @api.model
    def bp_discard_check(self, config_id):
        """So the confirmation never opens on something that cannot be discarded."""
        block = self._edit_mode_block(config_id, _(
            "This configuration exists in its own right, so there is nothing "
            "to discard. Retire it from the components grid instead."))
        if block:
            config = self._config(config_id)
            return {'ok': True, 'allowed': False,
                    'name': config.name or '' if config else '',
                    'counts': self._finish_counts(config) if config else {},
                    'reason': block['reason']}
        return super().bp_discard_check(config_id)

    # ==================================================================
    # Pay logic: gated in BOTH modes (owner ruling 2026-09-19)
    # ==================================================================
    @api.model
    def bp_components(self, config_id, sample_id=None):
        """The component list, now saying whether it may be changed.

        The Tax and Calendar tabs have always carried `editable` and a reason;
        the Components tab never did, because it was only ever opened on a
        draft. A list that offers a Configure button over rules the server will
        refuse to save is a screen that lies, so the answer travels with the
        list — from the same lock the write endpoints enforce, never a second
        one.
        """
        res = super().bp_components(config_id, sample_id)
        if not isinstance(res, dict) or not res.get('ok'):
            return res
        config = self._config(config_id)
        if not config:
            return res
        locked = self._edit_locks(config)['pay_logic']
        res['editable'] = not locked
        res['readonly_reason'] = self._pay_logic_reason(config) if locked else ''
        return res

    @api.model
    def bp_component_save(self, config_id, rule_id, payload):
        return (self._pay_logic_block(config_id)
                or super().bp_component_save(config_id, rule_id, payload))

    @api.model
    def bp_component_exclude(self, config_id, rule_ids, confirm=False,
                             revision=None):
        return (self._pay_logic_block(config_id)
                or super().bp_component_exclude(config_id, rule_ids, confirm,
                                                revision))

    @api.model
    def bp_component_include(self, config_id, code, revision=None):
        return (self._pay_logic_block(config_id)
                or super().bp_component_include(config_id, code, revision))

    @api.model
    def bp_component_restore_guided(self, rule_id, revision=None):
        rule = self.env['hr.formula.rule'].browse(int(rule_id or 0))
        if rule.exists():
            block = self._pay_logic_block(rule.config_id.id)
            if block:
                return block
        return super().bp_component_restore_guided(rule_id, revision)

    @api.model
    def bp_regenerate(self, config_id, revision=None):
        return (self._pay_logic_block(config_id)
                or super().bp_regenerate(config_id, revision))

    @api.model
    def bp_tax_save_bands(self, config_id, table_id, brackets, revision=None):
        return (self._pay_logic_block(config_id)
                or super().bp_tax_save_bands(config_id, table_id, brackets,
                                             revision))

    @api.model
    def bp_tax_save_values(self, config_id, values=None, prefs=None,
                           revision=None):
        return (self._pay_logic_block(config_id)
                or super().bp_tax_save_values(config_id, values, prefs,
                                              revision))

    @api.model
    def bp_tax_sync_pack(self, config_id, revision=None):
        return (self._pay_logic_block(config_id)
                or super().bp_tax_sync_pack(config_id, revision))

    @api.model
    def bp_calendar_save(self, config_id, calendar=None, payment=None,
                         revision=None):
        return (self._pay_logic_block(config_id)
                or super().bp_calendar_save(config_id, calendar, payment,
                                            revision))
