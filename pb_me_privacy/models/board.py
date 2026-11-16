# -*- coding: utf-8 -*-
"""People > Privacy: who has answered the company's privacy notice.

One company at a time (the notice is per company). Four places a person can
be, and each person is at exactly one, so the numbers add up to the head
count: agreed on My Payobook, agreed on paper (recorded by HR), said no, not
answered yet. Everything is read as HR, for the companies HR may see.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .notice import HR_GROUP

STATUSES = ('agreed', 'paper', 'declined', 'not_yet')
PAGE = 200


class PbPrivacyBoard(models.AbstractModel):
    _name = 'pb.privacy.board'
    _description = 'Privacy consent board'

    @api.model
    def _pb_allowed(self):
        return self.env.user.has_group(HR_GROUP) or self.env.user._is_admin()

    @api.model
    def _pb_company(self, company_id):
        companies = self.env.companies
        if company_id:
            company = self.env['res.company'].browse(int(company_id))
            if company in self.env.user.company_ids:
                return company
        return companies[:1] or self.env.company

    @api.model
    def get_board(self, company_id=0, status='', search='', offset=0):
        if not self._pb_allowed():
            return {'allowed': False,
                    'why': _("Only HR can see who has answered the privacy "
                             "notice.")}
        company = self._pb_company(company_id)
        Notice = self.env['pb.privacy.notice'].sudo()
        Consent = self.env['pb.privacy.consent'].sudo()
        notice = Notice._pb_current(company)
        draft = Notice.search([('company_id', '=', company.id),
                               ('state', '=', 'draft')], limit=1)
        out = {
            'allowed': True,
            'companies': [{'id': c.id, 'name': c.name}
                          for c in self.env.user.company_ids.sorted('name')],
            'company_id': company.id,
            'company': company.name,
            'notice': None,
            'draft_id': draft.id or 0,
            'counts': {k: 0 for k in STATUSES},
            'total': 0,
            'rows': [],
            'more': False,
        }
        if not notice:
            return out
        out['notice'] = {
            'id': notice.id, 'title': notice.name, 'version': notice.version,
            'published_on': fields.Datetime.to_string(notice.published_on)
            if notice.published_on else '',
            'published_by': notice.published_by.name or '',
        }
        employees = self.env['hr.employee'].sudo().search(
            [('company_id', '=', company.id), ('active', '=', True)],
            order='name, id')
        latest = {}
        for row in Consent.search([('notice_id', '=', notice.id)],
                                  order='answered_on asc, id asc'):
            latest[row.employee_id.id] = row      # the newest wins
        rows = []
        needle = (search or '').strip().lower()
        for emp in employees:
            row = latest.get(emp.id)
            st = Consent._pb_status(row)
            out['counts'][st] += 1
            if status in STATUSES and st != status:
                continue
            if needle and needle not in (emp.name or '').lower():
                continue
            rows.append({
                'employee_id': emp.id,
                'name': emp.name or '',
                'job': emp.job_title or (emp.job_id.name or ''),
                'has_login': bool(emp.user_id),
                'status': st,
                'when': fields.Datetime.to_string(row.answered_on) if row else '',
                'how': row.how if row else '',
                'by': (row.recorded_by.name if row and row.how == 'paper'
                       else (row.user_id.name if row else '')) or '',
            })
        out['total'] = len(employees)
        offset = max(0, int(offset or 0))
        out['rows'] = rows[offset:offset + PAGE]
        out['more'] = len(rows) > offset + PAGE
        out['shown'] = len(rows)
        return out

    @api.model
    def record_paper(self, employee_id, answer='agree', note=''):
        if not self._pb_allowed():
            raise AccessError(_("Only HR can record paper consent."))
        employee = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not employee:
            raise AccessError(_("That person could not be found."))
        self.env['pb.privacy.consent']._pb_record_paper(employee, answer, note)
        return True

    @api.model
    def open_notice(self, company_id=0, new=False):
        """The notice form: the current version, or (new=True, or none yet)
        a draft to write and publish."""
        if not self._pb_allowed():
            raise AccessError(_("Only HR can change the privacy notice."))
        company = self._pb_company(company_id)
        Notice = self.env['pb.privacy.notice']
        current = Notice._pb_current(company)
        if current and not new:
            return current.with_env(self.env)._pb_form_action()
        if current:
            return current.with_env(self.env).action_new_version()
        draft = Notice.search([('company_id', '=', company.id),
                               ('state', '=', 'draft')], limit=1)
        if not draft:
            draft = Notice.create({'company_id': company.id})
        return draft._pb_form_action()
