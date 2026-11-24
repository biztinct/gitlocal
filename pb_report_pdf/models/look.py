# -*- coding: utf-8 -*-
"""The "PDF look" of a report (`pb.report.pdf.look`).

One look per person per report (`source_model` + `source_id`), cloned from
the Explorer's saved views (`pb_explorer/models/pb_explorer_view.py`,
`security/pb_explorer_rules.xml`): private to whoever saved it unless the
report's owner shares it with everyone who opens that report; changed only
by its owner. A company default look ("Use this look for every new report")
is kept by administrators only.

A look is a set of PRINTING choices, never data: which columns to print and
how wide, the paper, the heading. The rows always come from the report
itself, read as the person printing — so a shared look never shows anybody
more than their own screen.
"""
from odoo import api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.pb_doc_studio.models.doc_common import FONT_KEYS, SIZES

PAPERS = ('A4', 'A3')
TURNS = ('fit', 'upright', 'sideways')
#: Header-row colours, from the locked palette: (key, background, text).
COLORS = (
    ('indigo', '#5A4BB0', '#FFFFFF'),
    ('ink', '#241F52', '#FFFFFF'),
    ('soft', '#EDEAF8', '#241F52'),
    ('slate', '#334155', '#FFFFFF'),
    ('plain', '#F3F4F8', '#1F2430'),
)
COLOR_KEYS = tuple(c[0] for c in COLORS)
TEXT_MAX = 160
NOTE_MAX = 600
MAX_COLUMNS = 80

LOOK_DEFAULT = {
    'paper': 'A4',
    'turn': 'fit',
    'letterhead': True,
    'font': 'clean',
    'size': 10,
    'title': '',          # '' = the report's own name
    'sub': '',            # '' = the period and filters, in words
    'sub_on': True,       # False = no second line at all
    'color': 'indigo',
    'stripes': True,
    'columns': {},        # key -> {'hide': bool, 'w': percent}
    'groups': True,       # group headings and subtotals, as on screen
    'total': True,        # grand total row
    'printed': True,      # "Printed on … by …"
    'pages': True,        # "Page 1 of 3"
    'note': '',           # closing note under the table
}
#: What a company default look carries: the page, never one report's columns
#: or words.
DEFAULT_KEYS = ('paper', 'turn', 'letterhead', 'font', 'size', 'color', 'stripes',
                'groups', 'total', 'printed', 'pages')
_KEY_OK = set('abcdefghijklmnopqrstuvwxyz0123456789_.')


def clean_look(look, base=None):
    """A look with every key and only allowed values (the browser is never
    trusted). Missing keys come from `base` (else the built-in look)."""
    look = look if isinstance(look, dict) else {}
    out = dict(base or LOOK_DEFAULT)
    out['columns'] = dict(out.get('columns') or {})
    if look.get('paper') in PAPERS:
        out['paper'] = look['paper']
    if look.get('turn') in TURNS:
        out['turn'] = look['turn']
    if look.get('font') in FONT_KEYS:
        out['font'] = look['font']
    try:
        if 'size' in look:
            size = int(look['size'])
            if size in SIZES:
                out['size'] = size
    except (TypeError, ValueError):
        pass
    if look.get('color') in COLOR_KEYS:
        out['color'] = look['color']
    for key in ('letterhead', 'stripes', 'groups', 'total', 'printed', 'pages', 'sub_on'):
        if key in look:
            out[key] = bool(look[key])
    for key, cap in (('title', TEXT_MAX), ('sub', TEXT_MAX * 2), ('note', NOTE_MAX)):
        if key in look:
            text = str(look.get(key) or '')
            text = ''.join(ch for ch in text if ch in '\n\t' or ord(ch) >= 32)
            out[key] = (text if key == 'note' else ' '.join(text.split()))[:cap].strip()
    if 'columns' in look:
        cols = {}
        raw = look.get('columns')
        if isinstance(raw, dict):
            for key, val in list(raw.items())[:MAX_COLUMNS]:
                if not isinstance(key, str) or not key or len(key) > 140 \
                        or not set(key) <= _KEY_OK or not isinstance(val, dict):
                    continue
                item = {}
                if 'hide' in val:
                    item['hide'] = bool(val['hide'])
                try:
                    width = float(val.get('w')) if val.get('w') not in (None, '') else None
                except (TypeError, ValueError):
                    width = None
                if width is not None and 2 <= width <= 90:
                    item['w'] = round(width, 2)
                if item:
                    cols[key] = item
        out['columns'] = cols
    return out


class PbReportPdfLook(models.Model):
    _name = 'pb.report.pdf.look'
    _description = 'PDF look of a report'
    _order = 'id desc'

    source_model = fields.Char(string='Report kind', index=True)
    source_id = fields.Integer(string='Report', index=True)
    user_id = fields.Many2one('res.users', string='Saved by', required=True, index=True,
                              ondelete='cascade', default=lambda self: self.env.user)
    shared = fields.Boolean(string='Everyone who opens this report')
    is_default = fields.Boolean(string='Company default', index=True)
    company_id = fields.Many2one('res.company', string='Company', ondelete='cascade',
                                 index=True)
    look = fields.Json(string='Look', default=dict)

    @api.model_create_multi
    def create(self, vals_list):
        self._pbrp_guard(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._pbrp_guard([vals])
        if self.filtered('is_default') and not self.env.user._is_admin() \
                and not self.env.su:
            raise AccessError(self.env._("Only administrators can change the company's "
                                         "default look."))
        return super().write(vals)

    def _pbrp_guard(self, vals_list):
        """A company default is for administrators only — also through the
        plain record API, not just the designer."""
        if self.env.su or self.env.user._is_admin():
            return
        if any(v.get('is_default') for v in vals_list):
            raise AccessError(self.env._("Only administrators can set the company's "
                                         "default look."))

    # ------------------------------------------------------------- reading
    @api.model
    def _pbrp_default_for(self, company):
        return self.sudo().search([('is_default', '=', True),
                                   ('company_id', '=', company.id)], limit=1)

    @api.model
    def _pbrp_find(self, source_model, source_id, user, owner=None, company=None):
        """(record, origin) of the look `user` prints with: their own, else
        the one the report's owner shared, else any shared one, else the
        company default, else nothing. Read with sudo — it is a printing
        choice, never data; the caller has already checked the report."""
        Look = self.sudo()
        base = [('source_model', '=', source_model), ('source_id', '=', source_id),
                ('is_default', '=', False)]
        own = Look.search(base + [('user_id', '=', user.id)], limit=1)
        if own:
            return own, 'mine'
        shared = Look.search(base + [('shared', '=', True)], order='id desc')
        if owner:
            first = shared.filtered(lambda l: l.user_id == owner)[:1]
            if first:
                return first, 'shared'
        if shared:
            return shared[:1], 'shared'
        default = self._pbrp_default_for(company or user.company_id)
        if default:
            return default, 'default'
        return Look.browse(), 'builtin'

    @api.model
    def _pbrp_resolve(self, source_model, source_id, user, owner=None, company=None):
        """(clean look dict, origin, record). `company`: whose default look
        applies (the company the person is working in; else their own)."""
        company = company or user.company_id
        rec, origin = self._pbrp_find(source_model, source_id, user, owner, company)
        if origin == 'default':
            base = clean_look({k: v for k, v in (rec.look or {}).items() if k in DEFAULT_KEYS})
            return base, origin, rec
        if origin in ('mine', 'shared'):
            default = self._pbrp_default_for(company)
            start = clean_look({k: v for k, v in (default.look or {}).items()
                                if k in DEFAULT_KEYS}) if default else None
            return clean_look(rec.look or {}, base=start), origin, rec
        return clean_look({}), origin, rec
