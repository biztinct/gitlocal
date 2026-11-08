from odoo import fields, models


class NoticeComment(models.Model):
    _name = 'pb.me.notice.comment'
    _description = 'Employee announcement comment'
    _order = 'create_date, id'

    post_id = fields.Many2one('pb.hr.comm.post', required=True, index=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='post_id.company_id', store=True, index=True)
    body = fields.Text(required=True)
    active = fields.Boolean(default=True)


class NoticeReaction(models.Model):
    _name = 'pb.me.notice.reaction'
    _description = 'Employee announcement like'

    post_id = fields.Many2one('pb.hr.comm.post', required=True, index=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='post_id.company_id', store=True, index=True)
    _one_per_person = models.Constraint('unique(post_id, employee_id)', 'You already liked this announcement.')
