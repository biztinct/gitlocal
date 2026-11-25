# -*- coding: utf-8 -*-
"""NEWHIRE P2 — the welcome legs of an approved studio hire (handover §2.2).

The person and the contract are the CORE (P1, `create_ext.py`): a failure
there rolls the whole approval back. Everything here is a WELCOME LEG and
runs AFTER the core, each in its own savepoint, in this fixed order:

    clock → week → own_fields → details → papers → asks → login → case →
    buddy → equipment → letter → invite

(the late and overtime rule is not a leg: it rides on the ONE employee
create through the P1 create hook, `pb_attendance_category`.)

A leg that fails never undoes the hire. It posts ONE plain sentence on the
employee's chatter — what could not be done, why, and where to do it by hand —
and comes back in `result['legs'] = [{key, ok, message}]` so the done card
(fast lane) can show it. This is the contract Hiring's "Confirm they joined"
uses (FACTS_ONBOARD §K1.4).

Every leg calls the product's OWN code (ledger rule 5):

    clock       the model's own unique constraint judges (`pb_clock`)
    week        one `pb.shift.pattern.member` row, the shape both writers
                (`assign_week`, `save_pattern`) create; the model's own
                constraint judges overlaps
    own_fields  `pb.form.studio.write_values` (Form builder's only write path)
    login       `pb.zoho.pipeline._auto_create_login` (email, as Hiring) or
                `pb.access.create_worker_logins` (employee number)
    case        `pb.zoho.pipeline._open_case` + `_after_onboard`, exactly as
                `pb_hiring/models/offer_closure.py` `_ensure_case`
    buddy       `pb.buddy.nomination.open_for(...).choose(...)`, exactly as
                Hiring's `_hand_over_buddy` (what `pb.onboarding.buddy_choose`
                wraps, without its lifecycle-manager gate)
    equipment   `pb.asset.request` rows in the state and shape
                `_raise_asset_requests` creates the laptop one
    letter      `pb.contracts.contract_document_save`

sudo only inside a leg and only for the documented role gaps (NH6). Nothing
here ever writes, posts, returns or logs a password or a sign-up link.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

#: The fixed order (handover §2.2). `case` after `login` so the day-one
#: "sign-in details" step finds a login; buddy and equipment need the case.
LEG_ORDER = ('clock', 'week', 'own_fields',
             # P3a (docs_legs.py): what HR typed, the papers HR attached and
             # what the new person will be asked — before the sign-in
             'details', 'papers', 'asks',
             'login', 'case', 'buddy', 'equipment', 'letter',
             # P3b (invite.py): the welcome message — last, it needs the
             # sign-in and the asks (not the checklist)
             'invite')

#: Tests set this to see a leg's programming error instead of a failed leg.
RAISE_CTX = 'pb_nh_legs_raise'

#: "Not needed" for this one person: the joining checklist must not fill in
#: the trial end the person's HR switched off (read by `pb.journey.case`).
NO_TRIAL_CTX = 'pb_nh_no_trial_employee_id'

#: P3a: the studio's contract letter may print the pay of this contract id.
LETTER_CTX = 'pb_nh_letter_contract_id'


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class LegFailed(Exception):
    """A leg could not do its work, for a reason a person can read."""


class PbNewHireLegs(models.AbstractModel):
    _name = 'pb.new.hire.legs'
    _description = 'New hire studio: the welcome after approval'

    # ================================================================ runner
    @api.model
    def run(self, employee, contract, values):
        """Run every leg the values ask for, in order. Never raises (except
        under the test flag). → `(legs, summary)`."""
        employee = employee.sudo()
        state = {'case': self.env['pb.journey.case'], 'contract': contract}
        legs = []
        for key in LEG_ORDER:
            leg = getattr(self, '_leg_%s' % key)
            try:
                with self.env.cr.savepoint():
                    message = leg(employee, values, state)
            except LegFailed as exc:
                legs.append(self._failed(employee, key, str(exc)))
                continue
            except (UserError, ValidationError) as exc:
                if self.env.context.get(RAISE_CTX):
                    raise
                legs.append(self._failed(employee, key, self._reason(exc)))
                continue
            except Exception as exc:            # noqa: BLE001 — a leg never undoes the hire
                if self.env.context.get(RAISE_CTX):
                    raise
                _logger.exception('new hire: welcome leg %s failed for employee %s',
                                  key, employee.id)
                legs.append(self._failed(employee, key, self._reason(exc)))
                continue
            if message:
                legs.append({'key': key, 'ok': True, 'message': message})
        done = [leg['message'] for leg in legs if leg['ok']]
        summary = _("Ready: %s.", ', '.join(done)) if done else ''
        return legs, summary

    @api.model
    def _reason(self, exc):
        text = (exc.args[0] if getattr(exc, 'args', None) else '') or ''
        text = str(text).strip()
        if not text or not isinstance(exc, (UserError, ValidationError, LegFailed)):
            return _("Something went wrong while doing it.")
        return text if text.endswith(('.', '!', '?')) else text + '.'

    @api.model
    def _failed(self, employee, key, reason):
        sentences = {
            'clock': _("The clock number could not be set: %s Type another one on the "
                       "employee record."),
            'week': _("The working week could not be set: %s Set it from Workforce."),
            'own_fields': _("Your own fields could not be saved: %s Fill them in on the "
                            "employee record."),
            'details': _("The details you typed could not be saved: %s Type them on the "
                         "employee record."),
            'papers': _("The papers could not be filed: %s Add them from the employee's side "
                        "panel, Documents."),
            'asks': _("What to ask the new person for could not be noted: %s Ask them "
                      "yourself for now."),
            'login': _("The sign-in could not be made: %s Make it from Access."),
            'case': _("The joining checklist could not be started: %s Start it from New "
                      "joiners."),
            'buddy': _("The buddy could not be set: %s The manager is asked to choose one "
                       "on the joining checklist."),
            'equipment': _("The equipment requests could not be raised: %s Raise them "
                           "from Equipment."),
            'letter': _("The contract letter could not be prepared: %s Prepare it from the "
                        "contract panel."),
        }
        message = sentences[key] % reason
        try:
            employee.message_post(body=message)
        except Exception:                       # noqa: BLE001 — the note is a courtesy
            _logger.warning('new hire: could not note a failed leg on %s', employee.id,
                            exc_info=True)
        return {'key': key, 'ok': False, 'message': message}

    # ================================================================ helpers
    @api.model
    def _first(self, employee):
        return (employee.name or '').split(' ')[0] or employee.name or ''

    @api.model
    def _day(self, values):
        return fields.Date.to_date(values.get('date_start')) if values.get('date_start') \
            else fields.Date.context_today(self)

    # ================================================================ clock
    @api.model
    def _leg_clock(self, employee, values, state):
        code = str(values.get('pb_clock_code') or '').strip()
        if not code or 'pb_clock_code' not in employee._fields:
            return False
        clash = self.env['hr.employee'].sudo().with_context(active_test=False).search([
            ('id', '!=', employee.id), ('company_id', '=', employee.company_id.id),
            ('pb_clock_code', '=', code)], limit=1)
        if clash:
            raise LegFailed(_("Clock number %(code)s was taken by %(name)s meanwhile.",
                              code=code, name=clash.name or ''))
        # sudo: the field is HR-only (NH6); the model's constraint is the judge
        employee.write({'pb_clock_code': code})
        return _("clock number %s", code)

    # ================================================================ week
    @api.model
    def _leg_week(self, employee, values, state):
        week_id = _int(values.get('week_id'))
        if not week_id or 'pb.shift.pattern' not in self.env:
            return False
        names = values.get('pb_nh_names') or {}
        week = self.env['pb.shift.pattern'].sudo().browse(week_id).exists()
        if not week or not week.active or week.company_id != employee.company_id:
            raise LegFailed(_("The working week %s was removed before approval.",
                              names.get('week') or ''))
        team = week.team_ids.sorted(lambda t: (t.sequence, t.id))[:1]
        if not team:
            raise LegFailed(_("The working week %s has no team to join.", week.name or ''))
        day = self._day(values)
        Member = self.env['pb.shift.pattern.member'].sudo()
        if Member.search_count([('pattern_id', '=', week.id), ('employee_id', '=', employee.id),
                                '|', ('date_to', '=', False), ('date_to', '>=', day)]):
            return _("working week %s", week.name or '')
        # sudo behind the HR gate: only an attendance manager may write member
        # rows (NH6); the row is the one both product writers create.
        Member.create({'pattern_id': week.id, 'team_id': team.id, 'employee_id': employee.id,
                       'date_from': day, 'date_to': False})
        return _("working week %s", week.name or '')

    # ================================================================ own fields
    @api.model
    def _leg_own_fields(self, employee, values, state):
        own = values.get('own_fields') or {}
        if not isinstance(own, dict) or not own or 'pb.form.studio' not in self.env:
            return False
        # The caller's own rights (write_values never elevates); the approver is HR.
        answer = self.env['pb.form.studio'].write_values('hr.employee', employee.id, dict(own))
        if not answer.get('ok'):
            labels = (values.get('pb_nh_names') or {}).get('own') or {}
            errors = answer.get('errors') or {}
            bits = ['%s: %s' % ((labels.get(name) or {}).get('label') or name, text)
                    for name, text in errors.items()]
            raise LegFailed('; '.join(bits) or answer.get('error') or '')
        n = len(answer.get('values') or {})
        return _("1 of your own fields") if n == 1 else _("%s of your own fields", n)

    # ================================================================ login
    @api.model
    def _leg_login(self, employee, values, state):
        mode = values.get('login_mode') or 'none'
        if mode == 'email':
            return self._login_email(employee)
        if mode == 'code':
            return self._login_code(employee)
        return False

    @api.model
    def _login_email(self, employee):
        if 'pb.zoho.pipeline' not in self.env or employee.pb_portal_user_id:
            return _("sign-in") if employee.pb_portal_user_id else False
        email = (employee.work_email or '').strip()
        private = (employee.private_email or '').strip()
        if not email and not private:
            raise LegFailed(_("there is no email address to sign in with."))
        param = self.env['ir.config_parameter'].sudo().get_param(
            'pb_zoho_bridge.auto_create_logins', '1')
        if str(param).strip() not in ('1', 'true', 'True', 'yes'):
            raise LegFailed(_("email sign-ins are switched off here."))
        if not email:
            # P3b §2.1: only a personal email before day one (the usual case)
            return self._login_private(employee, private)
        summary = {'logins': 0, 'created': 0, 'updated': 0, 'ignored': 0,
                   'review': 0, 'onboarding': 0, 'offboarding': 0}
        self.env['pb.zoho.pipeline'].sudo()._auto_create_login(
            employee, employee.company_id, summary)
        employee.invalidate_recordset(['pb_portal_user_id', 'user_id'])
        if not employee.pb_portal_user_id:
            raise LegFailed(_("no sign-in could be made for %s.", email))
        return _("sign-in for %s", email)

    @api.model
    def _login_private(self, employee, email):
        """The same employee-tier login `_auto_create_login` makes, with the
        PERSONAL email as login and address — its own building blocks (the
        user values, `no_reset_password`, `_link_employee_login`). An
        existing sign-in with that address is used only when it is an
        employee-tier login nobody else's employee holds."""
        Pipeline = self.env['pb.zoho.pipeline'].sudo()
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        company = employee.company_id or self.env.company
        existing = Users.search([('login', '=ilike', email)], limit=1)
        if existing:
            taken = self.env['hr.employee'].sudo().with_context(active_test=False).search_count([
                ('id', '!=', employee.id), '|', ('user_id', '=', existing.id),
                ('pb_portal_user_id', '=', existing.id)], limit=1)
            if not existing.share or taken:
                raise LegFailed(_("A sign-in with %s already exists for someone else. Create the "
                                  "sign-in from Access.", email))
            user = existing
        else:
            portal = self.env.ref('base.group_portal', raise_if_not_found=False)
            if not portal:
                raise LegFailed(_("employee sign-ins are not set up here."))
            user = self.env['res.users'].sudo().with_context(
                no_reset_password=True, mail_create_nosubscribe=True).create({
                    'name': employee.name,
                    'login': email,
                    'email': email,
                    'company_id': company.id,
                    'company_ids': [(6, 0, [company.id])],
                    'group_ids': [(6, 0, [portal.id])],
                })
        employee.write({'pb_portal_user_id': user.id})
        Pipeline._link_employee_login(employee, user)
        employee.invalidate_recordset(['pb_portal_user_id', 'user_id'])
        return _("sign-in for %s", email)

    @api.model
    def _login_code(self, employee):
        Access = self.env['pb.access']
        if not Access.can_manage():
            raise LegFailed(_("only someone who manages access can make a sign-in with an "
                              "employee number. Make it in Access, Logins for workers, which "
                              "prints the slip with the first password."))
        # The approver's own rights. The first password comes back once and
        # is dropped here: never stored, posted, returned or logged.
        answer = Access.create_worker_logins([employee.id])
        created = [row for row in answer.get('created') or []
                   if row.get('employee_id') == employee.id]
        if not created:
            why = next((row.get('why') for row in answer.get('skipped') or []), '') \
                or _("it could not be made.")
            raise LegFailed(why)
        code = created[0].get('login') or ''
        employee.invalidate_recordset(['user_id'])
        if employee.user_id and 'pb_portal_user_id' in employee._fields:
            employee.write({'pb_portal_user_id': employee.user_id.id})
        return _("sign-in with employee number %s (set the first password in Access)", code)

    # ================================================================ case
    @api.model
    def _leg_case(self, employee, values, state):
        if not values.get('open_case', True) or 'pb.zoho.pipeline' not in self.env:
            return False
        company = employee.company_id or self.env.company
        template = self.env['pb.journey.template'].sudo().pick_for(
            'onboarding', employee.country_id.id or False, company.id)
        if not template:
            return False                        # "No joining checklist is set up."
        anchor = self._day(values)
        pipeline = self.env['pb.zoho.pipeline'].sudo()
        if not values.get('trial_date_end'):
            pipeline = pipeline.with_context(**{NO_TRIAL_CTX: employee.id})
        case, opened = pipeline._open_case(employee, 'onboarding', anchor, company)
        if not case:
            raise LegFailed(_("no checklist was opened."))
        if opened:
            pipeline._after_onboard(case, {
                'name': employee.name or '',
                'date_of_joining': str(anchor or ''),
                'source': 'pb_new_hire',
                '_raw': {},
            })
        state['case'] = case
        n = len(case.task_ids)
        return _("joining checklist (1 step)") if n == 1 else \
            _("joining checklist (%s steps)", n)

    # ================================================================ buddy
    @api.model
    def _leg_buddy(self, employee, values, state):
        buddy_id = _int(values.get('buddy_id'))
        case = state.get('case')
        if not buddy_id or not case or 'pb.buddy.nomination' not in self.env:
            return False
        buddy = self.env['hr.employee'].sudo().browse(buddy_id).exists()
        if not buddy or not buddy.active:
            raise LegFailed(_("%s left before approval.",
                              (values.get('pb_nh_names') or {}).get('buddy') or ''))
        nomination = self.env['pb.buddy.nomination'].sudo().open_for(employee.id, case.id)
        nomination.choose(buddy.id)
        return _("buddy %s", buddy.name or '')

    # ================================================================ equipment
    @api.model
    def _leg_equipment(self, employee, values, state):
        chosen = values.get('equipment')
        case = state.get('case')
        if chosen is None or not case or 'pb.asset.request' not in self.env:
            return False                        # not chosen: the checklist's own default
        Category = self.env['pb.asset.category'].sudo()
        cats = Category.browse([_int(c) for c in chosen if _int(c)]).exists() \
            .filtered(lambda c: c.active and (not c.company_id or c.company_id == employee.company_id))
        laptop = self.env.ref('pb_assets.cat_laptop', raise_if_not_found=False)
        Request = self.env['pb.asset.request'].sudo()
        task = case.task_ids.filtered(lambda t: t.automation_key == 'asset_laptop')[:1]
        name = employee.name or ''
        if laptop and laptop not in cats:
            for req in Request.search([('employee_id', '=', employee.id),
                                       ('category_id', '=', laptop.id),
                                       ('journey_task_id', 'in', case.task_ids.ids),
                                       ('state', '=', 'draft')]):
                req.action_cancel()
            if task and not (cats - laptop) and task.state not in ('done', 'skipped'):
                task.action_skip(reason=_("Not needed for %s.", name))
        have = Request.search([('employee_id', '=', employee.id),
                               ('state', 'not in', ('cancelled', 'refused'))]).mapped('category_id')
        day = self._day(values)
        made = 0
        for cat in cats - have:
            Request.create({
                'employee_id': employee.id,
                'category_id': cat.id,
                'needed_by': day,
                'justification': _("%(what)s for %(name)s, who joins on %(day)s.",
                                   what=cat.name or '', name=name, day=day),
                'journey_task_id': task.id if task and task.state not in ('done', 'skipped') else False,
                'company_id': (employee.company_id or self.env.company).id,
            })
            made += 1
        total = len(Request.search([('employee_id', '=', employee.id),
                                    ('state', 'not in', ('cancelled', 'refused'))]))
        if made:
            case.message_post(body=_("%(count)s equipment request(s) raised for this joiner.",
                                     count=made))
        if not total:
            return False
        return _("1 equipment request") if total == 1 else _("%s equipment requests", total)

    # ================================================================ letter
    @api.model
    def _leg_letter(self, employee, values, state):
        contract = state.get('contract')
        if not values.get('letter') or not contract or 'pb.contracts' not in self.env:
            return False
        # P3a (architect decision): whoever approved the hire has just
        # approved this very wage, so the letter that prints it is made for
        # them. `sudo` cannot do that here — the pay gate reads `has_group`
        # and then reads the wage as the real user (NH23, NH32) — so the
        # gate is opened for THIS contract only, by a context key that
        # `pb.contracts._cd_unmask_wage` reads (docs_legs.py).
        answer = self.env['pb.contracts'].with_context(**{LETTER_CTX: contract.id}) \
            .contract_document_save(contract.id)
        if not answer or not answer.get('ok'):
            raise LegFailed((answer or {}).get('msg') or _("the letter could not be made."))
        return _("the contract letter")


class PbJourneyCaseNewHire(models.Model):
    """A trial period HR switched off for this one person stays off when the
    joining checklist opens (`pb_probation` fills an EMPTY trial end)."""
    _inherit = 'pb.journey.case'

    def _set_trial_end(self):
        no_trial = self.env.context.get(NO_TRIAL_CTX)
        if no_trial and self.employee_id.id == no_trial:
            return False
        return super()._set_trial_end()
