# -*- coding: utf-8 -*-
"""Views people save on a filtered list ("Hanoi plant, ending soon").

Private by default; "Share with everyone" puts the view in every user's
tab row for that screen (owner ruling 2026-10-30). The record rules in
security/filter_view_rules.xml enforce that, not this file.
"""
import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

NAME_MAX = 60
#: kit 1.5.0 — a person's own column choice for a list is ONE row of this
#: model filed under `<screen>::columns`. The suffix keeps it out of the view
#: tabs (`_pbf_views` searches the bare screen key) and the record rules
#: already make it private. A saved column set is never a reason to keep a
#: field: it lives in `columns`, which the Form builder's delete check does
#: not read, and a key that no longer exists is simply skipped on read.
COLUMNS_SUFFIX = '::columns'
#: Largest column set stored (serialised characters / entries / key length).
COLUMNS_MAX_CHARS = 20000
COLUMNS_MAX_ITEMS = 150
COLUMNS_MAX_KEY = 120
MODES = ('cards', 'table')
ADMIN_GROUP = 'base.group_system'


def _clean_columns(columns):
    """A stored column set: `[{key, on}]` in order, keys unique (str or int).

    Anything else is dropped rather than refused — a bad entry from an old
    browser must never stop somebody's list from opening."""
    if not isinstance(columns, list):
        return None
    out, seen = [], set()
    for item in columns[:COLUMNS_MAX_ITEMS]:
        if isinstance(item, dict):
            key, on = item.get('key'), item.get('on', True)
        else:
            key, on = item, True
        if isinstance(key, bool) or not isinstance(key, (str, int)):
            continue
        if isinstance(key, str):
            key = key.strip()[:COLUMNS_MAX_KEY]
            if not key:
                continue
        if key in seen:
            continue
        seen.add(key)
        out.append({'key': key, 'on': bool(on)})
    if len(json.dumps(out)) > COLUMNS_MAX_CHARS:
        return None
    return out


class PbFilterView(models.Model):
    _name = 'pb.filter.view'
    _description = 'Saved filter view'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    screen = fields.Char(required=True, index=True,
                         help='Which list this view belongs to, e.g. "employees".')
    user_id = fields.Many2one('res.users', string='Saved by', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    shared = fields.Boolean(string='Share with everyone')
    filters = fields.Json(default=dict)
    # NOT `search`: a field by that name hides the ORM's search() method.
    search_text = fields.Char(string='Search')
    sequence = fields.Integer(default=10)
    # kit 1.5.0: the table view's columns ({cols: [{key, on}], mode}) — set on
    # the per-person `<screen>::columns` row. New nullable column only.
    columns = fields.Json(help='Columns chosen for the table view of this list.')

    # ------------------------------------------------------------------ api
    @api.model
    def _pbf_clean_name(self, name):
        name = ' '.join((name or '').split())[:NAME_MAX]
        if not name:
            raise UserError(_('Give the view a name.'))
        return name

    @api.model
    def pbf_save(self, screen, name, filters=None, search=None, shared=False):
        """Create a view owned by the current user; returns its payload."""
        if not screen:
            raise UserError(_('This list cannot save views.'))
        view = self.create({
            'screen': screen,
            'name': self._pbf_clean_name(name),
            'filters': filters if isinstance(filters, dict) else {},
            'search_text': (search or '')[:200],
            'shared': bool(shared),
            'user_id': self.env.uid,
        })
        return view._pbf_payload()

    def pbf_update(self, vals):
        """Rename, re-share or overwrite the filters of one of your views."""
        self.ensure_one()
        clean = {}
        if 'name' in vals:
            clean['name'] = self._pbf_clean_name(vals['name'])
        if 'shared' in vals:
            clean['shared'] = bool(vals['shared'])
        if 'filters' in vals:
            clean['filters'] = vals['filters'] if isinstance(vals['filters'], dict) else {}
        if 'search' in vals:
            clean['search_text'] = (vals['search'] or '')[:200]
        if clean:
            self.write(clean)
        return self._pbf_payload()

    def pbf_delete(self):
        self.ensure_one()
        self.unlink()
        return True

    # ------------------------------------------------ columns (kit 1.5.0)
    # The table view's columns. Effective set = the company default (an
    # administrator's "For everyone", `pb.list.layout`) → the person's own
    # choice ("Just me", one `<screen>::columns` row here). Each layer is a
    # list of `{key, on}` in order; the browser merges them with the board's
    # column set, so a key the board no longer has is skipped and a column the
    # board gained since is added with its default.

    @api.model
    def _pbf_columns_key(self, screen):
        screen = (screen or '').strip()
        if not screen or COLUMNS_SUFFIX in screen:
            raise UserError(_('This list cannot keep a choice of columns.'))
        return screen + COLUMNS_SUFFIX

    @api.model
    def _pbf_columns_row(self, screen):
        return self.search([('screen', '=', self._pbf_columns_key(screen)),
                            ('user_id', '=', self.env.uid)], limit=1)

    @api.model
    def _pbf_is_admin(self):
        return self.env.user.has_group(ADMIN_GROUP)

    @api.model
    def pbf_columns_read(self, screen):
        """`{mine, mode, company, can_company}` for one list and this person."""
        row = self._pbf_columns_row(screen)
        data = row.columns if row and isinstance(row.columns, dict) else {}
        layout = self.env['pb.list.layout']._pbf_for(screen)
        mode = data.get('mode')
        return {
            'mine': _clean_columns(data.get('cols')),
            'mode': mode if mode in MODES else None,
            'company': _clean_columns(layout.columns) if layout else None,
            'can_company': self._pbf_is_admin(),
        }

    @api.model
    def pbf_columns_save(self, screen, columns=None, scope='me', mode=None):
        """Keep a column choice. `scope='me'` = this person only (anyone);
        `scope='company'` = the default for everyone in this company
        (administrator only). `mode` ('cards' | 'table') is remembered with
        the person's own choice."""
        if scope == 'company':
            if not self._pbf_is_admin():
                raise AccessError(_('Only an administrator can choose the columns for everyone.'))
            cols = _clean_columns(columns)
            if cols is None:
                raise UserError(_('These columns could not be saved. Try again.'))
            self.env['pb.list.layout']._pbf_set(screen, cols)
            return self.pbf_columns_read(screen)
        row = self._pbf_columns_row(screen)
        data = dict(row.columns) if row and isinstance(row.columns, dict) else {}
        if columns is not None:
            cols = _clean_columns(columns)
            if cols is None:
                raise UserError(_('These columns could not be saved. Try again.'))
            data['cols'] = cols
        if mode is not None:
            data['mode'] = mode if mode in MODES else None
        if row:
            row.write({'columns': data})
        else:
            self.create({
                'screen': self._pbf_columns_key(screen),
                # Never shown: the row lives outside the view tabs.
                'name': _('Columns'),
                'user_id': self.env.uid,
                'shared': False,
                'filters': {},
                'columns': data,
            })
        return self.pbf_columns_read(screen)

    @api.model
    def pbf_columns_reset(self, screen, scope='me'):
        """Back one layer: `me` drops the person's own columns (the company
        default shows again), `company` drops the company default (the
        board's standard set shows again for everyone who has no choice of
        their own)."""
        if scope == 'company':
            if not self._pbf_is_admin():
                raise AccessError(_('Only an administrator can choose the columns for everyone.'))
            self.env['pb.list.layout']._pbf_set(screen, None)
            return self.pbf_columns_read(screen)
        row = self._pbf_columns_row(screen)
        if row and isinstance(row.columns, dict):
            data = dict(row.columns)
            data.pop('cols', None)
            row.write({'columns': data})
        return self.pbf_columns_read(screen)


class PbListLayout(models.Model):
    """The company's default columns for one list ("For everyone").

    One row per (list, company). Everybody reads it; only an administrator
    changes it, through `pb.filter.view.pbf_columns_save(scope='company')`
    (ACL: write for `base.group_system` only)."""
    _name = 'pb.list.layout'
    _description = 'List columns for everyone'
    _order = 'screen, id'

    screen = fields.Char(required=True, index=True,
                         help='Which list these columns belong to, e.g. "employees".')
    company_id = fields.Many2one('res.company', required=True, index=True, ondelete='cascade',
                                 default=lambda self: self.env.company)
    columns = fields.Json(help='The default columns, in order, for everyone in this company.')

    _screen_company_uniq = models.Constraint(
        'UNIQUE(screen, company_id)',
        'A list has one default set of columns per company.',
    )

    @api.model
    def _pbf_for(self, screen):
        return self.search([('screen', '=', (screen or '').strip()),
                            ('company_id', '=', self.env.company.id)], limit=1)

    @api.model
    def _pbf_set(self, screen, columns):
        screen = (screen or '').strip()
        if not screen or COLUMNS_SUFFIX in screen:
            raise UserError(_('This list cannot keep a choice of columns.'))
        row = self._pbf_for(screen)
        if columns is None:
            row.unlink()
            return False
        if row:
            row.write({'columns': columns})
            return row
        return self.create({'screen': screen, 'company_id': self.env.company.id,
                            'columns': columns})

    def _pbf_payload(self):
        self.ensure_one()
        mine = self.user_id.id == self.env.uid
        return {
            'key': 'v%d' % self.id,
            'id': self.id,
            'label': self.name,
            'filters': self.filters or {},
            'search': self.search_text or '',
            'shared': self.shared,
            'mine': mine,
            'owner': '' if mine else (self.user_id.name or ''),
            'builtin': False,
        }
