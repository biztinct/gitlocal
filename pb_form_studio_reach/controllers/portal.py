# -*- coding: utf-8 -*-
"""My Payobook > My details: company details chosen per field (R14).

Subclasses `PbMeDetailsPortal` (precedent: pb_me_tax). pb_me_details and
pb_me_portal are not edited.

* The section(s) are built ONLY from the engine: `fields_for('hr.employee',
  'portal', record)` (which fields, their labels, sections, whether the
  employee may change them and how) and `portal_values` (what they read
  now). `_ess_employee()` hands a SUDO record (pb_me_portal); the engine's
  portal purpose is decided by each field's own "Show on My Payobook" tick,
  never by the caller, so it is safe around it.
* A change: `/my/details/company` (the form) -> POST `/my/details/company/send`.
  The employee is the SESSION's own (no route takes an employee id). Every
  submitted field — including a forged one — goes to the engine's
  `portal_check`, which refuses anything not changeable for this record.
  The part saved at once goes through `portal_apply`; the part HR approves
  becomes ONE request (`pb.me.detail.request`, kind "Company details").
"""
import logging

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_details.controllers.portal import PbMeDetailsPortal

from ..models.portal_request import FB_KIND

_logger = logging.getLogger(__name__)

EMP = 'hr.employee'
PREFIX = 'pbfr__'
#: A link field the employee may change here offers a short list of names
#: that are not personal data. Any other link target is shown only.
CHOICE_LINKS = ('res.country', 'hr.department', 'hr.job')


class PbFormBuilderMyDetails(PbMeDetailsPortal):

    # ------------------------------------------------------------ reading
    def _pbfr_fields(self, emp):
        return request.env['pb.form.studio'].fields_for(EMP, 'portal', record=emp.sudo()) or []

    def _pbfr_current(self, emp):
        """`{name: {'value', 'display'}}` from the engine (either shape)."""
        raw = request.env['pb.form.studio'].portal_values(EMP, emp.sudo()) or {}
        out = {}
        for name, cell in raw.items():
            if isinstance(cell, dict):
                out[name] = {'value': cell.get('value'), 'display': cell.get('display') or ''}
            else:
                out[name] = {'value': None, 'display': '' if cell in (None, False) else str(cell)}
        return out

    def _pbfr_link_options(self, emp, spec):
        comodel = spec.get('comodel') or (
            request.env[EMP]._fields[spec['name']].comodel_name
            if spec['name'] in request.env[EMP]._fields else '')
        if comodel not in CHOICE_LINKS:
            return None
        Co = request.env[comodel].sudo()
        dom = []
        if 'company_id' in Co._fields:
            dom = ['|', ('company_id', '=', False), ('company_id', '=', emp.company_id.id)]
        return [{'value': r.id, 'label': r.display_name}
                for r in Co.search(dom, limit=300, order='name')]

    def _pbfr_waiting(self, emp):
        Req = request.env['pb.me.detail.request'].sudo()
        names = set()
        for req in Req.search([('employee_id', '=', emp.id), ('kind', '=', FB_KIND),
                               ('state', '=', 'hr_review'), ('fb_replaced', '=', False)]):
            names.update(req._pbfr_values())
        return names

    def _pbfr_sections(self, emp):
        specs = self._pbfr_fields(emp)
        if not specs:
            return []
        current = self._pbfr_current(emp)
        waiting = self._pbfr_waiting(emp)
        sections, order = {}, []
        for spec in specs:
            title = self._pbfr_section_title(spec)
            if title not in sections:
                sections[title] = {'title': title, 'rows': [], 'can_change': False}
                order.append(title)
            cell = current.get(spec['name']) or {}
            editable = bool(spec.get('edit'))
            if editable and spec.get('type') == 'many2one' \
                    and self._pbfr_link_options(emp, spec) is None:
                editable = False
            sections[title]['rows'].append({
                'name': spec['name'], 'label': spec.get('label') or spec['name'],
                'value': cell.get('display') or '', 'edit': editable,
                'mode': spec.get('mode') or 'approve',
                'waiting': spec['name'] in waiting})
            sections[title]['can_change'] |= editable
        return [sections[t] for t in order]

    def _pbfr_section_title(self, spec):
        """The published layout's section title (engine `section_title`)."""
        return spec.get('section_title') or request.env._('Company details')

    def _pbmd_overview(self, emp):
        values = super()._pbmd_overview(emp)
        try:
            values['pbfr_sections'] = self._pbfr_sections(emp)
        except Exception:                               # noqa: BLE001
            # A broken extra card must never take the page down.
            _logger.exception('pb_form_studio_reach: My details company card failed')
            values['pbfr_sections'] = []
        return values

    def _pbmd_render_form(self, emp, kind, values=None, error=None, member=None, req=None):
        # A taken-back "Company details" change is edited on its own form.
        if kind == FB_KIND:
            return request.redirect('/my/details/company')
        return super()._pbmd_render_form(emp, kind, values=values, error=error,
                                         member=member, req=req)

    # --------------------------------------------------------------- form
    def _pbfr_form(self, emp, error=None, posted=None):
        specs = [s for s in self._pbfr_fields(emp) if s.get('edit')]
        current = self._pbfr_current(emp)
        record = emp.sudo()
        rows = []
        for spec in specs:
            name = spec['name']
            ftype = spec.get('type')
            options = spec.get('options') or []
            if ftype == 'many2one':
                options = self._pbfr_link_options(emp, spec)
                if options is None:
                    continue
            value = (current.get(name) or {}).get('value')
            if value is None and name in record._fields:
                value = record[name]           # a field the engine says is shown
            if hasattr(value, '_name'):
                value = value.id or ''
            if ftype == 'date' and value:
                value = fields.Date.to_string(value) if not isinstance(value, str) else value
            if posted and (PREFIX + name) in posted:
                value = posted[PREFIX + name]
            rows.append({'name': name, 'input': PREFIX + name, 'label': spec.get('label') or name,
                         'help': spec.get('help') or '', 'type': ftype, 'options': options,
                         'value': '' if value in (None, False) else value,
                         'mode': spec.get('mode') or 'approve'})
        return request.render('pb_form_studio_reach.portal_company_form', {
            'page_name': 'my_details_company', 'rows': rows, 'error': error,
            'waiting': self._pbfr_waiting(emp),
        })

    @http.route(['/my/details/company'], type='http', auth='user', website=True,
                methods=['GET'])
    def pbfr_company_form(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        return self._pbfr_form(emp)

    def _pbfr_posted(self, emp, post):
        """`{field: value}` of the submitted boxes, typed for the engine.
        Every `pbfr__*` name is passed on — a forged one is the engine's to
        refuse — and an unchanged box is left out."""
        record = emp.sudo()
        current = self._pbfr_current(emp)
        out = {}
        for key, raw in post.items():
            if not key.startswith(PREFIX):
                continue
            name = key[len(PREFIX):]
            field = record._fields.get(name)
            if field is None:
                out[name] = raw          # the engine refuses an unknown name
                continue
            ftype = field.type
            if ftype == 'boolean':
                value = raw in ('1', 'on', 'true', 'True', 'yes')
            elif ftype == 'many2one':
                value = int(raw) if str(raw).isdigit() else False
            else:
                value = (raw or '').strip()
            cur = (current.get(name) or {}).get('value')
            if cur is None:
                try:
                    cur = record[name]
                except AccessError:
                    cur = None
            if self._pbfr_same(field, cur, value):
                continue
            out[name] = value
        return out

    @staticmethod
    def _pbfr_same(field, current, value):
        if hasattr(current, '_name'):
            current = current.id or False
        if field.type == 'boolean':
            return bool(current) == bool(value)
        if field.type in ('integer', 'float', 'monetary'):
            try:
                return value != '' and float(str(value).replace(',', '')) == float(current or 0)
            except (TypeError, ValueError):
                return False
        if field.type == 'date':
            cur = fields.Date.to_string(current) if current and not isinstance(current, str) else (current or '')
            return (cur or '') == (value or '')
        return (current or '') == (value or '')

    @http.route(['/my/details/company/send'], type='http', auth='user', website=True,
                methods=['POST'])
    def pbfr_company_send(self, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        Studio = request.env['pb.form.studio']
        Req = request.env['pb.me.detail.request']
        try:
            vals = self._pbfr_posted(emp, post)
            if not vals:
                raise UserError(request.env._("Nothing was changed."))
            parts = Req._pbfr_check(emp, vals)
            if parts['instant']:
                Studio.portal_apply(EMP, emp.sudo(), parts['instant'],
                                    {'proposed_by': request.env.uid, 'approved_by': False})
            if parts['approve']:
                Req.pbfr_portal_send(emp, parts['approve'])
        except (UserError, ValidationError, AccessError) as exc:
            request.env.cr.rollback()
            message = exc.args[0] if exc.args else request.env._("This change could not be sent.")
            return self._pbfr_form(emp, error=message, posted=post)
        done = 'sent' if parts['approve'] else 'saved'
        return request.redirect('/my/details?done=%s' % done)
