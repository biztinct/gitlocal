# -*- coding: utf-8 -*-
"""Closing an offer — the ten minutes that turn a candidate into a colleague.

THIS IS THE SEAM THE WHOLE MODULE EXISTS FOR. Everything before it is
paperwork about somebody who does not work here; everything after it is the
product's existing machinery about somebody who does. So this file is
deliberately a JOIN and not a second implementation: the employee is made the
way the standard recruitment store makes one, the contract the way the
Contracts phase makes one, the pay package is the pay package, the joining
checklist is the SAME one a person arriving through the connected system gets,
and the login is the one ruling D6 already decided on.

THE ORDER IS LOAD-BEARING and it is written out here once, because it is the
thing a later phase will need and the thing a reader will not be able to infer:

  1. the employee            — everything else hangs off it, so it RAISES
  2. the applicant is hired  — the stage the job itself marks as hired
  3. the contract            — a joining date is a contract, not a field (R77)
  4. the pay package         — draft, every line ticked, for the Comp team
  5. the login               — held, silent, D6
  6. the joining checklist   — `_open_case` then `_after_onboard`
  7. the signed letter       — filed in the vault as the system
  8. the role                — filled when the head count is reached
  9. who is told             — the hiring manager and the recruiter's manager

Steps two to nine are LEGS in their own savepoints (R131). A failure that
reached the database aborts the whole transaction, and a try/except in Python
does not revive it: without the savepoints one bad email address would undo
the employee record, the contract and the package that had already been
written, and the screen would say the person had joined.

IDEMPOTENT ALL THE WAY THROUGH. Closing an offer twice finds the employee, the
contract, the package and the checklist that already exist and makes none of
them again — which is what makes it safe to press the button after a failure
rather than safe only the first time.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    OFFER_PERIOD_YEAR, P_CLOSURE_MAIL, P_CREATE_CONTRACT, flag, leg,
    slug_filename,
)

_logger = logging.getLogger(__name__)

#: What a pay-package line's "how often" is called. The offer's own periods
#: are the same three words, so nothing is translated on the way across.
_PACKAGE_PERIODS = ('monthly', 'yearly', 'one_time')


class PbHiringOfferClosure(models.Model):
    _inherit = 'pb.hiring.offer'

    # =====================================================================
    #  The door
    # =====================================================================
    def action_close(self):
        """They have joined. Everything downstream, in one press."""
        self.ensure_one()
        if self.state == 'closed':
            return True
        if self.state != 'signed':
            raise UserError(_(
                "An offer is closed once the signed copy is on it. This one "
                "is “%s” — record the signed letter first, and this button "
                "does the rest.",
                dict(self._fields['state'].selection).get(self.state,
                                                          self.state)))

        employee = self._ensure_employee()
        if not employee:
            raise UserError(_(
                "The employee record could not be created, so nothing else "
                "has been done. Nothing has changed. Try again, and tell the "
                "HR team if it keeps happening."))

        leg(self.env, 'hiring the candidate on offer %s' % self.name,
            self._mark_applicant_hired)
        leg(self.env, 'the contract on offer %s' % self.name,
            self._ensure_contract)
        leg(self.env, 'the pay package on offer %s' % self.name,
            self._ensure_package)
        leg(self.env, 'the login on offer %s' % self.name,
            self._ensure_login)
        leg(self.env, 'the joining checklist on offer %s' % self.name,
            self._ensure_case)
        leg(self.env, 'filing the signed letter on offer %s' % self.name,
            self._file_signed_copy)

        self.sudo().write({'state': 'closed',
                           'closed_on': fields.Datetime.now()})
        self.sudo().message_post(body=_(
            "%(who)s joins on %(when)s. Their record, their contract, their "
            "pay package and their joining checklist are all ready.",
            who=self.candidate_name or '', when=self.start_date or ''))

        leg(self.env, 'filling the role behind offer %s' % self.name,
            lambda: self.requisition_id._on_filled())
        leg(self.env, 'telling everybody about offer %s' % self.name,
            self._tell_them_they_joined)
        return True

    # =====================================================================
    #  1. The employee
    # =====================================================================
    def _ensure_employee(self):
        """The employee record, made the way the standard store makes one.

        `create_employee_from_applicant()` is the standard method and it is
        deliberately NOT called: it opens an action, it is gated on the
        interviewer check, and its `work_email` falls back to the COMPANY's
        address, which would give every joiner the switchboard's mailbox.
        Its VALUES are reused verbatim (`_get_employee_create_vals`, verified
        on the server at `hr_applicant.py:1024`) and the three things it gets
        wrong for a joiner are written afterwards.

        Through the ORM and never raw SQL (R14): on this build the employment
        fields live on a version record and a raw write of `job_title` would
        fail on a column that does not exist.
        """
        self.ensure_one()
        if self.employee_id:
            return self.employee_id
        applicant = self.applicant_id.sudo()
        existing = self.env['hr.employee'].sudo().search(
            [('applicant_ids', 'in', applicant.ids)], limit=1)
        if existing:
            self.sudo().write({'employee_id': existing.id})
            return existing
        if not applicant.partner_id:
            if not applicant.partner_name:
                raise UserError(_(
                    "This candidate has no name on them, so no employee "
                    "record can be made."))
            applicant.partner_id = self.env['res.partner'].sudo().create({
                'is_company': False,
                'name': applicant.partner_name,
                'email': applicant.email_from,
            })
        vals = applicant._get_employee_create_vals()
        vals.update({
            'company_id': self.company_id.id,
            # THEIR OWN ADDRESS AND NOT THE SWITCHBOARD'S. The standard vals
            # fall back to the company's email so the record has "a valid
            # address by default" — which on a joiner means every new
            # colleague shares one mailbox and the credentials email goes to
            # reception.
            'work_email': applicant.email_from or vals.get('work_email'),
            'job_title': self.job_title or vals.get('job_title'),
        })
        manager = self._person(self.reporting_manager_id
                               or self.requisition_id.reporting_manager_id)
        if manager:
            vals['parent_id'] = manager.id
        employee = self.env['hr.employee'].sudo().create(vals)
        self.sudo().write({'employee_id': employee.id})
        # The CV and anything else the candidate sent, on the person rather
        # than on a candidate record nobody will open again.
        try:
            applicant.attachment_ids.sudo().copy(
                {'res_model': 'hr.employee', 'res_id': employee.id})
        except Exception:               # noqa: BLE001 — never fail a joiner
            _logger.warning('pb_hiring: the candidate attachments on offer %s '
                            'were not copied', self.id, exc_info=True)
        _logger.info('pb_hiring: offer %s created employee %s', self.name,
                     employee.id)
        return employee

    # =====================================================================
    #  2. The candidate is hired
    # =====================================================================
    def _mark_applicant_hired(self):
        """The stage the JOB says is the hired one, and the last one if it
        says nothing. Writing `stage_id` is enough — the standard model sets
        `date_closed` off `hired_stage` itself."""
        self.ensure_one()
        applicant = self.applicant_id.sudo()
        Stage = self.env['hr.recruitment.stage'].sudo()
        job = applicant.job_id
        domain = ['|', ('job_ids', '=', False), ('job_ids', 'in', job.ids)] \
            if job else []
        stage = Stage.search(domain + [('hired_stage', '=', True)],
                             order='sequence', limit=1)
        if not stage:
            stage = Stage.search(domain, order='sequence desc', limit=1)
        if not stage:
            _logger.info('pb_hiring: this database has no recruitment stage, '
                         'so candidate %s was left where they were',
                         applicant.id)
            return False
        if applicant.stage_id.id != stage.id:
            applicant.write({'stage_id': stage.id})
        return True

    # =====================================================================
    #  3. The contract
    # =====================================================================
    def _ensure_contract(self):
        """A joining date is a CONTRACT, not a field.

        `hr_employee.first_contract_date` is a real column on this build and
        it is NOT writable — it is derived (R77). A joiner created without a
        contract therefore has no joining date at all, no work anniversary and
        no row in the joiner digest, and nothing anywhere says so. The join
        date comes through `pb_people`'s ladder: the column, then the earliest
        `hr.contract.date_start`, then the create date — so the contract is
        what makes the second rung true.

        THROUGH THE ORM AND NOT THROUGH THE NEW-HIRE WIZARD, deliberately.
        The wizard raises its own `newhire` proposal, which would put a
        SECOND sign-off in front of a wage the offer route has just agreed —
        and a joiner whose contract is sitting in somebody's inbox is a joiner
        with no joining date on the morning they arrive. The wage here has
        been agreed by the hiring manager and the HR lead on the record this
        method is called from.

        Open-ended on purpose: an offer says when somebody starts and says
        nothing about when they stop. A fixed term is a decision the Contracts
        phase already owns, on a screen built for it.
        """
        self.ensure_one()
        if self.contract_id:
            return self.contract_id
        if not flag(self.env, P_CREATE_CONTRACT):
            _logger.info('pb_hiring: contracts are switched off, so offer %s '
                         'created no contract for %s', self.name,
                         self.candidate_name)
            self.sudo().message_post(body=_(
                "No contract was written, because that is switched off on "
                "this system. Their joining date has to be set by hand or "
                "they will have none."))
            return False
        employee = self.employee_id
        if not employee:
            return False
        existing = self.env['hr.contract'].sudo().search(
            [('employee_id', '=', employee.id)], limit=1)
        if existing:
            self.sudo().write({'contract_id': existing.id})
            return existing
        basic = self._basic_line()
        company = self.company_id
        vals = {
            'employee_id': employee.id,
            'name': _('%(who)s — from %(when)s', who=employee.name or '',
                      when=self.start_date or ''),
            'wage': float(basic.amount or 0.0),
            'date_start': str(self.start_date or
                              fields.Date.context_today(self)),
            'company_id': company.id,
        }
        calendar = company.sudo().resource_calendar_id
        if calendar:
            vals['resource_calendar_id'] = calendar.id
        contract = self.env['hr.contract'].sudo().create(vals)
        self.sudo().write({'contract_id': contract.id})
        return contract

    def _basic_line(self):
        """The line the contract's wage comes from: the biggest monthly
        earning. A contract carries ONE number and an offer carries several;
        the basic pay is the one everything else is calculated from, and the
        biggest monthly earning is what that is in every scheme this product
        has seen."""
        self.ensure_one()
        earnings = self.line_ids.filtered(
            lambda ln: ln.period == 'monthly' and (ln.amount or 0.0) > 0
            and ln.kind == 'earning')
        if not earnings:
            earnings = self.line_ids.filtered(
                lambda ln: ln.period == 'monthly' and (ln.amount or 0.0) > 0)
        return earnings.sorted(lambda ln: -(ln.amount or 0.0))[:1]

    # =====================================================================
    #  4. The pay package
    # =====================================================================
    def _ensure_package(self):
        """The offer's own lines, as the package the Comp team will activate.

        EVERY LINE ARRIVES TICKED, and that is the opposite of what the
        package's bootstrap does — on purpose. R64's unchecked line exists
        because a contract COMPONENT is not necessarily money: a salary grade
        and a count of dependants both arrive looking like an amount and the
        scheme's own metadata cannot tell them apart. An offer line is not
        that: a person typed it, on purpose, into a document a candidate
        signed. So it counts, and the package's own refusal to activate while
        anything is unticked is left with nothing to refuse.

        LEFT IN DRAFT. Activating somebody's pay package is the Comp team's
        act and they have a screen for it; a hiring module that activated it
        would be putting a number into payroll on the day an offer was
        closed, which is a week or a month before the person arrives.
        """
        self.ensure_one()
        if self.comp_id:
            return self.comp_id
        employee = self.employee_id
        if not employee:
            return False
        Comp = self.env['pb.employee.comp'].sudo()
        existing = Comp.search([('employee_id', '=', employee.id)],
                               order='id desc', limit=1)
        if existing:
            self.sudo().write({'comp_id': existing.id})
            return existing
        package = Comp.create({
            'employee_id': employee.id,
            'effective_date': str(self.start_date
                                  or fields.Date.context_today(self)),
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'note': _("Built from the offer %(ref)s, signed on %(when)s.",
                      ref=self.name or '', when=self.signed_on or ''),
            'line_ids': [(0, 0, {
                'sequence': ln.sequence,
                'name': ln.name or '',
                'kind': ln.kind or 'earning',
                'amount': ln.amount or 0.0,
                'period': (ln.period if ln.period in _PACKAGE_PERIODS
                           else 'monthly'),
                'checked': True,
                'note': ln.note or '',
            }) for ln in self.line_ids.sorted(lambda r: (r.sequence, r.id))],
        })
        self.sudo().write({'comp_id': package.id})
        package.message_post(body=_(
            "Built from the offer %s. Every line was typed on an offer letter "
            "somebody signed, so every line is ticked — look it over and make "
            "it current when they start.", self.name or ''))
        return package

    # =====================================================================
    #  5. The login (D6)
    # =====================================================================
    def _ensure_login(self):
        """The portal account a joiner arrives to, made silently.

        THE SAME METHOD A CONNECTED-SYSTEM ARRIVAL USES, not a second one.
        `_auto_create_login` never touches an account that already exists, is
        gated on its own switch, and holds the credentials email until joining
        day — which is ruling D6, decided once and implemented once.
        """
        self.ensure_one()
        employee = self.employee_id
        if not employee or employee.pb_portal_user_id:
            if employee and employee.pb_portal_user_id:
                self.sudo().write(
                    {'login_user_id': employee.pb_portal_user_id.id})
            return False
        summary = {'logins': 0, 'created': 0, 'updated': 0, 'ignored': 0,
                   'review': 0, 'onboarding': 0, 'offboarding': 0}
        self.env['pb.zoho.pipeline'].sudo()._auto_create_login(
            employee.sudo(), self.company_id, summary)
        employee.sudo().invalidate_recordset(['pb_portal_user_id'])
        if employee.sudo().pb_portal_user_id:
            self.sudo().write(
                {'login_user_id': employee.sudo().pb_portal_user_id.id})
        return summary.get('logins', 0)

    # =====================================================================
    #  6. The joining checklist
    # =====================================================================
    def _ensure_case(self):
        """THE SAME JOINING CHECKLIST A CONNECTED-SYSTEM ARRIVAL GETS.

        `_open_case` is idempotent by state (R30) — a second call finds the
        one that is running — and `_after_onboard` is the hook `pb_onboarding`
        extends to set the checklist up. Calling the pipeline rather than
        building a case here is what makes "however somebody arrives, they get
        the same welcome" true rather than merely intended.
        """
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return False
        pipeline = self.env['pb.zoho.pipeline'].sudo()
        case, opened = pipeline._open_case(
            employee.sudo(), 'onboarding', self.start_date, self.company_id)
        if case:
            self.sudo().write({'case_id': case.id})
        if opened:
            # The arrival dict every extension of the hook reads. Ours is
            # short and honest: this person did not come from a spreadsheet.
            pipeline._after_onboard(case, {
                'name': employee.name or '',
                'date_of_joining': str(self.start_date or ''),
                'source': 'pb_hiring',
                '_raw': {},
            })
        return case

    # =====================================================================
    #  7. The signed letter, in the vault
    # =====================================================================
    def _file_signed_copy(self):
        """The signed offer, filed on the person it is about.

        As the SYSTEM: filing is an act the company performs on its own
        behalf, and the recruiter closing an offer is not necessarily somebody
        the vault grants create to — its `create` strips the verification
        fields and checks attachment ownership for anybody who is not HR
        (`employee_document.py:100-114`). Nothing here writes a verification
        field, which is the vault's one guarded surface.
        """
        self.ensure_one()
        if not self.signed_attachment_id or not self.employee_id:
            return False
        Doc = self.env['pb.employee.document'].sudo()
        existing = Doc.search([('employee_id', '=', self.employee_id.id),
                               ('name', 'like', self.name or '~none~')],
                              limit=1)
        if existing:
            return existing
        category = self.env.ref('pb_employee_vault.cat_other',
                                raise_if_not_found=False)
        if not category:
            _logger.info('pb_hiring: no document category, so the signed '
                         'offer on %s was not filed', self.name)
            return False
        copy = self.signed_attachment_id.sudo().copy(
            {'res_model': 'pb.employee.document', 'res_id': 0,
             'name': slug_filename(
                 _('Signed offer %(ref)s', ref=self.name or ''),
                 fallback='signed-offer')})
        doc = Doc.create({
            'employee_id': self.employee_id.id,
            'category_id': category.id,
            'name': _('Signed offer %(ref)s', ref=self.name or ''),
            'attachment_id': copy.id,
            'issue_date': self.signed_on or fields.Date.context_today(self),
            'company_id': self.company_id.id,
        })
        copy.write({'res_id': doc.id})
        return doc

    # =====================================================================
    #  9. Who is told
    # =====================================================================
    def _tell_them_they_joined(self):
        """The hiring manager and the recruiter's manager, by name.

        Two mails and not a broadcast: the people who have to do something
        about a joiner are the person whose team they join and the person who
        runs recruiting. Everybody else finds out from the joining checklist,
        which is a screen rather than an email.
        """
        self.ensure_one()
        if not flag(self.env, P_CLOSURE_MAIL):
            _logger.info('pb_hiring: closure mail is switched off; offer %s '
                         'told nobody', self.name)
            return 0
        req = self.requisition_id.sudo()
        addresses = []
        manager = self._person(self.reporting_manager_id
                               or req.reporting_manager_id)
        for candidate in (manager.user_id.email, manager.work_email,
                          req.recruiter_manager_id.email):
            address = (candidate or '').strip()
            if address and address not in addresses:
                addresses.append(address)
        sent = 0
        for address in addresses:
            if self._mail('pb_hiring.mail_template_offer_closed', address):
                sent += 1
        if not sent:
            _logger.info('pb_hiring: offer %s closed and there was nobody to '
                         'tell', self.name)
        return sent

    # =====================================================================
    #  The doors
    # =====================================================================
    def action_open_employee(self):
        self.ensure_one()
        if not self.employee_id:
            raise UserError(_(
                "There is no employee record yet. One is made the moment the "
                "offer is closed."))
        return {'type': 'ir.actions.act_window', 'res_model': 'hr.employee',
                'res_id': self.employee_id.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': self.employee_id.sudo().name or ''}

    def action_open_package(self):
        self.ensure_one()
        if not self.comp_id:
            raise UserError(_("There is no pay package yet."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.employee.comp', 'res_id': self.comp_id.id,
                'view_mode': 'form', 'views': [[False, 'form']],
                'name': self.comp_id.sudo().name or ''}

    def action_open_case(self):
        self.ensure_one()
        if not self.case_id:
            raise UserError(_("There is no joining checklist yet."))
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.journey.case', 'res_id': self.case_id.id,
                'view_mode': 'form', 'views': [[False, 'form']],
                'name': self.case_id.sudo().display_name or ''}

    @api.model
    def _annual_of(self, amount, period):
        """One year of a line, for anybody reading this module from outside."""
        return (amount or 0.0) * OFFER_PERIOD_YEAR.get(period or 'monthly',
                                                       12.0)
