"""Generated monthly workbooks expose schema components, not adapter aliases."""
from odoo import api, models


class TemplateMapping(models.AbstractModel):
    _inherit = 'pb.formula.studio'

    @api.model
    def import_mapping_data(self, config_id=None, batch_id=None):
        data = super().import_mapping_data(config_id, batch_id)
        context_id = data.get('context_id')
        if not data.get('ok') or not isinstance(context_id, int) or isinstance(context_id, bool):
            return data
        batch = self.env['hr.payroll.import.batch'].browse(context_id).exists()
        if not batch or not batch._template_period():
            return data
        cfg = batch.formula_config_id
        facade = self.env['pb.payroll.templates']
        identities = facade._identity_columns(cfg)
        aliases = {}
        inputs = cfg.rule_ids.filtered(lambda r: r.column_type == 'input')
        names = inputs.mapped('name')
        for rule in inputs:
            label = rule.name or rule.code
            canonical = rule.code if names.count(rule.name) > 1 else label
            entry = (canonical, label, rule.source_sheet_name or '', rule.column_letter or '')
            keys = [s.key for s in rule.source_ids if s.kind == 'excel' and s.key]
            keys += batch._rule_header_candidates(rule, allow_column_letter=False)
            for key in keys:
                aliases.setdefault(key, entry)
        # Older internally generated files carried these five fixed helpers.
        # Fold only this proven engine format; user uploads keep every column.
        for kind, keys in [('code', ('Employee ID', 'employee_code')),
                           ('name', ('Employee name', 'employee_name'))]:
            column = next(c for c in identities if c['kind'] == kind)
            if column['rule_id']:
                for key in keys:
                    aliases.setdefault(key, (column['label'], column['label'], '', ''))
        raw = self._import_batch_row(batch)
        legacy_email = 'email' in raw and not any(r.name == 'email' or r.source_ids.filtered(
            lambda s: s.kind == 'excel' and s.key == 'email') for r in cfg.rule_ids)
        left, seen = [], set()
        for card in data['left']:
            cid = card['id']
            if cid.startswith('c:'):
                key = cid[2:]
                if key == 'email' and legacy_email:
                    continue
                entry = aliases.get(key)
                if entry:
                    canonical, label, sheet, letter = entry
                    card = dict(card, id='c:' + canonical, label=label)
                    if canonical != label:
                        card['meta'] = dict(card.get('meta') or {}, sheet=sheet, letter=letter)
                    cid = card['id']
            if cid not in seen:
                left.append(card)
                seen.add(cid)
        data['left'] = left
        for wire in data['wires']:
            source = str(wire.get('leftId') or '')
            if source.startswith('c:') and source[2:] in aliases:
                canonical = aliases[source[2:]][0]
                wire['leftId'] = 'c:' + canonical
                wire['source'] = canonical
        return data
