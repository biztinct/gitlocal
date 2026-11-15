# -*- coding: utf-8 -*-
"""Pause hiring — where it stops things, and where it only warns (J6).

STOPS (a plain sentence, nothing written):
  * a NEW hiring request (`pb.hiring.requisition.create` — every path: the
    board's "New request", a recruiter opening a role, the Decision Room
    plan, an import);
  * sending a request in (`_request_send_in`);
  * opening a role for candidates (`_open_for_candidates`) and advertising it
    (`pb.hiring.posting.publish_for`);
  * a new open role added on the org chart (`pb.orgchart._do_add_open_role`);
  * the careers page and its application form (`hr.job`, see
    `hiring_pause_fields.py`).

CARRIES ON, with a warning on the role page and beside the offer:
  * candidates already in progress, interviews, an agreed request, offers.

Nothing in `pb_hiring` or `pb_orgchart` is edited: every stop is an override.
"""
from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.pb_hiring.models.hiring_common import as_id
from odoo.addons.pb_orgchart.models.pb_orgchart_write import _Refused

from .hiring_pause_fields import pause_sentence, team_pause


class HiringRequisitionPause(models.Model):
    _inherit = 'pb.hiring.requisition'

    def _pb_pause_sentence(self):
        """'' when hiring is open for this request's role/team/company."""
        self.ensure_one()
        rec = self.sudo()
        if rec.job_id and rec.job_id.pb_hiring_paused:
            return rec.job_id.pb_hiring_pause_sentence()
        return team_pause(self.env, rec.department_id, rec.company_id)[1]

    def _pb_refuse_if_paused(self):
        for rec in self:
            sentence = rec._pb_pause_sentence()
            if sentence:
                raise UserError(sentence)

    @api.model_create_multi
    def create(self, vals_list):
        Dept = self.env['hr.department'].sudo()
        Company = self.env['res.company'].sudo()
        Job = self.env['hr.job'].sudo()
        for vals in vals_list:
            job = Job.browse(vals.get('job_id') or 0).exists()
            if job and job.pb_hiring_paused:
                raise UserError(job.pb_hiring_pause_sentence())
            dept = Dept.browse(vals.get('department_id') or 0).exists()
            company = Company.browse(vals.get('company_id') or 0).exists() \
                or self.env.company
            paused, sentence = team_pause(self.env, dept, company)
            if paused:
                raise UserError(sentence)
        return super().create(vals_list)

    def _request_send_in(self, by_employee=None):
        self._pb_refuse_if_paused()
        return super()._request_send_in(by_employee=by_employee)

    def _open_for_candidates(self):
        if self.state != 'open':
            self._pb_refuse_if_paused()
        return super()._open_for_candidates()


class HiringPostingPause(models.Model):
    _inherit = 'pb.hiring.posting'

    def publish_for(self, requisition_id):
        req = self.env['pb.hiring.requisition'].browse(
            as_id(requisition_id)).exists()
        if req:
            req._pb_refuse_if_paused()
        return super().publish_for(requisition_id)


class HiringBoardPause(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _row(self, req):
        row = super()._row(req)
        sentence = self._safe(lambda: req._pb_pause_sentence(), default='')
        row['pb_paused'] = bool(sentence)
        row['pb_paused_reason'] = sentence
        return row

    @api.model
    def _board(self, req, row):
        board = super()._board(req, row)
        board['pb_paused_reason'] = self._safe(
            lambda: req._pb_pause_sentence(), default='')
        return board


class OrgChartPause(models.AbstractModel):
    _inherit = 'pb.orgchart'

    @api.model
    def _do_add_open_role(self, manager_id, title, reason=False):
        mgr = self.env['hr.employee'].sudo().browse(
            as_id(manager_id)).exists()
        if mgr:
            name = (title or '').strip()
            job = self.env['hr.job'].sudo().search([
                ('name', '=ilike', name),
                ('department_id', '=', mgr.department_id.id or False),
                ('company_id', '=', mgr.company_id.id)], limit=1) if name \
                else self.env['hr.job']
            if job and job.pb_hiring_paused:
                raise _Refused(job.pb_hiring_pause_sentence())
            paused, sentence = team_pause(self.env, mgr.department_id,
                                          mgr.company_id)
            if paused:
                raise _Refused(sentence)
        return super()._do_add_open_role(manager_id, title, reason)


__all__ = ['pause_sentence']
