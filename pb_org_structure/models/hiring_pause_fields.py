# -*- coding: utf-8 -*-
"""Pause hiring — the switches and the one answer (cross-step contract C-2).

Three switches, each with a reason, who and when:

* `res.company.pb_hiring_pause` — the whole company;
* `hr.department.pb_hiring_pause` — a team AND every team under it;
* `hr.job.pb_hiring_pause_self` — one role.

and ONE stored answer per job, `hr.job.pb_hiring_paused` (C-2: S6-B probes
`'pb_hiring_paused' in env['hr.job']._fields` and hides paused roles from
internal applicants). It is a stored compute of the three switches, so
switching one off restores the role exactly as it was: nothing about the
role, its request, its advert or its candidates is rewritten while paused.

`hr.department.pb_hiring_paused` is the department's own answer (its switch,
a parent's, or its company's), recursive over `parent_id`.
"""
from odoo import _, api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pb_hiring_pause = fields.Boolean(string='Hiring paused for the company')
    pb_hiring_pause_reason = fields.Char(string='Why hiring is paused')
    pb_hiring_pause_by = fields.Many2one('res.users', string='Paused by')
    pb_hiring_pause_on = fields.Datetime(string='Paused on')


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    pb_hiring_pause = fields.Boolean(string='Hiring paused for this team')
    pb_hiring_pause_reason = fields.Char(string='Why hiring is paused')
    pb_hiring_pause_by = fields.Many2one('res.users', string='Paused by')
    pb_hiring_pause_on = fields.Datetime(string='Paused on')
    pb_hiring_paused = fields.Boolean(
        string='Hiring paused', compute='_compute_pb_hiring_paused',
        store=True, recursive=True, index=True,
        help='Paused for this team, a team above it, or its company.')
    pb_cost_centre_id = fields.Many2one(
        'pb.cost.centre', string='Usual cost centre',
        help='Filled in on new contracts in this team that have no cost '
             'centre. Moving people already here is done from a date, on '
             'the Jobs tab.')

    @api.depends('pb_hiring_pause', 'parent_id.pb_hiring_paused',
                 'company_id.pb_hiring_pause')
    def _compute_pb_hiring_paused(self):
        for dept in self:
            dept.pb_hiring_paused = bool(
                dept.pb_hiring_pause or dept.parent_id.pb_hiring_paused
                or dept.company_id.pb_hiring_pause)

    def _pb_pause_source(self):
        """The record whose switch pauses this team: itself, the nearest
        team above it, or its company. Empty when hiring is not paused."""
        self.ensure_one()
        dept = self.sudo()
        seen = set()
        while dept and dept.id not in seen:
            seen.add(dept.id)
            if dept.pb_hiring_pause:
                return dept
            dept = dept.parent_id
        if self.sudo().company_id.pb_hiring_pause:
            return self.sudo().company_id
        return self.env['hr.department']


class HrJob(models.Model):
    _inherit = 'hr.job'

    pb_level_id = fields.Many2one(
        'pb.job.level', string='Level', index=True, ondelete='restrict')
    pb_hiring_pause_self = fields.Boolean(string='Hiring paused for this role')
    pb_hiring_pause_reason_self = fields.Char(string='Why hiring is paused')
    pb_hiring_pause_by = fields.Many2one('res.users', string='Paused by')
    pb_hiring_pause_on = fields.Datetime(string='Paused on')
    # C-2: the one boolean other steps read. Do not rename.
    pb_hiring_paused = fields.Boolean(
        string='Hiring paused', compute='_compute_pb_hiring_paused',
        store=True, index=True,
        help='Paused for this role, its team (or a team above it) or its '
             'company. New hiring requests and adverts stop; people already '
             'in progress carry on.')

    @api.depends('pb_hiring_pause_self', 'department_id.pb_hiring_paused',
                 'company_id.pb_hiring_pause')
    def _compute_pb_hiring_paused(self):
        for job in self:
            job.pb_hiring_paused = bool(
                job.pb_hiring_pause_self
                or job.department_id.pb_hiring_paused
                or job.company_id.pb_hiring_pause)

    # ------------------------------------------------------------ the words
    def _pb_pause_source(self):
        self.ensure_one()
        job = self.sudo()
        if job.pb_hiring_pause_self:
            return job
        if job.department_id:
            src = job.department_id._pb_pause_source()
            if src:
                return src
        if job.company_id.pb_hiring_pause:
            return job.company_id
        return self.env['hr.job']

    def pb_hiring_pause_sentence(self):
        """'' when hiring is open for this role, else the plain sentence."""
        self.ensure_one()
        if not self.sudo().pb_hiring_paused:
            return ''
        return pause_sentence(self.env, self._pb_pause_source(), self.sudo())

    # ------------------------------------------- the careers page and forms
    def pb_hiring_accepts_applications(self, website):
        if not super().pb_hiring_accepts_applications(website):
            return False
        return not self.sudo().exists().pb_hiring_paused

    @api.model
    def _search_get_detail(self, website, order, options):
        """The careers page list leaves paused roles out (restored the moment
        hiring is restarted, because nothing about the role was changed)."""
        detail = super()._search_get_detail(website, order, options)
        base = detail.get('base_domain')
        if isinstance(base, list):
            detail['base_domain'] = base + [[('pb_hiring_paused', '=', False)]]
        return detail


def pause_sentence(env, source, job=None):
    """"Hiring is paused for <where>: <reason>." in the reader's language."""
    if not source:
        return ''
    if source._name == 'hr.job':
        where = _("this role")
        reason = source.pb_hiring_pause_reason_self
    elif source._name == 'hr.department':
        where = source.display_name or source.name or _("this team")
        reason = source.pb_hiring_pause_reason
    else:
        where = source.name or _("this company")
        reason = source.pb_hiring_pause_reason
    if reason:
        return _("Hiring is paused for %(where)s: %(reason)s",
                 where=where, reason=reason)
    return _("Hiring is paused for %(where)s.", where=where)


def team_pause(env, department, company=None):
    """(paused?, sentence) for a team, or a company when there is no team."""
    if department:
        source = department._pb_pause_source()
        return bool(source), pause_sentence(env, source)
    company = (company or env.company).sudo()
    if company.pb_hiring_pause:
        return True, pause_sentence(env, company)
    return False, ''
