# -*- coding: utf-8 -*-
"""`pb.job.change.board` — the Change job screen's only server surface.

The board (every job change, quiet glance + filter panel), the guided flow
(one person: what changes, the details, the start date and the reason, and an
impact panel worked out on the server), and one change's page.

Rights: HR managers and the pay team (`GATE_GROUPS`); pay FIGURES only for the
pay team (`PAY_GROUPS`) — an HR manager without pay rights prepares the job
and team half and is told the pay team adds pay. Every read is scoped to the
reader's companies; contract and pay reads are done under sudo AFTER the gate
(facts §2 risk "CD3": a plain HR officer cannot read `hr.contract`).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from .job_change import (
    LIVE_STATES, REASON_KINDS, STATES, UNDO_HOURS, WAGE_CODES,
)

_logger = logging.getLogger(__name__)

PAGE_SIZE = 40
WHERE_DOMAINS = {
    'draft': [('state', 'in', ('draft', 'returned'))],
    'pending': [('state', '=', 'pending')],
    'scheduled': [('state', '=', 'scheduled')],
    'applied': [('state', '=', 'applied')],
    'closed': [('state', 'in', ('rejected', 'cancelled', 'undone'))],
}
LOOKUP_LIMIT = 20
OPTION_LIMIT = 300


class PbJobChangeBoard(models.AbstractModel):
    _name = 'pb.job.change.board'
    _inherit = ['pb.filter.mixin']
    _description = 'Change job — screen data'

    # ------------------------------------------------------------ gates
    @api.model
    def _jc(self):
        return self.env['pb.job.change']

    @api.model
    def _can(self):
        return self._jc()._may_prepare()

    @api.model
    def _refusal(self):
        return _("Changing somebody's job is for HR and the pay team. Ask your "
                 "administrator for the HR manager role to see this screen.")

    @api.model
    def _require(self):
        if not self._can():
            raise AccessError(self._refusal())

    @api.model
    def _scope(self):
        return [('company_id', 'in', self.env.companies.ids)]

    @api.model
    def _change(self, change_id):
        self._require()
        try:
            cid = int(change_id or 0)
        except (TypeError, ValueError):
            cid = 0
        rec = self._jc().search(self._scope() + [('id', '=', cid)], limit=1)
        if not rec:
            raise UserError(_("This job change is no longer there."))
        return rec

    @api.model
    def _employee(self, employee_id):
        try:
            eid = int(employee_id or 0)
        except (TypeError, ValueError):
            eid = 0
        emp = self.env['hr.employee'].sudo().search([
            ('id', '=', eid), ('company_id', 'in', self.env.companies.ids)],
            limit=1)
        if not emp:
            raise UserError(_("That person is not in a company you work in."))
        return emp

    @api.model
    def _safe(self, fn, default=0):
        try:
            with self.env.cr.savepoint(flush=False):
                return fn()
        except Exception as e:      # noqa: BLE001
            _logger.debug('job change board metric failed: %s', e)
            return default

    @api.model
    def _state_label(self, state):
        return self._jc()._label('state', state)

    @api.model
    def _kind_label(self, kind):
        return self._jc()._label('reason_kind', kind)

    # ============================================================ the board
    @api.model
    def get_board(self):
        if not self._can():
            return {'allowed': False, 'why': self._refusal()}
        Change = self._jc()
        scope = self._scope()
        kpis = {key: self._safe(lambda d=dom: Change.search_count(scope + d))
                for key, dom in WHERE_DOMAINS.items()}
        return {
            'allowed': True, 'why': '', 'kpis': kpis,
            'total': self._safe(lambda: Change.search_count(scope)),
            'can_pay': self._jc()._may_see_pay(),
        }

    def _pbf_model(self):
        return 'pb.job.change'

    def _pbf_screen(self):
        return 'job_changes'

    def _pbf_base_domain(self):
        return list(self._scope())

    def _pbf_search_domain(self, search):
        q = (search or '').strip()
        if not q:
            return None
        return Domain.OR([Domain('name', 'ilike', q),
                          Domain('employee_id.name', 'ilike', q),
                          Domain('reason', 'ilike', q)])

    def _pbf_sorts(self):
        return [
            {'key': 'new', 'label': _('Newest first'),
             'order': 'id desc'},
            {'key': 'start', 'label': _('Starting soonest'),
             'order': 'effective_date, id desc'},
            {'key': 'person', 'label': _('Person, A to Z'),
             'order': 'employee_id, id desc'},
        ]

    def _pbf_spec(self):
        return [
            {'key': 'where', 'label': _('Where it is'), 'icon': 'route',
             'group': 'people', 'type': 'choice', 'pinned': True,
             'requires': ['state'],
             'options': [
                 {'value': 'draft', 'label': _('Being prepared'),
                  'tone': 'slate', 'domain': WHERE_DOMAINS['draft']},
                 {'value': 'pending', 'label': _('Waiting for approval'),
                  'tone': 'amber', 'domain': WHERE_DOMAINS['pending']},
                 {'value': 'scheduled', 'label': _('Starts later'),
                  'tone': 'blue', 'domain': WHERE_DOMAINS['scheduled']},
                 {'value': 'applied', 'label': _('Done'), 'tone': 'green',
                  'domain': WHERE_DOMAINS['applied']},
                 {'value': 'closed', 'label': _('Closed'), 'tone': 'rose',
                  'domain': WHERE_DOMAINS['closed']},
             ]},
            {'key': 'kind', 'label': _('What kind'), 'icon': 'tag',
             'group': 'people', 'type': 'choice', 'pinned': True,
             'requires': ['reason_kind'],
             'options': [{'value': k, 'label': self._kind_label(k), 'tone': 'slate',
                          'domain': [('reason_kind', '=', k)]}
                         for k, v in REASON_KINDS]},
            {'key': 'team', 'label': _('Team'), 'icon': 'building',
             'group': 'people', 'type': 'many2one',
             'path': 'employee_id.department_id', 'label_sudo': True},
            {'key': 'who', 'label': _('Prepared by'), 'icon': 'user',
             'group': 'other', 'type': 'many2one', 'path': 'user_id',
             'label_sudo': True},
        ]

    def _pbf_builtin_views(self):
        return [
            {'key': 'all', 'label': _('All job changes'), 'icon': 'briefcase',
             'filters': {}},
            {'key': 'open', 'label': _('Not done yet'),
             'filters': {'where': ['draft', 'pending', 'scheduled']}},
            {'key': 'done', 'label': _('Done'),
             'filters': {'where': ['applied']}},
        ]

    @api.model
    def pbf_layout(self, **kw):
        if not self._can():
            return {'refused': self._refusal()}
        return super().pbf_layout(**kw)

    @api.model
    def get_page(self, filters=None, search=None, sort=None, offset=0,
                 limit=PAGE_SIZE):
        if not self._can():
            return {'rows': [], 'total': 0, 'offset': 0}
        Change = self._jc()
        try:
            offset = max(0, int(offset or 0))
            limit = max(1, min(int(limit or PAGE_SIZE), 200))
        except (TypeError, ValueError):
            offset, limit = 0, PAGE_SIZE
        filters = filters if isinstance(filters, dict) else {}
        domain = self.pbf_domain(filters, search)
        order = self.pbf_order(sort) or 'id desc'
        rows = []
        for rec in Change.search(domain, order=order, offset=offset,
                                 limit=limit):
            try:
                rows.append(self._row(rec))
            except Exception as e:      # noqa: BLE001
                _logger.debug('job change row %s failed: %s', rec.id, e)
        return {'rows': rows, 'total': Change.search_count(domain),
                'offset': offset}

    @api.model
    def _row(self, rec):
        rec = rec.sudo()
        emp = rec.employee_id
        rows = rec._rows(show_pay=False)
        what = ', '.join(str(r[0]) for r in rows[:4])
        if rec.change_pay:
            what = (what + ', ' if what else '') + _('pay')
        return {
            'id': rec.id, 'name': rec.name if rec.name != '/' else '',
            'employee': emp.name or '', 'employee_id': emp.id,
            'job': emp.job_title or emp.job_id.name or '',
            'kind': rec.reason_kind, 'kind_label': self._kind_label(
                rec.reason_kind),
            'what': what,
            'start': rec._day(rec.effective_date),
            'state': rec.state, 'state_label': self._state_label(rec.state),
            'waiting': rec._waiting_for() if rec.state == 'pending' else '',
            'paid_month': bool(rec.state == 'applied' and rec.paid_months()),
        }

    # ============================================================ people
    @api.model
    def search_people(self, term='', limit=LOOKUP_LIMIT):
        self._require()
        domain = [('company_id', 'in', self.env.companies.ids)]
        if (term or '').strip():
            domain.append(('name', 'ilike', term.strip()))
        out = []
        for emp in self.env['hr.employee'].sudo().search(
                domain, order='name', limit=int(limit or LOOKUP_LIMIT)):
            out.append(self._person(emp))
        return out

    @api.model
    def _person(self, emp):
        return {'id': emp.id, 'name': emp.name or '',
                'job': emp.job_title or emp.job_id.name or '',
                'team': emp.department_id.name or '',
                'company': emp.company_id.name or '',
                'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id}

    @api.model
    def lookup(self, kind, term='', company_id=0):
        """Search-as-you-type for the long lists (managers)."""
        self._require()
        company_ids = [int(company_id)] if company_id else \
            self.env.companies.ids
        term = (term or '').strip()
        if kind == 'manager':
            domain = [('company_id', 'in', company_ids)]
            if term:
                domain.append(('name', 'ilike', term))
            return [{'id': e.id, 'label': e.name or '',
                     'sub': e.job_title or e.job_id.name or ''}
                    for e in self.env['hr.employee'].sudo().search(
                        domain, order='name', limit=LOOKUP_LIMIT)]
        return []

    @api.model
    def _options(self, company):
        """The short lists, for the target company (and shared rows)."""
        ids = [company.id, False]

        def rows(model, domain=None, sub=None):
            Model = self.env[model].sudo()
            dom = list(domain or [])
            if 'company_id' in Model._fields:
                dom.append(('company_id', 'in', ids))
            return [{'id': r.id, 'label': r.display_name or '',
                     'sub': sub(r) if sub else ''}
                    for r in Model.search(dom, limit=OPTION_LIMIT)]
        return {
            'jobs': rows('hr.job'),
            'teams': rows('hr.department'),
            'locations': rows('hr.work.location'),
            'calendars': rows('resource.calendar'),
            'companies': [{'id': c.id, 'label': c.name or '',
                           'sub': c.currency_id.name or ''}
                          for c in self.env.companies],
        }

    # ============================================================ the flow
    @api.model
    def get_flow(self, employee_id, change_id=0, vals=None):
        """Everything the guided flow needs for one person."""
        self._require()
        Change = self._jc()
        can_pay = Change._may_see_pay()
        rec = self._change(change_id) if change_id else Change.browse()
        emp = rec.employee_id.sudo() if rec else self._employee(employee_id)
        contract = Change._running_contract(emp)
        company = emp.company_id
        currency = (contract.company_id or company).currency_id
        lines = []
        if contract and can_pay:
            for line in contract.advantages_ids.sorted(
                    key=lambda l: ((l.advantage_template_code or ''), l.id)):
                template = line.advantage_template_id
                if template and 'value_type' in template._fields and \
                        template.value_type == 'text':
                    continue
                lines.append({'code': line.advantage_template_code
                              or template.code or '',
                              'name': template.name or '',
                              'amount': float(line.amount or 0.0)})
        scheme = self._safe(lambda: self.env['pb.scheme.map'].sudo().resolve(
            emp), default={}) or {}
        addable = []
        if can_pay and scheme.get('config_id'):
            have = {l['code'] for l in lines}
            config = self.env['hr.formula.config'].sudo().browse(
                scheme['config_id']).exists()
            for rule in config.rule_ids if config else []:
                code = (rule.code or '').strip()
                if not code or code in have or code.upper() in WAGE_CODES:
                    continue
                if not getattr(rule, 'is_contract_component', False) or \
                        getattr(rule, 'is_text_component', False):
                    continue
                addable.append({'code': code, 'name': rule.name or code})
        now = {
            'job_id': emp.job_id.id, 'job': emp.job_id.name or '',
            'job_title': emp.job_title or '',
            'department_id': emp.department_id.id,
            'team': emp.department_id.name or '',
            'parent_id': emp.parent_id.id, 'manager': emp.parent_id.name or '',
            'work_location_id': emp.work_location_id.id,
            'location': emp.work_location_id.name or '',
            'resource_calendar_id': emp.resource_calendar_id.id,
            'calendar': emp.resource_calendar_id.name or '',
            'company_id': company.id, 'company': company.name or '',
            'wage': float(contract.wage or 0.0) if (contract and can_pay)
            else 0.0,
            'currency': currency.name or '',
            'decimals': currency.decimal_places or 0,
            'has_contract': bool(contract),
            'contract': contract.name or '',
            'scheme': scheme.get('config_name') or '',
        }
        draft = self._draft_payload(rec) if rec else self._prefill(vals, emp)
        return {
            'person': self._person(emp), 'now': now, 'lines': lines,
            'addable': addable, 'can_pay': can_pay,
            'options': self._options(company),
            'kinds': [{'key': k, 'label': self._kind_label(k)} for k, _v in REASON_KINDS],
            'draft': draft,
            'today': fields.Date.to_string(Change._today_for(company)),
            'change_id': rec.id if rec else 0,
            'state': rec.state if rec else 'draft',
        }

    @api.model
    def _draft_payload(self, rec):
        rec = rec.sudo()
        return {
            'reason_kind': rec.reason_kind, 'reason': rec.reason or '',
            'effective_date': fields.Date.to_string(rec.effective_date) or '',
            'new_job_id': rec.new_job_id.id, 'new_job_title':
                rec.new_job_title or '',
            'new_department_id': rec.new_department_id.id,
            'new_parent_id': rec.new_parent_id.id,
            'new_parent': rec.new_parent_id.name or '',
            'new_work_location_id': rec.new_work_location_id.id,
            'new_resource_calendar_id': rec.new_resource_calendar_id.id,
            'new_company_id': rec.new_company_id.id,
            'change_pay': bool(rec.change_pay),
            'new_wage': float(rec.new_wage or 0.0),
            'lines': [{'code': l.code, 'name': l.name or l.code,
                       'old': l.old_amount, 'new': l.new_amount}
                      for l in rec.line_ids],
            'source': rec.source or '',
        }

    @api.model
    def _prefill(self, vals, emp):
        """C-1: the `vals` `pb_start_for_employee` accepted, as draft fields."""
        vals = vals if isinstance(vals, dict) else {}
        out = {'reason_kind': vals.get('reason_kind') or 'promotion',
               'reason': vals.get('reason') or '',
               'effective_date': vals.get('effective_date') or '',
               'new_job_title': vals.get('job_title') or '',
               'change_pay': bool(vals.get('wage') or vals.get('lines')),
               'new_wage': float(vals.get('wage') or 0.0),
               'lines': [], 'source': vals.get('source') or '',
               'source_ref': vals.get('source_ref') or ''}
        for key, mine in (('job_id', 'new_job_id'),
                          ('department_id', 'new_department_id'),
                          ('parent_id', 'new_parent_id'),
                          ('work_location_id', 'new_work_location_id'),
                          ('resource_calendar_id', 'new_resource_calendar_id'),
                          ('company_id', 'new_company_id')):
            out[mine] = int(vals.get(key) or 0) or False
        if out.get('new_parent_id'):
            boss = self.env['hr.employee'].sudo().browse(
                out['new_parent_id']).exists()
            out['new_parent'] = boss.name if boss else ''
        for row in vals.get('lines') or []:
            if isinstance(row, dict) and row.get('code'):
                out['lines'].append({'code': row['code'],
                                     'name': row.get('name') or row['code'],
                                     'old': 0.0,
                                     'new': float(row.get('amount') or 0.0)})
        return out

    # ------------------------------------------------------------ to a record
    @api.model
    def _record_vals(self, vals, emp):
        vals = vals if isinstance(vals, dict) else {}
        can_pay = self._jc()._may_see_pay()
        out = {
            'employee_id': emp.id,
            'company_id': emp.company_id.id,
            'reason_kind': vals.get('reason_kind') if vals.get('reason_kind')
            in dict(REASON_KINDS) else 'other',
            'reason': (vals.get('reason') or '').strip()[:4000] or False,
            'effective_date': vals.get('effective_date') or False,
            'new_job_title': (vals.get('new_job_title') or '').strip()
            or False,
        }
        for key in ('new_job_id', 'new_department_id', 'new_parent_id',
                    'new_work_location_id', 'new_resource_calendar_id',
                    'new_company_id'):
            try:
                out[key] = int(vals.get(key) or 0) or False
            except (TypeError, ValueError):
                out[key] = False
        if out['new_company_id'] and \
                out['new_company_id'] not in self.env.companies.ids:
            raise UserError(_("You can only move people to a company you "
                              "work in."))
        if vals.get('source'):
            out['source'] = str(vals['source'])[:64]
        if vals.get('source_ref'):
            out['source_ref'] = str(vals['source_ref'])[:128]
        wants_pay = bool(vals.get('change_pay'))
        if wants_pay and not can_pay:
            raise AccessError(_("Pay is changed by the pay team. Leave pay "
                                "unchanged and ask them to add it."))
        out['change_pay'] = wants_pay
        if wants_pay:
            try:
                out['new_wage'] = float(vals.get('new_wage') or 0.0)
            except (TypeError, ValueError):
                raise UserError(_("Type the new monthly pay as a number."))
            lines = []
            for seq, row in enumerate(vals.get('lines') or []):
                if not isinstance(row, dict) or not row.get('code'):
                    continue
                try:
                    new = float(row.get('new') or 0.0)
                except (TypeError, ValueError):
                    raise UserError(_("Type every pay line as a number."))
                if new < 0:
                    raise UserError(_("A pay line cannot be below zero."))
                lines.append((0, 0, {'sequence': seq,
                                     'code': str(row['code'])[:64],
                                     'name': str(row.get('name') or '')[:128],
                                     'old_amount': float(row.get('old')
                                                         or 0.0),
                                     'new_amount': new}))
            out['line_ids'] = [(5, 0, 0)] + lines
        else:
            out['new_wage'] = 0.0
            out['line_ids'] = [(5, 0, 0)]
        return out

    @api.model
    def preview(self, vals, change_id=0):
        """The impact panel, worked out on an unsaved copy. Writes nothing."""
        self._require()
        vals = vals if isinstance(vals, dict) else {}
        emp = self._change(change_id).employee_id.sudo() if change_id \
            else self._employee(vals.get('employee_id'))
        record_vals = self._record_vals(vals, emp)
        line_vals = [v[2] for v in record_vals.pop('line_ids') if v[0] == 0]
        draft = self._jc().sudo().new(dict(record_vals, line_ids=[
            (0, 0, v) for v in line_vals]))
        problems = draft._problems()
        facts = draft._compute_facts()
        now, after = draft._scheme_now_and_after()
        reads = draft._scheme_reads(now.get('id'))
        company = draft._target_company()
        today = draft._today_for(company)
        timing = ''
        if draft.effective_date:
            if draft.effective_date > today:
                timing = 'future'
            elif draft.effective_date < today:
                timing = 'past'
            else:
                timing = 'today'
        paid = draft._paid_months() if facts['changes_pay']['value'] else []
        steps = []
        manager = draft._manager_user()
        if manager:
            steps.append({'key': 'mgr', 'label': _('Their manager'),
                          'who': manager.name})
        steps.append({'key': 'hr', 'label': _('HR lead'), 'who': ''})
        if facts['above_guidance']['value']:
            steps.append({'key': 'fin', 'label': _('Finance approver'),
                          'who': ''})
        pct = facts['pay_rise_pct']['value']
        return {
            'ok': not problems, 'problems': problems,
            'timing': timing,
            'start': draft._day(draft.effective_date),
            'pct': pct,
            'above_guidance': facts['above_guidance']['value'],
            'above_band': facts['above_band']['value'],
            'scheme_now': now.get('name') or '',
            'scheme_after': after.get('name') or '',
            'changes_scheme': facts['changes_scheme']['value'],
            'reads': reads,
            'paid': paid,
            'retro': self._jc()._retro_installed(),
            'steps': steps,
            'rows': [{'label': str(a), 'now': str(b), 'new': str(c)}
                     for a, b, c in draft._rows(
                         show_pay=self._jc()._may_see_pay())],
        }

    @api.model
    def save(self, vals, change_id=0):
        """Create or change a draft. Nothing is sent."""
        self._require()
        vals = vals if isinstance(vals, dict) else {}
        if change_id:
            rec = self._change(change_id)
            if rec.state not in ('draft', 'returned'):
                raise UserError(_("This job change has already been sent in, "
                                  "so it cannot be changed."))
            emp = rec.employee_id.sudo()
            rec.write(self._record_vals(vals, emp))
        else:
            emp = self._employee(vals.get('employee_id'))
            rec = self._jc().create(self._record_vals(vals, emp))
            rec.sudo().name = 'JC%05d' % rec.id
        return {'ok': True, 'id': rec.id}

    @api.model
    def send(self, vals, change_id=0):
        saved = self.save(vals, change_id)
        rec = self._change(saved['id'])
        return rec.action_send()

    # ============================================================ one change
    @api.model
    def get_change(self, change_id):
        rec = self._change(change_id)
        can_pay = self._jc()._may_see_pay()
        r = rec.sudo()
        request = r.approval_request_id
        steps = []
        if request:
            for step in request.step_ids.sorted('sequence'):
                if not step.included or step.kind in ('fast', 'notify'):
                    continue
                steps.append({
                    'title': step.title, 'status': step.status,
                    'people': ', '.join(sorted({s.acting_user_id.name or ''
                                                for s in step.seat_ids})),
                })
        now = fields.Datetime.now()
        undo_left = (r.state == 'applied' and r.undo_until
                     and r.undo_until > now)
        paid = r.paid_months() if r.state == 'applied' else []
        rework_open = bool(r.rework_id and self._jc()._retro_installed() and
                           self.env['pb.retro.review'].sudo().browse(
                               r.rework_id).exists())
        return {
            'id': r.id, 'name': r.name, 'state': r.state,
            'state_label': self._state_label(r.state),
            'person': self._person(r.employee_id),
            'kind_label': self._kind_label(r.reason_kind),
            'reason': r.reason or '',
            'start': r._day(r.effective_date),
            'start_iso': fields.Date.to_string(r.effective_date) or '',
            'rows': [{'label': str(a), 'now': str(b), 'new': str(c)}
                     for a, b, c in r._rows(show_pay=can_pay)],
            'steps': steps,
            'waiting': r._waiting_for() if r.state == 'pending' else '',
            'block_note': r.block_note or '',
            'blocked': bool(request and request.state == 'blocked'),
            'block_reason': (request.block_reason or '') if request else '',
            'prepared_by': r.user_id.name or '',
            'done_on': r._day(r.applied_at.date()) if r.applied_at else '',
            'done_by': r.applied_by.name or '',
            'by_job': bool(r.started_by_job),
            'undo': bool(undo_left and rec._may_act()),
            'undo_until': fields.Datetime.to_string(r.undo_until)
            if undo_left else '',
            'undo_hours': UNDO_HOURS,
            'can_cancel': r.state in ('draft', 'pending', 'scheduled',
                                      'returned') and rec._may_act(),
            'can_edit': r.state in ('draft', 'returned'),
            'paid': paid,
            'retro': self._jc()._retro_installed(),
            'retro_allowed': bool(self._jc()._retro_installed() and
                                  self.env['pb.retro.review']._pb_may_use()),
            'rework_id': r.rework_id if rework_open else 0,
            'letter_id': r.letter_id.id or 0,
            'letter': r.letter_id.subject or r.letter_id.name or ''
            if r.letter_id else '',
            'can_pay': can_pay,
        }

    @api.model
    def act(self, change_id, verb):
        rec = self._change(change_id)
        if verb == 'cancel':
            rec.action_cancel()
            return {'ok': True, 'msg': _("Cancelled. Nothing was changed.")}
        if verb == 'undo':
            rec.action_undo()
            return {'ok': True, 'msg': _("Taken back. The old details are in "
                                         "place again.")}
        if verb == 'send':
            return rec.action_send()
        if verb == 'rework':
            answer = rec.action_open_rework()
            return {'ok': True, 'review_id': answer.get('review_id') or 0}
        raise UserError(_("That cannot be done here."))

    @api.model
    def open_letter(self, change_id):
        rec = self._change(change_id)
        if not rec.sudo().letter_id:
            raise UserError(_("There is no letter for this change."))
        return {'type': 'ir.actions.act_window', 'res_model': 'pb.hr.letter',
                'res_id': rec.sudo().letter_id.id, 'view_mode': 'form',
                'views': [[False, 'form']], 'target': 'current'}

    # ============================================================ the chip
    @api.model
    def chip(self, employee_id):
        """One line on the person's side panel: a change waiting or coming."""
        if not self._can():
            return {}
        try:
            eid = int(employee_id or 0)
        except (TypeError, ValueError):
            return {}
        rec = self._jc().search(self._scope() + [
            ('employee_id', '=', eid), ('state', 'in', LIVE_STATES)],
            order='id desc', limit=1)
        if not rec:
            return {}
        r = rec.sudo()
        if r.state == 'scheduled':
            label = _("Job change from %s", r._day(r.effective_date))
        else:
            label = _("Job change waiting for approval")
        return {'id': r.id, 'label': label, 'state': r.state}
