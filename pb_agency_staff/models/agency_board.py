# -*- coding: utf-8 -*-
"""`pb.agency.board` — the "Agency staff" lens's only server surface.

Quiet glance (on site, starting later, ending in 30 days, ended), the filter
panel, one person's drawer (add / change / documents / end). HR only; every
read is scoped to the reader's companies by the record rule.
"""
import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

PAGE_SIZE = 40
GATE = 'hr.group_hr_user'
MIME_OK = ('application/pdf', 'image/png', 'image/jpeg')
MAX_FILE_BYTES = 10 * 1024 * 1024


class PbAgencyBoard(models.AbstractModel):
    _name = 'pb.agency.board'
    _inherit = ['pb.filter.mixin']
    _description = 'Agency staff — screen data'

    @api.model
    def _can(self):
        return bool(self.env.su or self.env.user.has_group(GATE))

    @api.model
    def _refusal(self):
        return _("Agency staff are looked after by HR. Ask your administrator "
                 "for an HR role to see this list.")

    @api.model
    def _require(self):
        if not self._can():
            raise AccessError(self._refusal())

    @api.model
    def _W(self):
        return self.env['pb.agency.worker']

    @api.model
    def _safe(self, fn, default=0):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('agency board metric failed: %s', e)
            return default

    @api.model
    def _where(self):
        W = self._W()
        return {
            'on_site': W._dom_on_site(),
            'upcoming': W._dom_upcoming(),
            'ending': W._dom_ending(),
            'ended': W._dom_ended(),
        }

    @api.model
    def get_board(self):
        if not self._can():
            return {'allowed': False, 'why': self._refusal()}
        W = self._W().with_context(active_test=False)
        base = [('company_id', 'in', self.env.companies.ids)]
        kpis = {k: self._safe(lambda d=d: W.search_count(base + d))
                for k, d in self._where().items()}
        return {'allowed': True, 'why': '', 'kpis': kpis,
                'total': self._safe(lambda: W.search_count(base)),
                'can_delete': self.env.user.has_group('hr.group_hr_manager')}

    # ------------------------------------------------------------ filter kit
    def _pbf_model(self):
        return 'pb.agency.worker'

    def _pbf_screen(self):
        return 'agency_staff'

    def _pbf_records(self):
        return self.env['pb.agency.worker'].with_context(active_test=False)

    def _pbf_base_domain(self):
        return [('company_id', 'in', self.env.companies.ids)]

    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        return Domain.OR([Domain('name', 'ilike', q),
                          Domain('job_title', 'ilike', q),
                          Domain('vendor_id', 'in', self.env['pb.vendor'].sudo()
                                 .search([('name', 'ilike', q)], limit=200).ids)])

    def _pbf_sorts(self):
        return [
            {'key': 'name', 'label': _('Name, A to Z'), 'order': 'name, id'},
            {'key': 'ending', 'label': _('Ending soonest'),
             'order': 'date_end, name'},
            {'key': 'new', 'label': _('Added last'), 'order': 'id desc'},
        ]

    def _pbf_spec(self):
        where = self._where()
        return [
            {'key': 'where', 'label': _('Where they are'), 'icon': 'mapPin',
             'group': 'people', 'type': 'choice', 'pinned': True,
             'requires': ['date_start', 'date_end'],
             'options': [
                 {'value': 'on_site', 'label': _('On site'), 'tone': 'green',
                  'domain': where['on_site']},
                 {'value': 'upcoming', 'label': _('Starting later'),
                  'tone': 'blue', 'domain': where['upcoming']},
                 {'value': 'ending', 'label': _('Ending in 30 days'),
                  'tone': 'amber', 'domain': where['ending']},
                 {'value': 'ended', 'label': _('Ended'), 'tone': 'slate',
                  'domain': where['ended']},
             ]},
            {'key': 'agency', 'label': _('Agency'), 'icon': 'building',
             'group': 'people', 'type': 'many2one', 'path': 'vendor_id', 'label_sudo': True,
             'pinned': True},
            {'key': 'team', 'label': _('Team'), 'icon': 'users',
             'group': 'people', 'type': 'many2one', 'path': 'department_id'},
            {'key': 'site', 'label': _('Site'), 'icon': 'mapPin',
             'group': 'people', 'type': 'many2one',
             'path': 'work_location_id'},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('Everyone'), 'icon': 'users',
             'filters': {}},
            {'key': 'on_site', 'label': _('On site'),
             'filters': {'where': ['on_site']}},
            {'key': 'ending', 'label': _('Ending soon'),
             'filters': {'where': ['ending']}},
        ]

    @api.model
    def pbf_layout(self, **kw):
        if not self._can():
            return {'refused': self._refusal()}
        return super().pbf_layout(**kw)

    @api.model
    def get_page(self, filters=None, search=None, sort=None, offset=0,
                 limit=PAGE_SIZE):
        if not self._can():
            return {'rows': [], 'total': 0, 'offset': 0}
        W = self._pbf_records()
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'name, id'
        rows = [self._row(w) for w in W.search(domain, order=order,
                                               offset=offset, limit=limit)]
        return {'rows': rows, 'total': W.search_count(domain),
                'offset': offset}

    @api.model
    def _day(self, value):
        from odoo.tools.misc import format_date
        return format_date(self.env, value, date_format='d MMM y') \
            if value else ''

    @api.model
    def _row(self, w):
        status = dict(w._fields['status']._description_selection(self.env))
        ending = bool(w.active and w.date_end and
                      0 <= (w.date_end - fields.Date.context_today(w)).days
                      <= 30)
        return {
            'id': w.id, 'name': w.name or '', 'role': w.job_title or '',
            'agency': w.vendor_id.sudo().name or '', 'team': w.department_id.name or '',
            'site': w.work_location_id.name or '',
            'manager': w.manager_id.name or '',
            'start': self._day(w.date_start), 'end': self._day(w.date_end),
            'status': w.status, 'status_label': status.get(w.status, ''),
            'ending': ending, 'docs': len(w.attachment_ids),
            'active': w.active,
        }

    # ------------------------------------------------------------ options
    @api.model
    def options(self):
        self._require()
        companies = self.env.companies.ids
        def rows(model, extra=None):
            Model = self.env[model]
            dom = list(extra or [])
            if 'company_id' in Model._fields:
                dom.append(('company_id', 'in', companies + [False]))
            return [{'id': r.id, 'label': r.display_name or ''}
                    for r in Model.search(dom, limit=300)]
        agencies = []
        try:
            agencies = [{'id': v.id, 'label': v.name or ''}
                        for v in self.env['pb.vendor'].sudo().search(
                            [('company_id', 'in', companies + [False])],
                            order='name', limit=300)]
        except Exception:       # noqa: BLE001
            agencies = []
        return {'agencies': agencies, 'teams': rows('hr.department'),
                'sites': rows('hr.work.location'),
                'companies': [{'id': c.id, 'label': c.name}
                              for c in self.env.companies],
                'company_id': self.env.company.id}

    @api.model
    def managers(self, term='', company_id=0):
        self._require()
        domain = [('company_id', 'in', [int(company_id)] if company_id
                   else self.env.companies.ids)]
        if (term or '').strip():
            domain.append(('name', 'ilike', term.strip()))
        return [{'id': e.id, 'label': e.name or '',
                 'sub': e.job_title or ''}
                for e in self.env['hr.employee'].search(domain, order='name',
                                                        limit=20)]

    # ------------------------------------------------------------ one person
    @api.model
    def _worker(self, worker_id):
        self._require()
        rec = self._W().with_context(active_test=False).search(
            [('id', '=', int(worker_id or 0))], limit=1)
        if not rec:
            raise UserError(_("This person is no longer on the list."))
        return rec

    @api.model
    def get_worker(self, worker_id):
        w = self._worker(worker_id)
        return dict(self._row(w), **{
            'job_title': w.job_title or '',
            'vendor_id': w.vendor_id.id, 'department_id': w.department_id.id,
            'work_location_id': w.work_location_id.id,
            'manager_id': w.manager_id.id, 'company_id': w.company_id.id,
            'date_start': fields.Date.to_string(w.date_start) or '',
            'date_end': fields.Date.to_string(w.date_end) or '',
            'phone': w.phone or '', 'email': w.email or '',
            'notes': w.notes or '',
            'files': [{'id': a.id, 'name': a.name or '',
                       'url': '/web/content/%s?download=true' % a.id}
                      for a in w.attachment_ids],
        })

    @api.model
    def save_worker(self, vals):
        self._require()
        vals = vals if isinstance(vals, dict) else {}
        out = {}
        for key in ('name', 'job_title', 'phone', 'email', 'notes'):
            if key in vals:
                out[key] = (vals.get(key) or '').strip() or False
        for key in ('vendor_id', 'department_id', 'work_location_id',
                    'manager_id', 'company_id'):
            if key in vals:
                try:
                    out[key] = int(vals.get(key) or 0) or False
                except (TypeError, ValueError):
                    out[key] = False
        for key in ('date_start', 'date_end'):
            if key in vals:
                out[key] = vals.get(key) or False
        if out.get('company_id') and \
                out['company_id'] not in self.env.companies.ids:
            raise UserError(_("Pick a company you work in."))
        worker_id = int(vals.get('id') or 0)
        if worker_id:
            rec = self._worker(worker_id)
            rec.write(out)
            return {'ok': True, 'id': rec.id,
                    'msg': _("%s has been updated.", rec.name)}
        if not out.get('name'):
            raise UserError(_("Type their name."))
        if not out.get('company_id'):
            out['company_id'] = self.env.company.id
        rec = self._W().create(out)
        return {'ok': True, 'id': rec.id,
                'msg': _("%s has been added. They are not an employee and are "
                         "never in a pay run.", rec.name)}

    @api.model
    def end_worker(self, worker_id, end_date=None):
        """They have left: the end date is set (today by default) and the
        record stays as a record."""
        rec = self._worker(worker_id)
        day = fields.Date.to_date(end_date) if end_date else \
            fields.Date.context_today(rec)
        if rec.date_start and day < rec.date_start:
            raise UserError(_("The end date cannot be before the start date."))
        rec.write({'date_end': day})
        return {'ok': True, 'msg': _("Recorded: %(who)s's last day is %(day)s.",
                                     who=rec.name, day=self._day(day))}

    @api.model
    def delete_worker(self, worker_id):
        if not self.env.user.has_group('hr.group_hr_manager'):
            raise AccessError(_("Only an HR manager can delete somebody from "
                                "this list. Set an end date instead."))
        rec = self._worker(worker_id)
        name = rec.name
        rec.unlink()
        return {'ok': True, 'msg': _("%s has been removed.", name)}

    @api.model
    def add_file(self, worker_id, name, mime, data):
        rec = self._worker(worker_id)
        if mime not in MIME_OK:
            raise UserError(_("Only PDF, PNG or JPG files can be added."))
        try:
            raw = base64.b64decode(data or '')
        except Exception:   # noqa: BLE001
            raise UserError(_("This file could not be read.")) from None
        if len(raw) > MAX_FILE_BYTES:
            raise UserError(_("A file can be at most 10 MB."))
        att = self.env['ir.attachment'].create({
            'name': (name or _('Document'))[:200], 'datas': data,
            'mimetype': mime, 'res_model': rec._name, 'res_id': rec.id,
        })
        rec.write({'attachment_ids': [(4, att.id)]})
        return self.get_worker(rec.id)

    @api.model
    def remove_file(self, worker_id, attachment_id):
        rec = self._worker(worker_id)
        att = rec.attachment_ids.filtered(lambda a: a.id == int(attachment_id))
        if att:
            rec.write({'attachment_ids': [(3, att.id)]})
            att.unlink()
        return self.get_worker(rec.id)
