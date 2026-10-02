# -*- coding: utf-8 -*-
"""`pb.goal.template` — a goal somebody has already worked out how to write.

THE BLANK PAGE IS THE PROBLEM THIS SOLVES. Ask four thousand people to write
three goals and most of the cost is not the thinking, it is the first sentence.
A template is HR's answer to "what does a good one look like for somebody doing
my job": a title, the paragraph underneath it, and the two or three key results
that make it answerable.

IT IS A STARTING POINT AND NEVER A RULE. Using one COPIES it in — the employee
then owns every word and can change all of it — rather than linking to it, so a
template edited in March does not silently reword goals people agreed in
January. The only thing that survives the copy is a pointer saying where it
came from, which is there so HR can see which templates people actually use.

`kr_titles` IS A TEXT BOX, ONE PER LINE, and that is a deliberate choice over a
child table. A person writing a template is writing a list of three short
phrases; asking them to open a sub-form three times to do it is how a feature
goes unused. The parse is one `splitlines()` and the round-trip is exact.
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class PbGoalTemplate(models.Model):
    _name = 'pb.goal.template'
    _description = 'Goal template'
    _order = 'sequence, name'

    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='What this template is for', required=True,
        help='How it appears in the list somebody picks from — "Grow a '
             'region", "Bring a new starter up to speed".')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company,
        help='Leave empty to offer it to everybody in every company.')

    title = fields.Char(string='The goal, as it will be written',
                        required=True)
    description = fields.Text(
        string='Why it matters and what good looks like', required=True)
    kr_titles = fields.Text(
        string='Key results, one per line',
        help='One per line. Each becomes a key result on the new goal, with '
             'the numbers left for the person to fill in.')

    job_ids = fields.Many2many(
        'hr.job', string='Offered to these jobs',
        help='Leave empty to offer it to everybody.')
    department_ids = fields.Many2many(
        'hr.department', string='Offered to these parts of the business',
        help='Leave empty to offer it to everybody.')
    note = fields.Text(string='Notes for the HR team')
    used_count = fields.Integer(string='Used', compute='_compute_used')

    @api.depends('name')
    def _compute_used(self):
        counts = {}
        if self.ids:
            rows = self.env['pb.goal'].sudo()._read_group(
                [('template_id', 'in', self.ids)], ['template_id'],
                ['__count'])
            counts = {template.id: count for template, count in rows}
        for record in self:
            record.used_count = counts.get(record.id, 0)

    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or _('Goal template')

    def kr_lines(self):
        """The key-result titles, as a list. Blank lines are not key results."""
        self.ensure_one()
        return [line.strip() for line in (self.kr_titles or '').splitlines()
                if line.strip()]

    # ------------------------------------------------------- who sees which
    @api.model
    def for_employee(self, employee):
        """The templates offered to one person, as the system.

        READ AS THE SYSTEM (R56): the caller is the employee, who holds no
        goals permission at all, and one field of an `hr.employee` prefetches
        forty of which forty sit behind payroll groups. The boundary is the
        company clause written out here.

        A template with NO job and NO department is offered to everybody —
        that is the ordinary case and it is what "leave it empty" means on the
        form. A template naming a job is offered only to that job. R17's
        lesson is the reason the two lists are ANDed the way they are: a
        wildcard row has to be the widest row, never a row that also matches
        something narrower by accident.
        """
        from .goals_common import as_id
        employee = self.env['hr.employee'].sudo().browse(
            as_id(employee)).exists()
        if not employee:
            return self.sudo().browse()
        rows = self.sudo().search([
            '|', ('company_id', '=', False),
            ('company_id', '=', employee.company_id.id),
        ], order='sequence, name')
        job = employee.job_id
        department = employee.department_id
        keep = self.sudo().browse()
        for row in rows:
            if row.job_ids and job not in row.job_ids:
                continue
            if row.department_ids and department not in row.department_ids:
                continue
            keep |= row
        return keep
