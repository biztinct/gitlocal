# -*- coding: utf-8 -*-
"""The designer's server side (`pb.report.pdf`): open, preview, save, put
back, company default, download.

Every entry point first checks the report for the person calling
(`_pbrp_source`: the source's own gate + read access) and builds the table
AS THAT PERSON (`_pbrp_table`). The preview keeps the table of the last few
seconds in a small per-person cache (same person, same companies, same
language, same saved report) so redrawing after each option change does not
read every row again; a download always reads fresh.
"""
import base64
import logging
import re
import threading
import time
from collections import OrderedDict

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .layout import (HEADER_SPACING, HEADER_SPACING_LETTERHEAD, MARGIN_TOP,
                     MARGIN_TOP_LETTERHEAD, FIT_COLUMNS, PDF_FONTS, ROW_CAP)
from .look import COLORS, DEFAULT_KEYS, PAPERS, clean_look

try:  # the tenant's own name for the product (WHITELABEL)
    from odoo.addons.biz_debrand.models.brand import product_label
except Exception:  # pragma: no cover — biz_debrand absent on this build
    def product_label(env, default='Payobook'):
        return default

_logger = logging.getLogger(__name__)

CACHE_TTL = 90
CACHE_SIZE = 6
LOOK_CAP = 500
_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()


def _file_word(text):
    text = re.sub(r'[\\/:*?"<>|\[\]\x00-\x1f]+', ' ', text or '').strip()
    return ' '.join(text.split())[:60]


class PbReportPdfFacade(models.AbstractModel):
    _inherit = 'pb.report.pdf'

    # ============================================================ the table
    @api.model
    def _pbrp_cache_key(self, rec):
        stamp = fields.Datetime.to_string(rec.write_date) if 'write_date' in rec._fields \
            and rec.write_date else ''
        return (self.env.cr.dbname, self.env.uid, rec._name, rec.id, stamp,
                self.env.lang or '', tuple(self.env.companies.ids))

    @api.model
    def _pbrp_info(self, rec, cached=False):
        if not cached:
            return self._pbrp_table(rec)
        key = self._pbrp_cache_key(rec)
        now = time.monotonic()
        with _CACHE_LOCK:
            hit = _CACHE.get(key)
            if hit and now - hit[0] < CACHE_TTL:
                _CACHE.move_to_end(key)
                return hit[1]
        info = self._pbrp_table(rec)
        with _CACHE_LOCK:
            _CACHE[key] = (now, info)
            _CACHE.move_to_end(key)
            while len(_CACHE) > CACHE_SIZE:
                _CACHE.popitem(last=False)
        return info

    @api.model
    def _pbrp_refusal(self, exc):
        msg = exc.args[0] if exc.args else ''
        return {'ok': False, 'msg': msg or self.env._("This report cannot be printed right now.")}

    # ============================================================ options
    @api.model
    def _pbrp_options(self):
        _ = self.env._
        styles = {s['key']: s for s in self.env['pb.doc.studio'].page_styles()}
        color_words = {
            'indigo': _("Indigo"), 'ink': _("Deep ink"), 'soft': _("Soft indigo"),
            'slate': _("Slate"), 'plain': _("Plain"),
        }
        return {
            'papers': [{'key': p, 'label': p} for p in PAPERS],
            'turns': [{'key': 'fit', 'label': _("Fit")},
                      {'key': 'upright', 'label': _("Upright")},
                      {'key': 'sideways', 'label': _("Sideways")}],
            # the C3 fonts that print differently (see layout.PDF_FONTS)
            'fonts': [{'key': o['value'], 'label': o['label'],
                       'css': self._pbrp_font_stack(o['value'])}
                      for o in styles['font']['options'] if o['value'] in PDF_FONTS],
            'sizes': [o['value'] for o in styles['size']['options']],
            'colors': [{'key': k, 'bg': bg, 'fg': fg, 'label': color_words.get(k, k)}
                       for k, bg, fg in COLORS],
            'fit': FIT_COLUMNS,
            'cap': ROW_CAP,
        }

    @api.model
    def _pbrp_column_list(self, info, look):
        return [{'key': c['key'], 'label': c['label'], 'type': c['type'], 'hide': c['hide'],
                 'default_hide': c['default_hide'], 'is_currency': c['is_currency'],
                 'w': c['w'] or 0} for c in self._pbrp_columns(info, look)]

    # ============================================================ preview
    @api.model
    def _pbrp_page(self, look):
        """The C3 page dict this look prints with (pb_doc_studio)."""
        return self.env['pb.doc.studio']._pbds_clean_page({
            'letterhead': look['letterhead'], 'margins': 'narrow', 'font': look['font'],
            'size': look['size'], 'sign': 'off'})

    @api.model
    def _pbrp_preview(self, info, look):
        """The first page, drawn by the server: {html, pages, rows, …}."""
        doc = self._pbrp_doc(info, look, preview=True)
        Studio = self.env['pb.doc.studio']
        company = self.env.company
        page = self._pbrp_page(look)
        body = self.env['ir.qweb']._render('pb_report_pdf.table_body', {'doc': doc})
        card = Studio._pbds_company_card(company)
        footer_contact = card.get('contact') if look['letterhead'] else ''
        card = dict(card, contact='')
        html = self.env['ir.qweb']._render('pb_report_pdf.screen_page', {
            'doc': doc,
            'page': page,
            'company': company.sudo(),
            'body': body,
            'company_card': card,
            'footer_contact': footer_contact,
            'doc_lang': self.env.lang,
            'page_word': self.env._("Page %(page)s of %(total)s", page=1, total=doc['pages']),
            'env': self.env,
        })
        return {
            'ok': True,
            'html': str(html),
            'pages': doc['pages'],
            'rows': doc['rows'],
            'total_rows': doc['total_rows'],
            'capped': doc['capped'],
            'cap_note': doc['cap_note'],
            'note': doc['source_note'],
            'sideways': doc['sideways'],
            'paper_mm': list(doc['paper_mm']),
            'visible': doc['visible'],
            'widths': {c['key']: c['w'] for c in doc['columns']},
            'empty': doc['empty'],
        }

    # ============================================================ RPC
    @api.model
    def open(self, source_model, source_id):
        """Everything the designer needs, with the first page drawn."""
        try:
            rec = self._pbrp_source(source_model, source_id)
            info = self._pbrp_info(rec, cached=True)
        except (UserError, AccessError) as exc:
            return self._pbrp_refusal(exc)
        me = self.env.user
        owner = self._pbrp_owner(rec)
        Look = self.env['pb.report.pdf.look']
        look, origin, lrec = Look._pbrp_resolve(rec._name, rec.id, me, owner, self.env.company)
        default = Look._pbrp_default_for(self.env.company)
        name = self._pbrp_name(rec)
        cols = self._pbrp_column_list(info, look)
        totals = self._pbrp_totals_map(info, self._pbrp_columns(info, look))
        return {
            'ok': True,
            'name': name,
            'title_default': info.get('title') or name,
            'sub_default': info.get('sub') or '',
            'look': look,
            'builtin': clean_look({}),
            'origin': origin,
            'shared_by': (lrec.user_id.sudo().name or '') if origin == 'shared' else '',
            'my_shared': bool(origin == 'mine' and lrec.shared),
            'can_share': bool(owner and owner == me),
            'is_admin': bool(me._is_admin()),
            'has_default': bool(default),
            'columns': cols,
            'has_groups': bool(info.get('groups')) and not info.get('summary'),
            'has_totals': bool(totals),
            'options': self._pbrp_options(),
            'preview': self._pbrp_preview(info, look),
        }

    @api.model
    def preview(self, source_model, source_id, look):
        """The first page for an UNSAVED look. Nothing is stored."""
        try:
            rec = self._pbrp_source(source_model, source_id)
            info = self._pbrp_info(rec, cached=True)
        except (UserError, AccessError) as exc:
            return self._pbrp_refusal(exc)
        look = clean_look(look)
        out = self._pbrp_preview(info, look)
        out['columns'] = self._pbrp_column_list(info, look)
        return out

    @api.model
    def save(self, source_model, source_id, look, shared=None):
        """Keep this look for this report (the caller's own look). Only the
        report's owner may share it with everyone who opens the report."""
        rec = self._pbrp_source(source_model, source_id)
        look = clean_look(look)
        me = self.env.user
        Look = self.env['pb.report.pdf.look']
        own = Look.search([('source_model', '=', rec._name), ('source_id', '=', rec.id),
                           ('user_id', '=', me.id), ('is_default', '=', False)], limit=1)
        vals = {'look': look}
        owner = self._pbrp_owner(rec)
        if shared is not None:
            if shared and owner != me:
                raise AccessError(self.env._("Only the person who saved this report can "
                                             "share its look."))
            vals['shared'] = bool(shared)
        if own:
            own.write(vals)
        else:
            if Look.search_count([('user_id', '=', me.id), ('is_default', '=', False)]) \
                    >= LOOK_CAP:
                raise UserError(self.env._(
                    "You already keep %(cap)s PDF looks. Put one you no longer use back "
                    "to the standard look first.", cap=LOOK_CAP))
            own = Look.create(dict(vals, source_model=rec._name, source_id=rec.id,
                                   user_id=me.id))
        return {'ok': True, 'origin': 'mine', 'my_shared': bool(own.shared),
                'look': clean_look(own.look or {})}

    @api.model
    def reset(self, source_model, source_id):
        """Back to the standard look: the caller's own look is removed."""
        rec = self._pbrp_source(source_model, source_id)
        Look = self.env['pb.report.pdf.look']
        Look.search([('source_model', '=', rec._name), ('source_id', '=', rec.id),
                     ('user_id', '=', self.env.uid), ('is_default', '=', False)]).unlink()
        return self.open(rec._name, rec.id)

    @api.model
    def set_default(self, look):
        """"Use this look for every new report" — administrators only. Only
        the page choices travel (never one report's columns or words)."""
        if not self.env.user._is_admin():
            raise AccessError(self.env._("Only administrators can set the company's "
                                         "default look."))
        look = clean_look(look)
        keep = {k: look[k] for k in DEFAULT_KEYS}
        Look = self.env['pb.report.pdf.look']
        company = self.env.company
        current = Look._pbrp_default_for(company)
        if current:
            current.sudo().write({'look': keep})
        else:
            Look.sudo().create({'is_default': True, 'company_id': company.id,
                                'user_id': self.env.uid, 'look': keep})
        return {'ok': True}

    @api.model
    def clear_default(self):
        if not self.env.user._is_admin():
            raise AccessError(self.env._("Only administrators can change the company's "
                                         "default look."))
        self.env['pb.report.pdf.look']._pbrp_default_for(self.env.company).sudo().unlink()
        return {'ok': True}

    @api.model
    def download(self, source_model, source_id, look):
        """The true PDF for the caller, from a fresh read of the report.
        → {ok, name, data (base64), rows, capped, seconds} or {ok: False, msg}."""
        started = time.monotonic()
        try:
            rec = self._pbrp_source(source_model, source_id)
            info = self._pbrp_info(rec)
        except (UserError, AccessError) as exc:
            return self._pbrp_refusal(exc)
        look = clean_look(look)
        if not any(not c['hide'] for c in self._pbrp_columns(info, look)):
            return {'ok': False, 'msg': self.env._("Pick at least one column to print.")}
        try:
            pdf = self._pbrp_pdf(info, look)
        except Exception:                                    # noqa: BLE001
            _logger.exception('pb_report_pdf: PDF of %s#%s failed', rec._name, rec.id)
            return {'ok': False, 'msg': self.env._(
                "The PDF could not be made right now. Try again in a moment; the page on "
                "screen is exactly what will print.")}
        title = look['title'] or info.get('title') or self._pbrp_name(rec)
        return {
            'ok': True,
            'name': self._pbrp_file_name(title),
            'data': base64.b64encode(pdf).decode('ascii'),
            'rows': min(len(info['rows']), ROW_CAP),
            'total_rows': len(info['rows']),
            'capped': len(info['rows']) > ROW_CAP,
            'seconds': round(time.monotonic() - started, 1),
        }

    @api.model
    def _pbrp_file_name(self, title):
        day = fields.Date.to_string(fields.Date.context_today(self))
        words = [w for w in (_file_word(product_label(self.env)), _file_word(title), day) if w]
        return '%s.pdf' % ' '.join(words)

    # ============================================================ the PDF
    @api.model
    def _pbrp_report(self, paper):
        return self.env.ref('pb_report_pdf.action_report_pdf_%s' % paper.lower())

    @api.model
    def _pbrp_pdf(self, info, look, company=None):
        """The PDF bytes of `info` printed with `look`, in this env's
        language — the same document the preview draws."""
        company = (company or self.env.company).sudo()
        doc = self._pbrp_doc(info, look)
        page = self._pbrp_page(look)
        body = self.env['ir.qweb']._render('pb_report_pdf.table_body', {'doc': doc})
        report = self._pbrp_report(look['paper'])
        letterhead = bool(look['letterhead'])
        data = {'pbrp': {
            'rp': doc,
            'page': page,
            'company': company,
            'body': body,
            'doc_lang': self.env.lang,
            'letterhead': letterhead,
            'margin_top': MARGIN_TOP_LETTERHEAD if letterhead else MARGIN_TOP,
            'header_spacing': HEADER_SPACING_LETTERHEAD if letterhead else HEADER_SPACING,
            # the PDF engine writes the numbers into these two spans
            'page_counter': escape(self.env._("Page %(page)s of %(total)s")) % {
                'page': Markup('<span class="page"></span>'),
                'total': Markup('<span class="topage"></span>')},
        }}
        ctx = {'landscape': bool(doc['sideways']), 'pbrp_footer': None}
        if letterhead and (doc['printed'] or doc['cap_note']):
            ctx['pbrp_footer'] = self.env['ir.qweb']._render(
                'pb_report_pdf.footer_extra', {'doc': doc})
        # The report RECORD carries the context: `_get_report` returns
        # `report_ref.sudo()`, so a plain record would drop it.
        report = report.with_context(**ctx)
        pdf, _ext = report._render_qweb_pdf(report, res_ids=None, data=data)
        return pdf
