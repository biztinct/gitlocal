# -*- coding: utf-8 -*-
"""What Change job adds to other modules — by inheritance only (S8 lane rule).

  * `pb.pay.apply.job_change_id` — the wage row a job change writes, so the
    old figure is kept the way Pay keeps it (facts §2 "Precedent to clone").
  * Two letter types and a general one, by `selection_add` on pb_lifecycle's
    list (no edit of `LETTER_TYPES`).
  * The person's timeline shows a job change as ONE event: the field lines the
    write produced are folded away and one line says what changed.
  * The scheme map answers "who would pay them in that team?" without writing
    anything: a context override of the one roster read it starts from.
"""
import json

from odoo import _, api, fields, models
from odoo.fields import Domain

from .job_change import LETTER_JOB_CHANGE, LETTER_PROMOTION, LETTER_TRANSFER

NEW_LETTER_TYPES = [
    (LETTER_PROMOTION, 'Promotion letter'),
    (LETTER_TRANSFER, 'Transfer letter'),
    (LETTER_JOB_CHANGE, 'Job change letter'),
]


class PbPayApplyJobChange(models.Model):
    _inherit = 'pb.pay.apply'

    job_change_id = fields.Many2one(
        'pb.job.change', string='Job change', ondelete='cascade', index=True)


class PbLetterTemplateJobChange(models.Model):
    _inherit = 'pb.letter.template'

    letter_type = fields.Selection(
        selection_add=NEW_LETTER_TYPES,
        ondelete={key: 'set default' for key, _label in NEW_LETTER_TYPES})


# `pb.hr.letter.letter_type` is related to its template's, so it follows the
# selection_add above by itself (a selection_add on it is ignored).


class BizAuditEntryJobChange(models.Model):
    _inherit = 'biz.audit.entry'

    @api.model
    def _search(self, domain, *args, **kwargs):
        hidden = self.env.context.get('pb_jc_hide_audit_ids')
        if hidden:
            domain = Domain.AND([Domain(domain),
                                 Domain('id', 'not in', list(hidden))])
        return super()._search(domain, *args, **kwargs)


class PbEmployeeTimelineJobChange(models.AbstractModel):
    _inherit = 'pb.employee.timeline'

    def _collect(self, employee, unmask_wage):
        changes = self.env['pb.job.change'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ('applied', 'undone'))])
        hidden = set()
        for change in changes:
            try:
                hidden.update(int(i) for i in json.loads(
                    change.audit_ids_json or '[]'))
            except (TypeError, ValueError):
                continue
        me = self.with_context(pb_jc_hide_audit_ids=tuple(sorted(hidden))) \
            if hidden else self
        items = super(PbEmployeeTimelineJobChange, me)._collect(
            employee, unmask_wage)
        extra = []
        Kinds = dict(self.env['pb.job.change']._fields['reason_kind']
                     ._description_selection(self.env))
        for change in changes:
            rows = change._rows(show_pay=bool(unmask_wage))
            detail = ' · '.join('%s: %s → %s' % row for row in rows[:6])
            stamp = change.applied_at or change.write_date
            title = _("Job changed — %s", Kinds.get(change.reason_kind, ''))
            if change.state == 'undone':
                title = _("Job change taken back — %s",
                          Kinds.get(change.reason_kind, ''))
            extra.append({
                '_dt': stamp,
                'stamp': fields.Datetime.to_string(stamp),
                'kind': 'employee', 'icon': 'briefcase',
                'title': title,
                'detail': (_("From %s", change._day(change.effective_date))
                           + (' · ' + detail if detail else '')),
                **self._actor(change.applied_by),
            })
        if not extra:
            return items
        items = items + extra
        items.sort(key=lambda it: it.get('stamp') or '', reverse=True)
        for it in items:
            it.pop('_dt', None)
        return items


class PbSchemeMapJobChange(models.AbstractModel):
    _inherit = 'pb.scheme.map'

    @api.model
    def _departments_for(self, employee_ids=None, company_ids=None):
        """`pb_jc_department_override = {employee_id: (department, company)}`
        answers "who would pay them in that team" for a preview. Read-only."""
        out = super()._departments_for(employee_ids=employee_ids,
                                       company_ids=company_ids)
        override = self.env.context.get('pb_jc_department_override') or {}
        for emp_id, pair in override.items():
            try:
                emp_id = int(emp_id)
            except (TypeError, ValueError):
                continue
            if emp_id in out or (employee_ids and emp_id in [
                    int(i) for i in employee_ids]):
                out[emp_id] = (int(pair[0] or 0), int(pair[1] or 0))
        return out
