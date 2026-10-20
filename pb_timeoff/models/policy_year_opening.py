"""Execute an HR-scheduled January opening using the native allocation engine."""
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from .rize_policy import _manager

_SEAL = object()


class PolicyYearOpening(models.Model):
    _name = 'pb.leave.policy.year.opening'
    _description = 'Scheduled Annual Leave Opening'
    _order = 'year desc, employee_id'

    employee_id = fields.Many2one('hr.employee', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='employee_id.company_id', store=True, index=True)
    edition_id = fields.Many2one('pb.leave.policy.edition', required=True, ondelete='restrict')
    leave_type_id = fields.Many2one('hr.leave.type', required=True, ondelete='restrict')
    year = fields.Integer(required=True, default=lambda s: fields.Date.today().year + 1)
    employment_start = fields.Date(required=True, string='Verified service start')
    review_reference = fields.Char(required=True, string='Year-opening authority reference')
    state = fields.Selection([('draft', 'Draft'), ('scheduled', 'Scheduled'),
                               ('blocked', 'Needs HR review'), ('done', 'Completed')],
                             default='draft', readonly=True, required=True, index=True)
    authorized_by = fields.Many2one('res.users', readonly=True, copy=False)
    authorized_at = fields.Datetime(readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    result = fields.Text(readonly=True, copy=False)

    _one_opening = models.Constraint('unique(employee_id, leave_type_id, year)',
                                     'This employee already has an opening for this leave type and year.')

    @api.constrains('employee_id', 'edition_id', 'leave_type_id', 'year', 'employment_start')
    def _check_scope(self):
        for row in self:
            if row.year < 2000 or row.year > 2200:
                raise ValidationError(_('Choose a valid opening year.'))
            row.edition_id._posting_subject(row.employee_id.id, row.leave_type_id.id)
            start = date(row.year, 1, 1)
            if (start < row.edition_id.effective_from or
                    (row.edition_id.effective_to and start > row.edition_id.effective_to)):
                raise ValidationError(_('The edition must be effective on 1 January of this opening year.'))
            if row.employment_start > start:
                raise ValidationError(_('A mid-year joiner needs a reviewed prorated credit through Entitlement Operations.'))

    @api.model_create_multi
    def create(self, vals_list):
        _manager(self.env)
        for vals in vals_list:
            if (vals.get('state', 'draft') != 'draft' or
                    set(vals) & {'authorized_by', 'authorized_at', 'completed_at', 'result'}):
                raise AccessError(_('Schedule the opening through its approval action.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('pb_year_opening_seal') is not _SEAL:
            _manager(self.env)
            if set(vals) & {'state', 'authorized_by', 'authorized_at', 'completed_at', 'result'}:
                raise AccessError(_('Use the year-opening actions.'))
            if any(r.state != 'draft' for r in self):
                raise UserError(_('A scheduled year opening is immutable. Resolve its source records and retry it.'))
        return super().write(vals)

    def unlink(self):
        _manager(self.env)
        if any(r.state != 'draft' for r in self):
            raise UserError(_('Keep scheduled year openings as allocation evidence.'))
        return super().unlink()

    def _stamp(self, vals):
        return self.with_context(pb_year_opening_seal=_SEAL).write(vals)

    def action_schedule(self):
        _manager(self.env)
        for row in self:
            if row.state != 'draft':
                continue
            row._check_scope()
            if date(row.year, 1, 1) < fields.Date.today():
                raise UserError(_('Automatic openings must be scheduled prospectively. Use reviewed opening balances for an elapsed year.'))
            if not (row.review_reference or '').strip():
                raise UserError(_('Record the authority for this employee’s annual opening.'))
            row._stamp({'state': 'scheduled', 'authorized_by': self.env.uid,
                        'authorized_at': fields.Datetime.now()})
        return True

    def action_retry(self):
        _manager(self.env)
        self.filtered(lambda r: r.state == 'blocked')._stamp({'state': 'scheduled', 'result': False})
        return True

    @api.model
    def _cron_open_year(self):
        today = fields.Date.today()
        jobs = self.search([('state', '=', 'scheduled'), ('year', '<=', today.year)], limit=100)
        for job in jobs:
            self.env.cr.execute('SELECT id FROM pb_leave_policy_year_opening WHERE id=%s FOR UPDATE SKIP LOCKED', [job.id])
            if not self.env.cr.fetchone():
                continue
            job.invalidate_recordset()
            if job.state != 'scheduled':
                continue
            try:
                with self.env.cr.savepoint():
                    job._check_scope()
                    start = date(job.year, 1, 1)
                    if job.year != today.year:
                        raise UserError(_('This opening missed its year. HR must reconcile the elapsed period.'))
                    posting_ids = []
                    # Existing employees need a reconciled prior close; absence
                    # of allocations is never treated as a zero carry balance.
                    if job.employment_start < start:
                        posting_ids += job.edition_id.post_rollover(job.employee_id.id, job.leave_type_id.id,
                            job.year, job.review_reference).ids
                    posting_ids += job.edition_id.post_annual_credit(job.employee_id.id, job.leave_type_id.id,
                        job.year, job.employment_start, review_reference=job.review_reference).ids
                    job._stamp({'state': 'done', 'completed_at': fields.Datetime.now(),
                                'result': _('Native entitlement postings: %s') % ', '.join(map(str, posting_ids))})
            except (UserError, ValidationError, AccessError) as exc:
                job._stamp({'state': 'blocked', 'result': str(exc)})
        return True
