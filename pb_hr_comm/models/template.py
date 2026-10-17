# -*- coding: utf-8 -*-
"""`pb.hr.comm.template` — an announcement somebody has already written once.

A TEMPLATE IS A STARTING POINT AND NEVER A LINK. Picking one COPIES its
subject, its words and its poster onto the post and then forgets about it: the
person writing owns every word from that moment on, and editing the template
next March cannot rewrite an announcement that went out in January. A
one2many-style link would make the library the truth and the post a view of it,
which is exactly backwards for something that is sent and then kept.

NOTHING IS SEEDED. Six sample templates written by us would be six things an
HR team has to delete before the library means anything, and the empty state
teaches better than a starter pack in somebody else's voice.
"""

from odoo import _, api, fields, models


class PbHrCommTemplate(models.Model):
    _name = 'pb.hr.comm.template'
    _description = 'Announcement template'
    _order = 'sequence, name'

    name = fields.Char(
        string='What it is called', required=True, translate=False,
        help='What the HR team will look for in the list — "Monthly town '
             'hall", "Public holiday notice".')
    sequence = fields.Integer(default=10)
    subject = fields.Char(
        string='Subject line',
        help='What people see in their inbox before they open anything. It '
             'is copied onto the announcement and can be changed there.')
    body_html = fields.Html(
        string='What it says', sanitize=True,
        help='The words, with the formatting. Copied onto the announcement — '
             'changing the template afterwards never changes something that '
             'has already gone out.')
    poster_ids = fields.Many2many(
        'ir.attachment', 'pb_hr_comm_template_attachment_rel',
        'template_id', 'attachment_id', string='Poster',
        help='A picture or a PDF that goes out with it.')
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave this empty and every company can use it.')
    note = fields.Text(
        string='When to use it',
        help='A line for whoever picks this up next year.')
    active = fields.Boolean(default=True)

    @api.model
    def usable_for(self, company_id=None):
        """The templates this company may pick from, newest wording first.

        A TEMPLATE WITH NO COMPANY BELONGS TO EVERYBODY, which is why the
        domain is an OR and not an equality — the everyday case is one HR team
        writing for four countries.
        """
        company_id = int(company_id or self.env.company.id)
        return self.search([
            '|', ('company_id', '=', False), ('company_id', '=', company_id),
        ])

    def action_use_it(self):
        """Open a new announcement with this template already copied in."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New announcement'),
            'res_model': 'pb.hr.comm.post',
            'view_mode': 'form',
            # R125 — a hand-built act_window dict MUST carry `views`, or the
            # client throws a TypeError the theme shows as a generic
            # "something went wrong" with nothing in the console.
            'views': [[False, 'form']],
            'target': 'current',
            'context': {'default_template_id': self.id},
        }
