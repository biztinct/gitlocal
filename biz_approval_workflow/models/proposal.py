# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""A proposal: the write, written down, before anybody is allowed to do it.

WHY THIS IS IN THE ENGINE. Phases 3-6 gave a route to records that already
existed — a pay run, a leave, an asset request. Phase 7 is the other half of
the product: a couple of dozen doors whose press IS the change. There is no
record to approve because the record is created (or overwritten) by the press
itself. Every one of them needs the same object: something that holds WHAT WAS
ASKED FOR, WHAT THE WORLD LOOKED LIKE AT THE TIME, and nothing else, until
somebody says yes.

Written once here rather than thirteen times because the interesting parts —
the snapshot re-check, the "the last approver carries it out as themselves"
rule, the audit line, the fast lane — are exactly the parts that would drift.
The engine learns NO business meaning from it: `kind` and `payload` are opaque,
the facts come from the caller, and the apply is a method on the business
model.

THE THREE RAILS every proposal inherits

1. **The snapshot.** `_live_snapshot()` re-reads the values the proposal is
   about, from the world, at apply time. If they have moved since the proposal
   was made, nothing is written and the difference is NAMED. (A stamp that is
   read back off the proposal's own stored copy would always equal itself —
   ledger AM46.)
2. **The gate.** The final approver performs the write AS THEMSELVES
   (safety rail 5, ledger AM54). A proposal declares the permission the
   original door required, and a person who does not hold it gets a refusal
   naming it rather than a write they were never allowed to make.
3. **The trail.** One `biz.audit.entry` per carried-out proposal, so "who said
   yes to this?" is answerable from the platform-wide trail and not only from
   the approvals screens. Never raises: a trail line that could not be written
   must not un-write the change.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

#: Every concrete proposal model in the registry, filled by `_register_hook`.
#: The seat bridge at the bottom of this file needs to know which requests are
#: about a proposal, and asking the registry is the only honest answer — a
#: module-level list written by hand goes stale the first time somebody adds an
#: adapter and forgets.
PROPOSAL_MODELS = set()

STATES = [
    ('draft', 'Being prepared'),
    ('pending', 'Waiting for approval'),
    ('applied', 'Carried out'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
]


#: What `json.dumps` can hold without help. Anything else is written down as
#: the words a person would read — which is also what makes a stored snapshot
#: and a re-read one COMPARABLE: a date read back off the world is a `date`
#: object, and the one in the proposal came through JSON as a string, so
#: without this every date would look as if somebody had moved it.
_JSONABLE = (str, int, float, bool)


def _plain(value):
    """A value in a form a human reads and a hash can be taken of."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in sorted(value.items())}
    if value is None or value is False:
        return ''
    if isinstance(value, _JSONABLE):
        return value
    return str(value)


class BizApprovalProposalMixin(models.AbstractModel):
    _name = 'biz.approval.proposal.mixin'
    _inherit = ['biz.approval.adapter.mixin']
    _description = 'Approval Proposal'
    _order = 'id desc'
    _rec_name = 'name'

    # ------------------------------------------------------- what to set up
    #: Letters in front of the reference a reader quotes back at you.
    _proposal_prefix = 'PR'
    #: kind key -> the words a person reads. Also the catalogue's kind list.
    _proposal_kind_labels = {}
    #: The facts a workflow may condition on, `{key: {'type', 'label'}}`.
    _proposal_fact_specs = {}
    #: Group xml ids the ORIGINAL door required. The last approver must hold
    #: one of them, because they are the one who performs the write.
    _proposal_gate_groups = ()
    #: May a route for this kind of proposal name "their manager"?
    #:
    #: FALSE by default, and that is a real answer rather than a shrug: most
    #: proposals are about a RATE, a BAND or a CUSTOMER and have no person for
    #: a manager to be the manager OF. A proposal that is about somebody sets
    #: this True and overrides `_approval_manager_uids` to say who — and if it
    #: does not, `validate_for_publish` refuses the route rather than letting a
    #: step resolve to nobody.
    _proposal_manager_mode = False

    # ------------------------------------------------------------- the row
    name = fields.Char(string='Reference', readonly=True, copy=False,
                       default='/')
    kind = fields.Char(string='What is being asked for', required=True,
                       readonly=True, index=True)
    title_text = fields.Char(string='Headline', readonly=True)
    payload_json = fields.Text(string='What was asked for (JSON)',
                               readonly=True)
    snapshot_json = fields.Text(string='How it looked at the time (JSON)',
                                readonly=True)
    facts_json = fields.Text(string='Facts (JSON)', readonly=True)
    scope_json = fields.Text(string='Where it applies (JSON)', readonly=True)
    #: Who it is ABOUT, as a plain list of user ids. Stored rather than passed
    #: through the context because the engine re-reads `_approval_context()` at
    #: apply time, off a fresh browse, where a context is long gone.
    subject_json = fields.Text(string='Who it is about (JSON)', readonly=True)
    amount = fields.Monetary(string='What it is worth', readonly=True,
                             currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency', readonly=True,
        default=lambda s: s.env.company.currency_id)
    scope_label = fields.Char(string='Where', readonly=True)
    note = fields.Text(string='Why', readonly=True)
    #: The record this proposal is about, when there is one already. A create
    #: has none, which is exactly why a proposal exists.
    target_model = fields.Char(string='About which kind of record',
                               readonly=True)
    target_id = fields.Integer(string='About which record', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', index=True,
                                 required=True,
                                 default=lambda s: s.env.company)
    user_id = fields.Many2one('res.users', string='Asked by', readonly=True,
                              default=lambda s: s.env.user, index=True)
    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)
    applied = fields.Boolean(string='Carried out', readonly=True, copy=False)
    applied_at = fields.Datetime(readonly=True, copy=False)
    block_note = fields.Text(string='Why it could not be carried out',
                             readonly=True, copy=False)
    result_json = fields.Text(string='What happened (JSON)', readonly=True,
                              copy=False)
    #: A seat is also a read (ledger AM60). Declared once here; Odoo gives
    #: every concrete model its own relation table (ledger AM92). The record
    #: RULE still has to be shipped per module — a rule names one model.
    seat_user_ids = fields.Many2many(
        'res.users', string='Asked to decide', copy=False)

    def _register_hook(self):
        PROPOSAL_MODELS.add(self._name)
        return super()._register_hook()

    # ==================================================================
    # Reading what is in it
    # ==================================================================
    def _json(self, field, default):
        self.ensure_one()
        try:
            value = json.loads(getattr(self, field) or 'null')
        except (TypeError, ValueError):
            return default
        return value if isinstance(value, type(default)) else default

    def payload(self):
        return self._json('payload_json', {})

    def snapshot(self):
        return self._json('snapshot_json', {})

    def facts(self):
        return self._json('facts_json', {})

    def scope_keys(self):
        keys = self._json('scope_json', [])
        return [str(k) for k in keys] or ['']

    def result(self):
        return self._json('result_json', {})

    # ==================================================================
    # Is anybody actually checking this?
    # ==================================================================
    @api.model
    def route_mode(self, company=None, kind_key=None, scope_keys=None):
        """``'none'``, ``'fast'`` or ``'route'`` for this kind of proposal.

        Most doors do not need this: they write the proposal down and let the
        engine decide, because a fast lane applies inside the same call and the
        answer looks exactly as it always did. The doors that DO need it are
        the ones hooked into a plain ``write()`` — a proposal there would have
        to return True for a change that has not happened, so where nobody is
        checking, the write is left alone entirely.

        ``'none'`` means the company has no route at all. That is NOT the same
        as a fast lane (ledger AM73) — but for a `write` hook it has to behave
        like one, because refusing every edit on a database that has never
        heard of this process would be a gate nobody asked for.
        """
        company = company or self.env.company
        process = self.env['biz.approval.process']._by_key(
            self._approval_process_key)
        if not process:
            return 'none'
        engine = self.env['biz.approval.engine'].sudo()
        binding, version, _trace, error = engine._resolve_binding(
            company, process, list(scope_keys or ['']), kind_key or 'any')
        if error or not version:
            return 'none'
        steps = (version.definition or {}).get('steps') or []
        live = [s for s in steps if s.get('kind') != 'notify']
        if not live or any(s.get('kind') == 'fast' for s in live):
            return 'fast'
        return 'route'

    @api.model
    def precheck(self, record, vals):
        """Let the RECORD refuse bad values before they become a request.

        A `write` hook that proposes instead of writing takes the ORM's own
        constraints out of the path: a schedule of "day 31", a rate of -5, a
        band whose bottom is above its top would all be written down, sent to
        somebody, agreed to, and only blow up at apply time — in front of the
        approver, about a mistake the person who typed it should have been
        told about at once.

        So the values are applied to an IN-MEMORY copy of the record and the
        model's own `@api.constrains` are run against it. Nothing is written,
        nothing is rolled back, and there is no second copy of the rule.
        """
        if not record or not vals:
            return True
        try:
            draft = record[:1].new(dict(vals), origin=record[:1])
            draft._validate_fields(list(vals))
        except (ValidationError, UserError):
            raise
        except Exception:       # noqa: BLE001 — a check must not invent a fault
            _logger.debug('proposal precheck could not run on %s',
                          record._name, exc_info=True)
        return True

    # ==================================================================
    # Making one
    # ==================================================================
    @api.model
    def propose(self, kind, title, payload, snapshot=None, facts=None,
                scope_keys=None, scope_label='', target=None, company=None,
                note='', subject_uids=None, amount=0.0):
        """Write the change down and ask for it. Nothing else happens here.

        Under a published "No approval needed" route the engine carries it out
        inside this very call and the answer says so — which is how a fast lane
        gives a business back the press it had, with a record of every use.

        `sudo()` here is the engine's own bookkeeping, not the business change:
        the DOOR that calls this has already checked the permission its screen
        always required, and `_approval_apply` checks it AGAIN against whoever
        finally approves. What sudo must never do is make the change itself
        possible, and it does not — `_apply_payload` runs as the real person.
        """
        company = company or self.env.company
        record = self.sudo().create({
            'kind': kind,
            'title_text': (title or '')[:200],
            'payload_json': json.dumps(_plain(payload or {}),
                                       sort_keys=True, default=str),
            'snapshot_json': json.dumps(_plain(snapshot or {}),
                                        sort_keys=True, default=str),
            'facts_json': json.dumps(facts or {}, default=str),
            'scope_json': json.dumps([str(k) for k in (scope_keys or [''])]),
            'subject_json': json.dumps(
                sorted({int(u) for u in (subject_uids or []) if u})),
            'scope_label': (scope_label or company.name or '')[:120],
            'note': (note or '').strip() or False,
            'target_model': target._name if target is not None and target
                            else False,
            'target_id': target.id if target is not None and target else 0,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'amount': float(amount or 0.0),
            'user_id': self.env.uid,
        })
        record.name = '%s%05d' % (self._proposal_prefix, record.id)
        self.env['biz.approval.engine'].sudo().submit(record)
        record.invalidate_recordset()
        return record

    def answer(self):
        """The shape every door in Phase 7 hands back to its screen."""
        self.ensure_one()
        request = self.approval_request_id
        return {
            'ok': True,
            'proposal_id': self.id,
            'reference': self.name,
            'kind': self.kind,
            'state': self.state,
            'applied': bool(self.applied),
            'pending': not self.applied and self.state == 'pending',
            'request_id': request.id if request else 0,
            'with_whom': self.waiting_for(),
            'route': self.route_labels(),
            'block_note': self.block_note or '',
            # THE ONE SENTENCE EVERY SCREEN PRINTS. A door that returns a
            # proposal and a screen that still says "Policy created" is the
            # worst kind of lie a control can tell — it is confident and it is
            # wrong. The server says what happened, once, in words, so no
            # screen has to work it out from an id that came back zero.
            'message': self.answer_message(),
            # What the app wants to say about who was asked — a backup taking
            # a seat because the holder sent it in, or nobody being able to
            # approve it yet. Warnings, never refusals.
            'notes': [note.get('msg') or '' for note in
                      (request.seat_notes or []) if request],
            'result': self.result(),
        }

    def answer_message(self):
        """What the screen says back, in one sentence.

        Three outcomes and three sentences, because a single "if not ok"
        branch always lies to one of them (ledger AM78).
        """
        self.ensure_one()
        if self.applied:
            return _("%s — done.", self._proposal_kind_label())
        if self.block_note:
            return _("%(what)s was approved but could not be carried out: "
                     "%(why)s", what=self._proposal_kind_label(),
                     why=self.block_note)
        who = self.waiting_for()
        if who:
            return _("Sent for approval — %s", who)
        return _("Sent for approval.")

    def waiting_for(self):
        """Whose desk this is on right now, in names."""
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(
            lambda s: s.key == request.current_step_key)[:1]
        names = sorted({seat.acting_user_id.name or ''
                        for seat in step.seat_ids if seat.status == 'open'})
        return ', '.join(n for n in names if n)

    def route_labels(self):
        """The steps this has to pass, in order, with their people."""
        self.ensure_one()
        request = self.approval_request_id
        if not request:
            return []
        out = []
        for step in request.step_ids.sorted('sequence'):
            if not step.included or step.kind == 'fast':
                continue
            out.append({
                'title': step.title,
                'status': step.status,
                'people': sorted({seat.acting_user_id.name or ''
                                  for seat in step.seat_ids}),
            })
        return out

    # ==================================================================
    # The adapter contract
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.applied:
            raise UserError(_("This has already been carried out."))
        if self.state == 'pending':
            raise UserError(_("This has already been sent in."))
        return True

    def _proposal_kind_label(self, kind=None):
        labels = self._proposal_kind_labels or {}
        return labels.get(kind or self.kind) or (kind or self.kind or '')

    def _proposal_headline(self):
        self.ensure_one()
        return self.title_text or self._proposal_kind_label()

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        facts = dict(self.facts() or {})
        facts.setdefault('kind', {'value': self.kind or '', 'unit': ''})
        return {
            'company_id': company.id,
            'title': self._proposal_headline(),
            'scope_keys': self.scope_keys(),
            'scope_label': self.scope_label or company.name,
            'kind_key': self.kind or 'any',
            'facts': facts,
            'amount': float(self.amount or 0.0),
            'currency_id': (self.currency_id or company.currency_id).id,
            'maker_uids': [self.user_id.id] if self.user_id else [],
            'submitter_uid': self.env.uid,
            'subject_uids': [int(u) for u in self._json('subject_json', [])],
            # The PAYLOAD is what everybody in the route agrees to, and it
            # never moves — so it is what the stamp covers. What the world
            # looked like is checked by name at apply time instead, because
            # "somebody changed this underneath you" deserves a sentence that
            # says WHICH value moved (ledger AM32/AM46/AM76).
            'source_revision': self._approval_revision_of(self.payload()),
            'evidence': [{
                'key': 'reason_given', 'name': _('A reason was written down'),
                'ok': bool((self.note or '').strip()),
                'note': (self.note or '')[:240]}],
        }

    @api.model
    def _approval_capabilities(self):
        specs = dict(self._proposal_fact_specs or {})
        specs.setdefault('kind', {'type': 'selection',
                                  'label': _('What is being asked for')})
        return {
            'facts': specs,
            'kinds': [{'key': key, 'label': label}
                      for key, label in sorted(
                          (self._proposal_kind_labels or {}).items())],
            'evidence': [{'key': 'reason_given',
                          'label': _('A reason was written down')}],
            'scope_levels': [_('Whole company')],
            'manager_mode': bool(self._proposal_manager_mode),
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        return self._proposal_kind_label()

    def _proposal_rows(self):
        """What would change, in the words a person reads.

        THE PAYLOAD IS NOT A SCREEN. It is the exact call the door would have
        made — `{'args': {...}, 'tenant_ids': [3], 'typed': 'canaryco'}` — and
        printing its keys gave an approver rows reading "args · 3 item(s)" and
        "values · 12 item(s)". That is not a description of a decision; it is
        a dump of an implementation, and an approver who cannot read what they
        are agreeing to should not be agreeing to it.

        Every concrete proposal answers this per `kind`, as a list of
        ``(label, before, after)`` — `before` empty where there is nothing to
        compare, which is most creates. The default is EMPTY on purpose: a
        proposal that has not said what it is about shows its chips and its
        reason and nothing else, rather than showing the wiring.
        """
        self.ensure_one()
        return []

    def _approval_detail(self, request):
        """The drawer's small table: plain words, never the payload."""
        self.ensure_one()
        rows = []
        for row in (self._proposal_rows() or [])[:40]:
            label, before, after = (list(row) + ['', ''])[:3]
            rows.append({
                'head': str(label)[:60],
                'sub': '',
                'cells': ['' if before in (None, False) else str(before)[:60],
                          '' if after in (None, False) else str(after)[:60]],
                'tone': 'on',
            })
        chips = [{'label': _('What'), 'value': self._proposal_kind_label()}]
        if self.scope_label:
            chips.append({'label': _('Where'), 'value': self.scope_label})
        if self.user_id:
            chips.append({'label': _('Asked by'), 'value': self.user_id.name})
        return {
            'title': _('What would change'),
            'columns': [_('Now'), _('Proposed')] if any(
                r['cells'][0] for r in rows) else ['', _('Proposed')],
            'rows': rows,
            'chips': chips,
            'note': self.note or '',
        }

    # -------------------------------------------------- a helper for rows
    def _row_label(self, model, res_id, fallback=''):
        """A record's own name, or a plain word when it has gone."""
        self.ensure_one()
        if not res_id or model not in self.env:
            return fallback
        record = self.env[model].sudo().browse(int(res_id)).exists()
        return record.display_name if record else fallback

    # -------------------------------------------------------- transitions
    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending', 'block_note': False})
        return True

    def _approval_return(self, request, reason):
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        self.sudo().write({'state': 'rejected'})
        return True

    # ==================================================================
    # Carrying it out
    # ==================================================================
    def _live_snapshot(self):
        """The values this proposal is about, re-read from the world NOW.

        The default is "nothing to compare" — right for a proposal that
        CREATES something, where there is no before. Anything that overwrites
        an existing value must override this, or the rail is decoration.
        """
        self.ensure_one()
        return {}

    def _proposal_moved(self):
        """Which values somebody else has moved since this was proposed."""
        self.ensure_one()
        before = self.snapshot() or {}
        now = _plain(self._live_snapshot() or {})
        moved = []
        for key in sorted(set(before) | set(now)):
            was, is_now = before.get(key), now.get(key)
            if was != is_now:
                moved.append(_("%(what)s (was %(was)s, now %(now)s)",
                               what=key,
                               was='—' if was in (None, '') else was,
                               now='—' if is_now in (None, '') else is_now))
        return moved

    def _proposal_gate_xmlids(self):
        """The permission the original door required, for THIS kind."""
        self.ensure_one()
        return tuple(self._proposal_gate_groups or ())

    def _proposal_check_gate(self):
        """The last approver performs the write as themselves (rail 5)."""
        self.ensure_one()
        xmlids = self._proposal_gate_xmlids()
        if not xmlids:
            return True
        user = self.env.user
        # Deliberately NOT `env.su`: a proposal is written down under sudo (the
        # engine's own bookkeeping) and the fast lane then applies it inside
        # that same call, so `env.su` would wave the gate through on exactly
        # the path that needs it. `env.user` is the real person either way.
        if user._is_superuser() or any(user.has_group(x) for x in xmlids):
            return True
        names = []
        for xmlid in xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                names.append(group.display_name or group.name or '')
        raise UserError(_(
            "%(who)s is allowed to approve this but not to carry it out — "
            "that needs %(what)s. Hand this step to somebody who has it, or "
            "ask for the permission to be added.",
            who=user.name,
            what=' / '.join(n for n in names if n) or _('another permission')))

    def _apply_payload(self):
        """Do the thing. Dispatched on `kind`, so a module adds a door by
        adding one `_apply_<kind>` method and nothing else."""
        self.ensure_one()
        handler = getattr(self, '_apply_%s' % (self.kind or ''), None)
        if handler is None:
            raise UserError(_(
                "This kind of request cannot be carried out on its own yet."))
        return handler() or {}

    def _approval_apply(self, request):
        self.ensure_one()
        if self.applied:
            return True
        moved = self._proposal_moved()
        if moved:
            shown = '; '.join(moved[:4])
            more = _(" and %s more", len(moved) - 4) if len(moved) > 4 else ''
            self.sudo().write({'block_note': _(
                "Nothing was changed: %(what)s%(more)s.",
                what=shown, more=more)})
            raise UserError(_(
                "Nothing was changed. Somebody else has already changed this "
                "since it was proposed: %(what)s%(more)s. Send it back and "
                "propose it again against what is there now.",
                what=shown, more=more))
        self._proposal_check_gate()
        result = self._apply_payload()
        self.sudo().write({
            'applied': True,
            'applied_at': fields.Datetime.now(),
            'state': 'applied',
            'result_json': json.dumps(_plain(result or {}), default=str),
            'block_note': False,
        })
        self._proposal_audit(request)
        return True

    def _proposal_audit(self, request):
        """One line in the platform-wide trail. Never raises."""
        self.ensure_one()
        Entry = self.env.get('biz.audit.entry')
        if Entry is None:
            return False
        try:
            Entry.sudo().create({
                'model_name': self.target_model or self._name,
                'res_id': self.target_id or self.id,
                'res_display': self._proposal_headline()[:120],
                'field_name': 'approved_change',
                'field_label': self._proposal_kind_label(),
                'old_value': _('Proposed by %s', self.user_id.name or '')[:256],
                'new_value': _('Approved as %(ref)s', ref=self.name)[:256],
                'company_id': (self.company_id or self.env.company).id,
            })
        except Exception:       # noqa: BLE001 — a trail must never undo a write
            _logger.exception('proposal audit failed for %s', self)
        return True


class BizApprovalRequestSeatProposal(models.Model):
    """A seat on a proposal is also a permission to READ it (AM60/AM96)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            model = request.res_model
            if model not in PROPOSAL_MODELS or not request.res_id:
                continue
            if model not in self.env:
                continue
            record = self.env[model].sudo().browse(request.res_id).exists()
            if not record or 'seat_user_ids' not in record._fields:
                continue
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if people:
                record.write({
                    'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats
