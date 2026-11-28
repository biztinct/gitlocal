# -*- coding: utf-8 -*-
"""The chat session learns which screens (⌘K rows) its person may open.

THE DOORS COME FROM THE BROWSER, AND THAT IS ACCEPTABLE FOR WHAT THEY DO.
The ⌘K registry lives in the client (37 modules' `*_palette.js`), already
filtered for this person by `hub_palette_service.entries()`. The chat sends
those rows here when it mounts; `open_screen` resolves the person's words
against them and answers with a row id the client then runs through the very
code path ⌘K uses. Opening a screen is navigation: every screen still asks
its own server-side questions. The server re-checks each row's `groups`
anyway (defence in depth, P1_HANDOVER) and never builds anything but a
navigation out of a row.
"""
import json
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..payai import gate, runner
from ..payai.i18n import reset_lang, set_lang

from ..payai.resolve import DOOR_KINDS

_logger = logging.getLogger(__name__)

MAX_DOORS = 600
_TEXT_CAP = 120


def _clean_str(value, cap=_TEXT_CAP):
    if not isinstance(value, str):
        return ''
    return ' '.join(value.split())[:cap]


def _clean_target(value):
    """FIX-1b — where a ⌘K row leads, by identifier only (its action's tag,
    xmlid, lens, focus): what the deny-list matches on besides the row id.
    Never a destination PayAI builds from — a door still runs only through
    the client's own palette (PA19)."""
    if not isinstance(value, dict):
        return {}
    out = {}
    for key in ('tag', 'xmlid', 'lens', 'focus'):
        text = _clean_str(value.get(key), 120)
        if text:
            out[key] = text
    return out


class PayrollAIConversation(models.Model):
    _inherit = 'payroll.ai.conversation'

    payai_doors_json = fields.Text(
        string='Screens this person may open',
        help="JSON list of the ⌘K rows the person's browser offered: id, "
             "label, where it lives and the permissions it names.")

    @api.model
    def rpc_register_doors(self, session_id=None, rows=None):
        """Store the person's visible ⌘K rows on their own conversation."""
        session = self.browse(int(session_id)).exists() if session_id else self.browse()
        if not session or session.user_id != self.env.user:
            session = self.get_or_create_session()
        clean = []
        seen = set()
        for row in (rows or [])[:MAX_DOORS]:
            if not isinstance(row, dict):
                continue
            rid = _clean_str(row.get('id'), 80)
            if not rid or rid in seen or rid == 'payai_ask':
                continue
            if row.get('restricted'):
                continue
            target = _clean_target(row.get('target'))
            # FIX-1b (owner ruling 2026-10-13): a door into Settings › Access
            # and delegations is never stored, so PayAI can never open it.
            if gate.door_denied({'id': rid, 'target': target}):
                continue
            seen.add(rid)
            groups = [g for g in (row.get('groups') or [])
                      if isinstance(g, str) and '.' in g][:12]
            entry = {
                'id': rid,
                'label': _clean_str(row.get('label')),
                'sublabel': _clean_str(row.get('sublabel')),
                'group': _clean_str(row.get('group'), 60),
                'groups': groups,
                # P2-F1 — ranking only (a lens before a deep link before a
                # lesson); never a permission, never a destination.
                'kind': row.get('kind') if row.get('kind') in DOOR_KINDS else '',
            }
            # GAPS (4b): the row's words as written in the code (English),
            # so the door can be shown in the reader's language — display
            # only, never matched as a permission or a destination.
            for key in ('label', 'sublabel'):
                src = _clean_str(row.get('%s_src' % key))
                if src and src != entry[key]:
                    entry['%s_src' % key] = src
            if target:
                entry['target'] = target
            clean.append(entry)
        blob = json.dumps(clean, ensure_ascii=False)
        if session.payai_doors_json != blob:
            session.write({'payai_doors_json': blob})
        return {'session_id': session.id, 'count': len(clean)}

    def payai_doors(self):
        """The registered rows, or [] on any shape problem."""
        self.ensure_one()
        try:
            rows = json.loads(self.payai_doors_json or '[]')
        except (TypeError, ValueError):
            return []
        # FIX-1b: rows stored before the deny-list existed are dropped here.
        return [r for r in rows if isinstance(r, dict) and r.get('id')
                and not gate.door_denied(r)]

    # ================================================================ P2
    # The Amber callbacks. Every one names a task by id and nothing else: the
    # server re-reads the task, checks it is the caller's own, and works from
    # what IT stored — the browser never sends `vals`, a tier or a right
    # (PA-R3, PA18). Progress is bookkeeping and is refused unless the task
    # was confirmed by this person.
    @api.model
    def rpc_send_message(self, message, session_id=None, screen=None, resolve=None,
                         voice=False, ask_only=False):
        """`voice` — the message was spoken (the transcript landed in the box
        and the person pressed send). It decides only two things: the plan is
        read back on the device, and a spoken "go ahead" may count when the
        company allows it.

        `ask_only` (ONECHAT OC1, handover E2/§4.9) — the helper's router read
        this sentence as a QUESTION: PayAI answers it and never plans from it
        (`PayrollAIEngine.process_message`). It can only take the command path
        away, never add one; a client that does not send it gets today's
        behaviour. The base module's `rpc_send_message` does not know the
        word, so only this module's chat patch ever sends it."""
        return super(PayrollAIConversation, self.with_context(
            payai_voice=bool(voice), payai_ask_only=bool(ask_only))).rpc_send_message(
                message, session_id=session_id, screen=screen, resolve=resolve)

    @api.model
    def rpc_helper_status(self, session_id=None):
        """ONECHAT OC1 — what only the command path knows: whether a spoken
        go-ahead counts in this company (`can_act` is the router's own hook,
        read by the base)."""
        out = super().rpc_helper_status(session_id)
        out['voice_go_ahead'] = bool(self.env.company.payai_voice_go_ahead)
        return out

    def action_clear(self):
        """Clear conversation (ONECHAT OC1, handover E3): the plans and
        questions still waiting in it stop for good — they were already
        harmless (a cleared chat has no "last thing I showed you"), and now
        the audit says so too. The runner's bookkeeping, written as the
        runner writes it (PA18); only this person's own rows in this
        conversation."""
        for conv in self:
            if conv.user_id != self.env.user:
                continue
            self.env['payai.task'].sudo().search([
                ('user_id', '=', self.env.user.id), ('session_id', '=', conv.id),
                ('state', 'in', ('planned', 'clarify')),
            ]).write({'state': 'expired'})
        return super().action_clear()

    def _payai_call(self, fn, task_id, *args):
        token = set_lang(self.env.lang or self.env.user.lang)
        try:
            task = self.env['payai.task'].sudo().browse(int(task_id or 0)).exists()
            if not task or task.user_id != self.env.user:
                raise AccessError(self.env._('That request belongs to somebody else.'))
            ctx = runner.Ctx.for_task(self.env, task)
            # FIX-1b: no card that leaves here offers a door into Access.
            return gate.scrub_card(fn(ctx, task.id, *args))
        finally:
            reset_lang(token)

    @api.model
    def rpc_confirm_task(self, task_id, how='tap', word=None, note=None):
        """Do it. `how` is 'tap' or 'voice' (Amber) or 'typed' (Red, with the
        `word` the person typed and an optional `note`). A spoken go-ahead is
        honoured only when the company allows it AND the task is Amber; a Red
        task counts only the typed word, checked here on the server (the
        runner checks all of it). Returns the card that replaces the plan card."""
        how = how if how in ('tap', 'voice', 'typed') else 'tap'
        word = word if isinstance(word, str) else ''
        note = note if isinstance(note, str) else ''
        card = self._payai_call(runner.confirm, task_id, how, word[:40], note[:2000])
        return {'card': card}

    @api.model
    def rpc_task_progress(self, task_id, done=0, total=0):
        return self._payai_call(runner.progress, task_id, done, total)

    @api.model
    def rpc_task_result(self, task_id, run_id=0, info=None):
        return {'card': self._payai_call(runner.result, task_id, run_id, info)}

    @api.model
    def rpc_task_undo(self, task_id):
        return {'card': self._payai_call(runner.undo, task_id)}

    @api.model
    def rpc_cancel_task(self, task_id):
        return {'card': self._payai_call(runner.cancel, task_id)}


class PayrollAIMessage(models.Model):
    _inherit = 'payroll.ai.message'

    def _card_dict(self):
        """A plan card is one card in three states (plan → running → result):
        history shows the task's LATEST card, not the plan as first sent."""
        # FIX-1b: a card from before the deny-list loses its Access door too.
        card = gate.scrub_card(super()._card_dict())
        if not card or card.get('kind') != 'plan' or not card.get('task_id'):
            return card
        task = self.env['payai.task'].sudo().browse(int(card['task_id'])).exists()
        if not task or task.user_id != self.env.user or not task.plan_json:
            return card
        try:
            latest = json.loads(task.plan_json)
        except (TypeError, ValueError):
            return card
        if not isinstance(latest, dict):
            return card
        if task.state in ('confirmed', 'running') and task.write_date \
                and task.write_date < fields.Datetime.now() - runner.RUN_STALE:
            # The page that was driving it closed. Say so, never a frozen bar.
            latest = dict(latest, state='failed', drive=None, actions=[], notes=[{
                'tone': 'warn',
                'text': self.env._('This stopped when the page was closed. Open the '
                                   'Runs board to see what was made.')}])
        latest.pop('drive', None)
        return gate.scrub_card(latest)
