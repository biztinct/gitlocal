# -*- coding: utf-8 -*-
"""The "Employment contract" document kind on letter templates.

`selection_add` on `pb.letter.template.letter_type` ONLY — never on
`pb.hr.letter.letter_type` (a related field: adding to it breaks the
registry load, FACTS §1). The gallery group is added to the studio's two
group fields the same way.

Built-in settings of the shipped contracts. The shipped records carry only
words (data, noupdate); their "Show only when" rules, page and main
language are this module's defaults, used while the document has never been
saved in the studio (`pbds_edited` false). The first save stores them like
any other document's; "Put back the built-in wording" clears them and the
defaults apply again. (So installing this module writes no studio data on
any template — the studio's silent-install rule holds.)
"""
from odoo import api, fields, models

from .contract_common import (
    CONTRACT_KIND, CONTRACT_TYPE, SHIPPED, SHIPPED_PAGE, SHIPPED_RULES,
)


class PbLetterTemplate(models.Model):
    _inherit = 'pb.letter.template'

    letter_type = fields.Selection(
        selection_add=[(CONTRACT_TYPE, 'Employment contract')],
        ondelete={CONTRACT_TYPE: 'set default'})
    pbds_kind_set = fields.Selection(
        selection_add=[(CONTRACT_KIND, 'Employment contracts')],
        ondelete={CONTRACT_KIND: 'set null'})
    pbds_kind = fields.Selection(
        selection_add=[(CONTRACT_KIND, 'Employment contracts')])
    # Owner ruling 2026-11-24: shipped contract wording goes live with a
    # notice "Sample wording. Have your own lawyer check it before you use
    # it." wherever it is shown on screen (never printed). True on the
    # shipped contracts (data) and on copies made from them; the first
    # time the customer saves their own wording it goes away for good.
    pbdc_sample = fields.Boolean(
        string='Sample wording', copy=False,
        help='Payobook\'s sample contract wording that the customer has not yet '
             'made their own.')

    @api.depends('letter_type', 'pbds_kind_set', 'pbds_replaces_id')
    def _compute_pbds_kind(self):
        super()._compute_pbds_kind()
        for rec in self:
            if rec._pbdc_is_contract():
                rec.pbds_kind = CONTRACT_KIND

    def _pbdc_is_contract(self):
        """Is this an employment contract document (or a copy of one)?"""
        self.ensure_one()
        root = self.pbds_replaces_id or self
        return CONTRACT_TYPE in (self.letter_type, root.letter_type) \
            or CONTRACT_KIND in (self.pbds_kind_set, root.pbds_kind_set)

    def _pbdc_xmlid(self):
        """The shipped xml id of this record, or False."""
        self.ensure_one()
        if not isinstance(self.id, int):
            return False
        row = self.env['ir.model.data'].sudo().search(
            [('model', '=', 'pb.letter.template'), ('res_id', '=', self.id),
             ('module', '=', 'pb_doc_contracts')], limit=1)
        return '%s.%s' % (row.module, row.name) if row else False

    def _pbdc_builtin(self):
        """The built-in spec of a shipped contract that was never saved in
        the studio, else False."""
        self.ensure_one()
        if self.pbds_edited:
            return False
        return SHIPPED.get(self._pbdc_xmlid()) or False

    def _pbdc_rules(self):
        """The rules this document prints with (its own, else the built-in
        ones of a shipped contract)."""
        self.ensure_one()
        if self.pbds_rules:
            return self.pbds_rules
        return dict(SHIPPED_RULES) if self._pbdc_builtin() else {}

    def _pbdc_page(self):
        """The page design this document prints with (its own, else the
        built-in one of a contract)."""
        self.ensure_one()
        if self.pbds_page:
            return self.pbds_page
        return dict(SHIPPED_PAGE) if self._pbdc_is_contract() else {}

    def _pbds_main_lang(self):
        spec = self._pbdc_builtin() if not self.pbds_main_lang else False
        if spec and spec.get('main_lang'):
            active = self.env['pb.doc.studio']._pbds_active_langs()
            if spec['main_lang'] in active:
                return spec['main_lang']
        return super()._pbds_main_lang()

    def _pbds_is_studio(self):
        """A contract is always printed by the studio (its paragraphs follow
        rules and its page has no letter signature block)."""
        return super()._pbds_is_studio() or self._pbdc_is_contract()

