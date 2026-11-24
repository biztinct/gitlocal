# -*- coding: utf-8 -*-
"""The contract panel's "Contract document" (`pb.contracts`, by inheritance).

Three methods, one rule for access: whoever may open the contract in the
panel (`_cd_require_read` + `_cd_contract`, read as the caller) may preview
and print its contract document. Values are read as the caller; pay follows
the pay rail (`pb.doc.studio._pbdc_pay`): somebody who sees the panel's wage
masked gets a plain refusal, never a figure.

    contract_document_available(contract_id)                the button
    contract_document(contract_id, lang, template_id)       the preview
    contract_document_pdf(contract_id, lang, template_id)   the true PDF
    contract_document_save(contract_id, lang, template_id)  file a new version

The wording is the studio's: the document chosen (the shipped "Employment
contract" unless the company made others), swapped for the company/country
copy that fits the person (`pb.hr.letter._pbds_swap_template`, the same rule
as every letter), read in the chosen language (`_pbds_draft_parts`, the same
order as a letter), with its "Show only when" paragraphs, fields and page.
Nothing is stored for a preview or a download: no letter, no file.
"""
import base64
import logging
import re

from lxml import etree, html as lxml_html
from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import html_sanitize
from odoo.tools.misc import format_date

from odoo.addons.pb_doc_studio.models.doc_common import MAIN_LANG
from odoo.addons.pb_doc_studio.models.doc_render import UnknownRule, rule_holds
from odoo.addons.pb_doc_studio.models.hr_letter import PayHidden

from .contract_common import (
    CONTRACT_TYPE, JUMP, RULE_JUMP, VAULT_CATEGORY,
)

_logger = logging.getLogger(__name__)

_RULE_RE = re.compile(r'pbds-r-([a-z][a-z0-9]{0,15})')


class Refused(Exception):
    """A plain sentence for the person; nothing was made."""


class PbContracts(models.AbstractModel):
    _inherit = 'pb.contracts'

    # ------------------------------------------------------------ panel
    @api.model
    def contract_document_available(self, contract_id):
        """May the caller print this contract's document? (the panel's
        "Contract document" button). Asked beside the panel's own payload,
        which stays exactly as `pb_contracts` builds it. Never raises."""
        try:
            if not self._cd_may_read():
                return False
            contract = self._cd_contract(contract_id)
            return bool(contract is not None and contract.employee_id
                        and self._pbdc_roots(contract))
        except Exception:   # noqa: BLE001 — a button, never a broken panel
            _logger.exception('Contract document: availability check failed for %s', contract_id)
            return False

    # ------------------------------------------------------------ helpers
    @api.model
    def _pbdc_roots(self, contract):
        """The employment contract documents this contract can print: the
        originals (not copies), switched on, shared or of its company."""
        company = contract.company_id or contract.employee_id.company_id
        return self.env['pb.letter.template'].sudo().search([
            ('letter_type', '=', CONTRACT_TYPE),
            ('pbds_replaces_id', '=', False),
            ('active', '=', True),
            ('company_id', 'in', [False, company.id]),
        ], order='sequence, id')

    @api.model
    def _pbdc_open(self, contract_id, template_id=None):
        """`(contract, employee, root, template)` for the caller, or
        `Refused` with the sentence to show."""
        self._cd_require_read()
        _ = self.env._
        contract = self._cd_contract(contract_id)
        if contract is None:
            raise Refused(_("This contract is not available to you. It may have been "
                            "removed, or it belongs to a company you do not work in."))
        employee = contract.employee_id
        if not employee:
            raise Refused(_("This contract has no employee yet, so there is nobody to "
                            "write the contract for."))
        roots = self._pbdc_roots(contract)
        if not roots:
            raise Refused(_("There is no employment contract wording switched on. "
                            "Someone who looks after documents can add or switch one on "
                            "in Settings, Documents."))
        root = roots.filtered(lambda t: t.id == int(template_id or 0))[:1] or roots[:1]
        tmpl = self.env['pb.hr.letter']._pbds_swap_template(root, employee.sudo())
        return contract, employee, root, tmpl.sudo()

    @api.model
    def _pbdc_langs(self, tmpl):
        """The languages this wording really exists in: its main language,
        each language it has a wording of its own in, and each language the
        product ships a translation of it in. (An English wording read in
        another language would print English sentences with foreign dates.)"""
        studio = self.env['pb.doc.studio']
        active = studio._pbds_active_langs()
        main_lang = tmpl._pbds_main_lang()
        codes = [main_lang]
        for ver in tmpl.pbds_version_ids:
            if ver.lang in active and ver.lang not in codes:
                codes.append(ver.lang)
        if main_lang == MAIN_LANG:
            main_body = str(tmpl.with_context(lang=MAIN_LANG).body_html or '')
            for code in sorted(active):
                if code in codes:
                    continue
                local = str(tmpl.with_context(lang=code).body_html or '')
                if local and local != main_body:
                    codes.append(code)
        names = {l['code']: l['name'] for l in studio._pbds_lang_list()}
        return [{'code': c, 'name': names.get(c, c), 'main': c == main_lang} for c in codes]

    @api.model
    def _pbdc_pick_lang(self, tmpl, employee, lang, langs):
        codes = [l['code'] for l in langs]
        if lang in codes:
            return lang
        emp = employee.sudo()
        for cand in (emp.lang if 'lang' in emp._fields else False,
                     emp.company_id.partner_id.lang):
            if cand in codes:
                return cand
        return codes[0]

    @api.model
    def _pbdc_render(self, contract, employee, tmpl, lang, preview):
        """The finished document for this contract.

        → dict(html, heading, page, read_lang, missing, blocked, hidden).
        `preview=False` is the real thing: an empty field prints nothing and
        a pay figure the caller may not see raises `PayHidden`."""
        studio = self.env['pb.doc.studio']
        _ = self.env._
        # The rules and page it prints with (a shipped contract never saved
        # in the studio uses its built-in ones, `_pbdc_rules` / `_pbdc_page`).
        draft = {'rules': tmpl._pbdc_rules(), 'page': tmpl._pbdc_page()}
        body, heading, rules, page, read_lang = studio._pbds_draft_parts(tmpl, draft, lang)
        company = (contract.company_id or employee.company_id or self.env.company)
        letter = self.env['pb.hr.letter'].new({
            'employee_id': employee.id,
            'template_id': tmpl.id,
            'company_id': company.id,
        })
        ctx = {'pbdc_contract_id': contract.id, 'pbdc_page': page,
               'pbds_rules_override': rules}
        _groups, flat = studio._pbds_catalogue(tmpl)
        missing, blocked = [], []

        def chip(key, is_blocked):
            spec = flat.get(key) or {}
            label = spec.get('label') or key.replace('_', ' ').capitalize()
            if is_blocked:
                blocked.append(key)
                text, cls = _('You may not see pay'), 'pbds-miss pbds-pay'
            elif spec.get('missing'):
                text, cls = _('A field that no longer exists'), 'pbds-miss'
            else:
                # "No trial period end date"; a label that starts with an
                # abbreviation keeps it ("No ID number").
                low = label if label[:2].isupper() else label[:1].lower() + label[1:]
                text, cls = _('No %s', low), 'pbds-miss'
            missing.append({'key': key, 'label': label, 'text': text,
                            'pay': bool(is_blocked), 'jump': self._pbdc_jump(key)})
            return '<span class="%s">%s</span>' % (cls, escape(text))

        def wrap(key, value):
            if value in (None, ''):
                return value
            return '<span class="pbds-v pbds-k-%s">%s</span>' % (key, value)

        renderer = letter.with_context(**ctx)
        if preview:
            html, hidden = renderer._pbds_render(body, read_lang, missing=chip, wrap=wrap)
        else:
            html, hidden = renderer._pbds_render(body, read_lang)
        seen, unique = set(), []
        for row in missing:
            if row['key'] not in seen:
                seen.add(row['key'])
                unique.append(row)
        return {
            'html': html, 'heading': heading or tmpl.with_context(lang=read_lang).name or '',
            'page': page, 'read_lang': read_lang, 'missing': unique,
            'blocked': bool(blocked), 'hidden': hidden, 'rules': rules, 'body': body,
            'company': company,
        }

    @api.model
    def _pbdc_jump(self, key):
        where = JUMP.get(key)
        if not where:
            return False
        return {'kind': where[0], 'name': where[1] or False}

    @api.model
    def _pbdc_left_out(self, contract, employee, rules, body):
        """The "Show only when" paragraphs this contract leaves out, each
        with the sentence of its rule and where its fact is changed."""
        studio = self.env['pb.doc.studio'].with_context(pbdc_contract_id=contract.id)
        facts, meta = studio._pbds_facts(employee)
        meta_full = {m['key']: m for m in studio._pbds_condition_meta()}
        out, seen = [], set()
        for rid in _RULE_RE.findall(body or ''):
            if rid in seen or rid not in (rules or {}):
                continue
            seen.add(rid)
            try:
                holds = rule_holds(rules[rid], facts, meta)
            except UnknownRule:
                continue
            if holds:
                continue
            lines = rules[rid].get('lines') or []
            where = RULE_JUMP.get((lines[0] or {}).get('field')) if lines else None
            out.append({'id': rid, 'sentence': studio._pbds_rule_sentence(rules[rid], meta_full),
                        'jump': {'kind': where[0], 'name': where[1]} if where else False})
        return out

    @api.model
    def _pbdc_frame(self, tmpl, rendered, mode):
        studio = self.env['pb.doc.studio']
        company = rendered['company'].sudo()
        lang = rendered['read_lang']
        page = rendered['page']
        values = {
            'page': page,
            'company': company,
            'body': Markup(html_sanitize(rendered['html'])),
            'subject': rendered['heading'],
            'date_text': studio._pbds_long_date(fields.Date.context_today(self), lang),
            'sign_image': studio._pbds_sign_uri(tmpl) if page.get('sign') == 'image' else False,
            'mode': mode,
            'doc_lang': lang,
            'company_card': studio._pbds_company_card(company),
            'env': self.env,
        }
        return str(self.env['ir.qweb']._render('pb_doc_studio.page_frame', values))

    @api.model
    def _pbdc_versions(self, contract):
        Doc = self.env['pb.employee.document']
        try:
            docs = Doc.search([('pbdc_contract_id', '=', contract.id)],
                              order='pbdc_version desc, id desc', limit=20)
            rows = []
            for doc in docs:
                rows.append({
                    'id': doc.id, 'name': doc.name or '', 'version': doc.pbdc_version,
                    'date': fields.Date.to_string(doc.issue_date) if doc.issue_date else False,
                    'by': doc.sudo().create_uid.name or '',
                    'url': '/web/content/%s?download=true' % doc.attachment_id.id
                    if doc.attachment_id else False,
                })
            return rows
        except AccessError:
            return []

    @api.model
    def _pbdc_next_version(self, contract):
        rows = self.env['pb.employee.document'].sudo().with_context(active_test=False).search_read(
            [('pbdc_contract_id', '=', contract.id)], ['pbdc_version'])
        return max([r['pbdc_version'] or 0 for r in rows] or [0]) + 1

    @api.model
    def _pbdc_may_file(self):
        return self.env['pb.employee.document'].has_access('create')

    @api.model
    def _pbdc_may_design(self):
        return self.env['pb.letter.template'].has_access('write')

    # ------------------------------------------------------------ preview
    @api.model
    def contract_document(self, contract_id, lang=None, template_id=None):
        """The preview of this contract's document. Never raises for a
        refusal: `{ok: False, msg}`."""
        _ = self.env._
        try:
            contract, employee, root, tmpl = self._pbdc_open(contract_id, template_id)
        except Refused as exc:
            return {'ok': False, 'msg': str(exc)}
        langs = self._pbdc_langs(tmpl)
        lang = self._pbdc_pick_lang(tmpl, employee, lang, langs)
        try:
            rendered = self._pbdc_render(contract, employee, tmpl, lang, preview=True)
        except AccessError:
            return {'ok': False, 'msg': _("You may not read everything this contract shows.")}
        html = self._pbdc_frame(tmpl, rendered, 'screen')
        values = {}
        try:
            for span in lxml_html.fromstring('<div>%s</div>' % rendered['html']).xpath(
                    "//span[contains(concat(' ', normalize-space(@class), ' '), ' pbds-v ')]"):
                values[span.get('class').split('pbds-k-')[-1]] = span.text_content()
        except (etree.ParserError, ValueError):
            values = {}
        roots = self._pbdc_roots(contract)
        may_file = self._pbdc_may_file()
        return {
            'ok': True,
            'html': html,
            'lang': lang,
            'read_lang': rendered['read_lang'],
            'langs': langs,
            'documents': [{'id': r.id, 'name': r.with_context(lang=self.env.lang).name or ''}
                          for r in roots],
            'document': {'id': root.id, 'name': root.with_context(lang=self.env.lang).name or '',
                         'used_id': tmpl.id,
                         'used_name': tmpl.with_context(lang=self.env.lang).name or '',
                         'note': tmpl._pbds_wording_note() or ''},
            'person': {'id': employee.id, 'name': employee.sudo().name or ''},
            'reference': contract.name or '',
            'missing': rendered['missing'],
            'left_out': self._pbdc_left_out(contract, employee, rendered['rules'], rendered['body']),
            'values': values,
            'pay_blocked': rendered['blocked'],
            'pay_msg': _("This contract shows pay, and you may not see this person's pay. "
                         "Ask someone who may see pay to print it.") if rendered['blocked'] else '',
            'can_file': may_file,
            'file_msg': '' if may_file else _(
                "You can download this contract. Filing it in the employee's documents "
                "needs the HR or payroll role."),
            'can_design': self._pbdc_may_design(),
            # Owner ruling 2026-11-24: shown on screen, never printed.
            'sample_wording': bool(tmpl.pbdc_sample),
            'versions': self._pbdc_versions(contract),
            'next_version': self._pbdc_next_version(contract),
        }

    # ------------------------------------------------------------ pdf
    @api.model
    def _pbdc_pdf(self, contract, employee, root, tmpl, lang):
        """`(pdf bytes, file name, read_lang)` — the real document. Raises
        `Refused` with the sentence to show."""
        _ = self.env._
        studio = self.env['pb.doc.studio']
        langs = self._pbdc_langs(tmpl)
        lang = self._pbdc_pick_lang(tmpl, employee, lang, langs)
        try:
            rendered = self._pbdc_render(contract, employee, tmpl, lang, preview=False)
        except PayHidden:
            raise Refused(_("This contract shows pay, and you may not see this person's pay. "
                            "Ask someone who may see pay to print it."))
        except AccessError:
            raise Refused(_("You may not read everything this contract shows."))
        page = rendered['page']
        sample = [{
            'record': False,
            'company': rendered['company'].sudo(),
            'page': page,
            'lang': rendered['read_lang'],
            'subject': rendered['heading'],
            'date_text': studio._pbds_long_date(fields.Date.context_today(self), rendered['read_lang']),
            'body': Markup(studio._pbds_inline_images(html_sanitize(rendered['html']), tmpl)),
            'sign_image': studio._pbds_sign_uri(tmpl) if page.get('sign') == 'image' else False,
        }]
        report = studio._pbds_report(page)
        try:
            # Every value is already in the page (read as the caller above);
            # the report itself is drawn the way the letter engine draws
            # letters (`_make_pdf`: `report.sudo()`).
            pdf, _ext = report.sudo().with_context(lang=rendered['read_lang'])._render_qweb_pdf(
                report, res_ids=None, data={'pbds_sample': sample})
        except Exception:                              # noqa: BLE001
            _logger.exception('Contract document: PDF of contract %s failed', contract.id)
            raise Refused(_("The PDF could not be made right now. Try again in a moment; "
                            "the preview on screen is exactly what will print."))
        name = '%s — %s.pdf' % (root.with_context(lang=self.env.lang).name or _('Employment contract'),
                                employee.sudo().name or '')
        return pdf, name.replace('/', '-'), rendered['read_lang']

    @api.model
    def contract_document_pdf(self, contract_id, lang=None, template_id=None):
        """The true PDF, to download. Nothing is filed. → {ok, name, data}
        or {ok: False, msg}."""
        try:
            contract, employee, root, tmpl = self._pbdc_open(contract_id, template_id)
            pdf, name, _lang = self._pbdc_pdf(contract, employee, root, tmpl, lang)
        except Refused as exc:
            return {'ok': False, 'msg': str(exc)}
        return {'ok': True, 'name': name, 'data': base64.b64encode(pdf).decode()}

    # ------------------------------------------------------------ save
    @api.model
    def contract_document_save(self, contract_id, lang=None, template_id=None):
        """File the PDF in the employee's documents as the next version.
        Earlier versions stay. → {ok, version, name, versions} or {ok: False, msg}."""
        _ = self.env._
        try:
            contract, employee, root, tmpl = self._pbdc_open(contract_id, template_id)
            if not self._pbdc_may_file():
                raise Refused(_("You can download this contract. Filing it in the employee's "
                                "documents needs the HR or payroll role."))
            pdf, name, _lang = self._pbdc_pdf(contract, employee, root, tmpl, lang)
        except Refused as exc:
            return {'ok': False, 'msg': str(exc)}
        # One version number per save, even when two people press at once.
        self.env.cr.execute('SELECT id FROM hr_contract WHERE id = %s FOR UPDATE', (contract.id,))
        version = self._pbdc_next_version(contract)
        today = fields.Date.context_today(self)
        doc_name = _('%(doc)s · v%(n)s · %(date)s',
                     doc=root.with_context(lang=self.env.lang).name or _('Employment contract'),
                     n=version,
                     date=format_date(self.env, today, date_format='d MMM y'))
        category = tmpl.vault_category_id or root.vault_category_id \
            or self.env.ref(VAULT_CATEGORY, raise_if_not_found=False)
        if not category:
            return {'ok': False, 'msg': _("The document kind for contracts is missing. "
                                          "Ask an administrator to add it back.")}
        att = self.env['ir.attachment'].sudo().create({
            'name': name,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'mimetype': 'application/pdf',
        })
        try:
            doc = self.env['pb.employee.document'].create({
                'employee_id': employee.id,
                'category_id': category.id,
                'name': doc_name,
                'attachment_id': att.id,
                'issue_date': today,
                'company_id': (employee.company_id or contract.company_id).id,
                'pbdc_contract_id': contract.id,
                'pbdc_version': version,
            })
        except (AccessError, UserError) as exc:
            att.unlink()
            return {'ok': False, 'msg': _("The contract could not be filed: %s", exc.args[0] if exc.args else '')}
        att.sudo().write({'res_model': 'pb.employee.document', 'res_id': doc.id})
        return {
            'ok': True,
            'version': version,
            'name': doc_name,
            'document_id': doc.id,
            'versions': self._pbdc_versions(contract),
            'next_version': version + 1,
        }
