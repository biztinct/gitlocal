"""Focused payroll templates with explicitly reviewed master-record updates."""
from odoo import fields, models


class PayrollRecordInputSettings(models.Model):
    _inherit = 'hr.formula.config'

    focused_payroll_inputs = fields.Boolean(
        string='Focused payroll inputs and editable mapped records',
        help='Export only schema inputs. Mapped employee and contract inputs may be edited '
             'for the month and optionally submitted for a reviewed master-record update.')


class PayrollRecordInputs(models.AbstractModel):
    _inherit = 'pb.payroll.templates'

    def _identity_rules(self, cfg):
        roles = super()._identity_rules(cfg)
        if cfg.focused_payroll_inputs:
            for mapping in self.env['pb.records.desk']._mappings(cfg.id):
                if (mapping.target_model_id.model == 'hr.employee'
                        and mapping.target_field_id.name == 'identification_id'):
                    roles.pop(mapping.component_id.id, None)
        return roles

    def _cards(self, cfg):
        cards = super()._cards(cfg)
        if cfg.focused_payroll_inputs:
            # A national/tax identifier is a payroll input, not the workbook's
            # stable employee matching key (employee_id/barcode).
            for fid, card in self.env['pb.records.desk']._cards(cfg.id).items():
                if fid == 'f:hr.employee:identification_id':
                    cards[fid] = card
        return cards

    def _catalog(self, cfg):
        catalog = super()._catalog(cfg)
        if not cfg.focused_payroll_inputs:
            return catalog
        cards = self._cards(cfg)
        result = []
        for item in catalog:
            if not item['id'].startswith('rule:'):
                continue
            card = cards.get(item.get('record_id'), {})
            result.append(dict(item, record_editable=bool(
                item.get('readonly') and card.get('editable')
                and card['id'].startswith(('f:', 'c:')))))
        return result
