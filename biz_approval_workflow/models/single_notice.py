# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""One message per event, one owner per message (WORKFLOW-2 P2b, D5/D6).

WHAT WAS TRUE BEFORE. When an Approval Matrix route is live, the engine tells
each approver "Your approval is needed" (a message and a to-do on the request,
`engine._activate_next`). Several areas ALSO told the same person with a to-do
or an email of their own (pay changes, overtime, contract extensions, org chart
plans, goals, time off). And for a few areas the person who asked heard
"approved / turned down" twice: once from the area, once from the engine.

WHAT IS TRUE NOW. Two questions, asked the same way everywhere:

* `tells_approver(record, user)` — has the engine queued its own "your turn"
  for THIS person on the step that is waiting right now? True only when that
  is proven (a queued or sent outbox row with that step's dedupe key), the
  engine's delivery job is switched on and the switch below is on. When in
  doubt the answer is False and the area sends exactly what it sent before.
* `notify_unless_told(record, users, send, ...)` — the guard an area wraps
  around its own send. People the engine tells are skipped; everybody else
  gets the area's message exactly as before. Called while the engine has not
  opened its step yet — the area's hook runs INSIDE `submit` (the record's
  status moves before the steps exist), or just BEFORE it (the area sends,
  then asks the engine) — the decision waits until `submit` has finished
  (`single_notice_flush`), when the engine's rows exist. If anything goes
  wrong there, everybody is sent the area's message.

WHY NOT AT THE END OF THE TRANSACTION. A pre-commit hook looked natural and is
wrong: every flushing savepoint runs the pre-commit hooks early (a goal sheet's
own paperwork runs inside savepoints while it is being sent in), and a rolled
back savepoint clears them. The waiting list below lives beside the cursor and
is emptied at the two moments that are certain: the end of `submit`, and the
area's own flush right after it asked the engine.

THE KILL SWITCH. System parameter `biz_approval.single_notice`: absent or "1"
means on; "0" restores the behaviour from before this phase everywhere, with
no deploy and no restart (it is read on every call).

Nothing here deletes or rewrites a message. Removing a guard restores the old
send line for line.
"""

import logging
import weakref

from odoo import api, models

_logger = logging.getLogger(__name__)

SINGLE_NOTICE_PARAM = 'biz_approval.single_notice'
_OFF_WORDS = ('0', 'false', 'off', 'no')

#: cursor -> {'submitting': {(model, id): depth}, 'items': [(key, item)]}
#: Lives exactly as long as the cursor; nothing here outlives a request.
_WAITING = weakref.WeakKeyDictionary()


def _waiting(cr):
    state = _WAITING.get(cr)
    if state is None:
        state = _WAITING[cr] = {'submitting': {}, 'items': []}
    return state


class BizApprovalEngineSingleNotice(models.AbstractModel):
    _inherit = 'biz.approval.engine'

    # ----------------------------------------------------------- the switch
    @api.model
    def _single_notice_switch(self):
        """The owner's switch alone (no delivery check)."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            SINGLE_NOTICE_PARAM)
        if raw in (None, False):
            return True
        return str(raw).strip().lower() not in _OFF_WORDS

    @api.model
    def _single_notice_on(self):
        """On, AND the engine really delivers what it queues.

        A database whose "Approvals: tell the people who are waiting" job is
        switched off (the demo site, the template) queues the engine's notices
        and never delivers them: there, the areas' own messages are the only
        ones anybody gets, so nothing may be skipped.
        """
        if not self._single_notice_switch():
            return False
        cron = self.env.ref('biz_approval_workflow.cron_outbox',
                            raise_if_not_found=False)
        return bool(cron and cron.sudo().active)

    # --------------------------------------------------------- the question
    @api.model
    def _latest_request(self, record):
        return self.env['biz.approval.request'].sudo().search([
            ('res_model', '=', record._name), ('res_id', '=', record.id),
        ], order='attempt desc, id desc', limit=1)

    @api.model
    def _waiting_step(self, request):
        if not request or request.state != 'pending':
            return request.env['biz.approval.request.step']
        return request.step_ids.filtered(
            lambda s: s.status == 'active').sorted('sequence')[:1]

    @api.model
    def _route_live(self, record):
        """Is an Approval Matrix route bound for this record's company?"""
        try:
            if hasattr(record, '_engine_managed'):
                return bool(record._engine_managed())
            process = record._approval_process()
            company = record.company_id[:1] if 'company_id' in record._fields \
                and record.company_id else self.env.company
            return bool(self.env['biz.approval.binding'].sudo().search_count([
                ('company_id', '=', company.id),
                ('process_id', '=', process.id), ('active', '=', True)]))
        except Exception:   # noqa: BLE001 — a question must never raise
            _logger.exception('single notice: could not tell whether %s has '
                              'a route', record)
            return False

    @api.model
    def tells_approver(self, record, user=None):
        """True only when the engine's own notice to `user` is proven.

        Proven = the record's latest request is waiting for a decision, its
        route is still bound, and the outbox holds a "your turn" for exactly
        this person on exactly the step that is waiting (the dedupe key
        `_activate_next` writes), not given up on. Without `user`: the step
        that is waiting has told at least one person.
        """
        if not record or not self._single_notice_on():
            return False
        request = self._latest_request(record)
        step = self._waiting_step(request)
        if not step:
            return False
        if request.binding_id and not request.binding_id.active:
            return False
        Outbox = self.env['biz.approval.outbox'].sudo()
        prefix = 'your_turn-%s-%s-' % (request.id, step.id)
        if user is None:
            return bool(Outbox.search_count([
                ('dedupe_key', '=like', prefix + '%'),
                ('state', 'in', ('queued', 'sent'))]))
        return bool(Outbox.search_count([
            ('dedupe_key', '=', prefix + str(user.id)),
            ('user_id', '=', user.id),
            ('state', 'in', ('queued', 'sent'))]))

    @api.model
    def told_by_engine(self, record, users):
        """The part of `users` the engine already tells (see above).

        Never raises: on any failure nobody counts as told, so the area
        sends to everyone, as before.
        """
        empty = self.env['res.users']
        try:
            users = users.sudo().exists() if users else empty
            if not users:
                return empty
            return users.filtered(lambda u: self.tells_approver(record, u))
        except Exception:   # noqa: BLE001 — when in doubt, send
            _logger.exception('single notice: could not tell who the engine '
                              'asks on %s', record)
            return empty

    # ------------------------------------------------------------- the guard
    @api.model
    def notify_unless_told(self, record, users, send, submitting=False,
                           live=None, what='', always=False):
        """Send the area's own approver message to everyone the engine does not.

        `users`  — the people the area would message (res.users).
        `send`   — callable(users) that performs the area's original send for
                   exactly those people.
        `submitting` — the area sends this just BEFORE it asks the engine, and
                   promises to call `single_notice_flush(record)` right after
                   (whether or not the engine was asked).
        `live`   — the area's own answer to "is a route bound"; asked here
                   when not given.
        `always` — call `send` even when everybody was told (with an empty
                   recordset), for a send that also tidies up after itself.

        Never raises: a failure anywhere means everybody gets the area's
        message, which is what happened before this phase.
        """
        users = users.sudo().exists() if users else users
        if not users:
            return None
        try:
            if not self._single_notice_on():
                return send(users)
            if live is None:
                live = self._route_live(record)
            if not live:
                return send(users)
            request = self._latest_request(record)
            if self._waiting_step(request):
                # the engine has already opened the step it tells people about
                return self._send_rest(record, users, send, what, always)
            key = (record._name, record.id)
            state = _waiting(self.env.cr)
            if submitting or key in state['submitting']:
                # the engine is about to be asked, or is half-way through
                # `submit`: decide once it has finished
                state['items'].append((key, (record, users, send, what,
                                             always)))
                return None
        except Exception:   # noqa: BLE001
            _logger.exception('single notice: deciding %s failed; sending '
                              'the area message to everyone', what or record)
        return send(users)

    @api.model
    def single_notice_flush(self, record):
        """Decide every area message waiting on `record` (see above). Never
        raises; called at the end of `submit` and by an area right after it
        asked the engine."""
        state = _WAITING.get(self.env.cr)
        if not state or not state['items'] or not record:
            return None
        key = (record._name, record.id)
        mine = [item for k, item in state['items'] if k == key]
        if not mine:
            return None
        state['items'] = [(k, item) for k, item in state['items'] if k != key]
        for rec, users, send, what, always in mine:
            try:
                if not rec.exists():
                    continue
                self._send_rest(rec, users, send, what, always)
            except Exception:   # noqa: BLE001 — when in doubt, send
                _logger.exception('single notice: deciding %s failed; sending '
                                  'the area message to everyone', what or rec)
                try:
                    send(users)
                except Exception:   # noqa: BLE001
                    _logger.exception('single notice: the area message for '
                                      '%s could not be sent', what or rec)
        return None

    @api.model
    def submit(self, record, res_id=None, idempotency_key=None):
        """The engine's own submit, then the area messages that waited for
        its steps (an area's status hook runs inside it, before the steps
        exist)."""
        target = self._as_record(record, res_id) \
            if not isinstance(record, models.BaseModel) else record
        key = (target._name, target.id) if target else None
        state = _waiting(self.env.cr)
        if key:
            state['submitting'][key] = state['submitting'].get(key, 0) + 1
        try:
            return super().submit(record, res_id=res_id,
                                  idempotency_key=idempotency_key)
        finally:
            if key:
                depth = state['submitting'].get(key, 1) - 1
                if depth > 0:
                    state['submitting'][key] = depth
                else:
                    state['submitting'].pop(key, None)
                    self.single_notice_flush(target)

    @api.model
    def _send_rest(self, record, users, send, what='', always=False):
        told = self.told_by_engine(record, users)
        rest = users - told
        if told:
            _logger.info('single notice: %s — %s already told by the approval '
                         'engine (user ids %s); the area message is not sent '
                         'to them', what or record, len(told), told.ids)
        if rest or always:
            return send(rest)
        return None

    # ------------------------------------------------ the requester (D6)
    @api.model
    def _area_tells_requester(self, request, record, result):
        """Does the area itself tell the requester about `result`?

        A model declares the results it tells the person who asked:
        ``_approval_requester_notice = ('approved', 'rejected')``. The engine
        then leaves its own copy out — but only when the person who sent it
        in IS the person the area writes to (the person it is about), and the
        record says it really will write (`_approval_area_tells_requester`).
        Anything else, and the engine's notice goes out as before.
        """
        try:
            if not record or not self._single_notice_switch():
                return False
            results = getattr(record, '_approval_requester_notice', None) \
                or ()
            if result not in results:
                return False
            submitter = request.submitter_uid
            if not submitter or submitter.id not in (request.subject_uids
                                                     or []):
                return False
            hook = getattr(record, '_approval_area_tells_requester', None)
            if hook is not None and not hook(request, result):
                return False
            return True
        except Exception:   # noqa: BLE001 — when in doubt, the engine tells
            _logger.exception('single notice: requester check on %s failed',
                              record)
            return False
