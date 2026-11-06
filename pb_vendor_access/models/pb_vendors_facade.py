# -*- coding: utf-8 -*-
"""`pb.vendors` — the Vendors panel's facade.

One read builds the whole board: every vendor this person is allowed to see,
what each one does, who looks after them, and when their agreement runs out.

THE BOUNDARY IS ENFORCED TWICE, DELIBERATELY. Nothing below sudoes a vendor row,
so `ir.rule` decides which rows come back — and a person who is set as the
responsible owner of one vendor sees exactly one vendor, without this file
knowing anything about that. The facade's own gate decides whether the SCREEN
opens at all, so somebody holding nothing gets one plain sentence rather than a
raw permission error out of the ORM.

The one place sudo appears is `_person`-shaped: reading a `res.users`'s name or
an `hr.employee`'s anything prefetches forty fields, several dozen of which sit
behind payroll groups on this build (R56), so a vendor manager who holds no
payroll group would get an AccessError in the middle of an action that wanted a
name. The security boundary stays the search that found the row.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .vendor_common import (PICKER_CAP, VENDOR_ROW_CAP, VENDOR_TYPES,
                            counted, fold, safe, state_label, type_label)

_logger = logging.getLogger(__name__)

#: Anybody holding one of these may open the board; what they then SEE is the
#: record rules' business, not this tuple's.
GATE_GROUPS = (
    'pb_vendor_access.group_vendor_user',
    'pb_vendor_access.group_vendor_manager',
    'pb_lifecycle.group_lifecycle_manager',
    'pb_lifecycle.group_lifecycle_admin',
)
EDIT_GROUPS = (
    'pb_vendor_access.group_vendor_manager',
    'pb_lifecycle.group_lifecycle_admin',
)


#: Cards per page on the filtered list ("Show N more" brings the next page).
PAGE_SIZE = 60


class PbVendors(models.AbstractModel):
    _name = 'pb.vendors'
    _description = 'Vendors board — facade'
    # The shared filter panel (pb_filter_kit, FILTER wave 4). Nothing here
    # sudoes a vendor search, so every count beside a value is counted under
    # the same record rules as the list itself: a vendor owner's panel counts
    # their own vendors and nobody else's.
    _inherit = ['pb.filter.mixin']

    # ================================================================= access
    @api.model
    def _is_admin(self):
        return self.env.user.has_group('base.group_system')

    @api.model
    def _has(self, groups):
        for g in groups:
            try:
                if self.env.user.has_group(g):
                    return True
            except (ValueError, KeyError):      # the group is not on this DB
                continue
        return False

    @api.model
    def _require(self):
        if self._is_admin() or self._has(GATE_GROUPS):
            return
        raise AccessError(_(
            "The vendor register is shown to the people who look after "
            "suppliers — the vendor team, the HR lifecycle team, and whoever "
            "is named as the owner of a particular vendor. Ask an "
            "administrator to add you if you should be seeing this."))

    @api.model
    def _require_edit(self):
        if self._is_admin() or self._has(EDIT_GROUPS):
            return
        raise AccessError(_(
            "Only the vendor team can add or change a vendor. You can read "
            "the register and export it."))

    @api.model
    def can_edit(self):
        return bool(self._is_admin() or self._has(EDIT_GROUPS))

    # ================================================================ the board
    @api.model
    def get_board(self, vendor_type=None, department_id=None, state=None,
                  search=None, limit=VENDOR_ROW_CAP):
        """Everything the panel draws, in one call."""
        self._require()
        Vendor = self.env['pb.vendor']
        domain = [('active', '=', True)]
        if vendor_type:
            domain.append(('vendor_type', '=', vendor_type))
        if department_id:
            domain.append(('department_id', '=', int(department_id)))
        if state:
            domain.append(('agreement_state', '=', state))

        vendors = Vendor.search(domain, limit=(limit or None) and (limit + 1),
                                order='name')
        truncated = bool(limit) and len(vendors) > limit
        if truncated:
            vendors = vendors[:limit]

        # The text search is done in PYTHON over folded text (R28/R78):
        # Postgres on this box has no `unaccent`, so `ilike '%bui%'` finds
        # nothing for "Bùi" and a filter that matches nothing is a broken
        # promise (R27).
        needle = fold(search)
        rows = [self._row(v) for v in vendors]
        if needle:
            rows = [r for r in rows if needle in r['haystack']]

        return {
            'can_edit': self.can_edit(),
            'rows': rows,
            'kpis': self._kpis(rows),
            'facets': self._facets(rows),
            'type_options': [{'key': k, 'label': type_label(k, self.env)}
                             for k, _l in VENDOR_TYPES],
            'state_options': self._state_options(),
            'truncated': truncated,
            'headline': self._headline(rows),
            'currency': self.env.company.currency_id.name or '',
        }

    def _row(self, vendor):
        v = vendor.sudo()                       # names only; the search was the
        #                                         boundary (R56)
        return {
            'id': vendor.id,
            'name': v.name or '',
            'type': v.vendor_type or '',
            'type_label': type_label(v.vendor_type, self.env),
            'contact_name': v.contact_name or '',
            'contact_email': v.contact_email or '',
            'contact_phone': v.contact_phone or '',
            'department': v.department_id.name or '',
            'department_id': v.department_id.id or 0,
            'responsible': v.responsible_user_id.name or '',
            'responsible_id': v.responsible_user_id.id or 0,
            'country': v.country_id.name or '',
            'agreements': v.agreement_count,
            'next_end': fields.Date.to_string(v.next_end_date) or '',
            'state': v.agreement_state or '',
            'state_label': (state_label(v.agreement_state, self.env)
                            if v.agreement_state else _('No agreement yet')),
            'mine': v.responsible_user_id.id == self.env.uid,
            'haystack': ' '.join(fold(x) for x in (
                v.name, v.contact_name, v.contact_email,
                v.department_id.name, v.responsible_user_id.name)),
        }

    def _kpis(self, rows):
        """Every count is computed from THE LIST THE SCREEN SHOWS (R80).

        A chip that counts one thing over a list that shows another is two
        bugs: a filter that matches nothing, and a quiet admission that a row
        exists which the board is not admitting to.
        """
        return {
            'vendors': len(rows),
            'expiring': len([r for r in rows if r['state'] == 'expiring']),
            'expired': len([r for r in rows if r['state'] == 'expired']),
            'none': len([r for r in rows if not r['state']]),
            'mine': len([r for r in rows if r['mine']]),
        }

    def _facets(self, rows):
        """Only the values the data ACTUALLY USES (R27).

        A filter chip that matches nothing is a broken promise, so the FILTER
        list is built from the rows. The ADD dialog offers every type — a
        register that could only ever grow into the categories it already has
        is not a register.
        """
        types, depts, states = {}, {}, {}
        for r in rows:
            if r['type']:
                types[r['type']] = types.get(r['type'], 0) + 1
            if r['department_id']:
                depts[r['department_id']] = depts.get(r['department_id'], 0) + 1
            key = r['state'] or 'none'
            states[key] = states.get(key, 0) + 1
        dept_names = {r['department_id']: r['department'] for r in rows
                      if r['department_id']}
        return {
            'types': sorted(
                [{'key': k, 'label': type_label(k, self.env), 'n': n}
                 for k, n in types.items()],
                key=lambda x: -x['n']),
            'departments': sorted(
                [{'key': k, 'label': dept_names.get(k, ''), 'n': n}
                 for k, n in depts.items()],
                key=lambda x: -x['n']),
            'states': sorted(
                [{'key': k,
                  'label': (state_label(k, self.env) if k != 'none'
                            else _('No agreement yet')),
                  'n': n}
                 for k, n in states.items()],
                key=lambda x: -x['n']),
        }

    def _state_options(self):
        from .vendor_common import AGREEMENT_STATES
        return [{'key': k, 'label': self.env._(lbl)}
                for k, lbl in AGREEMENT_STATES]

    def _headline(self, rows):
        """ONE expression per sentence, so the spaces survive (R34)."""
        if not rows:
            return _("No vendors on the register yet.")
        expiring = len([r for r in rows if r['state'] == 'expiring'])
        expired = len([r for r in rows if r['state'] == 'expired'])
        if expired:
            return _("%(n)s on the register, and %(x)s already run out.",
                     n=counted(len(rows), _("1 vendor"), _("%s vendors")),
                     x=counted(expired, _("1 agreement has"),
                               _("%s agreements have")))
        if expiring:
            return _("%(n)s on the register, %(x)s coming up for renewal.",
                     n=counted(len(rows), _("1 vendor"), _("%s vendors")),
                     x=counted(expiring, _("1 agreement"), _("%s agreements")))
        return _("%s on the register, and nothing needs renewing.",
                 counted(len(rows), _("1 vendor"), _("%s vendors")))

    # ============================================================ filter panel
    # The board used to load up to 800 vendors, count its chips over them and
    # fold the search in Python. The panel now counts on the server over the
    # whole register and the cards come one page at a time. `get_board` stays
    # as it was for the spreadsheet (R4).

    def _pbf_model(self):
        return 'pb.vendor'

    def _pbf_screen(self):
        return 'vendors'

    def _pbf_base_domain(self):
        return [('active', '=', True), '|', ('company_id', '=', False),
                ('company_id', 'in', self.env.companies.ids)]

    def _pbf_search_fields(self):
        return ['name', 'contact_name', 'contact_email', 'department_id.name',
                'responsible_user_id.name']

    @api.model
    def _pbf_search_domain(self, search):
        """The plain `ilike`, OR the folded match the board always had.

        Postgres here has no `unaccent`, so `ilike '%bui%'` misses "Bùi"
        (R28/R78). The register is small (the board capped it at 800), so the
        fold runs in Python over the vendors this person may see — the search
        is not sudoed, the names are read the way `_row` reads them — and
        comes back as an id list.
        """
        plain = super()._pbf_search_domain(search)
        needle = fold(search)
        if plain is None or not needle:
            return plain
        # the panel builds this domain once per count; fold once per call
        key = ('pb_vendors.fold', self.env.uid, needle)
        cache = self.env.cr.cache
        if key not in cache:
            found = self.env['pb.vendor'].search(self._pbf_base_domain(), limit=5000)
            hits = []
            for s in found.sudo():              # names only (R56)
                hay = ' '.join(fold(x) for x in (
                    s.name, s.contact_name, s.contact_email,
                    s.department_id.name, s.responsible_user_id.name))
                if needle in hay:
                    hits.append(s.id)
            cache[key] = hits
        hits = cache[key]
        if not hits:
            return plain
        return Domain.OR([plain, Domain('id', 'in', hits)])

    def _pbf_sorts(self):
        return [
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name asc, id asc'},
            {'key': 'name_desc', 'label': _('Name, Z to A'), 'order': 'name desc, id desc'},
            {'key': 'ending', 'label': _('Agreement ending soonest'),
             'order': 'next_end_date asc nulls last, name asc'},
            {'key': 'newest', 'label': _('Newest on the register'),
             'order': 'create_date desc, id desc'},
        ]

    def _pbf_spec(self):
        uid = self.env.uid
        return [
            # ---- pinned: what they do, where their agreement is, who owns it
            {'key': 'type', 'label': _('What they do'), 'icon': 'briefcase',
             'group': 'work', 'type': 'selection', 'path': 'vendor_type',
             'pinned': True},
            {'key': 'agreement', 'label': _('Agreement'), 'icon': 'fileText',
             'group': 'contract', 'type': 'selection', 'path': 'agreement_state',
             'pinned': True, 'none_label': _('No agreement yet')},
            {'key': 'owner', 'label': _('Who looks after them'), 'icon': 'userCheck',
             'group': 'people', 'type': 'many2one', 'path': 'responsible_user_id',
             'pinned': True},
            # ---- more filters
            {'key': 'mine', 'label': _('Looked after by me'), 'icon': 'user',
             'group': 'people', 'type': 'choice',
             'options': [
                 {'value': 'yes', 'label': _('I look after them'), 'tone': 'blue',
                  'domain': [('responsible_user_id', '=', uid)]},
                 {'value': 'no', 'label': _('Someone else does'), 'tone': 'slate',
                  'domain': [('responsible_user_id', '!=', uid)]},
             ]},
            {'key': 'department', 'label': _('Team they work with'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'department_id',
             'none_label': _('No team')},
            {'key': 'country', 'label': _('Country'), 'icon': 'globe',
             'group': 'work', 'type': 'many2one', 'path': 'country_id',
             'none_label': _('Not recorded')},
            {'key': 'next_end', 'label': _('Next agreement ends'), 'icon': 'calendarClock',
             'group': 'dates', 'type': 'date', 'path': 'next_end_date',
             'presets': 'future', 'none_label': _('Nothing recorded')},
            {'key': 'company', 'label': _('Company'), 'icon': 'landmark',
             'group': 'work', 'type': 'many2one', 'path': 'company_id',
             'none_label': _('Every company')},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All vendors'), 'icon': 'briefcase', 'filters': {}},
            {'key': 'expiring', 'label': _('Coming up for renewal'),
             'filters': {'agreement': ['expiring']}},
            {'key': 'expired', 'label': _('Already run out'),
             'filters': {'agreement': ['expired']}},
            {'key': 'none', 'label': _('Nothing recorded'),
             'filters': {'agreement': [False]}},
            {'key': 'mine', 'label': _('I look after'),
             'filters': {'mine': ['yes']}},
        ]

    @api.model
    def pbf_layout(self):
        try:
            self._require()
        except AccessError as e:
            return {'refused': str(e.args[0] if e.args else e)}
        return super().pbf_layout()

    @api.model
    def pbf_counts(self, filters=None, search=None, keys=None, **kw):
        # **kw rides every kit argument through (kit 1.3.0 added `views`).
        self._require()
        return super().pbf_counts(filters=filters, search=search, keys=keys, **kw)

    @api.model
    def get_head(self):
        """The header and the numbers line, counted over the whole register
        this person may see (whatever is filtered): the figures that filter
        tick the same filters as the built-in views."""
        self._require()
        Vendor = self.env['pb.vendor']
        base = self._pbf_base_domain()

        def n(extra):
            return safe(lambda: Vendor.search_count(base + extra), 0, 'a vendor count')

        return {
            'can_edit': self.can_edit(),
            # the Add dialog offers every type, not only the ones in use
            'type_options': [{'key': k, 'label': type_label(k, self.env)}
                             for k, _l in VENDOR_TYPES],
            'kpis': {
                'vendors': n([]),
                'expiring': n([('agreement_state', '=', 'expiring')]),
                'expired': n([('agreement_state', '=', 'expired')]),
                'none': n([('agreement_state', '=', False)]),
                'mine': n([('responsible_user_id', '=', self.env.uid)]),
            },
        }

    @api.model
    def get_vendor_page(self, filters=None, search=None, sort=None, offset=0,
                        limit=PAGE_SIZE):
        """One page of cards for the panel's state, with the sentence under
        the title said about the SAME list (R34: one expression each)."""
        self._require()
        Vendor = self.env['pb.vendor']
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        domain = self.pbf_domain(filters or {}, search)
        vendors = Vendor.search(domain, order=self.pbf_order(sort) or 'name',
                                offset=offset, limit=limit)
        rows = []
        for v in vendors:
            try:
                row = self._row(v)
                row.pop('haystack', None)
                rows.append(row)
            except Exception as ex:  # noqa: BLE001 — one bad card never blanks the list
                _logger.debug("Vendor card failed: %s", ex)
        total = Vendor.search_count(domain)
        out = {'rows': rows, 'total': total, 'offset': offset}
        if not offset:
            expired = Vendor.search_count(Domain.AND([domain, Domain('agreement_state', '=', 'expired')]))
            expiring = Vendor.search_count(Domain.AND([domain, Domain('agreement_state', '=', 'expiring')]))
            out['headline'] = self._headline_counts(total, expiring, expired)
        return out

    def _headline_counts(self, total, expiring, expired):
        """`_headline`, said from counts instead of loaded rows."""
        if not total:
            if self.env['pb.vendor'].search_count(self._pbf_base_domain(), limit=1):
                return _("No vendor on the register matches these filters.")
            return _("No vendors on the register yet.")
        if expired:
            return _("%(n)s on the register, and %(x)s already run out.",
                     n=counted(total, _("1 vendor"), _("%s vendors")),
                     x=counted(expired, _("1 agreement has"),
                               _("%s agreements have")))
        if expiring:
            return _("%(n)s on the register, %(x)s coming up for renewal.",
                     n=counted(total, _("1 vendor"), _("%s vendors")),
                     x=counted(expiring, _("1 agreement"), _("%s agreements")))
        return _("%s on the register, and nothing needs renewing.",
                 counted(total, _("1 vendor"), _("%s vendors")))

    # ================================================================ the drawer
    @api.model
    def get_vendor(self, vendor_id):
        self._require()
        vendor = self.env['pb.vendor'].browse(int(vendor_id))
        vendor.check_access('read')             # the record rule, out loud
        v = vendor.sudo()
        agreements = v.agreement_ids.filtered(lambda a: a.active).sorted(
            lambda a: (a.date_start or fields.Date.today()), reverse=True)
        return {
            'vendor': self._row(vendor),
            'notes': v.notes or '',
            'can_edit': self.can_edit(),
            'agreements': [self._agreement(a) for a in agreements],
        }

    def _agreement(self, a):
        return {
            'id': a.id,
            'name': a.name or '',
            'date_start': fields.Date.to_string(a.date_start) or '',
            'date_end': fields.Date.to_string(a.date_end) or '',
            'renewal_date': fields.Date.to_string(a.renewal_date) or '',
            'state': a.state or '',
            'state_label': state_label(a.state, self.env),
            'days_left': a.days_left,
            'value': a.value or 0.0,
            'currency': a.currency_id.name or '',
            'note': a.note or '',
            'is_renewed': a.is_renewed,
            'renewed_by': a.renewed_by_id.name or '',
            'last_alert_on': fields.Date.to_string(a.last_alert_on) or '',
            'files': [{'id': f.id, 'name': f.name or '',
                       'url': '/web/content/%s?download=true' % f.id}
                      for f in a.attachment_ids],
        }

    # ================================================================= writing
    @api.model
    def save_vendor(self, vals):
        """Add or edit. One door, because two doors drift."""
        self._require_edit()
        vals = dict(vals or {})
        vendor_id = int(vals.pop('id', 0) or 0)
        payload = self._clean_vendor(vals)
        if vendor_id:
            vendor = self.env['pb.vendor'].browse(vendor_id)
            vendor.check_access('write')
            vendor.write(payload)
            return {'ok': True, 'id': vendor.id,
                    'message': _("\"%s\" has been updated.", vendor.name)}
        if not payload.get('name'):
            raise UserError(_("Say who they are."))
        vendor = self.env['pb.vendor'].create(payload)
        return {'ok': True, 'id': vendor.id,
                'message': _("\"%s\" has been added to the register.",
                             vendor.name)}

    def _clean_vendor(self, vals):
        out = {}
        for key in ('name', 'contact_name', 'contact_email', 'contact_phone',
                    'notes'):
            if key in vals:
                out[key] = (vals.get(key) or '').strip()
        if vals.get('vendor_type'):
            out['vendor_type'] = vals['vendor_type']
        for key in ('department_id', 'responsible_user_id', 'country_id'):
            if key in vals:
                out[key] = int(vals.get(key) or 0) or False
        return out

    @api.model
    def save_agreement(self, vals):
        self._require_edit()
        vals = dict(vals or {})
        agreement_id = int(vals.pop('id', 0) or 0)
        payload = {}
        for key in ('name', 'note'):
            if key in vals:
                payload[key] = (vals.get(key) or '').strip()
        for key in ('date_start', 'date_end', 'renewal_date'):
            if key in vals:
                payload[key] = vals.get(key) or False
        if 'value' in vals:
            payload['value'] = float(vals.get('value') or 0.0)
        if agreement_id:
            rec = self.env['pb.vendor.agreement'].browse(agreement_id)
            rec.check_access('write')
            rec.write(payload)
            return {'ok': True, 'id': rec.id,
                    'message': _("The agreement has been updated.")}
        vendor_id = int(vals.get('vendor_id') or 0)
        if not vendor_id:
            raise UserError(_("An agreement has to belong to a vendor."))
        if not payload.get('name'):
            raise UserError(_("Say what the agreement covers."))
        if not payload.get('date_end'):
            raise UserError(_("Say when it ends. That is the date everything "
                              "else on this screen is about."))
        payload['vendor_id'] = vendor_id
        rec = self.env['pb.vendor.agreement'].create(payload)
        return {'ok': True, 'id': rec.id,
                'message': _("The agreement has been added.")}

    @api.model
    def renew_agreement(self, agreement_id, vals=None):
        self._require_edit()
        rec = self.env['pb.vendor.agreement'].browse(int(agreement_id))
        rec.check_access('write')
        new = rec.action_renew(vals)
        return {'ok': True, 'id': new.id,
                'message': _("A new agreement runs from %(start)s to %(end)s. "
                             "The old one is kept, marked as replaced.",
                             start=new.date_start, end=new.date_end)}

    @api.model
    def attach(self, agreement_id, filename, data_b64):
        """A file on an agreement. The attachment is created against the
        agreement, so it inherits its record rule and disappears with it."""
        self._require_edit()
        rec = self.env['pb.vendor.agreement'].browse(int(agreement_id))
        rec.check_access('write')
        name = (filename or '').strip() or _('Agreement file')
        att = self.env['ir.attachment'].create({
            'name': name,
            'datas': data_b64,
            'res_model': 'pb.vendor.agreement',
            'res_id': rec.id,
        })
        rec.write({'attachment_ids': [(4, att.id)]})
        return {'ok': True, 'id': att.id,
                'message': _("\"%s\" has been filed against the agreement.",
                             name)}

    @api.model
    def detach(self, agreement_id, attachment_id):
        self._require_edit()
        rec = self.env['pb.vendor.agreement'].browse(int(agreement_id))
        rec.check_access('write')
        rec.write({'attachment_ids': [(3, int(attachment_id))]})
        return {'ok': True, 'message': _("The file has been taken off.")}

    # =============================================================== the pickers
    @api.model
    def department_options(self, term=None):
        """Folded in Python, capped, and only the two columns it needs."""
        needle = fold(term)
        rows = self.env['hr.department'].sudo().search_read(
            [], ['name'], limit=400, order='name')
        out = [{'id': r['id'], 'name': r['name'] or ''} for r in rows
               if not needle or needle in fold(r['name'])]
        return out[:PICKER_CAP]

    @api.model
    def user_options(self, term=None):
        needle = fold(term)
        rows = self.env['res.users'].sudo().search_read(
            [('active', '=', True), ('share', '=', False)],
            ['name', 'login'], limit=600, order='name')
        out = [{'id': r['id'], 'name': r['name'] or '',
                'login': r['login'] or ''} for r in rows
               if not needle or needle in fold(r['name'])
               or needle in fold(r['login'])]
        return out[:PICKER_CAP]

    @api.model
    def country_options(self):
        rows = self.env['res.country'].sudo().search_read(
            [], ['name'], order='name')
        return [{'id': r['id'], 'name': r['name'] or ''} for r in rows]

    # ================================================================ the jobs
    @api.model
    def run_alerts(self):
        """"Check the agreements now" — and it does EXACTLY what the night
        does (R53). A button that runs four fifths of a job produces a number
        nobody can compare with the morning's log."""
        self._require_edit()
        res = self.env['pb.vendor.alerts'].run(limit=None)
        return {'ok': True, 'message': res['message'], 'counters': res}

    @api.model
    def export_vendors(self, filters=None, search=None):
        """The spreadsheet. With the panel's `filters`/`search` it holds the
        vendors the list shows right now (every page, not just the loaded
        one, R6); without them, the whole register as before."""
        self._require()
        ids = None
        if filters or (search or '').strip():
            ids = self.env['pb.vendor'].search(self.pbf_domain(filters or {}, search)).ids
        return self.env['pb.vendor.export'].build_vendors(vendor_ids=ids)

    # ================================================================== probes
    @api.model
    def probe(self):
        """Each independent number gets its OWN try/except (R92: at WARNING,
        with the traceback, so a failure is findable on a live server)."""
        return {
            'vendors': safe(
                lambda: self.env['pb.vendor'].search_count(
                    [('active', '=', True)]),
                0, 'the vendor count'),
            'agreements': safe(
                lambda: self.env['pb.vendor.agreement'].search_count(
                    [('active', '=', True)]),
                0, 'the agreement count'),
        }
