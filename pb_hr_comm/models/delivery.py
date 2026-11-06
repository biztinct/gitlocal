# -*- coding: utf-8 -*-
"""`pb.hr.comm.delivery` — one row per person per announcement.

THIS TABLE IS THE IDEMPOTENCY RULE, WRITTEN DOWN. An announcement to four and
a half thousand people does not go out in one breath: the sender queues five
hundred and comes back ten minutes later. Anything that decides "have we
already told this person" from a STATUS, a stamp or a count is guessing, and
the guess is wrong in exactly the case that matters — a job interrupted half
way through, which is the only reason the cap exists.

So the rule is a ROW, with a unique index on (post, person), and it is the
same lesson R21 and R49 record from two other directions: only the identifiers
a record actually HAS may go into an idempotency key, and a key that can be
empty matches every other empty row. A person either has a delivery row for
this post or they do not, and Postgres decides, not Python.

IT IS ALSO THE ANSWER TO "DID SO-AND-SO GET IT". Six months later somebody
will ask, and the honest answer is a row with a date on it rather than a
number on a post.
"""

from odoo import fields, models


class PbHrCommDelivery(models.Model):
    _name = 'pb.hr.comm.delivery'
    _description = 'Announcement sent to one person'
    _order = 'id desc'

    post_id = fields.Many2one(
        'pb.hr.comm.post', string='Announcement', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='Who', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', string='Company', related='post_id.company_id',
        store=True, readonly=True, index=True)
    email = fields.Char(string='Sent to', readonly=True)
    sent_on = fields.Datetime(string='When', readonly=True,
                              default=fields.Datetime.now)
    mail_id = fields.Many2one('mail.mail', string='The message',
                              ondelete='set null', readonly=True)

    #: Odoo 19 SILENTLY IGNORES a `_sql_constraints` list — the rule is simply
    #: not enforced and nothing says so. The Constraint attribute is the only
    #: spelling that reaches Postgres.
    _one_per_person = models.Constraint(
        'unique(post_id, employee_id)',
        'That person has already been sent this announcement.')
