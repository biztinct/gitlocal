# -*- coding: utf-8 -*-
"""Records (Master records) and so the Updates sheets (FS-5 item 2).

`pb.records.desk._master_fields` is the one seam both screens read
(FS_HOST_FACTS §C/§D): Updates' catalogue is `get_fields(0)` relabelled, its
sheet download, column match, review and apply all run on the same cards.

* Master records list the custom fields the reader may see
  (`fields_for(model, 'all')`, files left out — a sheet cell cannot carry a
  file). Writable where the person may write the record (the desk's own
  `_may_write` lock), written through the desk's normal path, so the
  approval route, the change log and Undo behave as for any field.
* EVERY desk mode (a pay scheme's mapped fields too) drops the card of a
  custom field the reader may not see, so neither its label nor its value
  reaches the grid, the sheet, the review or a forged apply (`_whitelist`
  reads `_cards`).
* Country of Work (R10): a cell of a field that does not apply to that
  person is blank and cannot be changed (refused in plain words).
"""
from odoo import api, models

from .common import CON, EMP, PREFIX


class RecordsDeskFormBuilder(models.AbstractModel):
    _inherit = 'pb.records.desk'

    @api.model
    def _master_fields(self):
        out = dict(super()._master_fields())
        Studio = self.env['pb.form.studio']
        for model in (EMP, CON):
            extra = tuple(s['name'] for s in Studio.fields_for(model, 'all')
                          if s['type'] != 'binary')
            if extra:
                out[model] = tuple(dict.fromkeys(tuple(out.get(model) or ()) + extra))
        return out

    @api.model
    def _cards(self, config_id):
        cards = super()._cards(config_id)
        Studio = self.env['pb.form.studio']
        for model in (EMP, CON):
            hidden = Studio._pbfr_hidden_names(model)
            for name in hidden:
                cards.pop('f:%s:%s' % (model, name), None)
        # A file field mapped by a scheme is never a sheet column either.
        for cid in [c for c, card in cards.items()
                    if cid_is_custom(c) and card.get('ttype') == 'binary']:
            cards.pop(cid, None)
        return cards

    @api.model
    def _pbfr_not_here(self, card, employee, contract, memo=None):
        """True when `card` is a custom field that does not apply to this
        person's Country of Work."""
        if card['id'][:1] != 'f' or not (card.get('field') or '').startswith(PREFIX):
            return False
        record = employee if card.get('model') == EMP else contract
        if not record:
            return False
        bucket = memo.setdefault('pbfr', {}) if isinstance(memo, dict) else {}
        return not self.env['pb.form.studio']._pbfr_applies(record, card['field'], bucket)

    @api.model
    def _read_cell(self, probe, card, employee, contract, memo=None):
        if self._pbfr_not_here(card, employee, contract, memo):
            # A blank cell — not "missing" (that word means "no contract" to
            # the desk); a change is then refused by `_coerce` below.
            return {'v': None, 'label': '', 'not_here': True}
        return super()._read_cell(probe, card, employee, contract, memo)

    @api.model
    def _coerce(self, probe, card, value, employee, contract, memo=None):
        if self._pbfr_not_here(card, employee, contract, memo):
            return None, '', self.env._(
                "%s does not apply to this person's country of work.", card['label'])
        return super()._coerce(probe, card, value, employee, contract, memo)


def cid_is_custom(card_id):
    return card_id.startswith('f:') and (':' + PREFIX) in card_id
