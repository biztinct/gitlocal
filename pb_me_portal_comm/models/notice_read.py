# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""`pb.me.notice.read` — "this person has opened this notice" (TIERS T3b D4).

One row per announcement and employee, written the first time the employee
opens the notice on `/my/notices/<id>`. A NEW table in this glue module: no
field is added to pb_hr_comm's post or delivery (D4, D7).
"""

from odoo import fields, models


class PbMeNoticeRead(models.Model):
    _name = 'pb.me.notice.read'
    _description = 'Notice opened by an employee'
    _order = 'read_on desc, id desc'

    post_id = fields.Many2one(
        'pb.hr.comm.post', string='Notice', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', related='employee_id.company_id',
        store=True, readonly=True, index=True)
    read_on = fields.Datetime(string='Opened on', required=True,
                              default=fields.Datetime.now, readonly=True)

    #: Odoo 19 SILENTLY IGNORES a `_sql_constraints` list (see
    #: pb_hr_comm/models/delivery.py:46-50); the Constraint attribute is the
    #: only spelling that reaches Postgres.
    _one_per_person = models.Constraint(
        'unique(post_id, employee_id)',
        'That person has already opened this notice.')
