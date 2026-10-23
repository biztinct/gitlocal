# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The write-hook a consumer model inherits to gain an old→new audit trail.

    class HrEmployee(models.Model):
        _name = 'hr.employee'
        _inherit = ['hr.employee', 'biz.audit.mixin']

Which fields are watched is DATA (biz.audit.rule), looked up ormcached per model.
The mixin NEVER blocks the business write — a logging failure is swallowed with
an exception log (a broken audit must not break HR operations). It logs nothing
when no rule watches the model (the common case), paying only one cached lookup.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class BizAuditMixin(models.AbstractModel):
    _name = 'biz.audit.mixin'
    _description = 'Field-Change Audit Mixin'

    def write(self, vals):
        watched = self.env['biz.audit.rule']._watched_fields(self._name)
        touched = [f for f in vals if f in watched]
        if not touched:
            # zero-overhead path — one cached lookup, no snapshot, no logging
            return super().write(vals)

        before = {rec.id: {f: rec[f] for f in touched} for rec in self}
        res = super().write(vals)
        # a broken audit may NOT break the business write (safety rail 2).
        # The SAVEPOINT is the load-bearing half (review H-M1): a DB-level
        # error in the entry INSERT poisons the whole transaction, and catching
        # the Python exception alone would still abort the business write at
        # flush time ("current transaction is aborted").
        try:
            with self.env.cr.savepoint():
                self._biz_audit_log(touched, before)
        except Exception:
            _logger.exception(
                "biz.audit.mixin: failed to log %s change(s) on %s",
                touched, self._name)
        return res

    # ------------------------------------------------------------------ logging
    def _biz_audit_log(self, touched, before):
        Entry = self.env['biz.audit.entry'].sudo()
        entries = []
        for rec in self:
            old = before.get(rec.id, {})
            for fname in touched:
                ov = rec._biz_audit_display(fname, old.get(fname))
                nv = rec._biz_audit_display(fname, rec[fname])
                if ov == nv:
                    continue  # a write that didn't actually change the value
                entries.append({
                    'model_name': rec._name,
                    'res_id': rec.id,
                    'res_display': (rec.display_name or '')[:512],
                    'field_name': fname,
                    'field_label': rec._fields[fname].string or fname,
                    'old_value': ov,
                    'new_value': nv,
                    'company_id': rec._biz_audit_company(),
                })
        if entries:
            Entry.create(entries)

    def _biz_audit_company(self):
        """The company an entry belongs to — the record's own if it carries one."""
        self.ensure_one()
        if 'company_id' in self._fields and self.company_id:
            return self.company_id.id
        return self.env.company.id

    def _biz_audit_display(self, fname, value):
        """A human display string for a field's raw stored value.

        ``value`` for the OLD snapshot is exactly what ``rec[fname]`` returned
        BEFORE the write (a recordset for relational fields, the raw key for a
        selection, etc.) — the same shape ``rec[fname]`` returns for the NEW
        value, so both sides format identically.
        """
        field = self._fields.get(fname)
        if field is None or value is None:
            return ''
        ftype = field.type
        # boolean BEFORE the falsy check: archiving must log "Yes → No", not
        # "Yes → " (review H-L1; the `is False` identity still protects 0.0)
        if ftype == 'boolean':
            return 'Yes' if value else 'No'
        if value is False:
            return ''
        if ftype == 'many2one':
            return value.display_name or '' if value else ''
        if ftype in ('one2many', 'many2many'):
            return ', '.join(value.mapped('display_name')) if value else ''
        if ftype == 'selection':
            try:
                sel = dict(field._description_selection(self.env))
            except Exception:
                sel = {}
            return str(sel.get(value, value))
        if ftype in ('date', 'datetime'):
            return fields.Datetime.to_string(value) if ftype == 'datetime' \
                else fields.Date.to_string(value)
        return str(value)
