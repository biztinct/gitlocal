# -*- coding: utf-8 -*-
"""`/my/jobs` — roles inside the company, on the employee's own pages.

THE ROUTE IS THE GATE (ledger T-R11). The employee is re-resolved from the
SESSION on every request (`_ess_employee`) and no route accepts an employee
id. The one id a route does take is the ROLE's, and it is checked again on
every request: open, open to staff, not confidential, not a quiet
replacement, not paused (C-2), and in the employee's own company. An
application reached through a role is only ever the session's own.

Portal (share) logins hold no rights on any hiring model, so every read and
write runs under sudo AFTER those checks. A refusal comes back to the same
page with a short key; the template owns the words. Never a traceback.

Helpers carry the `_pbhi_` prefix: every portal controller of every module
is merged into ONE class, so a generic name would collide (pb_ask_hr P3d).
"""
import base64
import logging

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from odoo.addons.pb_me_portal.controllers.portal import PbMePortal

from ..models.applicant import CV_MAX_BYTES, CV_MIME_OK, MAX_NOTE

_logger = logging.getLogger(__name__)

#: `?done=` keys the pages confirm.
_DONE = ('applied', 'withdrawn')
#: `?error=` keys the pages explain.
_ERRORS = ('closed', 'twice', 'size', 'type', 'late', 'failed')


class PbHiringInternalPortal(PbMePortal):

    # ------------------------------------------------------------ helpers
    def _pbhi_role(self, emp, requisition_id):
        """The role as a SUDO record when THIS employee may see it, else an
        empty recordset."""
        Req = request.env['pb.hiring.requisition'].sudo()
        try:
            req = Req.browse(int(requisition_id)).exists()
        except (TypeError, ValueError):
            return Req.browse()
        if not req or not emp or req.company_id not in emp.company_id:
            return Req.browse()
        return req

    def _pbhi_application(self, emp, req):
        """The session's own latest application to `req` (any state)."""
        return request.env['hr.applicant'].sudo().with_context(
            active_test=False).search([
                ('employee_id', '=', emp.id), ('pb_requisition_id', '=', req.id),
                ('pb_internal', '=', True)], order='id desc', limit=1)

    def _pbhi_role_row(self, emp, req, app=None):
        return {
            'id': req.id,
            'title': req._pbhi_title(),
            'department': req.department_id.name or '',
            'location': req.location or req.country_id.name or '',
            'opened_on': req.opened_on,
            'url': '/my/jobs/%s' % req.id,
            'state': app._pbhi_state() if app else '',
            'manager_on_team': req._pbhi_manager_on_team(emp),
        }

    def _pbhi_app_row(self, app):
        req = app.pb_requisition_id
        return {
            'id': app.id,
            'title': req._pbhi_title() if req else (app.job_id.name or ''),
            'department': req.department_id.name if req else '',
            'state': app._pbhi_state(),
            'applied_on': app.create_date,
            'url': '/my/jobs/%s' % req.id if req else '/my/jobs',
        }

    def _pbhi_count(self, emp):
        if not emp:
            return 0
        Req = request.env['pb.hiring.requisition']
        roles = Req._pbhi_roles_for(emp)
        mine = request.env['hr.applicant'].sudo().with_context(
            active_test=False).search_count([
                ('employee_id', 'in', self._ess_own_employees().ids),
                ('pb_internal', '=', True)])
        return len(roles) + mine

    # ------------------------------------------------------ home counter
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'pbhi_jobs_count' in counters:
            try:
                values['pbhi_jobs_count'] = self._pbhi_count(self._ess_employee())
            except Exception:           # noqa: BLE001 — never a 500 on /my
                _logger.warning('pb_hiring_internal: the jobs count failed',
                                exc_info=True)
                values['pbhi_jobs_count'] = 0
        return values

    # =============================================================== list
    @http.route(['/my/jobs'], type='http', auth='user', website=True)
    def portal_my_jobs(self, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        roles = request.env['pb.hiring.requisition']._pbhi_roles_for(emp)
        App = request.env['hr.applicant'].sudo().with_context(active_test=False)
        apps = App.search([('employee_id', '=', emp.id),
                           ('pb_internal', '=', True)], order='id desc',
                          limit=40)
        latest = {}
        for app in apps:
            latest.setdefault(app.pb_requisition_id.id, app)
        values = {
            'page_name': 'pbhi_jobs',
            'roles': [self._pbhi_role_row(emp, r, latest.get(r.id)) for r in roles],
            'mine': [self._pbhi_app_row(a) for a in apps],
            'done': kw.get('done') if kw.get('done') in _DONE else None,
        }
        return request.render('pb_hiring_internal.portal_my_jobs', values)

    # =============================================================== role
    @http.route(['/my/jobs/<int:requisition_id>'], type='http', auth='user',
                website=True, methods=['GET'])
    def portal_my_job(self, requisition_id, **kw):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        req = self._pbhi_role(emp, requisition_id)
        app = self._pbhi_application(emp, req) if req else None
        # A role closed or no longer open to staff stays readable ONLY for
        # somebody who applied to it (to follow their application).
        if not req or (not req._pbhi_open_for_staff() and not app):
            return request.render('pb_hiring_internal.portal_my_job_missing',
                                  {'page_name': 'pbhi_job'}, status=404)
        state = app._pbhi_state() if app else ''
        values = {
            'page_name': 'pbhi_job',
            'role': self._pbhi_role_row(emp, req, app),
            'advert': req.jd_current_id.body or False,
            'requirements': req.requirements or '',
            'application': self._pbhi_app_row(app) if app else None,
            'can_apply': req._pbhi_open_for_staff() and (
                not app or state in ('closed', 'withdrawn')),
            'can_withdraw': bool(app and app._pbhi_can_withdraw()),
            'max_note': MAX_NOTE,
            'done': kw.get('done') if kw.get('done') in _DONE else None,
            'error': kw.get('error') if kw.get('error') in _ERRORS else None,
        }
        return request.render('pb_hiring_internal.portal_my_job', values)

    @http.route(['/my/jobs/<int:requisition_id>/apply'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_job_apply(self, requisition_id, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        req = self._pbhi_role(emp, requisition_id)
        back = '/my/jobs/%s' % int(requisition_id)
        if not req or not req._pbhi_open_for_staff():
            return request.redirect(back + '?error=closed')
        cv = None
        upload = post.get('cv')
        if upload and getattr(upload, 'filename', ''):
            data = upload.read(CV_MAX_BYTES + 1)
            if len(data) > CV_MAX_BYTES:
                return request.redirect(back + '?error=size')
            if (upload.mimetype or '') not in CV_MIME_OK:
                return request.redirect(back + '?error=type')
            cv = {'name': upload.filename or 'CV',
                  'datas': base64.b64encode(data),
                  'mimetype': upload.mimetype}
        App = request.env['hr.applicant'].sudo()
        if App._pbhi_open_application(emp, req):
            return request.redirect(back + '?error=twice')
        try:
            with request.env.cr.savepoint():
                App._pbhi_apply(emp, req, note=post.get('note') or '', cv=cv)
        except (AccessError, UserError, ValidationError) as exc:
            _logger.info('pb_hiring_internal: an application was refused: %s',
                         exc)
            return request.redirect(back + '?error=failed')
        return request.redirect(back + '?done=applied')

    @http.route(['/my/jobs/<int:requisition_id>/withdraw'], type='http',
                auth='user', website=True, methods=['POST'])
    def portal_my_job_withdraw(self, requisition_id, **post):
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        req = self._pbhi_role(emp, requisition_id)
        back = '/my/jobs/%s' % int(requisition_id)
        app = self._pbhi_application(emp, req) if req else None
        if not app:
            return request.redirect('/my/jobs')
        if not app._pbhi_can_withdraw():
            return request.redirect(back + '?error=late')
        try:
            with request.env.cr.savepoint():
                app._pbhi_withdraw()
        except (AccessError, UserError, ValidationError) as exc:
            _logger.info('pb_hiring_internal: a withdrawal was refused: %s', exc)
            return request.redirect(back + '?error=late')
        return request.redirect(back + '?done=withdrawn')

    # ============================================================== moves
    @http.route(['/my/jobs/moves'], type='http', auth='user', website=True)
    def portal_my_team_moves(self, **kw):
        """A MANAGER's page: people in their team close to a move, from the
        moment they were told (E4). Nothing before that, nothing else."""
        emp = self._ess_employee()
        if not emp:
            return request.redirect('/my')
        moves = request.env['pb.me.home']._pbhi_team_moves(emp)
        rows = [{
            'name': a.employee_id.name or '',
            'role': a.pb_requisition_id._pbhi_title() if a.pb_requisition_id
            else (a.job_id.name or ''),
            'state': a._pbhi_state(),
            'told_on': a.pb_manager_told_on,
        } for a in moves]
        joining = [{
            'name': o.applicant_id.employee_id.name or '',
            'job': o.job_title or '',
            'when': o.expected_join_date or o.start_date,
        } for o in request.env['pb.me.home']._pbhi_team_joiners(emp)]
        return request.render('pb_hiring_internal.portal_my_team_moves',
                              {'page_name': 'pbhi_moves', 'rows': rows,
                               'joining': joining})
