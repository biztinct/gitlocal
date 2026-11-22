# -*- coding: utf-8 -*-
"""How a letter is made once the Document studio is installed.

Three seams on `pb.hr.letter`, and only three:

* `create` — swaps in a company / country copy of the template for the
  person (F7) and records the letter's language (F5). Every caller goes
  through it, including the ones that pick a template by a fixed xml id or by
  type only (FACTS gotchas 2-3, ledger DS-4).
* `action_generate` — a template the studio has never touched goes to the
  letter engine unchanged (rail R1: byte-identical). A studio template is
  rendered here: language version, "Show only when" paragraphs, fields.
* `_make_pdf` — a template with a page design prints with this module's
  report (contract C3); every other letter prints exactly as before.
"""
import base64
import logging

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import is_html_empty

from .doc_common import CALLER_CHOOSES_LANG, MAIN_LANG
from .doc_render import apply_rules, field_keys, substitute

_logger = logging.getLogger(__name__)


class PayHidden(Exception):
    """The person making the letter may not see a pay figure it prints."""


class PbHrLetter(models.Model):
    _inherit = 'pb.hr.letter'

    lang = fields.Char(
        string='Language', copy=False,
        help='The language this letter is written in: the person\'s own when '
             'the document has a wording in it.')

    # ------------------------------------------------------------ create
    @api.model_create_multi
    def create(self, vals_list):
        self._pbds_prepare_vals(vals_list)
        return super().create(vals_list)

    @api.model
    def _pbds_prepare_vals(self, vals_list):
        """Variant swap and language, ONE search per batch (not per row)."""
        Template = self.env['pb.letter.template'].sudo().with_context(
            active_test=False)
        tids = {v.get('template_id') for v in vals_list
                if isinstance(v.get('template_id'), int)}
        eids = {v.get('employee_id') for v in vals_list
                if isinstance(v.get('employee_id'), int)}
        templates = Template.browse(list(tids)).exists()
        employees = self.env['hr.employee'].sudo().browse(list(eids)).exists()
        roots = templates.mapped(lambda t: t.pbds_replaces_id or t)
        variants = Template.browse()
        if roots:
            variants = Template.search([('pbds_replaces_id', 'in', roots.ids),
                                        ('active', '=', True)])
        studio = self.env['pb.doc.studio']
        countries = studio._pbds_country_of_work(employees) \
            if (variants or templates.filtered('pbds_replaces_id')) else {}
        by_t = {t.id: t for t in templates}
        by_e = {e.id: e for e in employees}
        for vals in vals_list:
            tmpl = by_t.get(vals.get('template_id'))
            emp = by_e.get(vals.get('employee_id'))
            if tmpl and emp and (variants or tmpl.pbds_replaces_id):
                chosen = self._pbds_pick_variant(
                    tmpl, emp, variants, countries.get(emp.id))
                if chosen and chosen != tmpl:
                    vals['template_id'] = chosen.id
                    tmpl = chosen
            if not vals.get('lang'):
                vals['lang'] = self._pbds_default_lang(tmpl, emp)

    @api.model
    def _pbds_pick_variant(self, template, employee, variants, country_id):
        """The most specific ACTIVE copy of `template`'s root that fits the
        person: company + country > company > country > the template itself.
        Ties: lowest sequence, then oldest."""
        root = template.pbds_replaces_id or template
        company = employee.company_id

        def fits(tmpl):
            if tmpl.company_id and tmpl.company_id != company:
                return False
            if tmpl.pbds_country_ids and country_id not in tmpl.pbds_country_ids.ids:
                return False
            return True

        best, best_key = None, None
        for var in variants:
            if var.pbds_replaces_id != root or not fits(var):
                continue
            score = (2 if var.company_id else 0) + (1 if var.pbds_country_ids else 0)
            key = (-score, var.sequence, var.id)
            if best_key is None or key < best_key:
                best, best_key = var, key
        if best:
            return best
        if template != root and not fits(template):
            # A copy for somebody else: this person gets the letter it copies.
            return root
        return template

    @api.model
    def _pbds_default_lang(self, template, employee):
        """The person's language when it is in use here, else the company's,
        else the user's. Certificates keep the language their caller chose."""
        active = self.env['pb.doc.studio']._pbds_active_langs()
        if template and template.letter_type in CALLER_CHOOSES_LANG:
            ctx_lang = self.env.context.get('lang')
            if ctx_lang in active:
                return ctx_lang
        candidates = []
        if employee:
            emp = employee.sudo()
            if 'lang' in emp._fields:
                candidates.append(emp.lang)
            candidates.append(emp.company_id.partner_id.lang)
        candidates += [self.env.company.partner_id.lang, self.env.user.lang,
                       self.env.lang]
        for lang in candidates:
            if lang and lang in active:
                return lang
        return MAIN_LANG if MAIN_LANG in active else (sorted(active) or [MAIN_LANG])[0]

    # ------------------------------------------------------------ generate
    def action_generate(self):
        studio = self.filtered(lambda r: r.template_id and r.template_id._pbds_is_studio())
        legacy = self - studio
        if legacy:
            super(PbHrLetter, legacy).action_generate()
        for rec in studio:
            rec._pbds_generate()
        return True

    def _pbds_source(self, lang):
        """(body, heading) of the template in `lang`: its version when there is
        one, else the template read in that language (a translated wording
        shipped with the product still reaches its readers)."""
        self.ensure_one()
        tmpl = self.template_id
        version = tmpl.sudo().pbds_version_ids.filtered(lambda v: v.lang == lang)[:1]
        if version and not is_html_empty(version.body_html):
            return str(version.body_html), version.subject or ''
        local = tmpl.with_context(lang=lang)
        return str(local.body_html or ''), local.subject or ''

    def _pbds_generate(self):
        self.ensure_one()
        tmpl = self.template_id
        lang = self.lang or self._pbds_default_lang(tmpl, self.employee_id)
        body, heading = self._pbds_source(lang)
        if is_html_empty(body):
            raise UserError(_(
                "'%s' has no letter body yet, so there is nothing to print.",
                tmpl.name))
        try:
            html, _hidden = self._pbds_render(body, lang)
        except PayHidden:
            raise UserError(_(
                "This letter shows pay. Ask someone who may see pay to "
                "prepare it."))
        subject = self.subject
        main_subjects = {tmpl.with_context(lang=MAIN_LANG).subject,
                         tmpl.subject, tmpl.name}
        if heading and (not subject or subject in main_subjects):
            subject = heading
        self.write({
            'rendered_html': Markup(html),
            'subject': subject or tmpl.subject or tmpl.name,
            'state': 'generated',
            'generated_at': fields.Datetime.now(),
            'generated_by': self.env.uid,
            'lang': lang,
        })
        self._make_pdf()
        self._file_in_vault()
        self.message_post(body=_("Letter prepared."))

    def _pbds_render(self, body, lang, ghost=False, missing=None, wrap=None):
        """`(html, hidden)` of `body` for this letter's person, in `lang`.

        The real letter (`ghost=False`, no `missing`): hidden paragraphs are
        removed, an empty field prints nothing (rail R3) and a pay figure the
        user may not see raises `PayHidden`. The preview passes `ghost` and a
        `missing` callback to show chips instead."""
        self.ensure_one()
        studio = self.env['pb.doc.studio']
        tmpl = self.template_id
        emp = self.employee_id
        facts, meta = studio._pbds_facts(emp)
        rules = self.env.context.get('pbds_rules_override')
        if rules is None:
            rules = tmpl.pbds_rules or {}
        html, hidden, _bad = apply_rules(
            body, rules, facts, meta, ghost=ghost,
            log_ref='template %s' % tmpl.id)
        values, blocked = self._pbds_values(lang, field_keys(html))
        if blocked and missing is None:
            raise PayHidden()
        if wrap:
            values = {k: wrap(k, v) for k, v in values.items()}
        html = substitute(html, values,
                          missing=(lambda key: missing(key, key in blocked))
                          if missing else None)
        return html, hidden

    def _pbds_values(self, lang, keys):
        """`({key: escaped text}, blocked keys)` for the keys a body uses.

        The letter engine's own values come first, with every override other
        modules made (`_placeholder_values`), and the extra details the
        caller gave the letter win over anything worked out here."""
        self.ensure_one()
        local = self.with_context(lang=lang)
        values = dict(local._placeholder_values())
        wanted = [k for k in keys if k not in values]
        blocked = set()
        if wanted:
            more, blocked = self.env['pb.doc.studio'].with_context(
                lang=lang)._pbds_generic_values(
                    self.employee_id, self.company_id or self.employee_id.company_id,
                    lang, wanted)
            values.update(more)
        return values, blocked

    # ------------------------------------------------------------ pdf
    def _make_pdf(self):
        self.ensure_one()
        tmpl = self.template_id
        report = tmpl and tmpl.pbds_page and \
            self.env['pb.doc.studio']._pbds_report(tmpl.pbds_page)
        if not report:
            return super()._make_pdf()
        pdf, _ext = report.sudo()._render_qweb_pdf(report, res_ids=self.ids)
        filename = '%s.pdf' % (self.subject or self.name or 'Letter').replace(
            '/', '-')
        att = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': 'pb.hr.letter',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        old = self.attachment_id
        self.attachment_id = att.id
        if old:
            old.sudo().unlink()
        return att

    def _pbds_pdf_page(self):
        """What `pb_doc_studio.report_doc_letter` prints for this letter."""
        self.ensure_one()
        studio = self.env['pb.doc.studio']
        tmpl = self.template_id.sudo()
        lang = self.lang or MAIN_LANG
        company = (self.company_id or self.employee_id.company_id
                   or self.env.company).sudo()
        when = self.generated_at.date() if self.generated_at \
            else fields.Date.context_today(self)
        return {
            'record': self,
            'company': company,
            'page': tmpl.pbds_page or {},
            'lang': lang,
            'subject': self.subject or tmpl.subject or tmpl.name or '',
            'date_text': studio._pbds_long_date(when, lang),
            'body': Markup(studio._pbds_inline_images(
                str(self.rendered_html or ''), tmpl)),
            'sign_image': studio._pbds_sign_uri(tmpl),
        }
