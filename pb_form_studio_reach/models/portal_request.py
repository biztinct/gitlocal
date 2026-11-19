# -*- coding: utf-8 -*-
"""Company details an employee changes on My Payobook (R14, FS hosts ADDENDUM 2).

One new kind of the ONE "employee proposes -> HR approves" request model of
pb_me_details (`pb.me.detail.request`), extended from outside exactly as
pb_me_tax does: `selection_add` on `kind`, and the create / now / apply /
inbox rows / title hooks answer for this kind only; every other kind runs
exactly as before.

* What may change, and how, is the ENGINE's answer, never this module's:
  `pb.form.studio.portal_check(model, record, vals)` validates and coerces
  the proposal and splits it into the part saved at once (`instant`) and the
  part HR approves (`approve`). The controller saves the instant part with
  `portal_apply` straight away; the approve part becomes ONE request here.
* `_pb_clean` re-runs `portal_check` on what it is handed, so nothing reaches
  a request that the engine would refuse, whatever a caller passes.
* On approval `_pb_apply` writes through `portal_apply` — the engine's single
  write path (history line: who proposed, who approved, label, old -> new).
  Refusal, send-back and take-back write nothing.
* One open request per field: a new proposal takes over the fields still
  waiting in the open one (the open one is withdrawn and hidden as
  "replaced"); fields re-checked one by one, a field the company stopped
  offering is left out.
* When the administrator stops offering a field ("can change" or "show"
  unticked), every open request is cleared of it; a request left with
  nothing is closed with a plain note (`pb.form.field.meta.write`).
"""
import json
import logging

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError

from .common import EMP

_logger = logging.getLogger(__name__)

FB_KIND = 'company_details'
OPEN_STATES = ('draft', 'hr_review')


def _norm(value):
    """A comparable text for a raw field value (for "did it change")."""
    if value is None or value is False or value == '':
        return ''
    if hasattr(value, '_name'):            # a record
        return str(value.id or '')
    if hasattr(value, 'isoformat'):
        return value.isoformat()[:10] if not hasattr(value, 'hour') else value.isoformat()
    if isinstance(value, float):
        return repr(round(value, 6))
    if isinstance(value, bool):
        return '1' if value else ''
    return str(value)


class PbMeDetailRequestFormBuilder(models.Model):
    _inherit = 'pb.me.detail.request'

    kind = fields.Selection(selection_add=[(FB_KIND, 'Company details')],
                            ondelete={FB_KIND: 'cascade'})
    fb_model = fields.Char(string='Record type', readonly=True)
    fb_values_json = fields.Text(string='Proposed company details', readonly=True)
    fb_replaced = fields.Boolean(string='Replaced by a newer change', readonly=True,
                                 copy=False)

    # ============================================================ helpers
    def _pbfr_values(self):
        self.ensure_one()
        try:
            data = json.loads(self.sudo().fb_values_json or '{}')
        except (TypeError, ValueError):
            data = {}
        return data if isinstance(data, dict) else {}

    @api.model
    def _pbfr_check(self, employee, vals):
        """The engine's verdict on a proposal: `{'instant': {}, 'approve': {}}`.
        Raises in plain words on anything not changeable for this record."""
        out = self.env['pb.form.studio'].portal_check(EMP, employee.sudo(), dict(vals or {}))
        out = out or {}
        return {'instant': dict(out.get('instant') or {}),
                'approve': dict(out.get('approve') or {})}

    @api.model
    def _pbfr_specs(self, employee):
        return {s['name']: s for s in
                self.env['pb.form.studio'].fields_for(EMP, 'portal', employee.sudo())}

    def _pbfr_label(self, name, specs=None):
        specs = specs if specs is not None else self._pbfr_specs(self.employee_id)
        if name in specs:
            return specs[name].get('label') or name
        field = self.env[EMP]._fields.get(name)
        return field._description_string(self.env) if field else name

    @api.model
    def _pbfr_display(self, name, raw):
        """The words for a proposed raw value, in the reader's language."""
        _ = self.env._
        field = self.env[EMP]._fields.get(name)
        if field is None:
            return str(raw or '')
        if field.type == 'boolean':
            return _('Yes') if raw else _('No')
        if raw in (None, False, ''):
            return ''
        if field.type == 'selection':
            return dict(field._description_selection(self.env)).get(raw, str(raw))
        if field.type == 'many2one':
            try:
                rec = self.env[field.comodel_name].sudo().browse(int(raw)).exists()
            except (TypeError, ValueError):
                rec = None
            return rec.display_name if rec else ''
        if field.type == 'date':
            try:
                return tools.format_date(self.env, fields.Date.to_date(raw))
            except Exception:                           # noqa: BLE001
                return str(raw)
        if field.type in ('integer',):
            try:
                return '{:,}'.format(int(raw))
            except (TypeError, ValueError):
                return str(raw)
        if field.type in ('float', 'monetary'):
            try:
                return ('{:,.4f}'.format(float(raw))).rstrip('0').rstrip('.')
            except (TypeError, ValueError):
                return str(raw)
        return str(raw)

    # ============================================================= portal
    @api.model
    def pbfr_portal_send(self, employee, approve_vals):
        """Send the approve part of a proposal for the caller's OWN employee.
        A field already waiting in an open request is taken over by this one
        (one open request per field)."""
        emp = employee.sudo()
        if not emp or emp.user_id != self.env.user:
            raise AccessError(self.env._("You can only change your own details."))
        merged = {}
        olds = self.sudo().search([('employee_id', '=', emp.id), ('kind', '=', FB_KIND),
                                   ('state', 'in', OPEN_STATES), ('fb_replaced', '=', False)])
        for old in olds:
            for name, value in old._pbfr_values().items():
                if name in approve_vals:
                    continue
                try:            # still offered? (re-checked one by one)
                    merged.update(self._pbfr_check(emp, {name: value})['approve'])
                except (UserError, AccessError):
                    continue
        merged.update(approve_vals)
        for old in olds:
            if old.state == 'hr_review':
                old.pb_portal_withdraw()
            old.sudo().write({'fb_replaced': True})
        return self.with_context(pbfr_employee=emp.id).pb_portal_create(
            emp, FB_KIND, {'fb_values': merged})

    @api.model
    def _pb_clean(self, kind, values):
        if kind != FB_KIND:
            return super()._pb_clean(kind, values)
        emp = self.env['hr.employee'].sudo().browse(
            self.env.context.get('pbfr_employee') or 0).exists()
        raw = (values or {}).get('fb_values') or {}
        if not emp or not isinstance(raw, dict) or not raw:
            raise UserError(self.env._("There is no change to send."))
        # The engine decides, again: only the part HR must approve travels.
        approve = self._pbfr_check(emp, raw)['approve']
        if not approve:
            raise UserError(self.env._("There is no change to send."))
        return {'fb_model': EMP, 'fb_values_json': json.dumps(approve, default=str)}

    @api.model
    def _pb_check(self, kind, vals, member=None, attachment=None):
        if kind != FB_KIND:
            return super()._pb_check(kind, vals, member=member, attachment=attachment)
        return None

    # ================================================== what it changes
    def _pb_now(self):
        self.ensure_one()
        if self.kind != FB_KIND:
            return super()._pb_now()
        emp = self.employee_id.sudo()
        current = self.env['pb.form.studio'].portal_values(EMP, emp) or {}
        out = {}
        for name in self._pbfr_values():
            cell = current.get(name)
            out[name] = (cell.get('display') if isinstance(cell, dict) else cell) or ''
        return out

    def _pb_apply(self):
        self.ensure_one()
        if self.kind != FB_KIND:
            return super()._pb_apply()
        rec = self.sudo()
        vals = rec._pbfr_values()
        if vals:
            origin = {'kind': 'approved', 'request': rec.name, 'request_id': rec.id,
                      'proposed_by': rec.employee_id.user_id.id, 'approved_by': self.env.uid}
            self.env['pb.form.studio'].portal_apply(EMP, rec.employee_id.sudo(), vals, origin)
        rec.message_post(body=self.env._("Approved and written to the employee record."))
        return True

    # ========================================================= the inbox
    def _chain_revision_values(self):
        res = super()._chain_revision_values()
        if self.kind == FB_KIND:
            res['company'] = sorted((k, str(v)) for k, v in self._pbfr_values().items())
        return res

    def _pb_rows(self, *args, **kwargs):
        self.ensure_one()
        if self.kind != FB_KIND:
            return super()._pb_rows(*args, **kwargs)
        rec = self.sudo()
        try:
            before = json.loads(rec.before_json or '{}')
        except (TypeError, ValueError):
            before = {}
        specs = self._pbfr_specs(rec.employee_id)
        return [(self._pbfr_label(name, specs), str(before.get(name) or ''),
                 self._pbfr_display(name, value))
                for name, value in rec._pbfr_values().items()]

    def pb_label(self):
        self.ensure_one()
        if self.kind != FB_KIND:
            return super().pb_label()
        specs = self._pbfr_specs(self.employee_id)
        names = [self._pbfr_label(n, specs) for n in self._pbfr_values()]
        return self.env._("Company details: %s", ', '.join(names[:3]) +
                          (' …' if len(names) > 3 else ''))

    @api.model
    def _pb_page_domain(self):
        return super()._pb_page_domain() + [('fb_replaced', '=', False)]

    # ============================================ the field is withdrawn
    @api.model
    def _pbfr_drop_field(self, model, name, label):
        """Clear `name` from every open request; a request left with nothing
        is closed with a plain note, one left with other fields goes back to
        HR without it."""
        if model != EMP:
            return 0
        reqs = self.sudo().search([('kind', '=', FB_KIND), ('state', 'in', OPEN_STATES),
                                   ('fb_replaced', '=', False),
                                   ('fb_values_json', 'like', '"%s"' % name)])
        done = 0
        for req in reqs:
            vals = req._pbfr_values()
            if name not in vals:
                continue
            vals.pop(name)
            was_waiting = req.state == 'hr_review'
            if was_waiting:
                req.pb_portal_withdraw()
            if vals:
                req.write({'fb_values_json': json.dumps(vals, default=str)})
                if was_waiting:
                    req._pb_send()
            else:
                note = self.env._(
                    "The company no longer takes changes to %s on My Payobook, so this "
                    "change was closed. Nothing on your record changed.", label)
                with self.env.cr.savepoint():
                    req._chain_engine_write('refused')
                    req._chain_log('draft', 'refused', note)
                req.write({'decision_note': note, 'decided_on': fields.Datetime.now()})
            done += 1
        return done


class PbFormFieldMetaPortalWatch(models.Model):
    _inherit = 'pb.form.field.meta'

    def write(self, vals):
        before = {m.id: self._pbfr_offered(m) for m in self}
        res = super().write(vals)
        if {'portal_show', 'portal_edit'} & set(vals):
            Req = self.env['pb.me.detail.request']
            for meta in self:
                if before.get(meta.id) and not self._pbfr_offered(meta):
                    field = self.env[meta.model]._fields.get(meta.name) \
                        if meta.model in self.env else None
                    label = field._description_string(self.env) if field else meta.name
                    Req._pbfr_drop_field(meta.model, meta.name, label)
        return res

    @api.model
    def _pbfr_offered(self, meta):
        return bool(getattr(meta, 'portal_show', False) and getattr(meta, 'portal_edit', False))
