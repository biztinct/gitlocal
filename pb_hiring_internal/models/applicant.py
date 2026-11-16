# -*- coding: utf-8 -*-
"""A staff application: the standard candidate record, linked to the person.

ONE RECORD, THE STANDARD ONE. An internal application is an `hr.applicant`
on the real role, with the stock `employee_id` pointing at the person who
applied and `pb_internal` set. Everything the hiring team already does (the
board, the stages, interviews, scorecards, the offer) works unchanged; the
retention clean-up never takes it, because `_pb_retention_protected` already
protects any candidate with an employee record.

E4 — THE CURRENT MANAGER IS TOLD ONLY WHEN AN OFFER IS NEAR. "Near" is the
Offer stage (`offer`: "The person we want") or anything after it, or an
offer record being drafted. Until then:
  * the manager is not a follower of the application (removed at apply, in
    case a stock rule ever subscribes them),
  * no message, activity or approval names them,
  * nothing on their own pages mentions it.
At the moment an offer is near, they get ONE in-app note (when they use the
system inbox) and a line under "Needs you" on their own home, and the time
is recorded on the application for the hiring team.

THE APPLICATION IS NEVER COPIED OUT OF THE PERSON. "Fits another role" copies
a candidate onto another role; for an internal one the copy keeps the
employee link and the internal flag, or the second role would end in a
second employee record.
"""
import base64
import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.pb_hiring.models.hiring_common import OFFER_LIVE

_logger = logging.getLogger(__name__)

#: Stage keys from which the current manager is told (pb_hiring STAGE_ROWS).
OFFER_NEAR = ('offer', 'post_offer', 'joined')
#: Stages from which the employee may no longer withdraw on their own page.
NO_WITHDRAW = OFFER_NEAR
#: The stage a withdrawal moves the application to.
WITHDRAWN_STAGE = 'drop_out'
#: The longest note an employee may add.
MAX_NOTE = 2000
#: CV upload limits (the same as the referral page).
CV_MAX_BYTES = 5 * 1024 * 1024
CV_MIME_OK = (
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
)
#: The source name every staff application carries (looked up by name).
SOURCE_NAME = 'Internal'

#: The status an EMPLOYEE sees: a plain word, never a stage name (stage names
#: such as "CV reject" are the hiring team's words).
EMPLOYEE_STATES = ('received', 'considered', 'offer', 'accepted', 'moved',
                   'closed', 'withdrawn')


class HiringApplicantInternal(models.Model):
    _inherit = 'hr.applicant'

    pb_internal = fields.Boolean(
        string='Applied from inside the company', readonly=True, copy=False,
        index=True,
        help='This candidate already works here and applied from their own '
             'pages. Hiring them changes their job; it never makes a second '
             'employee record.')
    pb_internal_withdrawn_on = fields.Datetime(
        string='Withdrawn by them on', readonly=True, copy=False)
    pb_manager_told_on = fields.Datetime(
        string='Their manager was told on', readonly=True, copy=False,
        help='Their current manager is told only when an offer is near.')
    pb_manager_told_id = fields.Many2one(
        'hr.employee', string='Manager who was told', readonly=True,
        copy=False, ondelete='set null', index='btree_not_null')
    pb_new_manager_told_on = fields.Datetime(
        string='Their new manager was told on', readonly=True, copy=False)
    pb_new_manager_id = fields.Many2one(
        'hr.employee', string='New manager who was told', readonly=True,
        copy=False, ondelete='set null', index='btree_not_null')
    pb_job_change_state = fields.Selection(
        [('to_do', 'Job change to do'), ('opened', 'Job change opened')],
        string='Their job change', readonly=True, copy=False)

    # =================================================================
    #  Applying
    # =================================================================
    @api.model
    def _pbhi_source(self):
        Source = self.env['utm.source'].sudo()
        source = Source.search([('name', '=ilike', SOURCE_NAME)], limit=1)
        return source or Source.create({'name': SOURCE_NAME})

    @api.model
    def _pbhi_open_application(self, employee, requisition):
        """The person's application to this role that is still in play."""
        apps = self.sudo().with_context(active_test=False).search([
            ('employee_id', '=', employee.id),
            ('pb_requisition_id', '=', requisition.id),
            ('pb_internal', '=', True),
        ], order='id desc')
        return apps.filtered(lambda a: a._pbhi_state() not in
                             ('closed', 'withdrawn'))[:1]

    @api.model
    def _pbhi_apply(self, employee, requisition, note='', cv=None):
        """Apply for `requisition` as `employee`. THE CALLER PROVED the
        employee is the session's own; everything here runs under sudo.

        `cv` is `{'name', 'datas', 'mimetype'}` already checked for size and
        type by the controller, or None. Returns the application."""
        employee = employee.sudo()
        req = requisition.sudo()
        if not employee or not req:
            raise UserError(_("That role is not open to staff any more."))
        if req.company_id not in employee.company_id:
            raise UserError(_("That role is not open to staff any more."))
        if not req._pbhi_open_for_staff():
            raise UserError(_("That role is not open to staff any more."))
        if self._pbhi_open_application(employee, req):
            raise UserError(_("You have already applied for this role."))
        job = req.job_id or req._ensure_job()
        email = employee.work_email or employee.user_id.email or False
        phone = employee.mobile_phone or employee.work_phone or False
        # A contact of the application's own: the recruiter editing the
        # candidate must never rename or re-address the person's real
        # contact (the stock inverse writes name / email / phone back).
        partner = self.env['res.partner'].sudo().create({
            'name': employee.name, 'email': email, 'phone': phone,
            'company_id': req.company_id.id,
        })
        note = (note or '').strip()[:MAX_NOTE]
        current = employee.job_id.name or employee.job_title or ''
        notes = _("Applied from inside the company. Works here now as "
                  "%(job)s in %(dept)s.",
                  job=current or _('(no job title)'),
                  dept=employee.department_id.name or _('(no department)'))
        if note:
            notes += '\n\n' + note
        vals = {
            'partner_id': partner.id,
            'partner_name': employee.name,
            'email_from': email,
            'partner_phone': phone,
            'job_id': job.id,
            'company_id': req.company_id.id,
            'department_id': req.department_id.id,
            'user_id': req.recruiter_id.id or job.user_id.id or False,
            'pb_requisition_id': req.id,
            'employee_id': employee.id,
            'pb_internal': True,
            'source_id': self._pbhi_source().id,
            'applicant_notes': notes,
            'pb_application_touch': {'source': 'Internal',
                                     'employee_id': employee.id},
        }
        app = self.sudo().with_context(mail_create_nosubscribe=True).create(vals)
        if cv:
            try:
                with self.env.cr.savepoint():
                    self.env['ir.attachment'].sudo().create({
                        'name': cv.get('name') or 'CV',
                        'datas': cv.get('datas'),
                        'mimetype': cv.get('mimetype') or False,
                        'res_model': 'hr.applicant',
                        'res_id': app.id,
                    })
            except Exception:           # noqa: BLE001 — the application stands
                _logger.warning('pb_hiring_internal: the CV on application %s '
                                'was not stored', app.id, exc_info=True)
        app._pbhi_keep_manager_out()
        app.sudo().message_post(body=_(
            "%(who)s applied from inside the company. Their current manager "
            "is told only when an offer is near.", who=employee.name or ''),
            message_type='comment', subtype_xmlid='mail.mt_note')
        return app

    def _pbhi_keep_manager_out(self):
        """E4: the current manager follows nothing about this application
        until an offer is near — unless they are on the role's hiring team,
        where they see it anyway (the employee was told before applying)."""
        for app in self.sudo():
            manager = app.employee_id.parent_id
            req = app.pb_requisition_id
            if not manager or not manager.user_id or not req:
                continue
            if req._pbhi_manager_on_team(app.employee_id):
                continue
            partner = manager.user_id.partner_id
            if partner and partner in app.message_partner_ids:
                app.message_unsubscribe(partner_ids=partner.ids)

    # =================================================================
    #  Withdrawing
    # =================================================================
    def _pbhi_can_withdraw(self):
        self.ensure_one()
        app = self.sudo()
        if not app.pb_internal or app._pbhi_state() in ('closed', 'withdrawn'):
            return False
        if app.stage_id.pb_key in NO_WITHDRAW:
            return False
        live = self.env['pb.hiring.offer'].sudo().search_count([
            ('applicant_id', '=', app.id), ('state', 'in', list(OFFER_LIVE))])
        return not live

    def _pbhi_withdraw(self):
        """The employee takes their application back (before an offer)."""
        self.ensure_one()
        app = self.sudo()
        if not app._pbhi_can_withdraw():
            raise UserError(_(
                "This application can no longer be withdrawn here. Talk to "
                "the recruiter for this role."))
        vals = {'pb_internal_withdrawn_on': fields.Datetime.now()}
        stage = self.env['hr.recruitment.stage']._pb_stage(WITHDRAWN_STAGE)
        if stage:
            vals['stage_id'] = stage.id
        app.with_context(pb_no_stage_log=False).write(vals)
        app.message_post(body=_("%(who)s withdrew their application.",
                                who=app.employee_id.name or ''),
                         message_type='comment', subtype_xmlid='mail.mt_note')
        return True

    # =================================================================
    #  What the employee is shown
    # =================================================================
    def _pbhi_state(self):
        """One of EMPLOYEE_STATES — never the hiring team's stage name."""
        self.ensure_one()
        app = self.sudo().with_context(active_test=False)
        if app.pb_internal_withdrawn_on:
            return 'withdrawn'
        key = app.stage_id.pb_key or ''
        offers = self.env['pb.hiring.offer'].sudo().search(
            [('applicant_id', '=', app.id)], order='id desc', limit=1)
        if key == 'joined' or offers.state == 'joined' \
                or app.application_status == 'hired':
            return 'moved'
        if not app.active or app.stage_id.pb_family == 'closed' \
                or app.application_status in ('refused', 'archived'):
            return 'closed'
        if key == 'post_offer' or offers.state in ('accepted', 'signed'):
            return 'accepted'
        if key == 'offer' or offers.state in OFFER_LIVE:
            return 'offer'
        if key in ('screening', ''):
            return 'received'
        return 'considered'

    # =================================================================
    #  E4 — telling the current manager, once, when an offer is near
    # =================================================================
    def write(self, vals):
        res = super().write(vals)
        if 'stage_id' in vals and not self.env.context.get('pbhi_no_tell'):
            near = self.sudo().filtered(
                lambda a: a.pb_internal and not a.pb_manager_told_on
                and a.stage_id.pb_key in OFFER_NEAR)
            if near:
                near._pbhi_tell_manager()
        return res

    def copy_data(self, default=None):
        """"Fits another role" copies a candidate. An internal one keeps who
        they are, or the second role would hire a second employee."""
        vals_list = super().copy_data(default=default)
        for app, vals in zip(self, vals_list):
            if app.pb_internal and app.employee_id:
                vals.setdefault('employee_id', app.employee_id.id)
                vals.setdefault('pb_internal', True)
        return vals_list

    def _pbhi_tell_manager(self):
        """Tell the CURRENT manager that an offer is near. Idempotent: the
        time is stamped once, and a second call does nothing."""
        for app in self.sudo():
            if not app.pb_internal or app.pb_manager_told_on:
                continue
            emp = app.employee_id
            manager = emp.parent_id
            app.with_context(pbhi_no_tell=True).write({
                'pb_manager_told_on': fields.Datetime.now(),
                'pb_manager_told_id': manager.id or False,
            })
            if not manager:
                app.message_post(body=_(
                    "An offer is near. %(who)s has no manager on their "
                    "record, so nobody else was told.", who=emp.name or ''),
                    message_type='comment', subtype_xmlid='mail.mt_note')
                continue
            role = app.pb_requisition_id._pbhi_title() if app.pb_requisition_id \
                else (app.job_id.name or '')
            app._pbhi_note_manager(manager, emp, role)
            app.message_post(body=_(
                "An offer is near, so %(manager)s, their current manager, "
                "was told.", manager=manager.name or ''),
                message_type='comment', subtype_xmlid='mail.mt_note')

    def _pbhi_note_manager(self, manager, emp, role):
        """ONE in-app note in the manager's own inbox, when they use it. The
        line under "Needs you" on their home is drawn from this application
        (pb_me_home), so a manager without a backend login is told too.
        Never an email of its own (tenant email is off on purpose)."""
        user = manager.user_id
        if not user or user.share or user.notification_type != 'inbox':
            return False
        lang = user.lang or self.env.lang
        body = Markup('<p>%s</p>') % escape(self.with_context(lang=lang).env._(
            "%(who)s is close to an offer for %(role)s. HR will talk to you "
            "about the move and when it happens.",
            who=emp.name or '', role=role or ''))
        try:
            with self.env.cr.savepoint():
                emp.sudo().message_notify(
                    partner_ids=user.partner_id.ids, body=body,
                    subject=self.with_context(lang=lang).env._(
                        "A move in your team"))
        except Exception:               # noqa: BLE001 — a courtesy, never a failure
            _logger.warning('pb_hiring_internal: could not note manager %s',
                            manager.id, exc_info=True)
            return False
        return True
