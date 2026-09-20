# -*- coding: utf-8 -*-
"""Choosing the colleague who shows a new joiner the ropes.

THE ELIGIBILITY CHECK NEVER HIDES ANYBODY. Every candidate the manager might
think of is shown, WITH the verdict and the reason beside them — "joined two
months ago", "still in their trial period", "works in another office". A list
that silently omits the obvious choice is a list the manager stops trusting,
and the question they actually have is *why not her*, which a filtered list
cannot answer.

Three verdicts, and only one of them blocks:

    pass   nothing to say
    warn   worth knowing, choose anyway if you like
    fail   the rule this company set says no

The confirm does four things in one breath — names the buddy on the employee
record, tells both people, plans the recurring connects, and writes it into the
journey — and every one of them is idempotent, because a manager who taps
Confirm twice on a slow connection must not end up with twelve check-ins.
"""

import json
import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .onboarding_common import (
    NON_STAFF_TYPES, P_BUDDY_COUNT, P_BUDDY_DAYS, P_BUDDY_MAIL,
    P_BUDDY_TENURE, flag, initials, number,
)

_logger = logging.getLogger(__name__)

NOMINATION_STATES = [
    ('draft', 'Being chosen'),
    ('chosen', 'Chosen'),
    ('confirmed', 'Confirmed'),
    ('cancelled', 'Cancelled'),
]

#: More than this many joiners at once and being a buddy stops being a favour.
BUDDY_LOAD_WARN = 3


class PbBuddyNomination(models.Model):
    _name = 'pb.buddy.nomination'
    _description = 'Buddy Nomination'
    _order = 'create_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True,
                       string='Nomination')
    case_id = fields.Many2one(
        'pb.journey.case', string='Joining checklist', index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', string='New joiner', required=True, index=True,
        ondelete='cascade')
    manager_user_id = fields.Many2one(
        'res.users', string='Asked of', ondelete='set null')
    candidate_ids = fields.Many2many(
        'hr.employee', 'pb_buddy_nomination_candidate_rel', 'nomination_id',
        'employee_id', string='People considered')
    chosen_id = fields.Many2one(
        'hr.employee', string='Buddy chosen', ondelete='set null')
    state = fields.Selection(
        NOMINATION_STATES, string='Status', default='draft', required=True,
        index=True)
    eligibility_json = fields.Text(
        string='What the check said', readonly=True,
        help='The verdict on each person considered, kept so the choice can '
             'be explained later.')
    decided_at = fields.Datetime(string='Decided on', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.depends('employee_id', 'chosen_id')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Buddy for %(who)s%(chosen)s',
                         who=rec.employee_id.name or _('a new joiner'),
                         chosen=(' — %s' % rec.chosen_id.name)
                         if rec.chosen_id else '')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Buddy nomination')

    # =================================================== is this a good buddy?
    @api.model
    def check_candidate(self, employee, candidate):
        """One verdict on one person, in words a manager can read out loud.

        Never raises: a rule that cannot be evaluated becomes a warning that
        says so, because an exception here would empty the whole dialog.
        """
        reasons, level = [], 'pass'

        def note(bad, text):
            nonlocal level
            reasons.append({'level': bad, 'text': text})
            if bad == 'fail' or (bad == 'warn' and level == 'pass'):
                level = bad

        if not candidate or not candidate.exists():
            return {'level': 'fail',
                    'reasons': [{'level': 'fail',
                                 'text': _('That person is no longer here.')}]}
        if employee and candidate.id == employee.id:
            note('fail', _('Nobody can be their own buddy.'))
        if not candidate.active:
            note('fail', _('They have left the company.'))

        # ---- long enough here to know the ropes ----
        try:
            months = candidate._pb_tenure_months()
            need = number(self.env, P_BUDDY_TENURE, 6)
            if months < need:
                note('fail', _(
                    'Only %(months)s month(s) here — a buddy needs at least '
                    '%(need)s.', months=max(months, 0), need=need))
        except Exception:               # noqa: BLE001
            note('warn', _('We could not work out how long they have been '
                           'here.'))

        # ---- a permanent colleague ----
        try:
            kind = candidate.employee_type or ''
            if kind and kind in NON_STAFF_TYPES:
                note('fail', _('They are not permanent staff (%s).', kind))
            elif not kind:
                note('warn', _('Their employment type is not filled in, so '
                               'this was not checked.'))
        except Exception:               # noqa: BLE001
            note('warn', _('Their employment type could not be read.'))

        # ---- past their own trial period ----
        try:
            trial = candidate.sudo().trial_date_end
            if trial and trial >= date.today():
                note('fail', _('They are still in their own trial period, '
                               'until %s.', trial))
        except Exception:               # noqa: BLE001
            note('warn', _('Their trial period could not be checked.'))

        # ---- near enough to actually meet ----
        try:
            if employee:
                here = employee.work_location_id
                there = candidate.work_location_id
                if here and there and here.id != there.id:
                    note('warn', _('They work at %(theirs)s, not %(ours)s.',
                                   theirs=there.name, ours=here.name))
                elif employee.company_id and candidate.company_id \
                        and employee.company_id.id != candidate.company_id.id:
                    note('warn', _('They are in a different company.'))
        except Exception:               # noqa: BLE001
            pass

        # ---- not already looking after half the floor ----
        try:
            load = candidate.buddy_for_count
            if load >= BUDDY_LOAD_WARN:
                note('warn', _('They are already a buddy to %s other people.',
                               load))
        except Exception:               # noqa: BLE001
            pass

        # ---- a useful extra, not a rule ----
        try:
            if employee and employee.department_id and candidate.department_id \
                    and employee.department_id.id == candidate.department_id.id:
                reasons.append({'level': 'pass',
                                'text': _('Same team as the joiner.')})
        except Exception:               # noqa: BLE001
            pass

        return {'level': level, 'reasons': reasons}

    @api.model
    def candidate_card(self, employee, candidate):
        """One row of the dialog: who they are and what the check said."""
        verdict = self.check_candidate(employee, candidate)
        return {
            'id': candidate.id,
            'name': candidate.name or '',
            'initials': initials(candidate.name),
            'job': candidate.job_title
            or (candidate.job_id.name if candidate.job_id else '') or '',
            'dept': candidate.department_id.name
            if candidate.department_id else '',
            'avatar': '/web/image/hr.employee/%s/avatar_128' % candidate.id,
            'level': verdict['level'],
            'reasons': verdict['reasons'],
        }

    @api.model
    def suggest_candidates(self, employee, term=None, limit=12):
        """Who to offer first: their own team, then the rest.

        The suggestion is a STARTING POINT, never the whole list — the search
        box behind it reaches everybody, because the best buddy is quite often
        the person from the other team who joined the same month last year.
        """
        Emp = self.env['hr.employee']
        if not employee:
            return []
        company = employee.company_id or self.env.company
        base = [('active', '=', True), ('id', '!=', employee.id),
                ('company_id', '=', company.id)]
        if term:
            found = Emp.search(base + [('name', 'ilike', term)],
                               order='name', limit=int(limit))
        else:
            found = Emp.browse()
            if employee.department_id:
                found = Emp.search(
                    base + [('department_id', '=', employee.department_id.id)],
                    order='name', limit=int(limit))
            if len(found) < int(limit):
                found |= Emp.search(base, order='name',
                                    limit=int(limit) - len(found))
        return [self.candidate_card(employee, c) for c in found]

    # ====================================================== making the choice
    @api.model
    def open_for(self, employee_id, case_id=None):
        """The nomination for this joiner — one per journey, reused.

        Idempotent: asking twice returns the same record rather than starting
        a second competition for the same job.
        """
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("Pick the new joiner first."))
        domain = [('employee_id', '=', emp.id),
                  ('state', 'in', ('draft', 'chosen'))]
        if case_id:
            domain.append(('case_id', '=', int(case_id)))
        found = self.search(domain, limit=1)
        if found:
            return found
        case = self.env['pb.journey.case'].browse(int(case_id)).exists() \
            if case_id else self.env['pb.journey.case'].search(
                [('employee_id', '=', emp.id), ('case_type', '=', 'onboarding'),
                 ('state', 'in', ('draft', 'active', 'on_hold'))], limit=1)
        return self.create({
            'employee_id': emp.id,
            'case_id': case.id if case else False,
            'manager_user_id': emp.parent_id.user_id.id
            if (emp.parent_id and emp.parent_id.user_id) else False,
            'company_id': (emp.company_id or self.env.company).id,
        })

    def choose(self, candidate_id):
        """Name the buddy and do everything that follows from it."""
        self.ensure_one()
        candidate = self.env['hr.employee'].browse(
            int(candidate_id)).exists()
        if not candidate:
            raise UserError(_("That person could not be found."))
        verdict = self.check_candidate(self.employee_id, candidate)
        if verdict['level'] == 'fail':
            raise UserError(_(
                "%(who)s cannot be a buddy: %(why)s",
                who=candidate.name,
                why='; '.join(r['text'] for r in verdict['reasons']
                              if r['level'] == 'fail')))
        self.sudo().write({
            'chosen_id': candidate.id,
            'state': 'confirmed',
            'decided_at': fields.Datetime.now(),
            'candidate_ids': [(4, candidate.id)],
            'eligibility_json': json.dumps(
                {str(candidate.id): verdict}, default=str),
        })
        self.employee_id.sudo().write({'buddy_id': candidate.id})
        connects = self._schedule_connects(candidate)
        mails = self._tell_them(candidate)
        if self.case_id:
            self.case_id.message_post(body=_(
                "%(buddy)s is now the buddy for %(who)s. %(count)s connect(s) "
                "are in the diary.",
                buddy=candidate.name or '', who=self.employee_id.name or '',
                count=connects))
        self._tick_step()
        return {'connects': connects, 'mails': mails,
                'buddy': candidate.name or ''}

    def _tick_step(self):
        """Finish the "nominate a buddy" step, if the journey has one open."""
        self.ensure_one()
        if not self.case_id:
            return False
        try:
            step = self.case_id.task_ids.filtered(
                lambda t: t.automation_key == 'buddy_invite'
                and t.state in ('pending', 'in_progress', 'blocked'))[:1]
            if step:
                step.sudo().action_done(payload={'_buddy': {
                    'label': 'Buddy', 'value': self.chosen_id.name or ''}})
                return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_onboarding: could not tick the buddy step '
                              'for nomination %s', self.id)
        return False

    def _schedule_connects(self, buddy):
        """The recurring catch-ups, every fortnight for three months.

        Idempotent on (case, kind, date): a second confirm finds them already
        in the diary and adds nothing.
        """
        self.ensure_one()
        Checkin = self.env['pb.employee.checkin'].sudo()
        emp = self.employee_id
        every = number(self.env, P_BUDDY_DAYS, 14) or 14
        how_many = number(self.env, P_BUDDY_COUNT, 6)
        start = (self.case_id.anchor_date if self.case_id else False) \
            or emp._pb_join_date() or fields.Date.today()
        owner = buddy.user_id or emp.hrbp_user_id or self.env.user
        made = 0
        for n in range(1, max(how_many, 0) + 1):
            when = start + timedelta(days=every * n)
            if Checkin.search_count([
                    ('employee_id', '=', emp.id), ('kind', '=', 'buddy'),
                    ('scheduled_date', '=', when)]):
                continue
            Checkin.create({
                'employee_id': emp.id,
                'case_id': self.case_id.id if self.case_id else False,
                'kind': 'buddy',
                'owner_user_id': owner.id,
                'scheduled_date': when,
                'company_id': (emp.company_id or self.env.company).id,
            })
            made += 1
        return made

    def _tell_them(self, buddy):
        """Two emails, both behind one switch, both counted honestly."""
        self.ensure_one()
        if not flag(self.env, P_BUDDY_MAIL):
            _logger.info('pb_onboarding: buddy emails are switched off — '
                         'nothing sent for nomination %s', self.id)
            return 0
        sent = 0
        for xmlid, to in (
                ('pb_onboarding.mail_template_buddy_to_buddy',
                 (buddy.work_email or '').strip()),
                ('pb_onboarding.mail_template_buddy_to_joiner',
                 (self.employee_id.work_email or '').strip())):
            if not to:
                continue
            try:
                template = self.env.ref(xmlid, raise_if_not_found=False)
                if not template:
                    continue
                template.sudo().send_mail(
                    self.id, force_send=False,
                    email_values={'email_to': to, 'auto_delete': False})
                sent += 1
            except Exception:           # noqa: BLE001
                _logger.exception('pb_onboarding: buddy mail %s', xmlid)
        return sent

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True


class HrEmployeeBuddy(models.Model):
    """The temporary handover lives with the buddy logic, not with the fields."""
    _inherit = 'hr.employee'

    def set_temp_buddy(self, temp_employee_id, date_from=None, date_to=None):
        """Hand the buddy job over for a while, and move the connects with it.

        THE CONNECTS MOVE, or the handover is a note nobody acts on: every
        planned buddy catch-up inside the window is re-pointed at the stand-in,
        and the ones outside it are left exactly where they were.
        """
        self.ensure_one()
        Emp = self.env['hr.employee']
        temp = Emp.browse(int(temp_employee_id)).exists() \
            if temp_employee_id else Emp.browse()
        if temp_employee_id and not temp:
            raise UserError(_("That person could not be found."))
        if temp and temp.id == self.id:
            raise UserError(_("Nobody can stand in for themselves."))
        start = fields.Date.to_date(date_from) if date_from else \
            fields.Date.today()
        end = fields.Date.to_date(date_to) if date_to else False
        if end and start and end < start:
            raise UserError(_("The last day cannot be before the first day."))
        self.sudo().write({
            'buddy_temp_id': temp.id or False,
            'buddy_temp_from': start if temp else False,
            'buddy_temp_to': end if temp else False,
        })
        moved = self._move_connects(temp, start, end)
        self._tell_hr_about_cover(temp, start, end, moved)
        return {'moved': moved, 'temp': temp.name or ''}

    def _move_connects(self, temp, start, end):
        self.ensure_one()
        Checkin = self.env['pb.employee.checkin'].sudo()
        domain = [('employee_id', '=', self.id), ('kind', '=', 'buddy'),
                  ('state', '=', 'scheduled')]
        if start:
            domain.append(('scheduled_date', '>=', start))
        if end:
            domain.append(('scheduled_date', '<=', end))
        rows = Checkin.search(domain)
        owner = (temp.user_id if temp else False) \
            or (self.buddy_id.user_id if self.buddy_id else False)
        if not owner:
            return 0
        rows.write({'owner_user_id': owner.id})
        return len(rows)

    def _tell_hr_about_cover(self, temp, start, end, moved):
        """HR is told, because a cover nobody knows about is not a cover."""
        self.ensure_one()
        if not flag(self.env, P_BUDDY_MAIL):
            _logger.info('pb_onboarding: buddy emails are off — HR was not '
                         'told about the stand-in for %s', self.id)
            return False
        try:
            to = self.hrbp_user_id.email if self.hrbp_user_id else False
            if not to:
                users = self.env['pb.journey.case']._users_in_group(
                    'pb_lifecycle.group_lifecycle_manager',
                    self.company_id, limit=0)
                to = ','.join(u.email for u in users if u.email)
            if not to:
                _logger.info('pb_onboarding: nobody in HR has an email — no '
                             'stand-in notice for %s', self.id)
                return False
            body = _(
                "<p>%(temp)s is covering as buddy for %(who)s%(window)s.</p>"
                "<p>%(moved)s planned catch-up(s) moved across.</p>",
                temp=temp.name if temp else _('Nobody'),
                who=self.name or '',
                window=(' from %s' % start) + ((' to %s' % end) if end else ''),
                moved=moved)
            self.env['mail.mail'].sudo().create({
                'subject': _("Buddy cover for %s", self.name or ''),
                'email_to': to,
                'body_html': body,
                'auto_delete': False,
            })
            return True
        except Exception:               # noqa: BLE001
            _logger.exception('pb_onboarding: stand-in notice for %s', self.id)
            return False
