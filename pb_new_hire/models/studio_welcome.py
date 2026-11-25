# -*- coding: utf-8 -*-
"""NEWHIRE P2 — what steps 4 and 6 of the New Hire Studio read, and the
extra keys `send` builds for them (handover §2.3, §2.4).

Everything shown is the product's OWN answer (ledger rule 5):

  working weeks          `pb.shift.pattern` and its own slot reading
                         (`_pb_slot_map`, `_pb_cycle_index` — the read the
                         Workforce people table makes), Team A of the cycle
  leave                  `hr.leave.type.pb_ls_*` + `pb.timeoff._type_country`
  public holidays        `pb.holidays._column` (the company calendar's list)
  sign-in modes          the rules of `_auto_create_login` and
                         `create_worker_logins` / `_pb_sign_in_code`
  buddies                `pb.buddy.nomination.check_candidate`
  equipment              `pb.asset.category` (`auto_assign_at_joining`)
  contract letter        `pb.letter.template` roots + `_pbds_pick_variant` +
                         `_pbdc_langs` / `_pbdc_pick_lang`
  own fields             `pb.form.studio.fields_for('hr.employee', 'all')`
  joining checklist      `pb.journey.template.pick_for` by NATIONALITY, the
                         country `pb.zoho.pipeline._open_case` passes (NH19)
  timeline               the template's own anchors and offsets — display
                         arithmetic of `_anchor_base + offset_days`; owners
                         from `pb.journey.case._resolve_assignee` on an
                         in-memory case (never a second resolver)

Nothing here writes. Every public method starts with the HR gate.
"""
import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.tools.misc import format_date

from odoo.addons.pb_probation.models.probation_common import (
    P_AUTO_TRIGGER, P_LEAD_DAYS, flag, number,
)

from .studio import DRAFT_KEYS, MAX_CLOCK, MAX_EQUIPMENT, MAX_OWN, MAX_WEEKS, _int

_logger = logging.getLogger(__name__)

#: Form builder kinds the studio can collect (handover §2.4).
OWN_KINDS = ('text', 'longtext', 'integer', 'number', 'date', 'bool', 'select')

#: Words that tell a contract category's kind (no kind field on this build).
KIND_WORDS = {
    'permanent': ('permanent', 'indefinite', 'full-time', 'full time'),
    'fixed': ('fixed', 'temporary', 'contract', 'definite', 'seasonal'),
}

LOGIN_MODES = ('email', 'code', 'none')


class PbNewHireWelcome(models.AbstractModel):
    _inherit = 'pb.new.hire'

    # ============================================================ helpers
    @api.model
    def _first_of(self, name):
        return ' '.join(str(name or '').split()).split(' ')[0] or _("the new person")

    @api.model
    def _hhmm(self, value):
        if 'hr.shift.planning.grid' in self.env:
            return self.env['hr.shift.planning.grid']._pb_float_hhmm(value)
        h = int(value or 0)
        return '%02d:%02d' % (h, int(round(((value or 0) % 1) * 60)))

    @api.model
    def _iso(self, day):
        return fields.Date.to_string(day) if day else False

    # ===================================================== contract category
    @api.model
    def contract_categories(self, country_code, contract_kind='permanent'):
        """`[{id, name, suggested}]` — every employee category, the best match
        for the country and the kind suggested. `hr.contract.type` has
        `country_id` on this build and no kind field: the kind is read from
        the name; hourly categories are never suggested (the wage here is
        monthly). No confident match → none suggested."""
        self._gate()
        Types = self.env['hr.contract.type'].sudo()
        types = Types.search([], order='sequence, id', limit=200)
        country = self._country_record(country_code)
        cname = (country.name or '').casefold()
        kind = 'fixed' if contract_kind == 'fixed' else 'permanent'

        def fits_country(t):
            if 'country_id' in t._fields and t.country_id:
                return bool(country) and t.country_id == country
            return bool(cname) and cname in (t.name or '').casefold()

        def fits_kind(t):
            text = (t.name or '').casefold()
            if kind == 'fixed' and any(w in text for w in KIND_WORDS['permanent']):
                return False
            return any(w in text for w in KIND_WORDS[kind])

        def hourly(t):
            return 'wage_calculation' in t._fields and t.wage_calculation == 'hourly'

        best = next((t for t in types if fits_country(t) and fits_kind(t) and not hourly(t)), None)
        return [{'id': t.id, 'name': t.name or '', 'suggested': bool(best and t == best)}
                for t in types]

    # ===================================================== the contract letter
    @api.model
    def _letter_info(self, code):
        """The employment contract letter a hire in this country gets: the
        country's own wording when one exists, else the general one, and the
        language it is printed in — the same choice `contract_document_save`
        makes once the contract exists."""
        if 'pb.letter.template' not in self.env or 'pb.contracts' not in self.env:
            return {'available': False, 'reason': _("Contract letters are not set up here.")}
        try:
            company = self._company()
            Template = self.env['pb.letter.template'].sudo().with_context(active_test=False)
            roots = Template.search([
                ('letter_type', '=', 'employment_contract'), ('pbds_replaces_id', '=', False),
                ('active', '=', True), ('company_id', 'in', [False, company.id])],
                order='sequence, id', limit=1)
            if not roots:
                return {'available': False,
                        'reason': _("No contract letter wording is switched on yet.")}
            root = roots[:1]
            country = self._country_record(code)
            variants = Template.search([('pbds_replaces_id', '=', root.id), ('active', '=', True)])
            probe = self.env['hr.employee'].sudo().new({'company_id': company.id})
            tmpl = self.env['pb.hr.letter'].sudo()._pbds_pick_variant(
                root, probe, variants, country.id or False) if variants else root
            Contracts = self.env['pb.contracts'].sudo()
            langs = Contracts._pbdc_langs(tmpl)
            lang = Contracts._pbdc_pick_lang(tmpl, probe, None, langs)
            language = next((l['name'] for l in langs if l['code'] == lang), lang or '')
            own = bool(country) and country in tmpl.pbds_country_ids
            out = {'available': True, 'name': tmpl.with_context(lang=self.env.lang).name or '',
                   'language': language, 'own': own}
            if not own:
                out['note'] = _("No letter wording for %s yet, so the general one is used.",
                                self._country_label(code))
            return out
        except Exception:                       # noqa: BLE001 — a tile, never a crash
            _logger.warning('new hire: letter lookup failed', exc_info=True)
            return {'available': False, 'reason': _("The contract letter could not be looked up.")}

    @api.model
    def _letter_for_me(self, code, approval_needs):
        """The letter as step 6 offers it. P3a (architect decision): the
        letter prints the pay, and whoever approves the hire has just
        approved that very wage — so the letter leg makes it for them
        whatever their pay right (`LETTER_CTX`, docs_legs.py). P2's fast-lane
        switch-off and the approver warning are gone; a real failure (no PDF
        tool, no wording) is still an amber leg on the done card."""
        if not code:
            return {'available': False, 'reason': _("Choose the country of work in step 2 first.")}
        return self._letter_info(code)

    # ===================================================== step 4
    @api.model
    def _weeks(self, team, start):
        if 'pb.shift.pattern' not in self.env:
            return False
        company = self._company()
        patterns = self.env['pb.shift.pattern'].sudo().search(
            [('company_id', '=', company.id), ('active', '=', True)], limit=MAX_WEEKS)
        monday = start - timedelta(days=start.weekday())
        out = []
        for pattern in patterns:
            first_team = pattern.team_ids.sorted(lambda t: (t.sequence, t.id))[:1]
            if not first_team:
                continue                        # nobody can join a week with no team
            smap = pattern._pb_slot_map()
            days, hours, times = [], 0.0, set()
            for i in range(7):
                day = monday + timedelta(days=i)
                shift = smap.get(pattern._pb_cycle_index(day, first_team.offset_days or 0))
                row = {'label': format_date(self.env, day, date_format='EEE'), 'on': bool(shift),
                       'start': '', 'end': '', 'shift': ''}
                if shift:
                    row.update(start=self._hhmm(shift.start_hour), end=self._hhmm(shift.end_hour),
                               shift=shift.name or '')
                    hours += shift.duration or 0.0
                    times.add((row['start'], row['end']))
                days.append(row)
            if len(times) == 1:
                a, b = next(iter(times))
                when = _("%(a)s to %(b)s", a=a, b=b)
            elif not times:
                when = _("No working days set")
            else:
                when = _("Times change by day")
            rotation = (pattern.cycle_days or 7) > 7
            out.append({
                'id': pattern.id, 'name': pattern.name or '', 'when': when,
                'days': days, 'hours_per_week': round(hours, 2),
                'team_default': bool(team and pattern.department_id == team),
                'rotation': rotation,
                'rotation_note': _("Repeats every %s days. This is the first week.",
                                   pattern.cycle_days) if rotation else '',
            })
        out.sort(key=lambda w: (not w['team_default'], w['name'].casefold()))
        return out or False

    @api.model
    def _leave_rows(self, code):
        if 'pb_ls_earning' not in self.env['hr.leave.type']._fields:
            return []
        company = self._company()
        kinds = self.env['hr.leave.type'].sudo().search([
            ('active', '=', True), ('pb_ls_earning', '!=', 'none'),
            ('company_id', 'in', [False, company.id])], limit=50)
        Timeoff = self.env['pb.timeoff'] if 'pb.timeoff' in self.env else None
        how = dict(kinds._fields['pb_ls_earning']._description_selection(self.env))
        rows = []
        for kind in kinds:
            where = Timeoff._type_country(kind) if Timeoff is not None else ''
            if where and where != code:
                continue
            days = kind.pb_ls_days_per_year or 0.0
            if days <= 0:
                continue
            wait = kind.pb_ls_waiting_months if 'pb_ls_waiting_months' in kind._fields else 0
            rows.append({
                'name': kind.name or '', 'days_per_year': days,
                'how': how.get(kind.pb_ls_earning, ''),
                'wait': _("Starts after %s months of service.", wait) if wait else '',
            })
        return rows

    @api.model
    def _holidays(self, start):
        if 'pb.holidays' not in self.env:
            return {'count': 0, 'next': False}
        today = fields.Date.context_today(self)
        first = max(today, start or today)
        last = first + relativedelta(years=1) - timedelta(days=1)
        try:
            column = self.env['pb.holidays'].sudo()._column(self._company(), first, last, today)
        except Exception:                       # noqa: BLE001 — a count, never a crash
            _logger.warning('new hire: holiday list failed', exc_info=True)
            return {'count': 0, 'next': False}
        rows = column.get('rows') or []
        count = sum(int(r.get('days') or 1) for r in rows if r.get('date', '') >= self._iso(first))
        nxt = next(({'name': r.get('name') or '', 'date': r.get('date')} for r in rows
                    if r.get('date', '') >= self._iso(first)), False)
        return {'count': count, 'next': nxt}

    @api.model
    def schedule_options(self, department_id, country_code, date_start=False, first_name=''):
        """Step 4: the working weeks (team default flagged, the person's first
        week as a day strip), the late-rule feature, the clock, leave and the
        company's holiday list."""
        self._gate()
        team = self._team(department_id)
        start = self._day(date_start) or fields.Date.context_today(self)
        code = country_code if country_code in dict(self._countries()) else ''
        first = self._first_of(first_name)
        weeks = self._weeks(team, start)
        out = {
            'weeks': weeks,
            'weeks_reason': '' if weeks else _(
                "No working weeks are set up yet, so %s follows the company's usual "
                "working hours.", first),
            'setup_link': False,
            'late_groups': 'pb.attendance.policy' in self.env
            and 'pb_attendance_category' in self.env['hr.employee']._fields,
            'clock': 'pb_clock_code' in self.env['hr.employee']._fields,
            'clock_usual': False,
            'leave': self._leave_rows(code),
            'holidays': self._holidays(start),
        }
        if not weeks and 'pb.workforce.setup' in self.env:
            try:
                out['setup_link'] = bool(self.env['pb.workforce.setup']._can_read())
            except Exception:                   # noqa: BLE001 — a link, never a gate
                out['setup_link'] = False
        if out['clock'] and team:
            Emp = self.env['hr.employee'].sudo()
            mates = Emp.search_count([('department_id', '=', team.id), ('active', '=', True)])
            clocked = Emp.search_count([('department_id', '=', team.id), ('active', '=', True),
                                        ('pb_clock_code', '!=', False)])
            out['clock_usual'] = bool(mates and clocked * 2 >= mates)
        return out

    @api.model
    def check_clock(self, code):
        """Is this clock number free here? The model's own unique constraint
        judges at write time; this is the friendly pre-check."""
        self._gate()
        code = str(code or '').strip()
        if not code:
            return {'ok': True, 'message': ''}
        if len(code) > MAX_CLOCK:
            return {'ok': False, 'message': _("A clock number has at most %s characters.", MAX_CLOCK)}
        if 'pb_clock_code' not in self.env['hr.employee']._fields:
            return {'ok': True, 'message': ''}
        clash = self.env['hr.employee'].sudo().with_context(active_test=False).search([
            ('company_id', '=', self._company().id), ('pb_clock_code', '=', code)], limit=1)
        if clash:
            return {'ok': False, 'message': _(
                "Clock number %(code)s already belongs to %(name)s. Each person needs their "
                "own number.", code=code, name=clash.name or '')}
        return {'ok': True, 'message': _("Clock number %s is free.", code)}

    # ===================================================== step 6
    @api.model
    def _clean(self, draft):
        return {k: v for k, v in (draft or {}).items() if k in DRAFT_KEYS} \
            if isinstance(draft, dict) else {}

    @api.model
    def _clock_of(self, d):
        code = str(d.get('clock_code') or '').strip()
        return code if d.get('clock_on') and code else ''

    @api.model
    def _personal_email(self, d):
        """Step 1's personal contact when it is an email (P3b §2.1)."""
        personal = str(d.get('personal') or '').strip()
        return personal if '@' in personal else ''

    @api.model
    def _login_address(self, d):
        """The sign-in's address: the work email, else the personal one."""
        return (d.get('work_email') or '').strip() or self._personal_email(d)

    @api.model
    def _login_modes(self, d, case_ok, approval_needs):
        first = self._first_of(d.get('name'))
        email = self._login_address(d)
        code = self._clock_of(d)
        param = self.env['ir.config_parameter'].sudo().get_param(
            'pb_zoho_bridge.auto_create_logins', '1')
        email_on = str(param).strip() in ('1', 'true', 'True', 'yes')
        modes = []
        # email: `_auto_create_login` (Hiring's), the invitation sent on day one
        if not email:
            modes.append({'key': 'email', 'label': _("Email invitation"), 'available': False,
                          'why_not': _("Add a work or personal email in step 1, or use the employee "
                                       "number."),
                          'sub': '', 'fix': 'who'})
        elif not email_on:
            modes.append({'key': 'email', 'label': _("Email invitation"), 'available': False,
                          'why_not': _("Email sign-ins are switched off here."), 'sub': ''})
        else:
            # P3b: the sign-in's address is named; the welcome message (step
            # 5) is what carries the link before the first day
            sub = _("Signs in with %s. The sign-in details also go there on the first day.",
                    email) if case_ok else _("Signs in with %s.", email)
            modes.append({'key': 'email', 'label': _("Email invitation"), 'available': True,
                          'why_not': '', 'sub': sub})
        # code: `create_worker_logins` — the login is the clock number
        why, fix = '', False
        if not code:
            fix = 'sched'
            why = _("Type a clock number in step 4. It becomes the employee number %s signs "
                    "in with.", first)
        elif self.env['res.users'].sudo().with_context(active_test=False).search_count(
                [('login', '=ilike', code)], limit=1):
            why = _("Someone already signs in with %s. Choose another clock number in step 4.", code)
            fix = 'sched'
        elif not approval_needs and not self.env['pb.access'].can_manage():
            why = _("Only someone who manages access can make this sign-in. Make it in Access, "
                    "Logins for workers.")
        modes.append({'key': 'code', 'label': _("Employee number"), 'available': not why,
                      'why_not': why, 'fix': fix,
                      'sub': _("Signs in with %(code)s. Set the first password in Access once %(first)s "
                               "is added.", code=code, first=first) if not why else ''})
        modes.append({'key': 'none', 'label': _("Not yet"), 'available': True, 'why_not': '',
                      'sub': _("No sign-in yet. You can add one later from Access.")})
        default = next((m['key'] for m in modes if m['available']), 'none')
        return {'modes': modes, 'default': default}

    @api.model
    def _verdict(self, people):
        if 'pb.buddy.nomination' not in self.env:
            return {p.id: {'level': 'pass', 'why': ''} for p in people}
        Nomination = self.env['pb.buddy.nomination'].sudo()
        out = {}
        for person in people:
            try:
                verdict = Nomination.check_candidate(False, person)
            except Exception:                   # noqa: BLE001 — a hint, never a gate
                verdict = {'level': 'warn', 'reasons': []}
            reasons = [r.get('text') or '' for r in verdict.get('reasons') or []
                       if r.get('level') == verdict.get('level')]
            out[person.id] = {'level': verdict.get('level') or 'pass', 'why': ' '.join(reasons)}
        return out

    @api.model
    def find_buddies(self, query='', limit=12):
        """People who could be the buddy, each with the onboarding rule's own
        verdict (a refused one is shown WITH its reason, never hidden)."""
        rows = self.find_people(query, limit)
        people = self.env['hr.employee'].sudo().browse([r['id'] for r in rows])
        verdict = self._verdict(people)
        for row in rows:
            row.update(verdict.get(row['id']) or {'level': 'pass', 'why': ''})
        return rows

    @api.model
    def _equipment(self):
        if 'pb.asset.category' not in self.env:
            return []
        company = self._company()
        cats = self.env['pb.asset.category'].sudo().search(
            [('active', '=', True), ('company_id', 'in', [False, company.id])], limit=MAX_EQUIPMENT)
        return [{'id': c.id, 'name': c.name or '', 'icon': c.icon or 'package',
                 'usual': bool(c.auto_assign_at_joining)} for c in cats]

    @api.model
    def _own_fields(self, code):
        if 'pb.form.studio' not in self.env:
            return []
        try:
            rows = self.env['pb.form.studio'].fields_for('hr.employee', 'all')
        except Exception:                       # noqa: BLE001 — fields are a bonus card
            _logger.warning('new hire: own fields lookup failed', exc_info=True)
            return []
        country = self._country_record(code)
        out = []
        for row in rows[:MAX_OWN]:
            where = row.get('countries') or []
            if where and (not country or country.id not in where):
                continue
            out.append({
                'name': row['name'], 'label': row.get('label') or row['name'],
                'help': row.get('help') or '', 'kind': row.get('kind') or 'text',
                'required': bool(row.get('required')),
                'options': row.get('options') or [],
                'supported': (row.get('kind') or 'text') in OWN_KINDS,
                'countries': bool(where),
            })
        return out

    @api.model
    def _template_for(self, d):
        """The joining checklist `_open_case` will pick: by NATIONALITY (the
        employee's `country_id`), which defaults to the country of work."""
        company = self._company()
        nationality = self.env['res.country'].sudo().browse(_int(d.get('country_id'))).exists() \
            or self._country_record(d.get('payroll_country'))
        return self.env['pb.journey.template'].sudo().pick_for(
            'onboarding', nationality.id or False, company.id)

    @api.model
    def _fallback_words(self, ctx):
        """Who gets a step nobody else can own: the person who opens the
        checklist (`_generate_tasks` falls back to the case's creator) — the
        one who adds the hire, or whoever approves it."""
        return _("whoever approves the hire") if ctx['approval_needs'] else _("you")

    @api.model
    def _fallback_lead(self, ctx):
        """The same person, at the start of a line."""
        return _("Whoever approves the hire") if ctx['approval_needs'] else _("You")

    @api.model
    def _owner_words(self, rule, step, ctx):
        first = ctx['first']
        boss = ctx['manager']
        if rule == 'manager':
            if boss and boss.user_id:
                return _("Manager: %s", boss.name or '')
            if boss:
                return _("%(who)s, because %(boss)s has no sign-in yet",
                         who=self._fallback_lead(ctx), boss=boss.name or '')
            return _("%s, because there is no manager yet", self._fallback_lead(ctx))
        if rule == 'employee':
            return first if ctx['login'] != 'none' else _(
                "%(who)s, because %(first)s has no sign-in yet", who=self._fallback_lead(ctx), first=first)
        if rule == 'candidate':
            return _("%s, by a link", first)
        if rule == 'buddy':
            buddy = ctx['buddy']
            return _("Buddy: %s", buddy.name) if buddy and buddy.user_id else _("The buddy, once chosen")
        if rule == 'hrbp':
            return _("HR partner")
        if rule == 'user':
            return step.assignee_user_id.name or _("HR")
        label = {'hr': _("HR"), 'it': _("IT"), 'finance': _("Finance"), 'admin': _("Admin")}.get(rule, _("HR"))
        try:
            probe_case = self.env['pb.journey.case'].sudo().new({'company_id': self._company().id})
            user = probe_case._resolve_assignee(rule, self.env['hr.employee'].sudo().new(
                {'company_id': self._company().id}))
        except Exception:                       # noqa: BLE001 — a name, never a crash
            user = False
        return _("%(role)s: %(name)s", role=label, name=user[:1].name) if user \
            else _("%(role)s: %(who)s", role=label, who=self._fallback_words(ctx))

    @api.model
    def _step_line(self, step, ctx):
        """(title, sub) of one checklist step, or None when the choices on
        screen remove it (no equipment at all)."""
        key = getattr(step, 'automation_key', False) or ''
        first = ctx['first']
        title = step.name or ''
        if key == 'asset_laptop':
            names = ctx['equipment_names']
            if names is None:
                return title, _("Raised by itself as a laptop request.")
            if not names:
                return None
            return title, _("Requests: %s.", ', '.join(names))
        if key == 'credentials':
            mode, email, code = ctx['login'], ctx['email'], ctx['code']
            if mode == 'none':
                return title, _("Nothing to send: %s has no sign-in yet.", first)
            if mode == 'code' and not email:
                return title, _("Nothing to send: %(first)s signs in with employee number %(code)s.",
                                first=first, code=code)
            return title, _("Sends itself: the sign-in invitation to %s.", email)
        if key == 'buddy_invite':
            if ctx['buddy']:
                return _("Buddy: %s", ctx['buddy'].name or ''), _("Chosen now, so the manager is not asked.")
            return title, _("Sends itself: asks the manager to choose a buddy.")
        if key:
            return title, _("Sends itself.")
        if step.step_kind == 'form':
            return title, _("A short form, by a link.")
        return title, ''

    @api.model
    def _timeline(self, d, template, ctx):
        """What happens, and when: one entry per step of the checklist that
        will be picked (`_anchor_base + offset_days`, the arithmetic
        `_generate_tasks` uses), plus the first day, the check-ins the
        checklist plans and the end of the trial period. `past` = due today or
        earlier ("Straight away")."""
        today = fields.Date.context_today(self)
        opened = fields.Date.today()            # `_anchor_base('case_open')` reads this one
        start = ctx['start']
        first = ctx['first']
        out = []

        def add(key, when, title, who, sub, order, role=''):
            kind = 'day' if when == start else ('before' if when < start else 'after')
            out.append({'id': key, 'when': self._iso(when), 'title': title, 'who': who or '',
                        'sub': sub or '', 'kind': kind, 'past': when <= today, 'order': order,
                        # P3a: whose step it is, for the "Who does what" bar
                        'role': role})

        add('day', start, _("First day"), first, _("%s starts.", first), -1)
        if template and ctx['open_case']:
            for step in template.step_ids:
                line = self._step_line(step, ctx)
                if line is None:
                    continue
                base = opened if step.anchor == 'case_open' else start
                when = base + timedelta(days=step.offset_days or 0)
                add('step-%s' % step.id, when, line[0], self._owner_words(step.assignee_rule, step, ctx),
                    line[1], step.sequence, role=step.assignee_rule or '')
            for mark, offset in self._checkin_marks():
                when = start + timedelta(days=offset)
                if mark == 'pulse':
                    add('pulse-%s' % offset, when, _("First-week check"), first,
                        _("One tap for %s: how is it going?", first), 900)
                else:
                    add('checkin-%s' % offset, when, _("%s-day check-in", offset), _("HR partner or manager"),
                        _("Planned by itself, with a one-tap question for %s.", first)
                        if offset in ctx['pulse_days'] else _("Planned by itself."), 900)
        trial = ctx['trial']
        if trial:
            ends = fields.Date.to_date(trial['ends'])
            if ctx['review_auto']:
                add('trial', ends - timedelta(days=ctx['lead_days']), _("Trial period review opens"),
                    _("Manager"), _("The trial period ends on %s.", format_date(self.env, ends)), 950)
            else:
                add('trial', ends, _("Trial period ends"), _("HR"),
                    _("HR opens the review from Trial periods."), 950)
        out.sort(key=lambda e: (e['when'], e['order']))
        for e in out:
            e.pop('order')
        return out

    @api.model
    def _checkin_marks(self):
        """[(kind, day offset)] the checklist plans by itself: one-tap checks
        (`DAY_MARK_OFFSET`) and check-ins (`CHECKIN_PLAN`). A pulse on a
        check-in day is folded into that check-in."""
        try:
            from odoo.addons.pb_onboarding.models.journey_case_ext import CHECKIN_PLAN
            from odoo.addons.pb_onboarding.models.onboarding_common import DAY_MARK_OFFSET
        except ImportError:
            return []
        checkins = sorted(offset for _kind, offset in CHECKIN_PLAN)
        pulses = sorted(DAY_MARK_OFFSET.values())
        marks = [('pulse', p) for p in pulses if p not in checkins]
        marks += [('checkin', c) for c in checkins]
        return sorted(marks, key=lambda m: m[1])

    @api.model
    def welcome_options(self, draft):
        """Step 6: sign-in modes, buddies, equipment, the contract letter,
        your own fields, the joining checklist and its dated timeline."""
        self._gate()
        d = self._clean(draft)
        code = d.get('payroll_country') if d.get('payroll_country') in dict(self._countries()) else ''
        first = self._first_of(d.get('name'))
        start = self._day(d.get('date_start')) or fields.Date.context_today(self)
        template = self._template_for(d)
        open_case = d.get('open_case') is not False
        case_ok = bool(template) and open_case
        approval = self._approval_info()
        login = self._login_modes(d, case_ok, approval.get('needs'))
        mode = d.get('login_mode') if d.get('login_mode') in LOGIN_MODES else login['default']
        if not next((m for m in login['modes'] if m['key'] == mode and m['available']), None):
            mode = login['default']
        equipment = self._equipment()
        chosen = d.get('equipment')
        if isinstance(chosen, list):
            ids = {_int(c) for c in chosen}
            names = [c['name'] for c in equipment if c['id'] in ids]
        else:
            names = None
        team = self._team(d.get('department_id'))
        kind = 'fixed' if d.get('contract_kind') == 'fixed' else 'permanent'
        decided = self.decides(team.id if team else False, code, self._iso(start), kind) \
            if code else {}
        trial = decided.get('trial') if d.get('trial_on', True) is not False else False
        lead = number(self.env, P_LEAD_DAYS, 21)
        if trial and code:
            policy = self.env['pb.probation.policy'].sudo().policy_for_country(
                self._country_record(code), self._company())
            if policy and policy.evaluation_lead_days > 0:
                lead = policy.evaluation_lead_days
        try:
            from odoo.addons.pb_onboarding.models.onboarding_common import DAY_MARK_OFFSET
            pulse_days = set(DAY_MARK_OFFSET.values())
        except ImportError:
            pulse_days = set()
        ctx = {
            'first': first, 'start': start, 'login': mode,
            'email': self._login_address(d), 'code': self._clock_of(d),
            'manager': self._person(d.get('parent_id')),
            'buddy': self._person(d.get('buddy_id')) if open_case else self.env['hr.employee'],
            'equipment_names': names, 'open_case': open_case, 'trial': trial,
            'lead_days': lead, 'review_auto': flag(self.env, P_AUTO_TRIGGER),
            'pulse_days': pulse_days, 'approval_needs': bool(approval.get('needs')),
        }
        buddies = self.find_buddies(team.name if team else '', 8) if team else []
        return {
            'login': dict(login, chosen=mode),
            'buddies': buddies,
            'equipment': equipment,
            'letter': self._letter_for_me(code, approval.get('needs')),
            'own_fields': self._own_fields(code),
            'case': {'available': bool(template),
                     'template_name': template.name if template else '',
                     'steps': len(template.step_ids) if template else 0},
            'timeline': self._timeline(d, template, ctx),
        }

    # ===================================================== validate / values
    @api.model
    def _validate_welcome(self, d):
        """`None`, or where and what to fix in steps 3, 4 and 6."""
        if _int(d.get('type_id')) and not self.env['hr.contract.type'].sudo().browse(
                _int(d['type_id'])).exists():
            return self._refuse('pay', 'type_id', _("That contract category is no longer here. "
                                                    "Choose another one."))
        if _int(d.get('week_id')):
            week = self.env['pb.shift.pattern'].sudo().browse(_int(d['week_id'])).exists() \
                if 'pb.shift.pattern' in self.env else None
            if not week or not week.active or week.company_id != self._company():
                return self._refuse('sched', 'week_id', _("That working week is no longer here. "
                                                         "Choose another one."))
        code = self._clock_of(d)
        if code and len(code) > MAX_CLOCK:
            return self._refuse('sched', 'clock_code',
                                _("A clock number has at most %s characters.", MAX_CLOCK))
        mode = d.get('login_mode')
        if mode == 'email' and not self._login_address(d):
            return self._refuse('welcome', 'login_mode', _(
                "An email invitation needs an email address. Add one in step 1, or choose another "
                "sign-in."))
        if mode == 'code' and not code:
            return self._refuse('welcome', 'login_mode', _(
                "An employee-number sign-in needs a clock number. Type one in step 4, or choose "
                "another sign-in."))
        own = d.get('own') if isinstance(d.get('own'), dict) else {}
        for row in self._own_fields(d.get('payroll_country')):
            if not row['supported'] or not row['required'] or row['kind'] == 'bool':
                continue
            value = own.get(row['name'])
            if value is None or value is False or (isinstance(value, str) and not value.strip()):
                return self._refuse('welcome', 'own-%s' % row['name'],
                                    _("Fill in %s. It is required on every employee record.",
                                      row['label']))
        return None

    @api.model
    def _own_text(self, row, value):
        if row['kind'] == 'bool':
            return _("Yes") if value else _("No")
        if row['kind'] == 'select':
            return next((o['label'] for o in row['options'] if o['value'] == value), str(value))
        return str(value)

    @api.model
    def _values_welcome(self, d, vals, decided):
        """The P2 keys of the ONE values dict (JSON-plain, NH8)."""
        names = vals.setdefault('pb_nh_names', {})
        code = vals.get('payroll_country')
        # step 3: the contract category (the suggestion when none was picked)
        type_id = _int(d.get('type_id'))
        if not type_id:
            suggested = [c for c in self.contract_categories(code, vals.get('contract_kind'))
                         if c['suggested']]
            type_id = suggested[0]['id'] if suggested else 0
        if type_id:
            vals['type_id'] = type_id
        # step 4
        if d.get('late_group') in ('worker', 'manager') \
                and 'pb_attendance_category' in self.env['hr.employee']._fields \
                and 'pb.attendance.policy' in self.env:
            vals['pb_attendance_category'] = d['late_group']
        clock = self._clock_of(d)
        if clock:
            vals['pb_clock_code'] = clock
        if _int(d.get('week_id')) and 'pb.shift.pattern' in self.env:
            week = self.env['pb.shift.pattern'].sudo().browse(_int(d['week_id'])).exists()
            if week:
                vals['week_id'] = week.id
                names['week'] = week.name or ''
        # step 6
        own_rows = {r['name']: r for r in self._own_fields(code) if r['supported']}
        own_in = d.get('own') if isinstance(d.get('own'), dict) else {}
        own_out, own_names = {}, {}
        for name, value in own_in.items():
            row = own_rows.get(name)
            if not row or value is None or (isinstance(value, str) and not value.strip()):
                continue
            if row['kind'] != 'bool' and value is False:
                continue
            own_out[name] = value
            own_names[name] = {'label': row['label'], 'text': self._own_text(row, value)}
        if own_out:
            vals['own_fields'] = own_out
            names['own'] = own_names
        email = self._login_address(d)
        mode = d.get('login_mode') if d.get('login_mode') in LOGIN_MODES else ''
        if not mode:
            param = self.env['ir.config_parameter'].sudo().get_param(
                'pb_zoho_bridge.auto_create_logins', '1')
            mode = 'email' if email and str(param).strip() in ('1', 'true', 'True', 'yes') else 'none'
        vals['login_mode'] = mode
        open_case = d.get('open_case') is not False
        vals['open_case'] = open_case
        template = self._template_for(d)
        names['case'] = template.name if template else ''
        if open_case:
            buddy = self._person(d.get('buddy_id'))
            if buddy:
                vals['buddy_id'] = buddy.id
                names['buddy'] = buddy.name or ''
            if isinstance(d.get('equipment'), list):
                cats = {c['id']: c['name'] for c in self._equipment()}
                ids = [i for i in dict.fromkeys(_int(c) for c in d['equipment'][:MAX_EQUIPMENT])
                       if i in cats]
                vals['equipment'] = ids
                names['equipment'] = [cats[i] for i in ids]
        letter = self._letter_for_me(code, self._approval_info().get('needs'))
        if letter.get('available') and d.get('letter') is not False:
            vals['letter'] = True
            names['letter'] = _("In %(lang)s: %(name)s", lang=letter.get('language') or '',
                                name=letter.get('name') or '')
        else:
            vals['letter'] = False
