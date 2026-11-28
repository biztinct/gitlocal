# -*- coding: utf-8 -*-
"""One answer to one version of a company's privacy notice, per EMPLOYEE.

Keyed on the employee record, not on the login (FACTS §4.2): one person can
be employed by two companies, and each company asks its own question. The row
keeps the exact wording shown and the language, so what somebody agreed to
can always be shown again, word for word, even after the notice changes.

Rows are never edited. Changing an answer adds a new row; the newest row for
(employee, notice) is the answer.

WHO READS THEM. HR only (`hr.group_hr_user`). No line manager, no employee
backend access: the employee's own page reads their rows under sudo after the
session guard (ledger T-R11).
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .notice import HR_GROUP

ANSWERS = [('agree', 'I have read and agree'), ('disagree', 'I do not agree')]
HOW = [('screen', 'On My Payobook'), ('paper', 'On paper, recorded by HR')]


class PbPrivacyConsent(models.Model):
    _name = 'pb.privacy.consent'
    _description = 'Privacy notice answer'
    _order = 'answered_on desc, id desc'

    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, index=True, ondelete='cascade',
                                  readonly=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, readonly=True)
    notice_id = fields.Many2one('pb.privacy.notice', string='Notice',
                                required=True, index=True, ondelete='restrict',
                                readonly=True)
    version = fields.Integer(string='Version', readonly=True)
    answer = fields.Selection(ANSWERS, string='Answer', required=True,
                              readonly=True)
    how = fields.Selection(HOW, string='How', required=True, readonly=True,
                           default='screen')
    wording = fields.Html(string='Wording shown', sanitize=True, readonly=True)
    lang = fields.Char(string='Language', readonly=True)
    answered_on = fields.Datetime(string='When', required=True, readonly=True,
                                  default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Answered with the login',
                              readonly=True)
    recorded_by = fields.Many2one('res.users', string='Recorded by',
                                  readonly=True)
    note = fields.Char(string='Note', readonly=True)

    # ---------------------------------------------------------------- rules
    @api.model_create_multi
    def create(self, vals_list):
        # Only the two system paths below ever create a row (sudo after their
        # own check); nobody types one in through the backend.
        if not self.env.su:
            raise AccessError(_("Answers are recorded by My Payobook or by HR's "
                                "paper consent button only."))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            raise UserError(_("An answer is a record and cannot be changed. A "
                              "new answer is added instead."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_("An answer is a record and cannot be deleted."))
        return super().unlink()

    # ------------------------------------------------------------ the logic
    @api.model
    def _pb_latest(self, employee, notice):
        return self.sudo().search([('employee_id', '=', employee.id),
                                   ('notice_id', '=', notice.id)],
                                  order='answered_on desc, id desc', limit=1)

    @api.model
    def _pb_own_employees(self, user):
        if not user or user._is_public():
            return self.env['hr.employee'].sudo().browse()
        return self.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id), ('active', '=', True)], order='id')

    @api.model
    def _pb_pending(self, user):
        """`(notice, employee)` the login still has to answer, else
        `(None, None)`. Any answer to the CURRENT version counts, screen or
        paper, yes or no: the question is asked once per version."""
        Notice = self.env['pb.privacy.notice'].sudo()
        for employee in self._pb_own_employees(user):
            notice = Notice._pb_current(employee.company_id)
            if notice and not self._pb_latest(employee, notice):
                return notice, employee
        return None, None

    @api.model
    def _pb_has_notice(self, user):
        """Does any company of this login have a published notice?"""
        Notice = self.env['pb.privacy.notice'].sudo()
        return any(Notice._pb_current(e.company_id)
                   for e in self._pb_own_employees(user))

    @api.model
    def _pb_record_screen(self, user, notice, answer, lang=None):
        """The employee's own answer from My Payobook — for EVERY employee
        record of this login in the notice's company. The caller resolved
        `user` from the session; the notice must be that company's current
        one. Returns the rows made."""
        if answer not in dict(ANSWERS):
            raise UserError(_("Choose one of the two answers."))
        notice = notice.sudo()
        if notice.state != 'published':
            raise UserError(_("This notice has been replaced. Please read the "
                              "new one."))
        employees = self._pb_own_employees(user).filtered(
            lambda e: e.company_id == notice.company_id)
        if not employees:
            raise AccessError(_("This notice is not for you."))
        lang = lang or self.env.lang or 'en_US'
        wording = notice.with_context(lang=lang).body
        rows = self.sudo().create([{
            'employee_id': emp.id,
            'company_id': notice.company_id.id,
            'notice_id': notice.id,
            'version': notice.version,
            'answer': answer,
            'how': 'screen',
            'wording': wording,
            'lang': lang,
            'user_id': user.id,
        } for emp in employees])
        return rows

    @api.model
    def _pb_record_paper(self, employee, answer, note=None):
        """HR records a signed paper form for somebody (usually without a
        login). Only HR; the notice is the employee company's current one."""
        if not (self.env.su or self.env.user.has_group(HR_GROUP)):
            raise AccessError(_("Only HR can record paper consent."))
        if answer not in dict(ANSWERS):
            raise UserError(_("Choose one of the two answers."))
        employee = employee.sudo()
        if employee.company_id not in self.env.user.company_ids and not self.env.su:
            raise AccessError(_("This person is in a company you cannot see."))
        notice = self.env['pb.privacy.notice']._pb_current(employee.company_id)
        if not notice:
            raise UserError(_("%s has no published privacy notice yet.",
                              employee.company_id.name))
        lang = self.env.lang or 'en_US'
        return self.sudo().create({
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'notice_id': notice.id,
            'version': notice.version,
            'answer': answer,
            'how': 'paper',
            'wording': notice.with_context(lang=lang).body,
            'lang': lang,
            'recorded_by': self.env.uid,
            'note': (note or '')[:200] or False,
        })

    @api.model
    def _pb_status(self, row):
        """agreed / paper / declined / not_yet for one latest row (or none)."""
        if not row:
            return 'not_yet'
        if row.answer == 'disagree':
            return 'declined'
        return 'paper' if row.how == 'paper' else 'agreed'
