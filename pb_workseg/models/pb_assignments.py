# -*- coding: utf-8 -*-
"""`pb.assignments` — the only server surface the "Where they work" screen talks to.

The shape is the one `pb_assets`, `pb.decision.room` and `pb.group.room`
established: an `AbstractModel` facade, `@api.model` reads, every independent
figure inside `_safe()` so one failure answers a zero instead of taking the
screen down, a cap on anything a caller controls, and a SERVER-SIDE gate that
is the boundary.

A reader with no permission gets an EMPTY, EXPLAINED screen rather than an
access dialog. A dialog is a dead end, and this screen's whole job is to
explain what a split month is to somebody who has not met one.

THE PREVIEW RUNS FOR REAL AND IS THROWN AWAY
--------------------------------------------
"Twenty days in Vietnam, ten in Singapore" is a claim about money, and the
only thing that can settle it is the payroll engine. So the preview creates
the segment, creates the payslips, computes them through the real scheme, reads
the numbers — and then rolls the whole thing back inside a savepoint. Nothing
survives it: the check afterwards counts the rows and the test asserts zero.
"""

import logging
import time
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .pb_work_segment import POLICY_EACH, POLICY_HOME, POLICY_LABELS

_logger = logging.getLogger(__name__)

WRITE_GROUPS = (
    'pb_workseg.group_workseg_manager',
    'pb_group.group_group_admin',
)
READ_GROUPS = (
    'pb_workseg.group_workseg_manager',
    'pb_group.group_group_admin',
    'hr.group_hr_user',
    'pb_hr_payroll_formula.group_formula_user',
)

MAX_ROWS = 200
MAX_PEOPLE = 60


class _PreviewDone(Exception):
    """Carries the preview out of the savepoint that is about to be undone."""

    def __init__(self, payload):
        super().__init__('preview')
        self.payload = payload


class PbAssignments(models.AbstractModel):
    _name = 'pb.assignments'
    # GROUP P7 — every read on this screen goes through `who sees what`.
    # A reader with no visibility row is narrowed by nothing at all.
    _inherit = ['pb.group.scoped']
    _description = 'Where they work'

    # ================================================================= gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('Assignments figure failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        if user._is_admin():
            return True
        return any(self._safe(lambda n=n: user.has_group(n), default=False)
                   for n in READ_GROUPS)

    @api.model
    def _can_write(self):
        user = self.env.user
        if user._is_admin():
            return True
        return any(self._safe(lambda n=n: user.has_group(n), default=False)
                   for n in WRITE_GROUPS)

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at where people work, but changing it is for a "
                "payroll manager. Ask one of them to make the change."))
        return True

    # ============================================================== the read
    @api.model
    def _month_bounds(self, month):
        day = fields.Date.to_date(month) if month else \
            fields.Date.context_today(self)
        first = day.replace(day=1)
        last = (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        return first, last

    @api.model
    def get_screen(self, person_id=None, employee_id=None, month=None):
        started = time.time()
        blank = {
            'allowed': False, 'can_edit': False, 'person': None,
            'month': '', 'days': [], 'segments': [], 'policies': self._policies(),
            'group': None, 'companies': [], 'divisions': [], 'schemes': [],
            'transfers': [], 'suggestions': [], 'ms': 0,
        }
        if not self._can_read():
            return blank
        Person = self.env['pb.person'].sudo()
        person = Person.browse(int(person_id or 0)).exists()
        if not person and employee_id:
            employee = self.env['hr.employee'].sudo().browse(
                int(employee_id)).exists()
            if employee:
                person = self.env['pb.person'].for_employee(employee)
        if not person:
            person = self._first_person()
        first, last = self._month_bounds(month)
        payload = dict(blank)
        payload.update({
            'allowed': True,
            'can_edit': self._can_write(),
            'month': fields.Date.to_string(first),
            'month_label': first.strftime('%B %Y'),
            'group': self._safe(lambda: self._group(), default=None),
            'policies': self._policies(),
            'person': self._safe(lambda: self._person(person), default=None),
            'days': self._safe(lambda: self._days(person, first, last),
                               default=[]),
            'segments': self._safe(
                lambda: self._segments(person, first, last), default=[]),
            'transfers': self._safe(
                lambda: self._transfers(person, first, last), default=[]),
            'companies': self._safe(lambda: self._companies(), default=[]),
            'divisions': self._safe(lambda: self._divisions(), default=[]),
            'schemes': self._safe(lambda: self._schemes(), default=[]),
            'history': self._safe(lambda: self._history(person), default=[]),
        })
        payload['ms'] = int((time.time() - started) * 1000)
        return payload

    @api.model
    def _first_person(self):
        """Somebody to show when nobody was asked for.

        A person who already has a segment first — that is the interesting
        one — then the reader's own employment, then anybody.
        """
        Segment = self.env['pb.work.segment'].sudo()
        seg = Segment.search([('state', '!=', 'cancelled')],
                             order='date_from desc', limit=1)
        if seg.person_id:
            return seg.person_id
        mine = self.env.user.employee_id
        if mine:
            return self.env['pb.person'].for_employee(mine)
        employee = self.env['hr.employee'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)], limit=1)
        if employee:
            return self.env['pb.person'].for_employee(employee)
        return self.env['pb.person'].browse()

    @api.model
    def _policies(self):
        return [
            {'key': POLICY_EACH, 'label': _(POLICY_LABELS[POLICY_EACH]),
             'help': _("The home entity's payslip is reduced to the days that "
                       "stayed at home, and the host entity runs its own "
                       "payslip for its own days, in its own money.")},
            {'key': POLICY_HOME, 'label': _(POLICY_LABELS[POLICY_HOME]),
             'help': _("The home entity pays the whole month and the host "
                       "entity is charged its share. One payslip, one internal "
                       "cost line.")},
        ]

    @api.model
    def _group(self):
        if 'pb.group' not in self.env:
            return None
        group = self.env['pb.group'].sudo().search([], order='id', limit=1)
        if not group:
            return None
        policy = getattr(group, 'split_pay_policy', POLICY_EACH) or POLICY_EACH
        return {
            'id': group.id,
            'name': group.name or '',
            'policy': policy,
            'policy_label': _(POLICY_LABELS.get(policy,
                                                POLICY_LABELS[POLICY_EACH])),
            'currency': group.presentation_currency_id.name or '',
            'company_ids': group.company_ids.ids,
        }

    @api.model
    def _basic_pay(self, employees):
        """The standing monthly pay behind each employment, in ONE query.

        This is what the rough estimate under the strip is multiplied by, and
        it is deliberately the OPEN CONTRACT'S WAGE and nothing else: a
        standing monthly amount is exactly the part of a payslip that a
        fraction of a month may scale (ledger GR35). Everything else on a
        payslip — a pay-data file, overtime, a one-off — is already this
        month's figure and is left alone, which is precisely why the strip
        calls its answer an estimate and the preview behind it is the thing
        that settles the money.

        Sent down with the screen rather than fetched on the drag: a figure
        that has to be true WHILE the mouse is down cannot afford a round
        trip per day.
        """
        out = {}
        if not employees or 'hr.contract' not in self.env:
            return out
        rows = self.env['hr.contract'].sudo().search_read(
            [('employee_id', 'in', employees.ids), ('state', '=', 'open')],
            ['employee_id', 'wage'], order='wage desc')
        for row in rows:
            employee_id = (row['employee_id'] or [0])[0]
            if employee_id and employee_id not in out:
                out[employee_id] = row['wage'] or 0.0
        return out

    @api.model
    def _person(self, person):
        if not person:
            return None
        employments = []
        people = person.employee_ids[:MAX_ROWS]
        wages = self._safe(lambda: self._basic_pay(people), default={})
        for employee in people:
            currency = employee.company_id.currency_id
            wage = wages.get(employee.id, 0.0)
            employments.append({
                'id': employee.id,
                'name': employee.name or '',
                'company_id': employee.company_id.id,
                'company': employee.company_id.name or '',
                'currency': currency.name or '',
                # The three things the browser needs to write this money the
                # way this currency writes it, without inventing a locale of
                # its own: the symbol, which side it goes, and the decimals.
                'symbol': currency.symbol or '',
                'symbol_before': (currency.position or 'before') == 'before',
                'decimals': currency.decimal_places,
                'wage': wage,
                'wage_label': self._money(wage, currency),
                'home': employee.id == person.home_employee_id.id,
                'active': bool(employee.active),
            })
        return {
            'id': person.id,
            'name': person.name or '',
            'national_id': person.national_id or '',
            'email': person.email or '',
            'home_employee_id': person.home_employee_id.id,
            'employments': employments,
        }

    @api.model
    def _days(self, person, first, last):
        """The month as a strip of days, with the working ones marked."""
        employee = person.home_employee_id or person.employee_ids[:1]
        working = set()
        try:
            calendar = employee.resource_calendar_id if employee else None
            if calendar:
                working = {int(a.dayofweek)
                           for a in calendar.attendance_ids if a.dayofweek}
                working |= {0} if any(int(a.dayofweek) == 0
                                      for a in calendar.attendance_ids) else set()
        except Exception:       # noqa: BLE001
            working = set()
        if not working:
            working = {0, 1, 2, 3, 4}
        out = []
        day = first
        while day <= last:
            out.append({
                'date': fields.Date.to_string(day),
                'day': day.day,
                'dow': day.weekday(),
                'working': day.weekday() in working,
            })
            day += timedelta(days=1)
        return out

    @api.model
    def _segments(self, person, first, last):
        if not person:
            return []
        rows = self.env['pb.work.segment'].sudo().search([
            ('person_id', '=', person.id),
            ('date_from', '<=', last), ('date_to', '>=', first),
            ('state', '!=', 'cancelled'),
        ], limit=MAX_ROWS)
        return [self._segment_row(row) for row in rows]

    @api.model
    def _segment_row(self, row):
        return {
            'id': row.id,
            'kind': row.kind,
            'kind_label': dict(row._fields['kind'].selection).get(row.kind, ''),
            'state': row.state,
            'derived': bool(row.derived),
            'home_employee_id': row.home_employee_id.id,
            'home_company': row.home_company_id.name or '',
            'host_company_id': row.host_company_id.id,
            'host_company': row.host_company_id.name or '',
            'host_employee_id': row.host_employee_id.id,
            'host_employee': row.host_employee_id.name or '',
            'division_id': row.division_id.id,
            'division': row.division_id.name or '',
            'config_id': row.config_id.id,
            'config': row.config_id.name or '',
            'date_from': fields.Date.to_string(row.date_from),
            'date_to': fields.Date.to_string(row.date_to),
            'days': row.days,
            'month_days': row.month_days,
            'share': row.share,
            'fte': row.fte,
            'pay_policy': row.pay_policy,
            'effective_policy': row.effective_policy,
            'policy_label': _(POLICY_LABELS.get(row.effective_policy,
                                                POLICY_LABELS[POLICY_EACH])),
            'note': row.note or '',
        }

    @api.model
    def _transfers(self, person, first, last):
        if not person or 'pb.cost.transfer' not in self.env:
            return []
        rows = self.env['pb.cost.transfer'].sudo().search([
            ('person_id', '=', person.id),
            ('date_from', '<=', last), ('date_to', '>=', first),
        ], limit=MAX_ROWS)
        return [{
            'id': row.id,
            'amount': row.amount,
            # FORMATTED HERE, not in the template. A number formatted in the
            # browser reads in the browser's locale, and a payroll figure has
            # to read in the CURRENCY's — and a template expression is
            # compiled against the component, so `Number(...)` there is a
            # property of ours that does not exist.
            'amount_label': self._money(row.amount, row.currency_id),
            'currency': row.currency_id.name or '',
            'symbol': row.currency_id.symbol or '',
            'from': row.from_company_id.name or '',
            'to': row.to_company_id.name or '',
            'share': row.share,
            'date_from': fields.Date.to_string(row.date_from),
        } for row in rows]

    @api.model
    def _companies(self):
        """The entities a person's days can be moved to.

        The group's members when there is a group, because a host outside the
        group has no shared currency policy, no shared divisions and nobody to
        charge. With no group at all the reader's own companies stand in, and
        the screen says what that means.
        """
        Company = self.env['res.company'].sudo()
        group = self.env['pb.group'].sudo().search([], order='id', limit=1) \
            if 'pb.group' in self.env else None
        # With no group at all, every company the reader is ENTITLED to stands
        # in — not the switcher (GR27). Somebody splitting a month between two
        # entities is by definition looking at two entities.
        companies = group.company_ids if group else Company.browse(
            self._visible_companies(
                self.env.user.company_ids.ids or self.env.companies.ids))
        return [{
            'id': company.id,
            'name': company.name or '',
            'currency': company.currency_id.name or '',
            'symbol': company.currency_id.symbol or '',
            'country': company.country_id.name or '',
            'prorate': bool(getattr(company, 'prorate_joiners_leavers', False)),
        } for company in companies[:MAX_ROWS]]

    @api.model
    def _divisions(self):
        if 'pb.division' not in self.env:
            return []
        return [{'id': d.id, 'name': d.name or '', 'color': d.color or 0}
                for d in self.env['pb.division'].sudo().search([],
                                                               limit=MAX_ROWS)]

    @api.model
    def _schemes(self):
        if 'hr.formula.config' not in self.env:
            return []
        configs = self.env['hr.formula.config'].sudo().search(
            [('state', '=', 'active')], limit=MAX_ROWS)
        return [{
            'id': c.id, 'name': c.name or '',
            'company_id': c.company_id.id,
            'cycle': c.cycle_type or 'regular',
        } for c in configs]

    @api.model
    def _history(self, person):
        if not person:
            return []
        rows = self.env['pb.work.segment'].sudo().search(
            [('person_id', '=', person.id)], order='date_from desc',
            limit=MAX_ROWS)
        return [self._segment_row(row) for row in rows]

    # ============================================================= the write
    @api.model
    def _clean_segment(self, vals):
        vals = vals or {}
        person_id = int(vals.get('person_id') or 0)
        home_id = int(vals.get('home_employee_id') or 0)
        host_company_id = int(vals.get('host_company_id') or 0)
        if not (person_id and home_id and host_company_id):
            raise UserError(_(
                "Pick the person, the employment the days come out of, and "
                "where they worked."))
        date_from = fields.Date.to_date(vals.get('date_from'))
        date_to = fields.Date.to_date(vals.get('date_to'))
        if not (date_from and date_to):
            raise UserError(_("Pick the first and the last day."))
        allowed = {c['id'] for c in self._companies()}
        if host_company_id not in allowed:
            raise UserError(_(
                "That entity is not in the group, so it has no payroll of its "
                "own to run these days through. Add it to the group first."))
        # THE HOST EMPLOYMENT IS LOOKED UP WHEN IT IS NOT NAMED.
        #
        # A caller that says "these days were worked in Singapore" for a person
        # who already holds a Singapore employment has said everything that is
        # needed; making them repeat the employment id is a way of refusing a
        # perfectly clear instruction. Only ONE employment per person per
        # entity can be meant, so there is nothing to guess between.
        host_employee_id = int(vals.get('host_employee_id') or 0)
        if not host_employee_id:
            found = self.env['hr.employee'].sudo().search([
                ('pb_person_id', '=', person_id),
                ('company_id', '=', host_company_id)], limit=1)
            host_employee_id = found.id
        payload = {
            'person_id': person_id,
            'home_employee_id': home_id,
            'host_company_id': host_company_id,
            'host_employee_id': host_employee_id or False,
            'division_id': int(vals.get('division_id') or 0) or False,
            'config_id': int(vals.get('config_id') or 0) or False,
            'date_from': date_from,
            'date_to': date_to,
            'kind': vals.get('kind') or 'split',
            'pay_policy': vals.get('pay_policy') or 'inherit',
            'note': (vals.get('note') or '').strip() or False,
        }
        if vals.get('days'):
            payload['days'] = float(vals['days'])
        if vals.get('fte'):
            payload['fte'] = float(vals['fte'])
        return payload

    @api.model
    def save_segment(self, vals):
        """Create or change a stretch of days, and confirm it."""
        self._require_write()
        payload = self._clean_segment(vals)
        Segment = self.env['pb.work.segment'].sudo()
        segment_id = int((vals or {}).get('id') or 0)
        home = self.env['hr.employee'].sudo().browse(
            payload['home_employee_id']).exists()
        policy = payload['pay_policy']
        if policy == 'inherit':
            policy = Segment._group_policy(home.company_id)
        if policy == POLICY_EACH \
                and payload['kind'] not in ('joiner', 'leaver') \
                and not payload['host_employee_id']:
            if home.company_id.id != payload['host_company_id']:
                raise UserError(_(
                    "Under \"%(pattern)s\" the host entity runs its own "
                    "payslip, so this person needs an employment there. Use "
                    "\"Create the employment\" and it will be made for you.",
                    pattern=_(POLICY_LABELS[POLICY_EACH])))
        payload['state'] = 'confirmed'
        if segment_id:
            segment = Segment.browse(segment_id).exists()
            if not segment:
                raise UserError(_("Those days are no longer here."))
            segment.write(payload)
        else:
            segment = Segment.create(payload)
        return self.get_screen(person_id=payload['person_id'],
                               month=payload['date_from'])

    @api.model
    def remove_segment(self, segment_id):
        self._require_write()
        segment = self.env['pb.work.segment'].sudo().browse(
            int(segment_id or 0)).exists()
        if not segment:
            raise UserError(_("Those days are no longer here."))
        if segment.derived:
            raise UserError(_(
                "These days are worked out from the contract dates. Turn "
                "day-based pay off for the entity to remove them."))
        person_id, month = segment.person_id.id, segment.date_from
        segment.unlink()
        return self.get_screen(person_id=person_id, month=month)

    @api.model
    def set_segment_policy(self, segment_id, policy):
        self._require_write()
        if policy not in ('inherit', POLICY_EACH, POLICY_HOME):
            raise UserError(_("Pick one of the two patterns."))
        segment = self.env['pb.work.segment'].sudo().browse(
            int(segment_id or 0)).exists()
        if not segment:
            raise UserError(_("Those days are no longer here."))
        segment.write({'pay_policy': policy})
        return self.get_screen(person_id=segment.person_id.id,
                               month=segment.date_from)

    # ------------------------------------------------- the host employment
    @api.model
    def host_employment_plan(self, vals):
        """Exactly what pressing "Create the employment" would create.

        Shown BEFORE it happens. Nothing about a person's employment record is
        created silently by this product, and the point of the panel is that
        the reader recognises what they are about to make.
        """
        vals = vals or {}
        person = self.env['pb.person'].sudo().browse(
            int(vals.get('person_id') or 0)).exists()
        company = self.env['res.company'].sudo().browse(
            int(vals.get('host_company_id') or 0)).exists()
        if not (person and company):
            raise UserError(_("Pick the person and the entity first."))
        home = person.home_employee_id or person.employee_ids[:1]
        wage = 0.0
        if home and 'hr.contract' in self.env:
            contract = self.env['hr.contract'].sudo().search(
                [('employee_id', '=', home.id), ('state', '=', 'open')],
                order='wage desc', limit=1)
            wage = contract.wage or 0.0
        existing = self.env['hr.employee'].sudo().search([
            ('pb_person_id', '=', person.id),
            ('company_id', '=', company.id)], limit=1)
        return {
            'person_id': person.id,
            'name': person.name or '',
            'company_id': company.id,
            'company': company.name or '',
            'currency': company.currency_id.name or '',
            'symbol': company.currency_id.symbol or '',
            'home_wage': wage,
            'home_currency': (home.company_id.currency_id.name or ''
                              if home else ''),
            'exists_id': existing.id,
            'exists': existing.name or '',
            'sentence': _(
                "This will create an employment record for %(name)s in "
                "%(company)s and a contract in %(currency)s. Nothing is paid "
                "until a pay run includes it.",
                name=person.name or '', company=company.name or '',
                currency=company.currency_id.name or ''),
        }

    @api.model
    def create_host_employment(self, vals):
        """Make the employment the reader has just been shown."""
        self._require_write()
        plan = self.host_employment_plan(vals)
        if plan['exists_id']:
            return {'employee_id': plan['exists_id'], 'created': False}
        person = self.env['pb.person'].sudo().browse(plan['person_id'])
        company = self.env['res.company'].sudo().browse(plan['company_id'])
        wage = float((vals or {}).get('wage') or 0.0)
        employee = self.env['hr.employee'].sudo().with_company(company).create({
            'name': person.name or _("Unnamed"),
            'company_id': company.id,
            'pb_person_id': person.id,
        })
        if 'hr.contract' in self.env and wage > 0:
            self._safe(lambda: self.env['hr.contract'].sudo().with_company(
                company).create({
                    'name': _("%(name)s — %(company)s",
                              name=person.name or '', company=company.name or ''),
                    'employee_id': employee.id,
                    'company_id': company.id,
                    'wage': wage,
                    'date_start': fields.Date.context_today(self),
                    'state': 'open',
                }), default=None)
        return {'employee_id': employee.id, 'created': True,
                'name': employee.name}

    # ============================================================ the preview
    @api.model
    def preview(self, vals):
        """Both payslips, computed for real and thrown away.

        `days` becomes money here or it does not become anything: a person
        deciding how to split a month is deciding about pay, and a preview
        built from a percentage rather than from the payroll engine would be a
        different number from the one the run produces.
        """
        if not self._can_read():
            raise AccessError(_("You cannot look at pay for these people."))
        payload = self._clean_segment(vals)
        payload['state'] = 'confirmed'
        try:
            with self.env.cr.savepoint():
                self._preview_inside(payload, vals)
        except _PreviewDone as done:
            return done.payload
        except UserError:
            raise
        except Exception as e:      # noqa: BLE001
            _logger.warning('Assignments preview failed', exc_info=True)
            return {'ok': False, 'slips': [], 'transfer': None,
                    'note': _("The preview could not be worked out: %(why)s",
                              why=str(e)[:160])}
        return {'ok': False, 'slips': [], 'transfer': None,
                'note': _("The preview could not be worked out.")}

    @api.model
    def preview_saved(self, employee_id, month=None):
        """Both payslips for a segment that is ALREADY saved.

        The pay run's "Preview both slips" link, and the same savepoint: the
        run has not been computed yet and nothing here may leave a payslip
        behind that a later compute would find and adopt.
        """
        if not self._can_read():
            raise AccessError(_("You cannot look at pay for these people."))
        employee = self.env['hr.employee'].sudo().browse(
            int(employee_id or 0)).exists()
        if not employee:
            raise UserError(_("That employment is no longer here."))
        first, last = self._month_bounds(month)
        Segment = self.env['pb.work.segment'].sudo()
        home, host = Segment._segments_for(employee, first, last)
        segment = (home or host)[:1]
        if not segment:
            raise UserError(_(
                "Nobody has split this person's month, so there is only one "
                "payslip to look at."))
        try:
            with self.env.cr.savepoint():
                slips = []
                home_slip = self._compute_scratch(
                    segment.home_employee_id, first, last)
                if home_slip:
                    slips.append(self._slip_card(home_slip, segment, 'home'))
                transfer = None
                if segment.effective_policy == POLICY_HOME and home_slip:
                    made = Segment.write_transfers(home_slip)
                    if made:
                        row = made[0]
                        transfer = {
                            'amount': row.amount,
                            'currency': row.currency_id.name or '',
                            'symbol': row.currency_id.symbol or '',
                            'to': row.to_company_id.name or '',
                            'sentence': _(
                                "%(amount)s charged to %(company)s.",
                                amount=self._money(row.amount,
                                                   row.currency_id),
                                company=row.to_company_id.name or ''),
                        }
                elif segment.host_employee_id:
                    host_slip = self._compute_scratch(
                        segment.host_employee_id, first, last)
                    if host_slip:
                        slips.append(self._slip_card(host_slip, segment,
                                                     'host'))
                raise _PreviewDone({
                    'ok': True, 'slips': slips, 'transfer': transfer,
                    'policy': segment.effective_policy,
                    'policy_label': _(POLICY_LABELS.get(
                        segment.effective_policy, POLICY_LABELS[POLICY_EACH])),
                    'days': segment.days, 'month_days': segment.month_days,
                    'share': segment.share,
                    'summary': segment.note or '',
                })
        except _PreviewDone as done:
            return done.payload
        except UserError:
            raise
        except Exception as e:      # noqa: BLE001
            _logger.warning('Split preview failed', exc_info=True)
            return {'ok': False, 'slips': [], 'transfer': None,
                    'note': _("The preview could not be worked out: %(why)s",
                              why=str(e)[:160])}
        return {'ok': False, 'slips': [], 'transfer': None,
                'note': _("The preview could not be worked out.")}

    @api.model
    def _preview_inside(self, payload, vals):
        Segment = self.env['pb.work.segment'].sudo()
        segment = Segment.with_context(
            pb_skip_closed_run_check=True, tracking_disable=True,
            mail_create_nolog=True).create(payload)
        first, last = self._month_bounds(payload['date_from'])
        home = segment.home_employee_id
        host = segment.host_employee_id
        slips = []
        home_slip = self._compute_scratch(home, first, last)
        if home_slip:
            slips.append(self._slip_card(home_slip, segment, 'home'))
        transfer = None
        if segment.effective_policy == POLICY_HOME:
            made = Segment.write_transfers(home_slip) if home_slip else None
            if made:
                row = made[0]
                transfer = {
                    'amount': row.amount,
                    'currency': row.currency_id.name or '',
                    'symbol': row.currency_id.symbol or '',
                    'to': row.to_company_id.name or '',
                    'sentence': _(
                        "%(amount)s charged to %(company)s.",
                        amount=self._money(row.amount, row.currency_id),
                        company=row.to_company_id.name or ''),
                }
        elif host:
            host_slip = self._compute_scratch(host, first, last)
            if host_slip:
                slips.append(self._slip_card(host_slip, segment, 'host'))
        raise _PreviewDone({
            'ok': True,
            'slips': slips,
            'transfer': transfer,
            'policy': segment.effective_policy,
            'policy_label': _(POLICY_LABELS.get(segment.effective_policy,
                                                POLICY_LABELS[POLICY_EACH])),
            'days': segment.days,
            'month_days': segment.month_days,
            'share': segment.share,
            'summary': segment._summary(segment, 'home', 1.0 - segment.share),
        })

    @api.model
    def _compute_scratch(self, employee, first, last):
        """One payslip, computed inside the savepoint that will undo it."""
        if not employee:
            return None
        Slip = self.env['hr.payslip'].sudo()
        try:
            oc = Slip.onchange_employee_id(first, last, employee.id,
                                           contract_id=False)
            values = oc.get('value', {}) or {}
            if not values.get('contract_id'):
                return None
            slip = Slip.create({
                'employee_id': employee.id,
                'name': _("Preview — %(name)s", name=employee.name or ''),
                'struct_id': values.get('struct_id'),
                'contract_id': values.get('contract_id'),
                'date_from': first, 'date_to': last,
                'company_id': employee.company_id.id,
                'input_line_ids': [(0, 0, x)
                                   for x in (values.get('input_line_ids') or [])],
                'worked_days_line_ids': [
                    (0, 0, x)
                    for x in (values.get('worked_days_line_ids') or [])],
            })
            slip.compute_sheet()
            return slip
        except Exception:       # noqa: BLE001
            _logger.info('Assignments preview: %s could not be computed',
                         employee.id, exc_info=True)
            return None

    @api.model
    def _card_days(self, segment, side, employee, first, last):
        """How many days this card is FOR — asked of the thing that decides.

        NOT "the month minus this stretch". A person can have two stretches in
        one month, and the pattern in force changes the answer again: under
        "home pays" the home card covers the WHOLE month. Printing a day count
        that disagrees with the amount beside it is the one way a preview can
        be worse than no preview, so the count comes from the SAME function
        the payslip's own number came from.
        """
        month_days = segment.month_days or 0.0
        factor, _meta = self.env['pb.work.segment'].factor_for_period(
            employee, first, last)
        return round(factor * month_days, 1)

    @api.model
    def _slip_card(self, slip, segment, side):
        currency = slip.company_id.currency_id
        net, gross = 0.0, 0.0
        for line in slip.line_ids:
            role = getattr(line, 'pay_role', '') or ''
            detail = bool(getattr(line, 'component_detail', False))
            if (line.code or '').upper() == 'NET' or role == 'net':
                net = line.total
            elif role == 'earning' and not detail:
                gross += line.total
        return {
            'side': side,
            'company': slip.company_id.name or '',
            'employee': slip.employee_id.name or '',
            'currency': currency.name or '',
            'symbol': currency.symbol or '',
            'net': net,
            'net_label': self._money(net, currency),
            'gross': gross,
            'gross_label': self._money(gross, currency),
            'days': self._card_days(segment, side, slip.employee_id,
                                    slip.date_from, slip.date_to),
            'month_days': segment.month_days,
            'lines': len(slip.line_ids),
        }

    @api.model
    def _money(self, amount, currency):
        try:
            return currency.format(amount)
        except Exception:       # noqa: BLE001
            return '%s %s' % (currency.symbol or currency.name or '',
                              '{:,.0f}'.format(amount or 0.0))

    # ======================================================= "Same person?"
    @api.model
    def get_merge_review(self, company_ids=None):
        if not self._can_read():
            return {'allowed': False, 'suggestions': [], 'people': 0}
        Person = self.env['pb.person'].sudo()
        # EVERY COMPANY THE READER IS ENTITLED TO, not the switcher.
        #
        # Same family as GR27 and GR16: `env.companies` follows the company
        # menu, and a person joining two records of one human being should not
        # have to tick five boxes first — the whole point of the review is
        # that the two records are in DIFFERENT companies. With the switcher
        # on one company the review found the pair and reported "nobody looks
        # like a duplicate", which is the most convincing possible way to be
        # wrong.
        scope = self._visible_companies(
            company_ids or self.env.user.company_ids.ids
            or self.env.companies.ids)
        suggestions = self._safe(
            lambda: Person.suggest_merges(scope), default=[])
        return {
            'allowed': True,
            'can_edit': self._can_write(),
            'suggestions': suggestions[:MAX_PEOPLE],
            'people': Person.search_count([]),
            'strong': len([s for s in suggestions if s.get('strong')]),
        }

    @api.model
    def merge_people(self, person_ids):
        self._require_write()
        answer = self.env['pb.person'].sudo().browse(
            [int(p) for p in (person_ids or [])][:1]).merge(person_ids)
        return dict(answer, review=self.get_merge_review())

    @api.model
    def merge_all_strong(self):
        """Join every pair whose national identity numbers agree."""
        self._require_write()
        Person = self.env['pb.person'].sudo()
        scope = self._visible_companies(
            self.env.user.company_ids.ids or self.env.companies.ids)
        pairs = [s['person_ids'] for s in Person.suggest_merges(scope)
                 if s.get('strong')]
        answer = Person.merge_pairs(pairs)
        return dict(answer, review=self.get_merge_review())

    # ============================================================== the chip
    @api.model
    def chip_for(self, employee_id, month=None):
        """One line about this employment's month, for the person's card.

        `found: False` means "a whole month, here" — the normal case — and the
        chip draws nothing at all. A chip that says "not split" on four and a
        half thousand cards is noise dressed as information.
        """
        blank = {'found': False}
        if not self._can_read():
            return blank
        employee = self.env['hr.employee'].sudo().browse(
            int(employee_id or 0)).exists()
        if not employee or 'pb.work.segment' not in self.env:
            return blank
        first, last = self._month_bounds(month)
        try:
            home, host = self.env['pb.work.segment']._segments_for(
                employee, first, last)
        except Exception:       # noqa: BLE001
            return blank
        rows = (home | host).filtered(
            lambda s: s.host_company_id != s.home_company_id)
        if not rows:
            return blank
        row = rows[0]
        away = row.host_company_id if row.home_employee_id == employee \
            else row.home_company_id
        return {
            'found': True,
            'label': _("%(days)s days in %(company)s",
                       days='%g' % sum(rows.mapped('days')),
                       company=away.name or ''),
            'tooltip': _(
                "%(month)s: %(days)s of %(total)s working days were worked in "
                "%(company)s. %(pattern)s.",
                month=first.strftime('%B %Y'),
                days='%g' % sum(rows.mapped('days')),
                total='%g' % (row.month_days or 0),
                company=away.name or '',
                pattern=_(POLICY_LABELS.get(row.effective_policy,
                                            POLICY_LABELS[POLICY_EACH]))),
        }

    # ============================================================ the counts
    @api.model
    def split_people(self, company_ids=None, month=None):
        """How many people are paid in two places this month, and who.

        Read by the pay run's summary and by the Decision Room's note, so
        there is ONE answer to the question wherever it is asked.
        """
        first, last = self._month_bounds(month)
        domain = [('state', '=', 'confirmed'),
                  ('date_from', '<=', last), ('date_to', '>=', first),
                  ('kind', 'not in', ('joiner', 'leaver'))]
        if company_ids:
            domain.append(('home_company_id', 'in',
                           [int(c) for c in company_ids if c]))
        rows = self.env['pb.work.segment'].sudo().search(domain, limit=2000)
        rows = rows.filtered(
            lambda s: s.host_company_id != s.home_company_id)
        people = rows.mapped('person_id')
        return {
            'count': len(people),
            'segments': len(rows),
            'names': people[:20].mapped('name'),
        }
