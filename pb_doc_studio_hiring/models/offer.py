# -*- coding: utf-8 -*-
"""An offer prepared in Hiring uses the Document studio.

ONE SEAM, on `pb.hiring.offer`: `action_prepare_letter` / `_make_pdf`.

* The letter is chosen as Hiring chooses it (`letter_template_id`: the
  name-based pick, a cost profile, or a recruiter's choice), then the
  company / country copy rule of the studio applies ON TOP of it
  (`pb.hr.letter._pbds_pick_variant`, the same ranking every letter uses).
* A letter the studio never touched goes to Hiring's own code, unchanged:
  rail R1, byte-identical (test A1-02).
* A studio letter is read through the studio's own pipeline: the wording in
  the candidate's language (`pb.hr.letter._pbds_source`), "Show only when"
  paragraphs on the offer's facts (`doc_render.apply_rules`), the offer's
  own values (Hiring's `_placeholder_values`) filled by
  `doc_render.substitute`, the page design of the studio's report
  (`pb_doc_studio.report_doc_letter` + `page_frame`, contract C3).
* The PDF is rendered AS THE CALLER, never with `sudo()` (Hiring's R89);
  only the wording of the letter library is read as the system, as Hiring
  already does.
"""
import base64
import logging
import re

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import is_html_empty

from odoo.addons.pb_doc_studio.models.doc_common import MAIN_LANG
from odoo.addons.pb_doc_studio.models.doc_render import apply_rules, substitute
from odoo.addons.pb_hiring.models.hiring_common import slug_filename

from .offer_common import BLOCK_KEYS, KIND_CTX, OFFER, PERIOD_KEYS, PERIOD_LABELS

_logger = logging.getLogger(__name__)

#: `${lines}` alone in a paragraph: the table replaces the paragraph (a table
#: inside a <p> is not valid HTML; the editor drops a block chip on its own
#: line).
LINES_P_RE = re.compile(r'<p\b[^>]*>\s*(?:<br\s*/?>\s*)*\$\{lines\}\s*(?:<br\s*/?>\s*)*</p>', re.I)


class PbHiringOfferDocStudio(models.Model):
    _inherit = 'pb.hiring.offer'

    pbds_lang = fields.Char(
        string='Letter language', readonly=True, copy=False,
        help='The language the offer letter was written in the last time it '
             'was prepared.')
    pbds_lang_name = fields.Char(
        string='Letter written in', compute='_compute_pbds_lang_name')
    # Owner ruling (A1 follow-up): the recruiter may choose the letter's
    # language before it goes out; empty = automatic.
    pbds_letter_lang = fields.Selection(
        selection='_pbds_letter_lang_selection', string='Letter language',
        copy=False,
        help='Leave empty to write the letter in the language the candidate '
             'applied in, or in the company\'s language when that is not '
             'known. Choose a language to write it in that language instead; '
             'press "Write the letter" again afterwards.')
    pbds_wording_note = fields.Char(
        string='Wording used', compute='_compute_pbds_wording_note',
        help='Which wording the letter uses when a company or country has its '
             'own copy of the offer letter.')

    @api.depends('pbds_lang')
    def _compute_pbds_lang_name(self):
        names = dict(self.env['res.lang'].sudo().get_installed())
        for rec in self:
            rec.pbds_lang_name = names.get(rec.pbds_lang, rec.pbds_lang) if rec.pbds_lang else False

    def _compute_pbds_wording_note(self):
        for rec in self:
            tmpl = rec._pbds_offer_template()
            rec.pbds_wording_note = tmpl._pbds_wording_note() \
                if tmpl and tmpl != rec.letter_template_id.sudo() else False

    # ================================================================ choice
    def _pbds_offer_country(self):
        """The country the role is in: the hiring request's country, else the
        company's (the same order as Hiring's own letter pick)."""
        self.ensure_one()
        req = self.requisition_id.sudo()
        return req.country_id or self.company_id.sudo().country_id

    def _pbds_offer_template(self):
        """The wording this offer prints: the letter Hiring picked, swapped for
        the most specific ACTIVE company / country copy of it (copies always
        win, F-b ruling 1). Read as the system — the letter library is not a
        secret (Hiring reads it the same way)."""
        self.ensure_one()
        tmpl = self.letter_template_id.sudo().with_context(active_test=False)
        if not tmpl:
            return tmpl
        Template = self.env['pb.letter.template'].sudo().with_context(active_test=False)
        root = tmpl.pbds_replaces_id or tmpl
        variants = Template.search([('pbds_replaces_id', '=', root.id), ('active', '=', True)])
        if not variants and not tmpl.pbds_replaces_id:
            return tmpl
        # `_pbds_pick_variant` reads only `.company_id` of the person: the
        # offer answers it for the role (duck-typed, no second ranking).
        return self.env['pb.hr.letter']._pbds_pick_variant(
            tmpl, self.sudo(), variants, self._pbds_offer_country().id or False)

    @api.model
    def _pbds_letter_lang_selection(self):
        return [(code, name) for code, name in self.env['res.lang'].sudo().get_installed()]

    def _pbds_known_lang(self):
        """The candidate's language when it is KNOWN (owner ruling): the
        recruiter's own choice on the offer, else the language the candidate
        applied in on the careers page (`hr.applicant.pb_lang`). The contact
        card's language is NOT used (it is usually the recruiter's screen
        language). Only a language in use here counts. False when unknown."""
        self.ensure_one()
        active = self.env['pb.doc.studio']._pbds_active_langs()
        app = self.applicant_id.sudo()
        for lang in (self.pbds_letter_lang,
                     app.pb_lang if app and 'pb_lang' in app._fields else False):
            if lang and lang in active:
                return lang
        return False

    def _pbds_offer_lang(self):
        """The language the letter is written in: the known language
        (`_pbds_known_lang`), else the hiring company's language."""
        self.ensure_one()
        active = self.env['pb.doc.studio']._pbds_active_langs()
        candidates = [self._pbds_known_lang(), self.company_id.sudo().partner_id.lang]
        for lang in candidates:
            if lang and lang in active:
                return lang
        return MAIN_LANG if MAIN_LANG in active else (sorted(active) or [MAIN_LANG])[0]

    @api.model
    def _pbds_source_for(self, tmpl, lang):
        """`(body, heading, lang it reads in)` — the studio's own reading order
        (`pb.hr.letter._pbds_source`), reused on an unsaved letter that only
        carries the template."""
        letter = self.env['pb.hr.letter'].sudo().new({'template_id': tmpl.id})
        return letter._pbds_source(lang)

    # ================================================================ facts
    def _pbds_offer_facts(self):
        """What a "Show only when" rule asks about an offer."""
        self.ensure_one()
        req = self.requisition_id.sudo()
        job = req.job_id
        return {
            'country_of_work': self._pbds_offer_country().id or False,
            'company': self.company_id.id or False,
            'department': req.department_id.id or False,
            'job': job.id or False,
            'contract_type': job.contract_type_id.id
            if job and 'contract_type_id' in job._fields and job.contract_type_id else False,
        }

    @api.model
    def _pbds_offer_meta(self):
        studio = self.env['pb.doc.studio'].with_context(**{KIND_CTX: OFFER})
        return {m['key']: m for m in studio._pbds_condition_meta_light()}

    # ================================================================ values
    def _pbds_lines_table(self, lang):
        """The pay lines as one table, in the letter's language. The same
        lines, order and money as Hiring's `${lines}`; headings and "how
        often" are written in the letter's language."""
        self.ensure_one()
        local = self.with_context(lang=lang)
        env = local.env
        Line = env['pb.hiring.offer.line']
        periods = dict(Line._fields['period']._description_selection(env))
        periods.update({k: env._(label) for k, label in zip(PERIOD_KEYS, PERIOD_LABELS)})
        cell = 'padding:5px 8px; border:1px solid #c9ced8;'
        head = 'padding:5px 8px; border:1px solid #c9ced8; background:#f3f4f8; font-weight:700;'
        rows = [Markup(
            '<tr><td style="%(c)s">%(what)s</td>'
            '<td style="%(c)s text-align:right; white-space:nowrap;">%(amount)s</td>'
            '<td style="%(c)s color:#64748b;">%(when)s</td></tr>') % {
                'c': cell,
                'what': ln.name or '',
                'amount': local._money(ln.amount),
                'when': periods.get(ln.period, ''),
            } for ln in local.line_ids.sorted(lambda r: (r.sequence, r.id))]
        if not rows:
            return Markup('')
        return Markup(
            '<table class="pbdh-lines" style="border-collapse:collapse; width:100%%; margin:6px 0 12px;">'
            '<thead><tr><th style="%(h)s text-align:left;">%(what)s</th>'
            '<th style="%(h)s text-align:right;">%(amount)s</th>'
            '<th style="%(h)s text-align:left;">%(when)s</th></tr></thead>'
            '<tbody>%(rows)s</tbody></table>') % {
                'h': head,
                'what': env._('Pay item'),
                'amount': env._('Amount'),
                'when': env._('How often'),
                'rows': Markup('').join(rows),
            }

    def _pbds_offer_values(self, lang):
        """`{key: escaped text}` — Hiring's own values of the offer (its
        `_placeholder_values`, read in the letter's language) + the pay lines
        table."""
        self.ensure_one()
        local = self.with_context(lang=lang)
        values = dict(local._placeholder_values())
        table = local._pbds_lines_table(lang)
        if hasattr(local, '_pbpb_letter'):
            table = local._pbpb_letter(table)
        values['lines'] = str(table)
        return values

    def _pbds_offer_render(self, tmpl, body, lang, rules=None, ghost=False,
                           missing=None, wrap=None):
        """`(html, hidden)` of `body` for this offer, in `lang`. The real letter
        (no `missing`): hidden paragraphs removed, an empty field prints
        nothing. The preview passes `ghost`, `missing` and `wrap`."""
        self.ensure_one()
        if rules is None:
            rules = tmpl.pbds_rules or {}
        html, hidden, _bad = apply_rules(
            body, rules, self._pbds_offer_facts(), self._pbds_offer_meta(),
            ghost=ghost, log_ref='offer %s / template %s' % (self.id, tmpl.id))
        html = LINES_P_RE.sub('${lines}', html or '')
        values = self._pbds_offer_values(lang)
        if wrap:
            values = {k: (v if k in BLOCK_KEYS else wrap(k, v)) for k, v in values.items()}
        html = substitute(html, values, missing=missing)
        return html, hidden

    # ================================================================ page
    @api.model
    def _pbds_sign_html(self, page, lang, sign_image, company, candidate):
        """The company's signature block (as the page design says) and the
        candidate's line under it — the offer's two signatures, drawn with
        the studio's own classes so the page design applies to both."""
        studio = self.env['pb.doc.studio']
        pv = studio.page_values(page, lang)
        local = self.with_context(lang=lang).env
        out = []
        if pv['sign'] != 'off':
            if pv['sign'] == 'image' and sign_image:
                top = Markup('<img src="%s" class="pbds-sign-img" alt=""/>') % sign_image
            else:
                top = Markup('<div class="pbds-sign-space"></div>')
            out.append(Markup(
                '<div class="pbds-sign">%s<div class="pbds-sign-line"><strong>%s</strong>'
                '<div class="pbds-sign-title">%s</div></div></div>') % (
                    top, pv['sign_name'] or (company.name or ''), pv['sign_title']))
        out.append(Markup(
            '<div class="pbds-sign pbdh-accept"><div class="pbds-sign-space"></div>'
            '<div class="pbds-sign-line"><strong>%s</strong>'
            '<div class="pbds-sign-title">%s</div></div></div>') % (
                candidate or '', local._('Signature and date')))
        return Markup('').join(out)

    def _pbds_offer_page(self, tmpl, page, lang, body_html, heading, sign_image):
        """One page dict of `pb_doc_studio.report_doc_letter` (contract C3)
        for this offer. The frame's own signature block is switched off: the
        two signatures are drawn after the wording (`_pbds_sign_html`).
        `body_html` is the letter as rendered (the real letter, like the
        studio's own `_pbds_pdf_page`) or the sanitized draft (sample PDF)."""
        self.ensure_one()
        studio = self.env['pb.doc.studio']
        company = self.company_id.sudo() or self.env.company.sudo()
        clean = studio._pbds_clean_page(page)
        body = Markup(studio._pbds_inline_images(body_html or '', tmpl))
        body += self._pbds_sign_html(clean, lang, sign_image, company, self.candidate_name)
        return {
            'record': self,
            'company': company,
            'page': dict(clean, sign='off'),
            'lang': lang,
            'subject': heading or tmpl.with_context(lang=lang).name or '',
            'date_text': studio._pbds_long_date(fields.Date.context_today(self), lang),
            'body': body,
            'sign_image': False,
        }

    # ================================================================ prepare
    def _pbds_is_studio_offer(self):
        self.ensure_one()
        tmpl = self._pbds_offer_template()
        return bool(tmpl and tmpl._pbds_is_studio())

    def action_prepare_letter(self):
        """A letter the studio never touched: Hiring's own code, byte for
        byte. A studio letter: the studio's pipeline, as the caller."""
        self.ensure_one()
        tmpl = self._pbds_offer_template()
        if not tmpl or not tmpl._pbds_is_studio():
            chosen = self.pbds_letter_lang
            if not chosen or chosen not in self.env['pb.doc.studio']._pbds_active_langs():
                # Nothing chosen: Hiring's own code, byte for byte (rail R1).
                return super().action_prepare_letter()
            # The recruiter chose a language: Hiring's own code, read in it.
            res = super(PbHiringOfferDocStudio, self.with_context(lang=chosen)).action_prepare_letter()
            self.sudo().write({'pbds_lang': chosen})
            return res
        if not self.line_ids:
            raise UserError(_(
                "There is nothing in this offer yet. Add what is being "
                "offered — the basic pay at least — before the letter is "
                "written."))
        lang = self._pbds_offer_lang()
        body, _heading, read_lang = self._pbds_source_for(tmpl, lang)
        if is_html_empty(body):
            raise UserError(_(
                "“%s” has no wording in it yet, so there is nothing to print.",
                tmpl.name))
        html, _hidden = self._pbds_offer_render(tmpl, body, read_lang)
        self.sudo().write({'rendered_html': Markup(html), 'pbds_lang': read_lang})
        self._make_pdf()
        return True

    def _make_pdf(self):
        """The studio's page for a studio letter, rendered AS THE CALLER
        (R89) — Hiring's own report for every other letter."""
        self.ensure_one()
        tmpl = self._pbds_offer_template()
        if not (tmpl and tmpl._pbds_is_studio() and tmpl.pbds_page):
            return super()._make_pdf()
        studio = self.env['pb.doc.studio']
        lang = self.pbds_lang or self._pbds_offer_lang()
        _body, heading, _read = self._pbds_source_for(tmpl, lang)
        page = studio._pbds_clean_page(tmpl.pbds_page)
        sample = [self._pbds_offer_page(tmpl, page, lang, str(self.rendered_html or ''),
                                        heading, studio._pbds_sign_uri(tmpl))]
        report = studio._pbds_report(page)
        if not report:
            _logger.warning('pb_doc_studio_hiring: the studio letter report is missing')
            return super()._make_pdf()
        pdf, _ext = report.with_context(
            lang=lang, allowed_company_ids=self.env.companies.ids,
        )._render_qweb_pdf(report, res_ids=None, data={'pbds_sample': sample})
        filename = '%s.pdf' % slug_filename(
            _('Offer %(who)s', who=self.candidate_name or self.name or ''),
            fallback='offer')
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': 'pb.hiring.offer',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        old = self.attachment_id
        self.sudo().write({'attachment_id': attachment.id})
        if old:
            old.sudo().unlink()
        return attachment

    # ================================================================ studio
    def _pbds_offer_card(self):
        """The offer as the designer's "preview with" picker shows it."""
        self.ensure_one()
        studio = self.env['pb.doc.studio']
        names = {l['code']: l['name'] for l in studio._pbds_lang_list()}
        lang = self._pbds_offer_lang()
        states = dict(self._fields['state']._description_selection(self.env))
        return {
            'id': self.id,
            'name': self.candidate_name or self.name or '',
            'job': self.job_title or '',
            'company': self.company_id.name or '',
            'ref': self.name or '',
            'state': states.get(self.state, ''),
            'lang': lang,
            'lang_name': names.get(lang, lang),
            'avatar': False,
            'kind': OFFER,
        }
