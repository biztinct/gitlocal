# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Append-only field-change entry (one old→new row).

Clones the biz.approval.step.log discipline (append-only, forced actor/stamp at
create). Two hardening rules on top:

  * The actor and timestamp are FORCED server-side at create — a crafted call_kw
    create can never forge who or when (C18.24 doctrine, the same as the step
    log). The mixin creates entries via ``sudo()`` (it fires on any user's write
    to a consumer model and cannot assume that user holds create rights here), so
    forcing ``user_id = env.uid`` — which ``sudo()`` leaves as the REAL clicking
    user — keeps the trail truthful.
  * Entries are append-only: write()/unlink() raise for everyone except system
    (group_system / su / admin) and the retention GC (a module-level sentinel a
    JSON client cannot forge). ``res_display`` snapshots the record's name so the
    row stays meaningful after the audited record is deleted.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# The retention vacuum is the ONE non-system path allowed to unlink entries.
# A Python object() identity cannot be produced by a JSON-RPC context, unlike a
# plain boolean flag call_kw would happily accept (C18.24 sentinel doctrine).
_AUDIT_GC_TOKEN = object()

_RETENTION_PARAM = 'biz_audit_trail.retention_days'
_DEFAULT_RETENTION_DAYS = 730


class BizAuditEntry(models.Model):
    _name = 'biz.audit.entry'
    _description = 'Audit Entry'
    _order = 'stamp desc, id desc'
    _rec_name = 'field_label'

    model_name = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    res_display = fields.Char(
        string='Record', help="Name snapshot — survives the record's deletion.")
    field_name = fields.Char(string='Field', required=True)
    field_label = fields.Char(string='Field Label')
    old_value = fields.Char(string='Old Value')
    new_value = fields.Char(string='New Value')
    user_id = fields.Many2one(
        'res.users', string='By', required=True, readonly=True, index=True,
        default=lambda self: self.env.user)
    # index: the table accumulates years of app-wide HR writes and every
    # consumer (_order above, the 360 timeline, the Phase-J console) sorts and
    # windows on stamp (C18.68, review H-M3)
    stamp = fields.Datetime(
        string='When', required=True, readonly=True, index=True,
        default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string='Company', index=True)

    # ----------------------------------------------------- append-only guards
    def _audit_sys_allowed(self):
        return (self.env.su or self.env.user._is_admin()
                or self.env.context.get('audit_gc') is _AUDIT_GC_TOKEN)

    @api.model_create_multi
    def create(self, vals_list):
        # who/when are always the server's idea — never client-supplied.
        for vals in vals_list:
            vals['user_id'] = self.env.uid
            vals.pop('stamp', None)
        return super().create(vals_list)

    def write(self, vals):
        if not self._audit_sys_allowed():
            raise AccessError(_(
                "Audit entries are append-only and cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if not self._audit_sys_allowed():
            raise AccessError(_(
                "Audit entries are append-only and cannot be deleted."))
        return super().unlink()

    # --------------------------------------------------------- retention GC
    @api.model
    def _retention_days(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            _RETENTION_PARAM, _DEFAULT_RETENTION_DAYS)
        try:
            days = int(raw)
        except (TypeError, ValueError):
            days = _DEFAULT_RETENTION_DAYS
        # a non-positive value would purge the whole trail — fall back
        return days if days > 0 else _DEFAULT_RETENTION_DAYS

    @api.model
    def _gc_vacuum(self):
        """Unlink entries older than the retention window. The clock runs from
        write_date (an entry is never edited, so write_date == create time in
        practice — C18.40 keys retention on the terminal date, not creation)."""
        cutoff = fields.Datetime.now() - timedelta(days=self._retention_days())
        stale = self.sudo().search([('write_date', '<', cutoff)])
        count = len(stale)
        if stale:
            # the GC sentinel is the only non-system path through unlink()
            stale.with_context(audit_gc=_AUDIT_GC_TOKEN).unlink()
            _logger.info("biz.audit.entry: vacuumed %s entr(y/ies) older "
                         "than the retention window", count)
        return count

    @api.model
    def cron_gc(self):
        """Cron entry point — a vacuum failure must never raise from the cron."""
        try:
            with self.env.cr.savepoint():
                self._gc_vacuum()
        except Exception:
            _logger.exception("biz.audit.entry cron: retention vacuum")
        return True
