# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Eleven small state machines, one configurable engine, no rewrites.

WHAT WAS TRUE BEFORE. `biz.approval.chain.mixin` gives a business object a
hard-coded ladder: a dictionary of `(from, to) -> group`, a button per rung,
and a trail of its own. Eleven objects use it — asset requests, attendance
corrections, bank-account changes, business trips, awards, contract
extensions, employee-record changes, resignations, pay changes, pay reviews
and recognition. Each ladder is a decision somebody made once, in code, and no
business could change it without a developer.

WHAT IS TRUE NOW. When a company has published a route for that kind of
request, the SAME buttons drive the engine instead: pressing the first rung
sends the record in, pressing a later rung records that person's decision, and
the record's own status follows the route it was actually given — one step or
five, roles or managers, with conditions, deadlines, reminders, hand-overs,
the independence rule and one inbox. When no route is published the shim is
dormant and every consumer behaves exactly as it did before, to the line.

THE SHIM IS ONE FILE FOR ALL ELEVEN because the difference between them is
data, not behaviour: which catalogue row they are approved under, which status
means "sent in", and which statuses the route drives. That is the whole of
`CHAIN_PROCESS_KEYS`; a consumer module registers its row at import time and
then only has to say what its FACTS are — the things a route may ask about.

WHAT STAYS THE BUSINESS MODULE'S. Scope. The engine never parses a scope key
(ledger AM2), so "which part of the business is this about" is answered by
resolvers a host product registers — `pb_approval_config` registers the
Payobook one, which speaks of divisions. With none registered, every request
is scoped to its company, which is the honest answer for a product that has no
such concept.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: model name -> what the engine needs to know about that ladder.
CHAIN_PROCESS_KEYS = {}

#: Context key marking a state write the engine itself asked for, so the
#: cancel-the-open-request guard below does not fire on our own moves. It is
#: never a permission: `_chain_state_write`'s own token still decides whether
#: the write is allowed at all, and a forged flag could only ever stop a
#: request being withdrawn — never start one, decide one or skip one.
ENGINE_WRITE = 'biz_chain_engine_write'

#: A host product may register a resolver that says which part of ITS business
#: a record belongs to. Signature: ``fn(env, employee, on_date) -> [{'key',
#: 'label'}]``, most specific first, never including the company rank (the
#: shim appends it). The engine still never parses a key.
SCOPE_RESOLVERS = []

#: The same question asked of a whole company, for the coverage scan:
#: ``fn(env, company) -> [{'key', 'label', 'headcount'}]``.
SCOPE_CATALOGUES = []


def register_chain(model_name, process_key, submit_state, driven,
                   draft_state='draft', refuse_state='refused',
                   reverse_to=None, employee_field='employee_id',
                   amount_field=None, currency_field='currency_id',
                   date_field=None):
    """Tell the shim how one consumer's ladder maps onto a route.

    ``submit_state``  the status that means "sent in, nobody has decided yet".
    ``driven``        the statuses the route drives, in order; the last one is
                      reached when the whole request is carried out, the ones
                      before it as each step is decided. Statuses AFTER the
                      last one (a pay change being applied and closed) are not
                      the route's business and keep their own buttons.
    ``reverse_to``    statuses that mean "sent back down"; default: the draft.
    """
    spec = {
        'process_key': process_key,
        'submit_state': submit_state,
        'driven': tuple(driven),
        'intermediate': tuple(driven[:-1]),
        'final_state': driven[-1],
        'draft_state': draft_state,
        'refuse_state': refuse_state,
        'reverse_to': tuple(reverse_to if reverse_to is not None
                            else (draft_state,)),
        'employee_field': employee_field,
        'amount_field': amount_field,
        'currency_field': currency_field,
        'date_field': date_field,
    }
    CHAIN_PROCESS_KEYS[model_name] = spec
    return spec


def manager_step(title, key='mgr', condition=None, kind='approve'):
    """A step decided by the manager of the person it is about."""
    return {'key': key, 'kind': kind, 'title': title,
            'who': {'mode': 'manager'}, 'min_amount': 0,
            'condition': condition}


def role_step(title, role, key=None, scope='company', condition=None,
              kind='approve'):
    """A step decided by whoever holds one responsibility.

    ``scope='company'`` by default and on purpose: a responsibility looked up
    under 'area' is looked up under the REQUEST's own scope keys (ledger
    AM80), so a company-wide holder does not cover a division and every
    request would block on a seat nobody has been given yet. A business that
    wants one person per part of the business changes the step to 'area' and
    names them — which is a choice it makes, not one it inherits.
    """
    return {'key': key or role, 'kind': kind, 'title': title,
            'who': {'mode': 'role', 'role': role, 'scope': scope},
            'min_amount': 0, 'condition': condition}


def route(*steps, independent=True, due_days=2, reassign=False):
    """A whole definition document from a list of steps.

    Every default route this phase ships has the same safeguards — the person
    who asked cannot approve their own, the same person is not asked twice in
    a row, and a step is chased after two working days — so they are written
    once here rather than eleven times, where they would drift.
    """
    return {
        'schema_version': 1,
        'steps': [dict(step) for step in steps],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': independent,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'working_days', 'days': due_days, 'day': 15,
                    'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2,
                     'reassign': reassign},
        },
    }


def register_scope_resolver(fn):
    if fn not in SCOPE_RESOLVERS:
        SCOPE_RESOLVERS.append(fn)
    return fn


def register_scope_catalogue(fn):
    if fn not in SCOPE_CATALOGUES:
        SCOPE_CATALOGUES.append(fn)
    return fn


class BizApprovalChainShim(models.AbstractModel):
    """The engine, wired into the chain mixin every consumer already has."""
    _name = 'biz.approval.chain.mixin'
    _inherit = ['biz.approval.chain.mixin', 'biz.approval.adapter.mixin']

    #: A SEAT IS ALSO A READ (ledger AM60). A route may ask somebody to decide
    #: a record the ORM would otherwise refuse them — a line manager who holds
    #: no HR group is the everyday case. A record rule is a domain and cannot
    #: reach an answer that has no column, so the people asked are kept here
    #: and each consumer's own rule reads it.
    seat_user_ids = fields.Many2many(
        'res.users', string='Asked to decide', copy=False,
        help='Everyone a published approval route has asked to decide this. '
             'Being here is not a permission to change anything.')

    # ==================================================================
    # The registry
    # ==================================================================
    def _chain_spec(self):
        return CHAIN_PROCESS_KEYS.get(self._name)

    def _approval_engine_process_key(self):
        """The catalogue row this kind of record is approved under."""
        spec = CHAIN_PROCESS_KEYS.get(self._name)
        return (spec or {}).get('process_key') \
            or getattr(self, '_approval_process_key', None)

    def _approval_process_key_for(self):
        self.ensure_one()
        return self._approval_engine_process_key()

    def _engine_managed(self):
        """Has this company asked for this kind of request to be approved?

        The test is a live binding, not a resolvable route: a company that has
        set one up and then broken it must get the engine's named refusal, not
        a silent fall-back to the old ladder. No route at all is the only
        thing that leaves the shim dormant.
        """
        self.ensure_one()
        spec = self._chain_spec()
        if not spec:
            return False
        if 'biz.approval.binding' not in self.env:
            return False
        process = self.env['biz.approval.process']._by_key(spec['process_key'])
        if not process:
            return False
        company = self._chain_company()
        return bool(self.env['biz.approval.binding'].sudo().search_count([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id),
            ('active', '=', True),
        ]))

    # ==================================================================
    # What the record is about
    # ==================================================================
    def _chain_company(self):
        self.ensure_one()
        company = self._fields.get('company_id') and self.company_id
        return company[:1] if company else self.env.company

    def _chain_employee(self):
        """The person this is about."""
        self.ensure_one()
        spec = self._chain_spec() or {}
        name = spec.get('employee_field') or 'employee_id'
        if name not in self._fields:
            return self.env['hr.employee']
        return self.sudo()[name][:1]

    def _chain_date(self):
        self.ensure_one()
        spec = self._chain_spec() or {}
        name = spec.get('date_field')
        value = self[name] if name and name in self._fields else False
        return fields.Date.to_date(value) or fields.Date.context_today(self)

    def _chain_amount(self):
        """(amount, currency) — nothing, for a request that costs nothing."""
        self.ensure_one()
        spec = self._chain_spec() or {}
        name = spec.get('amount_field')
        amount = 0.0
        if name and name in self._fields:
            try:
                amount = float(self[name] or 0.0)
            except (TypeError, ValueError):
                amount = 0.0
        currency_field = spec.get('currency_field') or 'currency_id'
        currency = self.env['res.currency']
        if currency_field in self._fields and self[currency_field]:
            currency = self[currency_field][:1]
        if not currency:
            currency = self._chain_company().currency_id
        return amount, currency

    def _chain_title(self):
        self.ensure_one()
        return self.display_name or self._description

    def _chain_kind_key(self):
        """Which KIND of this request it is, when the model has kinds."""
        return 'any'

    def _chain_facts(self):
        """What a route may condition on, frozen as it is now.

        ``{key: {'value': ..., 'unit': ''}}``. A unit is a word — a currency
        code, "hours", "days" — never the shape of the value (ledger AM25).
        """
        return {}

    @api.model
    def _chain_fact_specs(self):
        """The same facts, described for the workflow builder."""
        return {}

    @api.model
    def _chain_kinds(self):
        return []

    def _chain_revision_values(self):
        """What an approver is signing for.

        Never `write_date` and never anything the freeze itself moves — the
        status above all (ledger AM32, AM46, AM76).
        """
        self.ensure_one()
        amount, _currency = self._chain_amount()
        return {'amount': amount,
                'facts': {key: (value or {}).get('value')
                          for key, value in (self._chain_facts() or {}).items()}}

    # ------------------------------------------------------------- the scope
    def _chain_scopes(self):
        """Where this request happens, in the host product's own words."""
        self.ensure_one()
        employee = self._chain_employee()
        on_date = self._chain_date()
        rows = []
        for resolver in SCOPE_RESOLVERS:
            try:
                rows += list(resolver(self.env, employee, on_date) or [])
            except Exception:   # noqa: BLE001 — a scope must never raise
                _logger.exception('approval: a scope resolver failed on %s',
                                  self._name)
        return [row for row in rows if row.get('key')]

    # ==================================================================
    # The adapter contract
    # ==================================================================
    def _approval_context(self):
        self.ensure_one()
        company = self._chain_company()
        employee = self._chain_employee()
        scopes = self._chain_scopes()
        amount, currency = self._chain_amount()
        makers = {self.create_uid.id}
        if employee.user_id:
            makers.add(employee.user_id.id)
        makers.discard(False)
        return {
            'company_id': company.id,
            'title': self._chain_title(),
            'scope_keys': [row['key'] for row in scopes] + [''],
            'scope_label': (scopes[0].get('label') if scopes
                            else company.name) or company.name,
            'scope_date': fields.Date.to_string(self._chain_date()),
            'kind_key': self._chain_kind_key(),
            'facts': self._chain_facts() or {},
            'amount': amount,
            'currency_id': currency.id if currency else False,
            'maker_uids': sorted(makers),
            'submitter_uid': self.env.uid,
            'subject_uids': [employee.user_id.id] if employee.user_id else [],
            'source_revision': self._approval_revision_of(
                self._chain_revision_values()),
            'evidence': [],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': self._chain_fact_specs(),
            'kinds': self._chain_kinds(),
            'evidence': [],
            'scope_levels': [_('Part of the business')],
            'manager_mode': True,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        rows = []
        for catalogue in SCOPE_CATALOGUES:
            try:
                rows += list(catalogue(self.env, company) or [])
            except Exception:   # noqa: BLE001 — the scan must never raise
                _logger.exception('approval: a scope catalogue failed')
        out = [{'scope_key': row['key'],
                'scope_keys': [row['key'], ''],
                'label': row.get('label') or '',
                'headcount': row.get('headcount') or 0,
                'kind_key': 'any', 'facts': {}}
               for row in rows if row.get('key')]
        if not out:
            out = [{'scope_key': '', 'scope_keys': [''],
                    'label': company.name, 'headcount': 0,
                    'kind_key': 'any', 'facts': {}}]
        return out

    def _approval_manager_uids(self):
        """"Their manager" is the manager of the person this is ABOUT.

        The generic answer maps `subject_uids` back through `hr.employee`,
        which needs the subject to have a login. Plenty of the people these
        requests are about have none (ledger AM50), and the record names the
        employee directly, so ask them.
        """
        self.ensure_one()
        if not self._chain_spec():
            return super()._approval_manager_uids()
        employee = self._chain_employee()
        manager = employee.sudo().parent_id.user_id
        return manager.ids

    def _approval_skip_manager_uids(self):
        self.ensure_one()
        if not self._chain_spec():
            return super()._approval_skip_manager_uids()
        employee = self._chain_employee()
        return employee.sudo().parent_id.parent_id.user_id.ids

    def _approval_validate(self):
        """The last moment before a request exists: may this be sent in?"""
        self.ensure_one()
        spec = self._chain_spec()
        if not spec:
            return super()._approval_validate()
        if self.state in spec['driven'] or self.state == spec['submit_state']:
            raise UserError(_("This has already been sent in."))
        if self.state in (self._approval_dead_states or ()):
            raise UserError(_("This one is closed, so it cannot be sent in."))
        if not super()._approval_can(self.state, spec['submit_state']):
            raise UserError(_("You are not allowed to send this in."))
        self._before_approval_transition(spec['submit_state'])
        return True

    def _approval_freeze(self, request):
        """It is in. Move the record's own status to say so."""
        self.ensure_one()
        spec = self._chain_spec()
        if not spec:
            return super()._approval_freeze(request)
        target = spec['submit_state']
        if self.state != target:
            frm = self.state
            self._chain_engine_write(target)
            self._after_approval_transition(target)
            self._chain_log(frm, target,
                            self.env.context.get('chain_note') or '')
        return True

    def _approval_advance(self, request):
        """A step was decided and the route goes on: follow it."""
        self.ensure_one()
        spec = self._chain_spec()
        if not spec:
            return super()._approval_advance(request)
        ladder = spec['intermediate']
        if not ladder:
            return True
        done = len(request.step_ids.filtered(
            lambda s: s.included and s.kind not in ('notify', 'fast')
            and s.status == 'done'))
        if done < 1:
            return True
        target = ladder[min(done, len(ladder)) - 1]
        if self.state in (target, spec['final_state']):
            return True
        frm = self.state
        self._before_approval_transition(target)
        self._chain_engine_write(target)
        self._after_approval_transition(target)
        self._chain_log(frm, target, '')
        return True

    def _approval_apply(self, request):
        """The whole route said yes: do what the last rung always did."""
        self.ensure_one()
        spec = self._chain_spec()
        if not spec:
            return super()._approval_apply(request)
        final = spec['final_state']
        if self.state == final:
            return True
        frm = self.state
        self._before_approval_transition(final)
        self._chain_engine_write(final)
        self._after_approval_transition(final)
        self._chain_log(frm, final, '')
        return True

    def _approval_return(self, request, reason):
        """Sent back: editable again, where it started."""
        self.ensure_one()
        spec = self._chain_spec()
        if not spec:
            return super()._approval_return(request, reason)
        target = spec['draft_state']
        if self.state != target:
            frm = self.state
            self._chain_engine_write(target)
            self._chain_log(frm, target, reason or '')
        return True

    def _approval_reject(self, request, reason):
        """Turned down for good."""
        self.ensure_one()
        spec = self._chain_spec()
        if not spec:
            return super()._approval_reject(request, reason)
        target = spec['refuse_state']
        if self.state != target:
            frm = self.state
            self._before_approval_transition(target)
            self._chain_engine_write(target)
            self._after_approval_transition(target)
            self._chain_log(frm, target, reason or '')
        return True

    def _approval_card_count(self, request):
        self.ensure_one()
        if not self._chain_spec():
            return super()._approval_card_count(request)
        employee = self._chain_employee()
        return employee.name or ''

    # ==================================================================
    # The buttons every consumer already has
    # ==================================================================
    def _advance_state(self, to_state, note=False):
        self.ensure_one()
        spec = self._chain_spec()
        if not spec or not self._engine_managed():
            return super()._advance_state(to_state, note)
        frm = self.state
        if (frm, to_state) not in self._approval_transitions:
            raise UserError(
                _("Illegal approval transition: %s → %s.", frm, to_state))
        if to_state in spec['reverse_to'] and frm != spec['draft_state']:
            return self._chain_decide('return', note or _("Sent back"))
        if to_state == spec['submit_state'] and frm not in spec['driven']:
            self.with_context(chain_note=note or '').action_approval_submit()
            return True
        if to_state in spec['driven']:
            return self._chain_decide('approve', note)
        # past the route's last rung — applying a pay change, closing it —
        # is the record's own business and always was
        return super()._advance_state(to_state, note)

    def action_refuse_chain(self, note=False):
        managed = self.filtered(
            lambda r: r._chain_spec() and r._engine_managed()
            and r._chain_open_request())
        for rec in managed:
            rec._chain_decide('reject', note or _("Turned down"))
        return super(BizApprovalChainShim, self - managed).action_refuse_chain(
            note)

    def _approval_can(self, from_state, to_state):
        self.ensure_one()
        spec = self._chain_spec()
        if not spec or not self._engine_managed():
            return super()._approval_can(from_state, to_state)
        if self.env.su or self.env.user._is_admin():
            return True
        if to_state == spec['submit_state'] and from_state not in spec['driven']:
            return super()._approval_can(from_state, to_state)
        if to_state in spec['driven'] or to_state in spec['reverse_to']:
            return bool(self._chain_my_seat())
        return super()._approval_can(from_state, to_state)

    def _approval_can_refuse(self, from_state):
        self.ensure_one()
        spec = self._chain_spec()
        if not spec or not self._engine_managed() \
                or not self._chain_open_request():
            return super()._approval_can_refuse(from_state)
        if self.env.su or self.env.user._is_admin():
            return True
        return bool(self._chain_my_seat())

    # ==================================================================
    # Talking to the engine
    # ==================================================================
    def _chain_open_request(self):
        self.ensure_one()
        request = self.approval_request_id
        return request if request and request.state in ('pending', 'blocked') \
            else self.env['biz.approval.request']

    def _chain_active_step(self):
        self.ensure_one()
        request = self._chain_open_request()
        if not request:
            return self.env['biz.approval.request.step']
        return request.step_ids.filtered(
            lambda s: s.status == 'active').sorted('sequence')[:1]

    def _chain_my_seat(self):
        self.ensure_one()
        step = self._chain_active_step()
        if not step:
            return self.env['biz.approval.request.seat']
        return step.sudo().seat_ids.filtered(
            lambda s: s.status == 'open'
            and s.acting_user_id.id == self.env.uid)[:1]

    def _chain_decide(self, action, note=False):
        """One press of a legacy button = one decision on the live route."""
        self.ensure_one()
        request = self._chain_open_request()
        if not request:
            raise UserError(_(
                "This has not been sent in for approval, so there is nothing "
                "to decide yet."))
        step = self._chain_active_step()
        if not step:
            raise UserError(_(
                "No step is waiting for a decision on this one."))
        self.env['biz.approval.engine'].decide(
            request.id, step.key, action, note or '')
        self.invalidate_recordset(['approval_request_id', 'approval_state'])
        return True

    def _chain_engine_write(self, state):
        """A state write the route asked for, so the guard below lets it by."""
        self.ensure_one()
        return self.with_context(**{ENGINE_WRITE: True})._chain_state_write(
            state)

    def _chain_log(self, from_state, to_state, note):
        """The consumer's own trail keeps its shape. Never fatal."""
        self.ensure_one()
        try:
            self._log_transition(from_state, to_state, note or False)
        except Exception:   # noqa: BLE001 — a trail row is not a decision
            _logger.exception('approval: %s could not log %s → %s',
                              self._name, from_state, to_state)
        return True

    # ------------------------------------------- nothing is left orphaned
    def write(self, vals):
        """Leaving the ladder by another door closes the open request.

        Cancel, withdraw, reset to draft, undo: six places across the eleven
        consumers write the status directly, and every one of them would have
        left a request sitting in somebody's inbox for a record that is no
        longer on the route.
        """
        if 'state' not in vals or self.env.context.get(ENGINE_WRITE):
            return super().write(vals)
        orphans = []
        for rec in self:
            if not rec._chain_spec() or vals['state'] == rec.state:
                continue
            request = rec._chain_open_request()
            if request:
                orphans.append((rec, request, rec.state, vals['state']))
        result = super().write(vals)
        for rec, request, was, now in orphans:
            rec._chain_close_request(request, was, now)
        return result

    def _chain_close_request(self, request, was, now):
        """Withdraw a request whose record has left the route.

        `sudo()` because the gate has already been passed: the person was
        allowed to write this status through a sanctioned action, and the
        request is bookkeeping that has to follow. It does not change who
        `env.uid` is, so the trail keeps their name.
        """
        self.ensure_one()
        label = dict(self._fields['state'].selection or []).get(now, now)
        try:
            self.env['biz.approval.engine'].sudo().cancel(
                request.id, _("Withdrawn from the record itself: %s", label))
        except Exception:   # noqa: BLE001 — the record has already moved
            _logger.exception('approval: %s could not close request %s',
                              self._name, request.id)
        self.invalidate_recordset(['approval_request_id', 'approval_state'])
        return True

    # ==================================================================
    # The trail on the form
    # ==================================================================
    def get_approval_trail(self):
        self.ensure_one()
        request = self.approval_request_id if self._chain_spec() else None
        if not request:
            return super().get_approval_trail()
        return self._chain_trail(request)

    def _chain_trail(self, request):
        rows = [{
            'from_state': '', 'to_state': '_sent',
            'user': request.submitter_uid.name or '',
            'user_id': request.submitter_uid.id,
            'avatar': '/web/image/res.users/%s/avatar_128'
                      % request.submitter_uid.id,
            'stamp': fields.Datetime.to_string(request.submitted_at),
            'note': '',
        }]
        for decision in request.sudo().decision_ids.sorted('stamp'):
            if decision.action == 'approve':
                to_state = 'step:%s' % (decision.step_key or '')
            elif decision.action == 'reject':
                to_state = '_stopped'
            elif decision.action == 'return':
                to_state = '_returned'
            elif decision.action == 'cancel':
                to_state = 'cancelled'
            else:
                continue
            rows.append({
                'from_state': '', 'to_state': to_state,
                'user': decision.user_id.name or '',
                'user_id': decision.user_id.id,
                'avatar': '/web/image/res.users/%s/avatar_128'
                          % decision.user_id.id,
                'stamp': fields.Datetime.to_string(decision.stamp),
                'note': decision.reason or '',
            })
        if request.state == 'applied':
            rows.append({
                'from_state': '', 'to_state': '_done',
                'user': '', 'user_id': 0, 'avatar': '',
                'stamp': fields.Datetime.to_string(request.closed_at),
                'note': '',
            })
        return rows

    def _approval_widget_payload(self, steps):
        """The stepper draws the route this record was really given."""
        self.ensure_one()
        request = self.approval_request_id if self._chain_spec() else None
        if not request:
            return super()._approval_widget_payload(steps)
        route = [{'state': '_sent', 'label': _('Sent in'),
                  'group_label': request.submitter_uid.name or ''}]
        for step in request.sudo().step_ids.sorted('sequence'):
            if not step.included:
                continue
            names = ', '.join(sorted({seat.acting_user_id.name or ''
                                      for seat in step.seat_ids})) or ''
            route.append({'state': 'step:%s' % step.key,
                          'label': step.title or '',
                          'group_label': names})
        route.append({'state': '_done', 'label': _('Approved'),
                      'group_label': ''})
        current = '_sent'
        active = request.step_ids.filtered(
            lambda s: s.status == 'active')[:1]
        if request.state in ('approved', 'applied'):
            current = '_done'
        elif request.state == 'rejected':
            current = '_stopped'
        elif request.state == 'returned':
            current = '_returned'
        elif request.state == 'cancelled':
            current = 'cancelled'
        elif active:
            current = 'step:%s' % active.key
        return json.dumps({
            'steps': route,
            'trail': self._chain_trail(request),
            'current': current,
            'dead_states': ['_stopped', '_returned', 'cancelled'],
        })


class BizApprovalRequestSeatChain(models.Model):
    """A seat on a chain consumer's request is also a read of it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            model = request.res_model
            if model not in CHAIN_PROCESS_KEYS or not request.res_id:
                continue
            if model not in self.env:
                continue
            record = self.env[model].sudo().browse(request.res_id).exists()
            if not record or 'seat_user_ids' not in record._fields:
                continue
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if people:
                record.with_context(**{ENGINE_WRITE: True}).write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats
