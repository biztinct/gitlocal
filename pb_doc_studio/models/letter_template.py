# -*- coding: utf-8 -*-
"""What the Document studio stores on a letter template.

Nothing here is written at install (rail R5): every field starts empty, and a
template with no studio data is printed exactly as before (rail R1,
`pb.hr.letter._pbds_is_studio`).
"""
from odoo import api, fields, models

from .doc_common import KIND_KEYS, KIND_SELECTION, MAIN_LANG, MODULE_KIND, TYPE_KIND


class PbLetterTemplate(models.Model):
    _inherit = 'pb.letter.template'

    # "Show only when..." rules, keyed by the id written in the body as the
    # class `pbds-r-<id>`: {"r1": {"match": "all"|"any",
    #                             "lines": [{"field", "op", "value"}]}}
    pbds_rules = fields.Json(string='Show-only-when rules', copy=True)
    # Page design (contract C3): see `pb.doc.studio.page_styles()`.
    pbds_page = fields.Json(string='Page design', copy=True)
    pbds_sign_image = fields.Binary(string='Signature image', attachment=True,
                                    copy=True)
    pbds_version_ids = fields.One2many('pb.doc.version', 'template_id',
                                       string='Language versions')
    # Company / country copies (F7).
    pbds_replaces_id = fields.Many2one(
        'pb.letter.template', string='Copy of', index=True, ondelete='cascade',
        help='The letter this one replaces for the companies and countries '
             'it is for.')
    pbds_variant_ids = fields.One2many('pb.letter.template', 'pbds_replaces_id',
                                       string='Copies')
    pbds_country_ids = fields.Many2many(
        'res.country', 'pb_doc_studio_template_country_rel', 'template_id',
        'country_id', string='Countries of work')
    # Edited in the studio, and the wording it had before (rail R6).
    pbds_edited = fields.Boolean(string='Edited in the Document studio',
                                 copy=False)
    pbds_original_html = fields.Html(string='Built-in wording', sanitize=False,
                                     copy=False)
    # The raw stored value of the translated columns before the first edit:
    # "Put back the built-in wording" writes it back as it was, every language
    # included, so an untouched letter is byte-identical again.
    pbds_original_json = fields.Json(string='Built-in wording, stored', copy=False)
    pbds_undo = fields.Json(string='Undo of the last reset', copy=False)
    pbds_changed_by = fields.Many2one('res.users', string='Changed by',
                                      copy=False)
    pbds_changed_on = fields.Datetime(string='Changed on', copy=False)
    # F-b ruling 3: the language the main wording is written in (empty =
    # English, as before). The text itself stays in the template's own body.
    pbds_main_lang = fields.Char(string='Main wording language', copy=True)
    # The gallery group a document created in the studio was made for.
    pbds_kind_set = fields.Selection(KIND_SELECTION, string='Shown under', copy=True)
    pbds_kind = fields.Selection(KIND_SELECTION, compute='_compute_pbds_kind',
                                 string='Group')

    @api.depends('letter_type', 'pbds_kind_set', 'pbds_replaces_id')
    def _compute_pbds_kind(self):
        xmlids = self._pbds_xmlid_modules()
        for rec in self:
            root = rec.pbds_replaces_id or rec
            kind = rec.pbds_kind_set or root.pbds_kind_set \
                or MODULE_KIND.get(xmlids.get(root.id)) \
                or TYPE_KIND.get(rec.letter_type) or 'other'
            rec.pbds_kind = kind if kind in KIND_KEYS else 'other'

    def _pbds_xmlid_modules(self):
        """{template id: module that shipped it} for these and their roots."""
        ids = set(self.ids) | set(self.mapped('pbds_replaces_id').ids)
        ids = [i for i in ids if isinstance(i, int)]
        if not ids:
            return {}
        rows = self.env['ir.model.data'].sudo().search_read(
            [('model', '=', 'pb.letter.template'), ('res_id', 'in', ids)],
            ['module', 'res_id'])
        return {r['res_id']: r['module'] for r in rows}

    def _pbds_main_lang(self):
        """The language the main wording is written in (F-b ruling 3)."""
        self.ensure_one()
        return self.pbds_main_lang or MAIN_LANG

    def _pbds_wording_note(self):
        """"Using DEMO B's wording for Indonesia" — said wherever a letter
        shows the document it uses, when that document is a company or
        country copy (F-b ruling 1)."""
        self.ensure_one()
        if not self.pbds_replaces_id:
            return False
        _ = self.env._
        company = self.company_id.name
        countries = ', '.join(self.pbds_country_ids.mapped('name'))
        if company and countries:
            return _("Using %(company)s's wording for %(countries)s",
                     company=company, countries=countries)
        if company:
            return _("Using %s's wording", company)
        if countries:
            return _("Using the wording for %s", countries)
        return False

    def _pbds_is_studio(self):
        """Does the studio decide how this template prints? (rail R1)"""
        self.ensure_one()
        return bool(self.pbds_edited or self.pbds_page or self.pbds_rules
                    or self.pbds_version_ids or self.pbds_replaces_id)


class PbDocVersion(models.Model):
    """The wording of a document in one language other than the main one.

    The main wording stays in the template's own `body_html`; a version is a
    whole separate wording (not a term-by-term translation), so a Vietnamese
    letter can be built differently from the English one (ledger DS-1).
    """
    _name = 'pb.doc.version'
    _description = 'Document wording in one language'
    _order = 'template_id, lang'

    template_id = fields.Many2one('pb.letter.template', required=True,
                                  index=True, ondelete='cascade')
    lang = fields.Char(string='Language', required=True)
    subject = fields.Char(string='Heading')
    body_html = fields.Html(string='Wording', translate=False, sanitize=True)
    company_id = fields.Many2one(related='template_id.company_id', store=True,
                                 index=True)

    _lang_unique = models.Constraint(
        'unique(template_id, lang)',
        'A document has one wording per language.')
