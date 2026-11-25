# -*- coding: utf-8 -*-
"""NEWHIRE P1 — `pb.new.hire`, the server side of the New Hire Studio.

Everything the screen reads before Send is worked out here by the product's
OWN code (ledger rule 5 — no parallel engines):

  which scheme pays the team   `pb.scheme.map.resolve_for_team` (rungs 2/3/5)
  the money of a country       `hr.formula.config.currency_by_country`
  the trial period             `pb.probation.policy.policy_for_country` +
                               `probation_common.add_months` (same day N
                               months later, D5)
  the scheme's usual answers   `hr.formula.config._pb_usual_answer_rules`
                               + the rule's own record-free word helpers
  who approves                 the approval engine's route lookup
                               (`route_mode`, `_resolve_binding`, `preview`)
  pay band / pay scale hint    `pb.pay.bands.place_hire`,
                               `pb.pay.scales.joiner_suggest` (feature-probed)

Nothing is written before `send`, and `send` writes exactly one thing: a
`pb.newhire.proposal` (kind `employee`). The approved replay is
`create_employee(values)` (see `create_ext.py`).

Every public method starts with `require_hr` (the sentence HR already knows);
the company is read with sudo AFTER that gate (WFSETUP WS2), and every search
is scoped to the current company.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import formatLang

from odoo.addons.pb_people_advanced.models.newhire_approval import (
    NEWHIRE_PROCESS_KEY, require_hr,
)
from odoo.addons.pb_probation.models.probation_common import add_months

_logger = logging.getLogger(__name__)

#: Caps on what a caller controls (reachable over JSON-RPC).
MAX_TEAMS = 500
MAX_JOBS = 1000
MAX_FIND = 50
MAX_USUAL = 60
MAX_WEEKS = 200
MAX_OWN = 80
MAX_EQUIPMENT = 40
MAX_CLOCK = 32

#: The keys a draft from the screen may carry. Anything else is ignored.
DRAFT_KEYS = (
    'name', 'date_start', 'work_email', 'personal', 'department_id', 'job_id',
    'job_title', 'payroll_country', 'parent_id', 'work_location_id',
    'country_id', 'wage', 'contract_kind', 'date_end', 'trial_on', 'usual',
    'pb_scale_pin_reason', 'pb_scale_pin_note', 'fill_job_id',
    # P2 — step 3's category, step 4 and step 6
    'type_id', 'week_id', 'late_group', 'clock_on', 'clock_code', 'login_mode',
    'buddy_id', 'equipment', 'letter', 'open_case', 'own',
)

_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value):
    """A number from the screen, or None when it is not one."""
    if value is None or value is False or value is True or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm(text):
    return ' '.join(str(text or '').split()).casefold()


class PbNewHire(models.AbstractModel):
    _name = 'pb.new.hire'
    _description = 'New hire studio'

    # ================================================================ bits
    @api.model
    def _gate(self):
        require_hr(self.env)

    @api.model
    def _company(self):
        return self.env.company.sudo()

    @api.model
    def _day(self, value):
        try:
            return fields.Date.to_date(value) if value else False
        except (TypeError, ValueError):
            return False

    @api.model
    def _countries(self):
        """`[(code, label)]` a new hire can work in: the employee's Country of
        Work choices that a CONTRACT can also hold (NH1 — writing TH/KH/PH on
        a contract raises), in the employee field's order and words."""
        emp_field = self.env['hr.employee']._fields.get('payroll_country')
        if not emp_field:
            return []
        choices = emp_field._description_selection(self.env)
        con_field = self.env['hr.contract']._fields.get('payroll_country')
        allowed = {c for c, _l in con_field._description_selection(self.env)} \
            if con_field else {c for c, _l in choices}
        return [(c, l) for c, l in choices if c in allowed]

    @api.model
    def _country_label(self, code):
        return dict(self._countries()).get(code or '', '') or (code or '')

    @api.model
    def _country_record(self, code):
        if not code:
            return self.env['res.country']
        return self.env['res.country'].sudo().search([('code', '=', code)], limit=1)

    @api.model
    def _currencies(self):
        try:
            return self.env['hr.formula.config'].sudo().currency_by_country()
        except Exception:                       # noqa: BLE001 — a symbol, not a crash
            _logger.warning('new hire: currency_by_country failed', exc_info=True)
            return {}

    @api.model
    def _company_currency(self):
        cur = self._company().currency_id
        return {'id': cur.id, 'name': cur.name or '', 'symbol': cur.symbol or cur.name or '',
                'position': cur.position or 'after',
                'decimals': cur.decimal_places if cur.decimal_places is not None else 2}

    @api.model
    def _currency_for(self, code):
        return self._currencies().get(code or '') or self._company_currency()

    @api.model
    def _team(self, department_id):
        company = self._company()
        dept = self.env['hr.department'].sudo().browse(_int(department_id)).exists()
        if dept and dept.company_id and dept.company_id != company:
            return self.env['hr.department']
        return dept

    @api.model
    def _job(self, job_id):
        company = self._company()
        job = self.env['hr.job'].sudo().browse(_int(job_id)).exists()
        if job and job.company_id and job.company_id != company:
            return self.env['hr.job']
        return job

    @api.model
    def _person(self, employee_id):
        company = self._company()
        emp = self.env['hr.employee'].sudo().browse(_int(employee_id)).exists()
        if emp and (not emp.active or (emp.company_id and emp.company_id != company)):
            return self.env['hr.employee']
        return emp

    @api.model
    def _site(self, location_id):
        if 'hr.work.location' not in self.env:
            return False
        company = self._company()
        site = self.env['hr.work.location'].sudo().browse(_int(location_id)).exists()
        if site and site.company_id and site.company_id != company:
            return self.env['hr.work.location']
        return site

    @api.model
    def _features(self):
        bands = False
        if 'pb.pay.bands' in self.env:
            try:
                bands = bool(self.env['pb.pay.bands']._can_read())
            except Exception:                   # noqa: BLE001 — a probe
                bands = False
        joiners = False
        if 'pb.onboarding' in self.env:
            try:
                joiners = bool(self.env['pb.onboarding']._can_read())
            except Exception:                   # noqa: BLE001 — a probe
                joiners = False
        return {'bands': bands, 'scales': 'pb.pay.scales' in self.env,
                # P2: "See new joiners" only for people the board lets in
                'joiners': joiners}

    # ============================================================ approval
    @api.model
    def _approval_info(self):
        """Before the last step: does a second person approve, and who?

        The approval engine's own lookups — `route_mode` (the one the mixin
        uses to tell a fast lane from a route) and, for a route, `preview` of
        the version that binds (the read the approvals set-up screen shows).
        No route at all is NH9: Send would raise, so the screen says why.
        """
        company = self._company()
        out = {'needs': True, 'with_whom': False, 'problem': False}
        Proposal = self.env['pb.newhire.proposal'].sudo()
        try:
            mode = Proposal.route_mode(company=company, kind_key='employee',
                                       scope_keys=[''])
        except Exception:                       # noqa: BLE001 — Send will say
            _logger.warning('new hire: route lookup failed', exc_info=True)
            return out
        if mode == 'none':
            out['problem'] = _("New hires cannot be sent yet: nobody is set to approve them. "
                               "Ask an administrator to set this in Approvals.")
            return out
        if mode == 'fast':
            out['needs'] = False
            return out
        try:
            Engine = self.env['biz.approval.engine'].sudo()
            process = self.env['biz.approval.process'].sudo()._by_key(NEWHIRE_PROCESS_KEY)
            _binding, version, _trace, error = Engine._resolve_binding(
                company, process, [''], 'employee')
            if error or not version:
                return out
            preview = Engine.preview(version, {
                'company_id': company.id, 'process_key': NEWHIRE_PROCESS_KEY,
                'scope_keys': [''], 'scope_label': company.name, 'kind_key': 'employee',
                'facts': {'kind': {'value': 'employee', 'unit': ''}}, 'amount': 0.0,
                'submitter_uid': self.env.uid, 'maker_uids': [self.env.uid],
            })
            first = next((s for s in preview.get('steps') or []
                          if s.get('included') and s.get('kind') not in ('notify', 'fast')),
                         None)
            if first:
                names = [p.get('name') for p in first.get('people') or [] if p.get('name')]
                out['with_whom'] = ', '.join(names) or False
                issue = first.get('issue') or {}
                if issue.get('level') == 'block':
                    out['problem'] = _("%(why)s Ask an administrator to set this in Approvals.",
                                       why=issue.get('msg') or '')
        except Exception:                       # noqa: BLE001 — a name, not a gate
            _logger.warning('new hire: route preview failed', exc_info=True)
        return out

    # ================================================================ load
    @api.model
    def load(self, prefill=None):
        """Everything the screen needs to start, in one call."""
        self._gate()
        company = self._company()
        Dept = self.env['hr.department'].sudo()
        teams = Dept.search([('company_id', 'in', [company.id, False])],
                            order='name, id', limit=MAX_TEAMS) \
            .sorted(lambda t: ((t.complete_name or t.name or '').casefold(), t.id))
        Job = self.env['hr.job'].sudo()
        jobs = Job.search([('company_id', 'in', [company.id, False])],
                          order='name, id', limit=MAX_JOBS)
        sites = []
        if 'hr.work.location' in self.env:
            sites = [{'id': s.id, 'name': s.name or ''} for s in self.env['hr.work.location'].sudo().search(
                [('company_id', 'in', [company.id, False])], order='name, id', limit=200)]
        countries = [{'code': c, 'name': l} for c, l in self._countries()]
        codes = [c['code'] for c in countries]
        nationalities = [{'id': c.id, 'name': c.name or '', 'code': c.code or ''}
                         for c in self.env['res.country'].sudo().search([], order='name')]
        today = fields.Date.context_today(self)
        company_code = company.country_id.code or ''
        draft = {
            'date_start': fields.Date.to_string(today),
            'payroll_country': company_code if company_code in codes else '',
        }
        pre = prefill if isinstance(prefill, dict) else {}
        if pre:
            team = self._team(pre.get('department_id'))
            if team:
                draft['department_id'] = team.id
            job = self._job(pre.get('job_id'))
            if job:
                draft['job_id'] = job.id
            elif pre.get('job_title'):
                draft['job_title'] = str(pre['job_title'])[:200]
            boss = self._person(pre.get('parent_id'))
            if boss:
                draft['parent_id'] = boss.id
                draft['parent_name'] = boss.name or ''
            fill = self._job(pre.get('fill_job_id'))
            if fill:
                draft['fill_job_id'] = fill.id
        return {
            'can_send': True,
            'company': {'id': company.id, 'name': company.name or '',
                        'country_code': company_code},
            'user': {'id': self.env.uid, 'name': self.env.user.name or ''},
            'today': fields.Date.to_string(today),
            'countries': countries,
            'currencies': {c: self._currency_for(c) for c in codes},
            'teams': [{'id': t.id, 'name': t.complete_name or t.name or '',
                       'manager_id': t.manager_id.id or False,
                       'manager_name': t.manager_id.name or ''} for t in teams],
            'jobs': [{'id': j.id, 'name': j.name or '', 'department_id': j.department_id.id or False}
                     for j in jobs],
            'managers': self.find_people('', 20),
            'sites': sites,
            'nationalities': nationalities,
            'approval': self._approval_info(),
            'features': self._features(),
            'draft': draft,
        }

    # ======================================================= team defaults
    @api.model
    def team_defaults(self, department_id):
        """What picking a team suggests: its manager, the site most of its
        people work at, and the country of the scheme that pays it."""
        self._gate()
        team = self._team(department_id)
        out = {'manager_id': False, 'manager_name': '', 'site_id': False,
               'country_code': False, 'scheme': False}
        if not team:
            return out
        boss = team.manager_id
        if boss and boss.active:
            out['manager_id'] = boss.id
            out['manager_name'] = boss.name or ''
        if 'hr.work.location' in self.env:
            groups = self.env['hr.employee'].sudo()._read_group(
                [('department_id', '=', team.id), ('active', '=', True),
                 ('work_location_id', '!=', False)],
                ['work_location_id'], ['__count'], order='__count desc', limit=1)
            if groups:
                out['site_id'] = groups[0][0].id
        answer = self.env['pb.scheme.map'].sudo().resolve_for_team(team.id, self._company().id)
        if answer.get('config_id'):
            config = self.env['hr.formula.config'].sudo().browse(answer['config_id'])
            codes = dict(self._countries())
            out['scheme'] = {'id': config.id, 'name': config.name or ''}
            if config.country_code in codes:
                out['country_code'] = config.country_code
        return out

    # ======================================================== what decides
    @api.model
    def _why(self, rung, team, company):
        if rung == 'department':
            return _("Because %(team)s is paid by this scheme.", team=team.name or '')
        if rung == 'division':
            return _("Because %(team)s's division is paid by this scheme.", team=team.name or '')
        if rung == 'only':
            return _("It is the only pay scheme in %(company)s.", company=company.name or '')
        return ''

    @api.model
    def decides(self, department_id, country_code, date_start=False, contract_kind='permanent'):
        """"What this decides": the pay scheme (from the team, checked against
        the chosen country — D3), the currency and the trial period (from the
        chosen country — D4, D5)."""
        self._gate()
        company = self._company()
        code = country_code if country_code in dict(self._countries()) else ''
        out = {'scheme': False, 'currency': self._currency_for(code) if code else False,
               'trial': False, 'trial_none': False, 'problem': False, 'fix': False}
        team = self._team(department_id)
        if team:
            answer = self.env['pb.scheme.map'].sudo().resolve_for_team(team.id, company.id)
            config = self.env['hr.formula.config'].sudo().browse(
                answer.get('config_id') or 0).exists()
            if config:
                match = not code or config.country_code == code
                out['scheme'] = {
                    'id': config.id, 'name': config.name or '',
                    'country_code': config.country_code or '',
                    'country_name': self._country_label(config.country_code),
                    'match': match, 'rung': answer.get('rung') or '',
                    'why': self._why(answer.get('rung'), team, company),
                }
                if not match:
                    theirs = self._country_label(config.country_code)
                    mine = self._country_label(code)
                    out['problem'] = _(
                        "%(team)s is paid by %(scheme)s, a %(theirs)s scheme, but you chose "
                        "%(mine)s as the country of work.",
                        team=team.name or '', scheme=config.name or '', theirs=theirs, mine=mine)
                    out['fix'] = _("Choose %(theirs)s, or pick the team that %(mine)s people "
                                   "belong to.", theirs=theirs, mine=mine)
            else:
                out['problem'] = _("No pay scheme pays %(team)s yet.", team=team.name or '')
                out['fix'] = _("You can still add the person. Set who pays this team in Mapping "
                               "before the first pay run.")
        start = self._day(date_start)
        if code:
            policy = self.env['pb.probation.policy'].sudo().policy_for_country(
                self._country_record(code), company)
            if policy and policy.duration_months > 0 and start:
                out['trial'] = {
                    'months': policy.duration_months,
                    'ends': fields.Date.to_string(add_months(start, policy.duration_months)),
                    'policy_name': policy.name or '',
                }
            elif not policy or policy.duration_months <= 0:
                out['trial_none'] = _("No trial period rule for %(country)s.",
                                      country=self._country_label(code))
            out['letter'] = self._letter_info(code)     # P2: the Contract letter tile
        return out

    # ======================================================= usual answers
    @api.model
    def _scheme(self, config_id):
        company = self._company()
        config = self.env['hr.formula.config'].sudo().browse(_int(config_id)).exists()
        if config and config.company_id and config.company_id != company:
            return self.env['hr.formula.config']
        return config

    @api.model
    def usual_answers(self, config_id):
        """The scheme's usual answers, as the screen offers them. Record-free:
        the rule's own word helpers decide toggle / choice / number."""
        self._gate()
        config = self._scheme(config_id)
        if not config or not hasattr(config, '_pb_usual_answer_rules'):
            return []
        out = []
        for rule in config._pb_usual_answer_rules()[:MAX_USUAL]:
            kind = rule.value_label_control()
            control = {'toggle': 'toggle', 'select': 'choice'}.get(kind, 'number')
            value = rule.default_value or 0.0
            word = rule.value_label_for(value)
            out.append({
                'code': (rule.code or '').strip(),
                'name': rule.name or rule.code or '',
                'control': control,
                'value': value,
                'text': word or formatLang(self.env, value, digits=2).rstrip('0').rstrip('.,'),
                'options': [{'value': o['value'], 'label': o['label']}
                            for o in rule.value_word_choices()] if control != 'number' else [],
            })
        return out

    # ============================================================ pay hint
    @api.model
    def pay_hint(self, job_id, date_start=False, wage=None, country_code=False):
        """The pay band for the job (only when it is in the wage's money, and
        only for people who may read bands — NH6) and the pay-scale line the
        old window showed (`joiner_suggest`, as `joiner_hint.js` called it)."""
        self._gate()
        out = {'band': False, 'band_note': False, 'scale': False}
        job = self._job(job_id)
        if not job:
            return out
        currency = self._currency_for(country_code) if country_code else False
        if 'pb.pay.bands' in self.env:
            try:
                placed = self.env['pb.pay.bands'].place_hire(job_id=job.id)
                band = (placed or {}).get('band')
                if band:
                    if currency and band.get('currency_code') and band['currency_code'] != currency['name']:
                        out['band_note'] = _(
                            "The pay band for this job is in %(theirs)s, so it is not shown "
                            "against a wage in %(mine)s.",
                            theirs=band['currency_code'], mine=currency['name'])
                    else:
                        out['band'] = {k: band.get(k) for k in (
                            'min', 'mid', 'max', 'min_label', 'mid_label', 'max_label',
                            'currency_code', 'name')}
            except AccessError:
                pass                            # NH6: a plain HR officer reads no bands
            except Exception:                   # noqa: BLE001 — a hint never blocks
                _logger.warning('new hire: pay band hint failed', exc_info=True)
        if 'pb.pay.scales' in self.env:
            try:
                hint = self.env['pb.pay.scales'].joiner_suggest(
                    job_id=job.id, date_start=date_start or None,
                    company_id=self._company().id,
                    wage=wage if _float(wage) else None)
                if hint and (hint.get('found') or hint.get('show_why')):
                    out['scale'] = hint
            except Exception:                   # noqa: BLE001 — a hint never blocks
                _logger.warning('new hire: pay scale hint failed', exc_info=True)
        return out

    # ============================================================== people
    @api.model
    def find_people(self, query='', limit=20):
        """Active employees of the company for the manager picker."""
        self._gate()
        company = self._company()
        q = (query or '').strip()
        domain = [('active', '=', True), ('company_id', '=', company.id)]
        if q:
            domain += ['|', ('name', 'ilike', q), ('department_id.name', 'ilike', q)]
        limit = max(1, min(_int(limit) or 20, MAX_FIND))
        people = self.env['hr.employee'].sudo().search(domain, order='name, id', limit=limit)
        return [{'id': e.id, 'name': e.name or '', 'job': e.job_title or e.job_id.name or '',
                 'team': e.department_id.name or ''} for e in people]

    @api.model
    def check_person(self, name, work_email=''):
        """Is somebody of that name (case and spaces ignored) already an
        employee here, and is the work email taken? Never blocks."""
        self._gate()
        company = self._company()
        out = {'same_name': [], 'email_taken': False}
        norm = _norm(name)
        Emp = self.env['hr.employee'].sudo()
        if len(norm) >= 3:
            first = norm.split(' ')[0]
            found = Emp.search([('company_id', '=', company.id), ('active', '=', True),
                                ('name', 'ilike', first)], limit=400)
            out['same_name'] = [{'id': e.id, 'name': e.name or '',
                                 'job': e.job_title or e.job_id.name or '',
                                 'team': e.department_id.name or ''}
                                for e in found if _norm(e.name) == norm][:5]
        email = (work_email or '').strip()
        if email and _EMAIL.match(email):
            out['email_taken'] = bool(Emp.search_count([
                ('company_id', '=', company.id), ('active', '=', True),
                ('work_email', '=ilike', email)], limit=1))
        return out

    # ================================================================ send
    @api.model
    def _refuse(self, step, field, message):
        return {'ok': False, 'step': step, 'field': field, 'message': message}

    @api.model
    def _validate(self, d):
        """`None` when the draft can be sent, else where and what to fix."""
        if not (d.get('name') or '').strip():
            return self._refuse('who', 'name', _("Type the person's full name."))
        start = self._day(d.get('date_start'))
        if not start:
            return self._refuse('who', 'date_start', _("Choose the first day."))
        email = (d.get('work_email') or '').strip()
        if email and not _EMAIL.match(email):
            return self._refuse('who', 'work_email', _("That work email does not look right."))
        if not _int(d.get('department_id')):
            return self._refuse('role', 'department_id', _("Choose the team this person joins."))
        if not self._team(d.get('department_id')):
            return self._refuse('role', 'department_id',
                                _("That team is no longer here. Choose another one."))
        if not _int(d.get('job_id')) and not (d.get('job_title') or '').strip():
            return self._refuse('role', 'job_id', _("Choose a job, or type a new job title."))
        if _int(d.get('job_id')) and not self._job(d.get('job_id')):
            return self._refuse('role', 'job_id', _("That job is no longer here. Choose another one."))
        if not d.get('payroll_country'):
            return self._refuse('role', 'payroll_country', _("Choose the country of work."))
        if d.get('payroll_country') not in dict(self._countries()):
            return self._refuse('role', 'payroll_country',
                                _("Choose one of the countries in the list."))
        if _int(d.get('parent_id')) and not self._person(d.get('parent_id')):
            return self._refuse('role', 'parent_id',
                                _("That manager is no longer an employee here. Choose another one."))
        if _int(d.get('work_location_id')) and not self._site(d.get('work_location_id')):
            return self._refuse('role', 'work_location_id',
                                _("That work site is no longer here. Choose another one."))
        wage = _float(d.get('wage'))
        given = d.get('wage')
        if given is not None and given is not False and given != '' and (wage is None or wage < 0):
            return self._refuse('pay', 'wage', _("The wage must be a number above zero."))
        if not wage and not self._scale_amount(d):
            return self._refuse('pay', 'wage', _("Type the monthly wage."))
        if (d.get('contract_kind') or 'permanent') == 'fixed':
            end = self._day(d.get('date_end'))
            if not end:
                return self._refuse('pay', 'date_end', _("A fixed-term contract needs an end date."))
            if end <= start:
                return self._refuse('pay', 'date_end', _("The contract must end after the first day."))
        return self._validate_welcome(d)                # P2: steps 4 and 6

    @api.model
    def _scale_amount(self, d):
        """The pay-scale amount an empty wage box will take, or 0."""
        if 'pb.pay.scales' not in self.env or not _int(d.get('job_id')):
            return 0.0
        try:
            hint = self.env['pb.pay.scales'].joiner_suggest(
                job_id=_int(d.get('job_id')), date_start=d.get('date_start') or None,
                company_id=self._company().id)
        except Exception:                       # noqa: BLE001
            return 0.0
        return float(hint.get('amount') or 0.0) if hint and hint.get('found') else 0.0

    @api.model
    def _usual_choices(self, d, config):
        """The usual answers the person CHANGED, as `{code, amount, name, text}`
        — only codes of the scheme's usual answers, only values that differ."""
        if not config:
            return []
        rows = {r['code']: r for r in self.usual_answers(config.id)}
        out = []
        given = d.get('usual') or []
        if isinstance(given, dict):
            given = [{'code': k, 'amount': v} for k, v in given.items()]
        for item in given[:MAX_USUAL]:
            if not isinstance(item, dict):
                continue
            code = str(item.get('code') or '').strip()
            amount = _float(item.get('amount'))
            row = rows.get(code)
            if not row or amount is None or abs(amount - (row['value'] or 0.0)) < 1e-9:
                continue
            word = next((o['label'] for o in row['options'] if abs(o['value'] - amount) < 1e-9), '')
            out.append({'code': code, 'amount': amount, 'name': row['name'],
                        'text': word or formatLang(self.env, amount, digits=2)})
        return out

    @api.model
    def _values(self, d):
        """The ONE values dict a studio hire is proposed with (D2). Old keys
        keep their meaning; the new ones are all JSON-plain (NH8)."""
        company = self._company()
        code = d['payroll_country']
        team = self._team(d.get('department_id'))
        job = self._job(d.get('job_id'))
        boss = self._person(d.get('parent_id'))
        site = self._site(d.get('work_location_id'))
        start = self._day(d.get('date_start'))
        kind = 'fixed' if d.get('contract_kind') == 'fixed' else 'permanent'
        decided = self.decides(team.id, code, fields.Date.to_string(start), kind)
        scheme = decided.get('scheme') or {}
        config = self._scheme(scheme.get('id'))
        nationality = self.env['res.country'].sudo().browse(_int(d.get('country_id'))).exists() \
            or self._country_record(code)
        wage = _float(d.get('wage'))
        personal = (d.get('personal') or '').strip()
        trial = decided.get('trial') if d.get('trial_on', True) else False
        vals = {
            'name': ' '.join(str(d.get('name') or '').split()),
            'department_id': team.id,
            'with_contract': True,
            'activate': True,
            'date_start': fields.Date.to_string(start),
            'wage': wage if wage else '',
            'pb_nh': True,
            'payroll_country': code,
            'date_of_joining': fields.Date.to_string(start),
            'contract_kind': kind,
            'trial_date_end': trial['ends'] if trial else False,
            'usual': self._usual_choices(d, config),
            'pb_nh_scheme_id': config.id or False,
            'pb_nh_names': {
                'department_id': team.name or '',
                'job_id': job.name or '',
                'parent_id': boss.name or '',
                'work_location_id': site.name if site else '',
                'scheme': config.name or '',
                'country': self._country_label(code),
                'currency': (decided.get('currency') or {}).get('name') or '',
            },
        }
        if job:
            vals['job_id'] = job.id
        else:
            vals['job_title'] = str(d.get('job_title') or '').strip()[:200]
        if boss:
            vals['parent_id'] = boss.id
        if site:
            vals['work_location_id'] = site.id
        if nationality:
            vals['country_id'] = nationality.id
        email = (d.get('work_email') or '').strip()
        if email:
            vals['work_email'] = email
        if personal:
            vals['private_email' if '@' in personal else 'private_phone'] = personal
        if kind == 'fixed':
            vals['date_end'] = fields.Date.to_string(self._day(d.get('date_end')))
        for key in ('pb_scale_pin_reason', 'pb_scale_pin_note'):
            if d.get(key):
                vals[key] = str(d[key])[:200]
        fill = self._job(d.get('fill_job_id'))
        if fill:
            vals['fill_job_id'] = fill.id
        self._values_welcome(d, vals, decided)          # P2: steps 4 and 6
        return vals, decided

    @api.model
    def send(self, draft):
        """Validate, build the values and propose ONE new hire. Nothing else
        is written. A user mistake comes back as `{ok: False, step, field,
        message}`; the answer otherwise is the proposal's own `answer()`."""
        self._gate()
        d = {k: v for k, v in (draft or {}).items() if k in DRAFT_KEYS} \
            if isinstance(draft, dict) else {}
        refused = self._validate(d)
        if refused:
            return refused
        vals, decided = self._values(d)
        amount = vals['wage'] or self._scale_amount(d)
        currency = (decided.get('currency') or {}).get('name') or self._company_currency()['name']
        try:
            proposal = self.env['pb.newhire.proposal'].propose(
                'employee',
                _("Add %s to the payroll", vals['name']),
                payload={'values': vals},
                facts={'wage': {'value': float(amount or 0.0), 'unit': currency},
                       'has_bank': {'value': False, 'unit': ''},
                       'contract_type': {'value': _("Fixed term") if vals['contract_kind'] == 'fixed'
                                         else _("Permanent"), 'unit': ''}},
                amount=float(amount or 0.0),
            )
        except UserError as exc:
            message = exc.args[0] if exc.args else ''
            return {'ok': False, 'step': 'check', 'field': False,
                    'message': message or _("The hire could not be sent. Try again in a moment.")}
        answer = proposal.answer()
        result = answer.get('result') or {}
        return dict(answer,
                    employee_id=result.get('employee_id') or 0,
                    employee_name=vals['name'],
                    contract_id=result.get('contract_id') or 0)

    # ============================================================ withdraw
    @api.model
    def withdraw(self, proposal_id, reason=''):
        """Take a waiting hire back to change it (D7). Only the person who
        sent it, only while it waits; the engine's own cancel."""
        self._gate()
        proposal = self.env['pb.newhire.proposal'].sudo().browse(_int(proposal_id)).exists()
        if not proposal or proposal.user_id != self.env.user:
            return {'ok': False, 'message': _("Only the person who sent this hire can withdraw it.")}
        if proposal.state != 'pending' or not proposal.approval_request_id:
            return {'ok': False, 'message': _(
                "This hire is no longer waiting for approval, so it cannot be withdrawn.")}
        # sudo after the asker check: the engine re-checks the submitter itself
        self.env['biz.approval.engine'].sudo().cancel(
            proposal.approval_request_id, reason or _("Withdrawn to change it."))
        return {'ok': True, 'message': _("The hire was withdrawn. Change it and send it again.")}
