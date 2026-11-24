# -*- coding: utf-8 -*-
"""The Document studio learns offer letters (phase A1).

Through the extension points of `pb.doc.studio` only (F report §4 / C3):
`_template`, `_pbds_templates`, `_pbds_catalogue`, `_pbds_condition_meta`
(+ `_light`), `_pbds_sample_person`, `_pbds_card`, `board`, `open`, `save`,
`preview`, `sample_pdf`, `create_blank`. Nothing of `pb_doc_studio` is
edited.

An offer has no employee: the designer previews with a REAL OFFER the user
may read (record rules of Hiring, never sudo), and its fields are the offer's
own (Hiring's placeholders). Every call still starts with the studio's own
`_require` (write access on the letter library).
"""
import base64
import logging

from lxml import etree, html as lxml_html
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html_sanitize

from odoo.addons.pb_doc_studio.models.doc_common import MAIN_LANG

from .offer_common import (
    BLOCK_KEYS, COND_KEYS, COND_LABELS, FIELD_KEYS, FIELD_LABELS, GROUP_KEYS,
    GROUP_LABELS, HIRING, KIND_CTX, OFFER, _lt,
)

_logger = logging.getLogger(__name__)

HIRING_LABEL = _lt('Hiring')
GROUP_HIRING_USER = 'pb_hiring.group_hiring_user'


class PbDocStudioOffer(models.AbstractModel):
    _inherit = 'pb.doc.studio'

    # ============================================================ helpers
    @api.model
    def _pbds_offer_tmpl(self, template_id):
        """The template when it is an offer letter, else an empty record."""
        try:
            tid = int(template_id or 0)
        except (TypeError, ValueError):
            tid = 0
        tmpl = self.env['pb.letter.template'].sudo().with_context(
            active_test=False).browse(tid).exists()
        return tmpl if tmpl and tmpl.letter_type == OFFER else tmpl.browse()

    @api.model
    def _pbds_as_offer(self):
        return self.with_context(**{KIND_CTX: OFFER})

    @api.model
    def _pbds_offer_for(self, offer_id):
        """A real offer to preview with, read AS THE CALLER (Hiring's record
        rules decide; never sudo)."""
        try:
            oid = int(offer_id or 0)
        except (TypeError, ValueError):
            oid = 0
        offer = self.env['pb.hiring.offer'].browse(oid).exists()
        if not offer:
            raise UserError(self.env._("Choose an offer to preview with."))
        try:
            offer.check_access('read')
        except AccessError:
            raise AccessError(self.env._(
                "You may not see this offer. Ask your administrator for Hiring "
                "access."))
        return offer

    # ============================================================ rights
    @api.model
    def _template(self, template_id, mode='write'):
        """Offer letters are documents of the studio now (F's `NOT_HERE_YET`
        kept them out while Hiring rendered them alone)."""
        if self._pbds_offer_tmpl(template_id):
            self._require()
            tmpl = self.env['pb.letter.template'].with_context(
                active_test=False).browse(int(template_id))
            tmpl.check_access(mode)
            return tmpl
        return super()._template(template_id, mode)

    @api.model
    def _pbds_templates(self):
        Template = self.env['pb.letter.template'].with_context(active_test=False)
        return super()._pbds_templates() | Template.search([('letter_type', '=', OFFER)])

    # ============================================================ fields
    @api.model
    def _pbds_catalogue(self, tmpl):
        """An offer letter's fields are the offer's own."""
        if not tmpl or tmpl.letter_type != OFFER:
            return super()._pbds_catalogue(tmpl)
        _ = self.env._
        flat = {}
        for (key, group), label in zip(FIELD_KEYS, FIELD_LABELS):
            flat[key] = {'key': key, 'label': _(label), 'group': group, 'pay': False}
            if key in BLOCK_KEYS:
                flat[key]['block'] = True
        # A field the wording uses that an offer does not have (a letter's
        # field pasted in, a misspelling): it prints nothing — said in amber.
        for key in self._pbds_used_keys(tmpl):
            if key not in flat:
                flat[key] = {'key': key,
                             'label': key.replace('_', ' ').strip().capitalize() or key,
                             'group': 'document', 'pay': False, 'missing': True}
        groups = {g: [] for g in GROUP_KEYS}
        for spec in flat.values():
            groups.setdefault(spec['group'], []).append(spec)
        out = [{'key': g, 'label': _(label), 'fields': groups.get(g, [])}
               for g, label in zip(GROUP_KEYS, GROUP_LABELS) if groups.get(g)]
        return out, flat

    # ============================================================ rules
    @api.model
    def _pbds_offer_conditions(self, rows):
        if self.env.context.get(KIND_CTX) != OFFER:
            return rows
        labels = dict(zip(COND_KEYS, COND_LABELS))
        by_key = {r['key']: r for r in rows}
        out = []
        for key in COND_KEYS:
            if key in by_key:
                row = dict(by_key[key])
                if 'label' in row:
                    row['label'] = self.env._(labels[key])
                out.append(row)
        return out

    @api.model
    def _pbds_condition_meta(self):
        """For an offer: country, company, department, job, employment type
        (the job's employment type) — what a role can be told apart by."""
        return self._pbds_offer_conditions(super()._pbds_condition_meta())

    @api.model
    def _pbds_condition_meta_light(self):
        return self._pbds_offer_conditions(super()._pbds_condition_meta_light())

    # ============================================================ gallery
    @api.model
    def _pbds_card(self, tmpl, flat=None):
        card = super()._pbds_card(tmpl, flat)
        if tmpl.letter_type == OFFER:
            _ = self.env._
            card['prints_for'] = _("Printed when an offer is prepared in Hiring")
            try:
                card['uses'] = self.env['pb.hiring.offer'].search_count(
                    [('letter_template_id', '=', (tmpl.pbds_replaces_id or tmpl).id)])
            except AccessError:
                card['uses'] = False
            card['uses_text'] = _("Used by 1 offer") if card['uses'] == 1 else (
                _("Used by %s offers", card['uses']) if card['uses'] else '')
        return card

    @api.model
    def board(self):
        res = super().board()
        kinds = [k for k in res['kinds'] if k['key'] != HIRING]
        res['kinds'] = [{'key': HIRING, 'label': self.env._(HIRING_LABEL)}] + kinds
        order = [k['key'] for k in res['kinds']]
        # Stable: copies stay right after the document they copy.
        res['cards'].sort(key=lambda c: order.index(c['kind']) if c['kind'] in order else 99)
        return res

    @api.model
    def create_blank(self, kind, name=None):
        if kind != HIRING:
            return super().create_blank(kind, name)
        _ = self.env._
        res = super().create_blank('other', str(name or '').strip() or _('New offer letter'))
        tmpl = self.env['pb.letter.template'].browse(res['id'])
        body = '<p>%s</p><p>%s</p><p>${lines}</p><p>%s</p>' % (
            _('Dear ${candidate_name},'),
            _('We are pleased to offer you the role of ${job_title}, starting on ${start_date}.'),
            _('Kind regards,'))
        tmpl.with_context(lang=MAIN_LANG).write({
            'letter_type': OFFER, 'pbds_kind_set': HIRING, 'body_html': body,
            'pbds_original_json': False, 'pbds_original_html': False,
        })
        # Its "built-in wording" is the offer wording it starts from.
        self._pbds_snapshot_original(tmpl)
        return res

    # ============================================================ designer
    @api.model
    def _pbds_sample_person(self, tmpl):
        """An offer letter previews with the newest offer the user may read
        (the document's company first)."""
        if not tmpl or tmpl.letter_type != OFFER:
            return super()._pbds_sample_person(tmpl)
        Offer = self.env['pb.hiring.offer']
        domain = [('company_id', 'in', self.env.companies.ids)]
        if tmpl.company_id:
            domain = [('company_id', '=', tmpl.company_id.id)]
        try:
            offer = Offer.search(domain + [('line_ids', '!=', False)], limit=1, order='id desc') \
                or Offer.search(domain, limit=1, order='id desc')
        except AccessError:
            return False
        return offer._pbds_offer_card() if offer else False

    @api.model
    def open(self, template_id):
        if not self._pbds_offer_tmpl(template_id):
            res = super().open(template_id)
            res['preview_kind'] = 'person'
            return res
        res = super(PbDocStudioOffer, self._pbds_as_offer()).open(template_id)
        res['preview_kind'] = OFFER
        res['offer_access'] = self.env.user.has_group(GROUP_HIRING_USER)
        return res

    @api.model
    def save(self, template_id, payload):
        if not self._pbds_offer_tmpl(template_id):
            return super().save(template_id, payload)
        return super(PbDocStudioOffer, self._pbds_as_offer()).save(template_id, payload)

    @api.model
    def offers(self, term=''):
        """Offers the caller may read (Hiring's record rules, no sudo) — the
        "preview with" list of an offer letter."""
        self._require()
        term = str(term or '').strip()[:80]
        domain = [('company_id', 'in', self.env.companies.ids)]
        if term:
            domain += ['|', '|', ('candidate_name', 'ilike', term), ('name', 'ilike', term),
                       ('job_title', 'ilike', term)]
        try:
            offers = self.env['pb.hiring.offer'].search(domain, limit=12, order='id desc')
        except AccessError:
            return []
        return [o._pbds_offer_card() for o in offers]

    # ------------------------------------------------------------ preview
    @api.model
    def _pbds_offer_parts(self, template_id, draft, offer_id, lang):
        tmpl = self._template(template_id, 'read')
        offer = self._pbds_offer_for(offer_id)
        active = self._pbds_active_langs()
        asked = lang if lang in active else offer._pbds_offer_lang()
        body, heading, rules, page, read_lang = self._pbds_draft_parts(tmpl, draft, asked)
        return tmpl, offer, asked, body, heading, rules, page, read_lang

    @api.model
    def preview(self, template_id, draft, employee_id, lang=None):
        """For an offer letter, `employee_id` is the OFFER picked in "preview
        with" (the same call shape as a letter, so the screen stays one)."""
        if not self._pbds_offer_tmpl(template_id):
            return super().preview(template_id, draft, employee_id, lang)
        self = self._pbds_as_offer()
        _ = self.env._
        tmpl, offer, asked, body, heading, rules, page, lang = self._pbds_offer_parts(
            template_id, draft, employee_id, lang)
        _groups, flat = self._pbds_catalogue(tmpl)
        missing = []

        def chip(key):
            spec = flat.get(key) or {}
            label = spec.get('label') or key
            if spec.get('missing') or not spec:
                text = _('A field that no longer exists')
            else:
                text = _('No %s on this offer', label.lower())
            missing.append({'key': key, 'label': label, 'why': 'pbds-miss', 'text': text})
            return '<span class="pbds-miss">%s</span>' % escape(text)

        def wrap(key, value):
            if value in (None, ''):
                return value
            return '<span class="pbds-v pbds-k-%s">%s</span>' % (key, value)

        html, hidden = offer._pbds_offer_render(tmpl, body, lang, rules=rules, ghost=True,
                                                missing=chip, wrap=wrap)
        values = {}
        for key, val in offer._pbds_offer_values(lang).items():
            if key not in flat or val in (None, ''):
                continue
            if key in BLOCK_KEYS:
                n = len(offer.line_ids)
                values[key] = _('1 line') if n == 1 else _('%s lines', n)
                continue
            try:
                values[key] = lxml_html.fromstring('<div>%s</div>' % val).text_content()
            except (etree.ParserError, ValueError):
                values[key] = str(val)
        company = (offer.company_id or self.env.company).sudo()
        sign = self._pbds_draft_sign(tmpl, draft) if page['sign'] == 'image' else False
        body_markup = Markup(html_sanitize(html)) + offer._pbds_sign_html(
            page, lang, sign, company, offer.candidate_name)
        frame = self.env['ir.qweb']._render('pb_doc_studio.page_frame', {
            'page': dict(page, sign='off'),
            'company': company,
            'body': body_markup,
            'subject': heading or tmpl.with_context(lang=lang).name,
            'date_text': self._pbds_long_date(fields.Date.context_today(self), lang),
            'mode': 'screen',
            'doc_lang': lang,
            'company_card': self._pbds_company_card(company),
            'env': self.env,
        })
        seen, unique = set(), []
        for row in missing:
            if row['key'] not in seen:
                seen.add(row['key'])
                unique.append(row)
        return {'html': str(frame), 'hidden': hidden, 'missing': unique,
                'values': values, 'lang': asked, 'read_lang': lang}

    @api.model
    def sample_pdf(self, template_id, draft, employee_id, lang=None):
        """The true PDF of an offer letter for one real offer, from the draft:
        nothing is stored on the offer, nothing is sent."""
        if not self._pbds_offer_tmpl(template_id):
            return super().sample_pdf(template_id, draft, employee_id, lang)
        self = self._pbds_as_offer()
        _ = self.env._
        tmpl, offer, _asked, body, heading, rules, page, lang = self._pbds_offer_parts(
            template_id, draft, employee_id, lang)
        html, _hidden = offer._pbds_offer_render(tmpl, body, lang, rules=rules)
        sign = self._pbds_draft_sign(tmpl, draft) if page['sign'] == 'image' else False
        sample = [offer._pbds_offer_page(tmpl, page, lang, html_sanitize(html), heading, sign)]
        report = self._pbds_report(page)
        try:
            pdf, _ext = report.with_context(lang=lang)._render_qweb_pdf(
                report, res_ids=None, data={'pbds_sample': sample})
        except Exception:                              # noqa: BLE001
            _logger.exception('pb_doc_studio_hiring: sample offer PDF of template %s failed', tmpl.id)
            return {'ok': False, 'msg': _(
                "The PDF could not be made right now. Try again in a moment; "
                "the preview on screen is exactly what will print.")}
        name = '%s — %s.pdf' % (tmpl.with_context(lang=lang).name or _('Offer letter'),
                                 offer.candidate_name or offer.name)
        return {'ok': True, 'name': name.replace('/', '-'),
                'data': base64.b64encode(pdf).decode()}

