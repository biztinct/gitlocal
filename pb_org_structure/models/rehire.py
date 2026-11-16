# -*- coding: utf-8 -*-
"""Would we hire them again? — a mark on the leaver, for HR only.

* `hr.employee.pb_rehire` yes / no / not sure, with a note, who and when.
  Field-level `groups=` (PRC-W1: an employee login can read its own record
  through the ORM, so a screen filter alone is not enough). Screens read and
  write it under sudo after their own gate.
* Asked in the Exits drawer (`pb.exits.get_exit` + `set_rehire`), for anybody
  on the Exits board — including people whose last day has passed.
* On the Hiring board a candidate whose email or phone matches a former
  employee shows a quiet chip "Worked here before · would rehire: yes", to
  HR only. Never a block, never shown to line managers or agencies.
"""
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .org_common import GROUP_HR_USER, REHIRE, has

HR_ONLY = 'hr.group_hr_user'


class HrEmployeeRehire(models.Model):
    _inherit = 'hr.employee'

    pb_rehire = fields.Selection(
        REHIRE, string='Would rehire', groups=HR_ONLY,
        help='Would the company hire this person again? Seen by HR only.')
    pb_rehire_note = fields.Text(string='Why (rehire)', groups=HR_ONLY)
    pb_rehire_by = fields.Many2one('res.users', string='Rehire answer by',
                                   groups=HR_ONLY)
    pb_rehire_on = fields.Datetime(string='Rehire answer on', groups=HR_ONLY)

    def _pb_rehire_dict(self):
        self.ensure_one()
        emp = self.sudo()
        return {
            'value': emp.pb_rehire or '',
            'label': dict(self._fields['pb_rehire']._description_selection(
                self.env)).get(emp.pb_rehire, '') if emp.pb_rehire else '',
            'note': emp.pb_rehire_note or '',
            'by': emp.pb_rehire_by.name or '',
            'on': str(emp.pb_rehire_on or '')[:10],
        }

    def _pb_set_rehire(self, value, note=''):
        self.ensure_one()
        if value not in dict(REHIRE) and value not in ('', False, None):
            raise UserError(_("Choose yes, no or not sure."))
        self.sudo().write({
            'pb_rehire': value or False,
            'pb_rehire_note': (note or '').strip() or False,
            'pb_rehire_by': self.env.user.id if value else False,
            'pb_rehire_on': fields.Datetime.now() if value else False,
        })
        return self._pb_rehire_dict()


class ExitsRehire(models.AbstractModel):
    _inherit = 'pb.exits'

    @api.model
    def _pb_rehire_allowed(self):
        return self._can_write() and has(self.env.user, GROUP_HR_USER,
                                         'hr.group_hr_manager')

    @api.model
    def get_exit(self, case_id):
        detail = super().get_exit(case_id)
        if self._pb_rehire_allowed():
            case = self.env['pb.journey.case'].sudo().browse(int(case_id))
            emp = case.employee_id.with_context(active_test=False)
            if emp:
                detail['pb_rehire'] = dict(
                    emp._pb_rehire_dict(), case_id=case.id,
                    options=[{'key': k, 'label': lbl} for k, lbl in
                             emp._fields['pb_rehire']._description_selection(
                                 self.env)])
        return detail

    @api.model
    def set_rehire(self, case_id, value, note=''):
        if not self._pb_rehire_allowed():
            raise AccessError(_(
                "Whether somebody would be hired again is recorded by HR."))
        case = self.env['pb.journey.case'].sudo().browse(
            int(case_id or 0)).exists()
        if not case or not case.employee_id:
            raise UserError(_("That leaving checklist is no longer there."))
        return case.employee_id.with_context(
            active_test=False)._pb_set_rehire(value, note)


def _digits(text):
    return re.sub(r'\D', '', text or '')


class HiringCardRehire(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _pb_former_employee(self, app):
        """The most recent former employee with this candidate's email or
        phone, or nothing. Former = archived (they left)."""
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        companies = self.env.companies.ids or [self.env.company.id]
        email = (app.email_from or '').strip().lower()
        hits = Emp.browse()
        if email and '@' in email:
            hits = Emp.search([
                ('active', '=', False), ('company_id', 'in', companies),
                '|', ('work_email', '=ilike', email),
                ('private_email', '=ilike', email)],
                order='write_date desc', limit=1)
        phone = _digits(getattr(app, 'partner_phone', '') or '')
        if not hits and len(phone) >= 8:
            # digits only, so "+84 90 123 4567" finds "0901234567"'s tail too
            self.env['hr.employee'].flush_model(
                ['mobile_phone', 'private_phone', 'active', 'company_id'])
            self.env.cr.execute("""
                SELECT id FROM hr_employee
                 WHERE active IS NOT TRUE AND company_id = ANY(%s)
                   AND (right(regexp_replace(coalesce(mobile_phone, ''), '\\D', '', 'g'), 9) = right(%s, 9)
                    OR right(regexp_replace(coalesce(private_phone, ''), '\\D', '', 'g'), 9) = right(%s, 9))
                 ORDER BY write_date DESC LIMIT 1""", (companies, phone, phone))
            row = self.env.cr.fetchone()
            hits = Emp.browse(row[0]) if row else Emp.browse()
        return hits[:1]

    @api.model
    def _card(self, app, ivs, doc_count, req, now, today, can_recruit):
        card = super()._card(app, ivs, doc_count, req, now, today, can_recruit)
        if not has(self.env.user, GROUP_HR_USER, 'hr.group_hr_manager'):
            return card
        try:
            emp = self._pb_former_employee(app)
        except Exception:  # noqa: BLE001 - a chip never breaks the board
            emp = None
        if not emp:
            return card
        emp = emp.sudo()
        first = emp.first_contract_date if 'first_contract_date' in emp._fields \
            else False
        last = emp.departure_date if 'departure_date' in emp._fields else False
        years = ''
        if first and last:
            years = '%s–%s' % (first.year, last.year) if first.year != last.year \
                else str(last.year)
        elif last:
            years = str(last.year)
        value = emp.pb_rehire
        if value:
            label = dict(emp._fields['pb_rehire']._description_selection(
                self.env)).get(value, '')
            text = _("Worked here %(years)s · would rehire: %(answer)s",
                     years=years, answer=label) if years else \
                _("Worked here before · would rehire: %s", label)
        else:
            text = _("Worked here %s", years) if years else \
                _("Worked here before")
        chips = card.get('chips') or []
        chips.insert(0, {'label': text, 'tone': 'amber' if value == 'no' else ''})
        card['chips'] = chips[:2]
        card['pb_former_employee'] = text
        return card
