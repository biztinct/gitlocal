# -*- coding: utf-8 -*-
"""Which field feeds which component, and how often it is fetched.

WHAT WAS TRUE BEFORE. A mapping decides where a number on a payslip comes
from. Turning one on, pointing it somewhere else, or moving the schedule that
fetches it changes what everybody is paid next month — and every one of those
was a press that wrote at once.

WHAT IS TRUE NOW. Five doors write a proposal (`pb.mapping.proposal`) and the
change happens when the route says yes:

  * the fetch SCHEDULE on a connector (how often, which day, what time);
  * ACTIVATING mappings — the promotion from "suggested" to "active", which is
    the moment a guess becomes load-bearing;
  * FETCHING the source system's field list, which creates mapping rows;
  * AUTO-MAPPING a row by name similarity;
  * REPAIRING severed mappings against the rename ledger.

WHAT IS NOT HELD, AND IS SAID OUT LOUD. The Mapping studio's own per-field
editors (`api_mapping_*`, `mapping_*`, `import_mapping_*`) still write when
they are pressed. They are a working surface with an undo of its own, and
holding each keystroke behind a route would make the screen unusable; the
moment those mappings become load-bearing — the activation above — IS held.
Grouping a whole studio session into one proposal is the remaining piece and
it is written down in the phase report rather than half-done here.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

MAPPING_PROCESS_KEY = 'mappings'

#: What changing a mapping has always needed.
MAPPING_GROUP = 'pb_hr_payroll_formula.group_formula_manager'

#: "This write IS the approved change."
MAPPING_WRITE = 'pb_mapping_approved_write'


class PbMappingProposal(models.Model):
    _name = 'pb.mapping.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed mapping change'

    _approval_process_key = MAPPING_PROCESS_KEY
    _proposal_prefix = 'MAP'
    _proposal_gate_groups = (MAPPING_GROUP,)
    _proposal_kind_labels = {
        'schedule': 'Change the fetch schedule',
        'activate': 'Make mappings load-bearing',
        'fetch_fields': 'Fetch the source field list',
        'auto_map': 'Point a mapping at a component',
        'repair': 'Repair severed mappings',
    }
    _proposal_fact_specs = {
        'mappings_changed': {'type': 'int', 'label': 'Mappings changed'},
        'activations': {'type': 'int', 'label': 'Mappings switched on'},
        'schedule_changed': {'type': 'bool', 'label': 'Schedule changed'},
    }

    # ------------------------------------------------------- the snapshot
    def _live_snapshot(self):
        self.ensure_one()
        target = self._target()
        if not target:
            return {}
        if self.kind == 'schedule':
            return {f: target[f] for f in sorted(
                (self.payload() or {}).get('values') or {})
                if f in target._fields}
        if self.kind == 'auto_map':
            return {'target_rule_id': target.target_rule_id.id}
        if self.kind == 'activate':
            return {'suggested': len(target.field_mapping_ids.filtered(
                lambda m: m.active_state == 'suggested'))}
        return {}

    def _target(self):
        self.ensure_one()
        if not self.target_model or not self.target_id \
                or self.target_model not in self.env:
            return None
        record = self.env[self.target_model].sudo().browse(
            self.target_id).exists()
        return record or None

    # ------------------------------------------------------------ the rows
    _SCHEDULE_WORDS = {
        'sync_frequency': 'How often it fetches',
        'sync_weekday': 'Which day of the week',
        'sync_day_of_month': 'Which day of the month',
        'sync_time': 'At what time',
    }

    def _proposal_rows(self):
        self.ensure_one()
        payload = self.payload() or {}
        snapshot = self.snapshot() or {}
        target = self._target()
        rows = []
        if target is not None:
            rows.append((_('Connection') if self.kind != 'auto_map'
                         else _('Mapping'), '', target.display_name or ''))
        if self.kind == 'schedule':
            for key, value in sorted((payload.get('values') or {}).items()):
                rows.append((_(self._SCHEDULE_WORDS.get(key, key)),
                             snapshot.get(key, ''), value))
        elif self.kind == 'activate':
            rows.append((_('Mappings waiting to be switched on'), '',
                         str(snapshot.get('suggested', ''))))
            rows.append((_('What happens'), '',
                         _('Each one that resolves to a value starts '
                           'feeding the payslip')))
        elif self.kind == 'fetch_fields':
            rows.append((_('What happens'), '',
                         _('The source system is asked what fields it has, '
                           'and a mapping row is made for each new one')))
        elif self.kind == 'auto_map':
            rows.append((_('What happens'), '',
                         _('The mapping is pointed at the component whose '
                           'name matches')))
        elif self.kind == 'repair':
            rows.append((_('Severed mappings to mend'), '',
                         str(len(payload.get('mapping_ids') or []))))
        return rows

    # --------------------------------------------------------- the applies
    def _apply_schedule(self):
        target = self._target()
        if not target:
            raise UserError(_("That connection no longer exists."))
        target.with_context(**{MAPPING_WRITE: True}).write(
            (self.payload() or {}).get('values') or {})
        return {'connector_id': target.id}

    def _apply_activate(self):
        target = self._target()
        if not target:
            raise UserError(_("That connection no longer exists."))
        return target.with_context(
            **{MAPPING_WRITE: True}).action_test_field_mappings(
                (self.payload() or {}).get('config_id'))

    def _apply_fetch_fields(self):
        target = self._target()
        if not target:
            raise UserError(_("That connection no longer exists."))
        target.with_context(
            **{MAPPING_WRITE: True}).action_fetch_available_fields()
        return {'connector_id': target.id,
                'fields': len(target.field_mapping_ids)}

    def _apply_auto_map(self):
        target = self._target()
        if not target:
            raise UserError(_("That mapping no longer exists."))
        target.with_context(**{MAPPING_WRITE: True}).action_auto_map()
        return {'mapping_id': target.id,
                'target_rule_id': target.target_rule_id.id}

    def _apply_repair(self):
        ids = (self.payload() or {}).get('mapping_ids') or []
        rows = self.env['hr.integration.field.mapping'].sudo().browse(
            [int(i) for i in ids]).exists()
        return rows.with_context(**{MAPPING_WRITE: True}).action_repair_severed()

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(
            company, 'payroll_mgr',
            ('pb_hr_payroll_base.group_payroll_base_manager',
             'pb_hr_payroll_formula.group_formula_manager'))
        return Seed.lay(
            company, MAPPING_PROCESS_KEY, 'Mapping and feed changes',
            route(role_step(_('Payroll manager'), 'payroll_mgr')),
            binding_note='The route a change to where pay data comes from '
                         'follows.',
            model_name='pb.mapping.proposal',
            role_keys=('payroll_mgr',),
            reason='Set up when mapping approvals were switched on')


# ======================================================================
# The doors
# ======================================================================
def _held(env):
    """Is anybody checking mapping changes on this database right now?"""
    if env.context.get(MAPPING_WRITE) or env.context.get('install_mode'):
        return False
    return 'pb.mapping.proposal' in env


class HrIntegrationConnectorApproval(models.Model):
    _inherit = 'hr.integration.connector'

    #: WHEN the fetch runs, and nothing else. `cron_pull_enabled` is
    #: deliberately NOT among them, for the reason `integration_cron.py`
    #: already gives: switching a fetch ON is not a change to WHEN it runs,
    #: it is a connector opting in at all — and holding it would mean the
    #: dispatcher never sees a connector somebody just turned on.
    _SC2_APPROVED_FIELDS = ('sync_frequency', 'sync_weekday',
                            'sync_day_of_month', 'sync_time')

    def write(self, vals):
        """A fetch schedule decides WHEN next month's pay data arrives."""
        touched = [f for f in (vals or {}) if f in self._SC2_APPROVED_FIELDS]
        if not touched or not _held(self.env) or not self:
            return super().write(vals)
        Proposal = self.env['pb.mapping.proposal']
        if Proposal.route_mode(company=self.env.company,
                               kind_key='schedule') != 'route':
            return super().write(vals)
        held = {f: vals[f] for f in touched}
        # The ORM's own constraints still get to refuse this, before anybody
        # is asked to agree to it.
        Proposal.precheck(self, held)
        for connector in self:
            Proposal.propose(
                'schedule',
                _("Fetch schedule · %s", connector.display_name or ''),
                payload={'values': held},
                snapshot={f: connector[f] for f in sorted(held)
                          if f in connector._fields},
                facts={'mappings_changed': {'value': 0, 'unit': ''},
                       'activations': {'value': 0, 'unit': ''},
                       'schedule_changed': {'value': True, 'unit': ''}},
                target=connector,
            )
        rest = {k: v for k, v in (vals or {}).items() if k not in held}
        if rest:
            return super().write(rest)
        return True

    def action_test_field_mappings(self, config_id=None):
        """Promotion to "active" is the moment a guess starts paying people."""
        self.ensure_one()
        if not _held(self.env):
            return super().action_test_field_mappings(config_id)
        suggested = len(self.field_mapping_ids.filtered(
            lambda m: m.active_state == 'suggested'))
        proposal = self.env['pb.mapping.proposal'].propose(
            'activate',
            _("Switch on %(n)s mapping(s) · %(who)s",
              n=suggested, who=self.display_name or ''),
            payload={'config_id': config_id},
            snapshot={'suggested': suggested},
            facts={'mappings_changed': {'value': suggested, 'unit': ''},
                   'activations': {'value': suggested, 'unit': ''},
                   'schedule_changed': {'value': False, 'unit': ''}},
            target=self,
        )
        answer = proposal.answer()
        if answer.get('applied'):
            return dict(answer.get('result') or {}, ok=True,
                        reference=answer.get('reference'))
        return dict(answer, ok=True, pending=True, promoted=0, tested=0,
                    msg=answer.get('message') or '')

    def action_fetch_available_fields(self):
        self.ensure_one()
        if not _held(self.env):
            return super().action_fetch_available_fields()
        proposal = self.env['pb.mapping.proposal'].propose(
            'fetch_fields',
            _("Read the field list · %s", self.display_name or ''),
            payload={'connector_id': self.id},
            facts={'mappings_changed': {'value': 0, 'unit': ''},
                   'activations': {'value': 0, 'unit': ''},
                   'schedule_changed': {'value': False, 'unit': ''}},
            target=self,
        )
        answer = proposal.answer()
        message = _("The field list was read.") if answer.get('applied') \
            else (answer.get('message') or '')
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'message': message,
                       'type': 'success' if answer.get('applied')
                       else 'info'},
        }


class HrIntegrationFieldMappingApproval(models.Model):
    _inherit = 'hr.integration.field.mapping'

    def action_auto_map(self):
        self.ensure_one()
        if not _held(self.env) or self.target_rule_id:
            return super().action_auto_map()
        proposal = self.env['pb.mapping.proposal'].propose(
            'auto_map',
            _("Point %s at a component", self.source_field or ''),
            payload={'mapping_id': self.id},
            snapshot={'target_rule_id': self.target_rule_id.id},
            facts={'mappings_changed': {'value': 1, 'unit': ''},
                   'activations': {'value': 0, 'unit': ''},
                   'schedule_changed': {'value': False, 'unit': ''}},
            target=self,
        )
        answer = proposal.answer()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': answer.get('message') or '',
                       'type': 'success' if answer.get('applied')
                       else 'info'},
        }

    def action_repair_severed(self):
        if not _held(self.env) or not self:
            return super().action_repair_severed()
        proposal = self.env['pb.mapping.proposal'].propose(
            'repair',
            _("Repair %s severed mapping(s)", len(self)),
            payload={'mapping_ids': self.ids},
            facts={'mappings_changed': {'value': len(self), 'unit': ''},
                   'activations': {'value': 0, 'unit': ''},
                   'schedule_changed': {'value': False, 'unit': ''}},
            target=self[:1],
        )
        answer = proposal.answer()
        if answer.get('applied'):
            return answer.get('result') or {'applied': 0, 'verdicts': []}
        return dict(answer, applied=0, verdicts=[], pending=True)


class ResCompanyMappingSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.mapping.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('mappings: %s has no route yet', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.mapping.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('mappings: %s has no route yet', company.name)
    return done
