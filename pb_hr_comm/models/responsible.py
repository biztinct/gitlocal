# -*- coding: utf-8 -*-
"""`pb.hr.comm.default` — who an announcement lands on, per company.

THE DEFAULT IS THE HR LEAD AND THIS TABLE IS THE EXCEPTION. Every company on
this database already has an HR lead in the Approval Matrix, and that is the
person the business has already said is in charge of HR there — asking them to
name the same person twice, in a second place that can drift, is how two
screens end up disagreeing about who is responsible for something.

So the ladder is short and it is written down here once:

  1. this table, if somebody has deliberately named a different person for a
     company (a communications officer who is not the HR lead is the everyday
     reason);
  2. the company's `hr_lead` responsibility holder;
  3. whoever is writing the post, because a post with nobody's name on it is
     worse than a post with the wrong name on it — the wrong name can be
     changed by anybody who opens it.

WHAT IT IS NOT. It is not a permission. The responsible person may edit their
own post until the window closes because a RECORD RULE says so (R157), and
being named here grants nothing else.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PbHrCommDefault(models.Model):
    _name = 'pb.hr.comm.default'
    _description = 'Who announcements land on'
    _order = 'company_id'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        ondelete='cascade', default=lambda self: self.env.company)
    user_id = fields.Many2one(
        'res.users', string='Who looks after announcements', required=True,
        domain=[('share', '=', False)],
        help='New announcements for this company arrive with this person\'s '
             'name on them. They are the one reminded two days before, and '
             'the one who can change it up to then.')
    note = fields.Char(string='Why', help='A line for whoever reads this next.')

    #: ONE ROW PER COMPANY. Odoo 19 SILENTLY IGNORES a `_sql_constraints`
    #: list — the rule simply is not enforced and nothing says so — and a
    #: `models.Constraint` class attribute is the form that reaches Postgres.
    _one_per_company = models.Constraint(
        'unique(company_id)',
        'That company already says who looks after its announcements.')

    @api.constrains('user_id', 'company_id')
    def _check_user_sees_the_company(self):
        """Somebody who cannot see the company cannot look after its posts.

        Named here rather than left to fail later: a responsible person who
        cannot open their own announcement is a dead end that only shows up
        two days before it goes out, in an email that links to a page they get
        refused from.
        """
        for rec in self:
            if not rec.user_id or not rec.company_id:
                continue
            if rec.company_id.id not in rec.user_id.company_ids.ids:
                raise ValidationError(_(
                    "%(who)s cannot see %(company)s, so they cannot look "
                    "after its announcements. Give them that company first.",
                    who=rec.user_id.name or '',
                    company=rec.company_id.name or ''))

    @api.model
    def responsible_for(self, company):
        """The ladder above, in one place, answered as a `res.users`.

        READ AS THE SYSTEM. The seat and this table both sit behind
        permissions a country HR user does not hold, and "who is in charge
        here" is not a secret — it is on every announcement they can already
        read.
        """
        company = company[:1] if hasattr(company, 'ids') else \
            self.env['res.company'].browse(int(company or 0))
        if not company:
            return self.env['res.users']
        row = self.sudo().search([('company_id', '=', company.id)], limit=1)
        if row.user_id:
            return row.user_id
        holder = self._hr_lead_for(company)
        if holder:
            return holder
        return self.env.user

    @api.model
    def _hr_lead_for(self, company):
        """The Approval Matrix's own answer, asked the way the engine asks it.

        `responsibility.resolve(company, role, scope_keys, on_date)` takes a
        ROLE RECORD and the scope list the adapter minted, most specific
        first, ending with '' for the whole company. An announcement is a
        company-wide thing, so the list is exactly that one rank.

        ON TODAY'S DATE AND NEVER A DATE ON THE RECORD (R192). A seat resolved
        as of a post's send date would ask "who held this in November" about a
        post scheduled for November, and a route asks who holds the seat NOW,
        because now is when somebody is being told.
        """
        Role = self.env['biz.approval.role'].sudo()
        role = Role.search([('key', '=', 'hr_lead')], limit=1)
        if not role:
            return self.env['res.users']
        row, _label = self.env['biz.approval.responsibility'].sudo().resolve(
            company, role, [''], fields.Date.context_today(self))
        return row.user_id if row else self.env['res.users']
