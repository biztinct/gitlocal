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


class PbVendors(models.AbstractModel):
    _name = 'pb.vendors'
    _description = 'Vendors board — facade'

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
    def export_vendors(self):
        self._require()
        return self.env['pb.vendor.export'].build_vendors()

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
