# -*- coding: utf-8 -*-
"""RED ACTIONS — approve, send back, reject: the person's OWN decision.

approve_item, send_back_item, reject_item (P3_HANDOVER §Scope 1).

The shape is the Amber one (plan card → confirm → result) with three rails
of its own:

  * the item is found ONLY in the person's own inbox ("My turn":
    `pb.approval.inbox.list_requests(tab='mine')`). Anything else they can
    see is answered with who decides it and a "Remind <name>" chip — never
    decided, never reassigned, never an exception grant;
  * the confirm is a TYPED word, checked on the server (runner.confirm):
    a tap or a spoken yes is refused with "this one needs typing";
  * Do it calls the inbox's own `decide(...)` as the person, with the lock
    revision the plan read and the task as the idempotency key. The engine
    re-checks the seat, the account, the record and the independence rule.

Nothing here is ever sudo (PA-R2). Two reads go through the inbox's own
gated helpers (`_readable`, `_current_step`), the same ones its drawer uses.
"""
import json
import logging

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from .i18n import T, num, stamp

from . import cards
from .actions_amber import learn_action
from .actions_green import RUNS_DOOR, money
from .registry import Action, Slot, Stale, payai_action
from .resolve import (
    MAX_CHIPS, ambiguous, division_names, fold, missing, month_label, parse_period,
    resolved, tok_match, tokens,
)

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

HOME_SCREEN = ('pb_home_hub.item_home',)
APPROVALS_DOOR = 'homehub_approvals'
APPROVALS_HUB = {'tag': 'pb_home_hub', 'lens': 'approvals'}


def approvals_hub(request_id=0, scope='me'):
    """P4 — the Approvals inbox opened ON one request: `pb_focus`
    "request:<id>[:<scope>]" (pb_approval_config inbox.js reads it on arrival,
    opens that request's drawer, on the tab and scope where it lives).
    Navigation only (PA19): the drawer re-reads the request with the person's
    own rights."""
    if not request_id:
        return dict(APPROVALS_HUB)
    focus = 'request:%d' % int(request_id)
    if scope and scope != 'me':
        focus += ':%s' % scope
    return dict(APPROVALS_HUB, focus=focus, context={'pb_focus': focus})
PAYRUN_MODEL = 'hr.payslip.run'
#: The facade's own floor for a send-back / reject reason (inbox_facade.MIN_REASON).
MIN_REASON = 6
MAX_REASON = 2000

#: Words that never narrow which request is meant.
ITEM_STOP = frozenset((
    'the', 'a', 'an', 'my', 'our', 'for', 'of', 'please', 'that', 'this',
    'request', 'requests', 'item', 'one', 'waiting', 's', 'approval',
    'approvals', 'it', 'to', 'me', 'from', 'on', 'in', 'with', 'and',
    # P4 — Vietnamese words that never narrow it ("duyệt cái đó cho tôi",
    # "yêu cầu đang chờ tôi"). "bảng/đợt/kỳ lương" are NOT here: a pay run's
    # own words carry them, so they narrow to pay runs, as "run" does.
    'no', 'cai', 'nay', 'do', 'kia', 'yeu', 'cau', 'cua', 'toi', 'minh',
    'dang', 'cho', 'den', 'luot', 'muc', 'viec', 'cac', 'nhung', 'thang',
))
#: The Learn walkthrough a done card offers, per process (P3 §2). There is no
#: walkthrough of deciding in the Approvals inbox itself; for a pay run the
#: approver's own job on the screen is reading the run and its payslips.
LEARN_FOR = {'payrun': 'sc_payslips'}


def _clip(text, size=MAX_REASON):
    return ' '.join((text or '').split())[:size]


def _stamp(ctx):
    when = fields.Datetime.context_timestamp(ctx.env.user, fields.Datetime.now())
    return stamp(when)


def _names(seats):
    return [s['name'] for s in seats if s.get('name')]


def _joined(names):
    names = [n for n in names if n]
    if len(names) <= 1:
        return ''.join(names)
    return T(_lt('%(first)s and %(last)s')) % {'first': ', '.join(names[:-1]),
                                               'last': names[-1]}


# ------------------------------------------------------------------ matching
def _record_dates(record):
    out = []
    for fname in ('date_start', 'date_end', 'date_from', 'date_to', 'date'):
        if record is not None and fname in record._fields and record[fname]:
            try:
                out.append(fields.Date.to_date(record[fname]))
            except Exception:                           # noqa: BLE001
                continue
    return out


def _card_words(inbox, card):
    """The words a request answers to: its title, process, kind, where it
    belongs, who sent it, its frozen facts — and for a pay run, the run's own
    name, scheme and division (the words the Runs board answers to)."""
    request = inbox.env['biz.approval.request'].browse(card['id'])
    parts = [card.get('title') or '', card.get('process') or '', card.get('kind') or '',
             card.get('sub') or '', card.get('submitted_by') or '']
    record = None
    try:
        for raw in (request.facts or {}).values():
            value = raw.get('value') if isinstance(raw, dict) else raw
            if isinstance(value, str):
                parts.append(value)
        record = inbox._record_of(request)
    except Exception:                                   # noqa: BLE001
        record = None
    if record is not None and record._name == PAYRUN_MODEL:
        # P4: and the Vietnamese screens' words for a pay run, so "duyệt bảng
        # lương tháng 6" narrows to pay runs exactly as "approve the run" does.
        parts += [record.name or '', 'pay run payroll', 'bảng lương đợt lương kỳ lương']
        for fname in ('pb_division', 'pb_division_label'):
            if fname in record._fields and record[fname]:
                parts.append(str(record[fname]))
        if 'pb_division' in record._fields and record.pb_division:
            parts.append(division_names(record.pb_division))
        if 'pb_formula_config_id' in record._fields and record.pb_formula_config_id:
            parts.append(record.pb_formula_config_id.name or '')
    return tokens(' '.join(parts)), record


def match_cards(ctx, inbox, text, cards_):
    """[(exact, card)] whose words cover every word said. None when nothing
    narrowing was said at all (no words, no month)."""
    today = fields.Date.context_today(ctx.env.user)
    per = parse_period(text or '', today)
    rest = per[3] if per else fold(text or '')
    query = [t for t in tokens(rest, ITEM_STOP) if not t.isdigit()]
    if not query and not per:
        return None
    out = []
    for card in cards_:
        words, record = _card_words(inbox, card)
        if per:
            dates = _record_dates(record)
            if dates:
                if not any(per[0] <= d <= per[1] for d in dates):
                    continue
            elif fold(month_label(per[0], 'en_US').split()[0]) not in words:
                continue
        if all(any(tok_match(q, w) for w in words) for q in query):
            out.append((all(q in words for q in query), card))
    return out


def _chip(card):
    sub = ' · '.join(x for x in (card.get('process') or '', card.get('submitted_by') or '') if x)
    return {'value': card['id'], 'label': card.get('title') or '', 'sublabel': sub}


# =========================================================================
class _Red(Action):
    tier = 'decide'
    priority = 20
    screen_keys = HOME_SCREEN
    door_id = APPROVALS_DOOR
    right_label = _lt('Approvals')
    #: what the inbox's `decide` is asked to record
    engine_action = 'approve'
    reason_required = False
    #: past tense for the result card and the audit line
    did = _lt('approved')

    def method_gate(self, env, user):
        """The screen-level question: can this person take part in approvals
        at all? Whether they may decide THIS request is the seat, asked per
        request (`can_decide`) and again by the engine at Do it."""
        if 'pb.approval.inbox' not in env or 'biz.approval.request' not in env:
            return False
        return bool(env['biz.approval.request'].with_user(user).has_access('read'))

    def _inbox(self, ctx):
        return ctx.env['pb.approval.inbox']

    # ------------------------------------------------------------ slots
    def resolve_slot(self, ctx, slot, text):
        if slot.kind == 'item':
            return self._resolve_item(ctx, text)
        if slot.kind == 'reason':
            return self._resolve_reason(ctx, text)
        return super().resolve_slot(ctx, slot, text)

    def reask_slot(self, ctx, slot):
        if slot.kind == 'reason':
            return {'status': 'ask'}
        return self.resolve_slot(ctx, slot, '')

    def _resolve_reason(self, ctx, text):
        text = _clip(text)
        if not text:
            if not self.reason_required:
                return resolved('', '', 'default')
            return {'status': 'ask', 'question': self._reason_question(),
                    'note': T(_lt('Type it below. The person who sent it in reads exactly '
                                  'these words. I will show you the plan before anything '
                                  'is done.'))}
        if self.reason_required and len(text) < MIN_REASON:
            return {'status': 'ask', 'question': self._reason_question(),
                    'note': T(_lt('A few more words, please: say what should change.'))}
        return resolved(text, text, 'said')

    def _reason_question(self):
        return T(_lt('What should change? Type the reason.'))

    def _resolve_item(self, ctx, text):
        inbox = self._inbox(ctx)
        mine = (inbox.list_requests(tab='mine', scope='me') or {}).get('cards') or []
        hits = match_cards(ctx, inbox, text, mine)
        if hits is None:
            # "Approve it": nothing narrowing said — what is waiting for me.
            if len(mine) == 1:
                return resolved(mine[0]['id'], mine[0]['title'] or '', 'assumed')
            if mine:
                return ambiguous([_chip(c) for c in mine[:MAX_CHIPS]])
            return self._nothing_waiting(ctx)
        full = [c for _e, c in hits]
        if len(full) == 1:
            exact = hits[0][0]
            return resolved(full[0]['id'], full[0]['title'] or '', 'said' if exact else 'assumed')
        if full:
            return ambiguous([_chip(c) for c in full[:MAX_CHIPS]])
        # Not in MY inbox: is it something I can see, waiting for somebody else?
        mine_ids = {c['id'] for c in mine}
        for scope in self._scopes(inbox):
            try:
                others = (inbox.list_requests(tab='all', scope=scope) or {}).get('cards') or []
            except (AccessError, UserError):
                continue
            others = [c for c in others if c['id'] not in mine_ids]
            found = [c for _e, c in (match_cards(ctx, inbox, text, others) or [])]
            if found:
                return {'status': 'missing', 'card': self._not_mine_card(ctx, found[0]['id'], scope),
                        'note': 'not in their inbox', 'candidates': []}
        if mine:
            out = ambiguous([_chip(c) for c in mine[:MAX_CHIPS]])
            out['note'] = T(_lt(
                'I could not find "%s" among the things waiting for your decision. '
                'These are:')) % (text or '')[:60]
            return out
        return self._nothing_waiting(ctx, text)

    def _scopes(self, inbox):
        scopes = ['me']
        try:
            if inbox._can_org():
                scopes.append('org')
        except Exception:                               # noqa: BLE001
            pass
        return scopes

    def _nothing_waiting(self, ctx, text=''):
        note = T(_lt('Nothing is waiting for your decision right now.'))
        if (text or '').strip():
            note = T(_lt('I could not find "%s" waiting for your decision, and nothing '
                         'else is waiting for you right now.')) % text[:60]
        out = missing(note)
        out['door_id'] = APPROVALS_DOOR
        return out

    # ------------------------------------------- not yours / cannot decide
    def _holders(self, ctx, request_id, scope):
        """(request, step, [{user_id, name}]) of the open seats on the live
        step, read the way the inbox drawer reads them."""
        inbox = self._inbox(ctx)
        request = inbox._readable(request_id, scope)
        step = inbox._current_step(request)
        seats = []
        for seat in step.seat_ids.filtered(lambda s: s.status == 'open'):
            name = seat.acting_user_id.name or ''
            if seat.user_id and seat.acting_user_id != seat.user_id:
                name = T(_lt('%(who)s, covering for %(whose)s')) % {
                    'who': seat.acting_user_id.name or '', 'whose': seat.user_id.name or ''}
            seats.append({'user_id': seat.acting_user_id.id, 'name': name,
                          'first': (seat.acting_user_id.name or '').split(' ')[0]})
        return request, step, seats

    def _not_mine_card(self, ctx, request_id, scope='me'):
        """Not waiting for this person: who decides it, Remind them, and the
        inbox. Nothing is decided, moved or granted (binding non-goal)."""
        try:
            request, step, seats = self._holders(ctx, request_id, scope)
        except (AccessError, UserError):
            return self._gone_card(ctx)
        actions = self._inbox_door(ctx, request_id=request.id, scope=scope)
        title = request.title or ''
        if request.state == 'blocked':
            return cards.card(
                'refused', ctx.task, 'decide', title=_lt('Nobody can decide this yet'),
                subtitle=title, notes=[cards.note('warn', request.block_reason or T(_lt(
                    'Nobody could be found to decide it.')))], actions=actions)
        if request.state != 'pending' or not seats:
            return self._gone_card(ctx, request)
        who = _joined([s['name'] for s in seats])
        notes = [cards.note('info', T(_lt(
            '"%(what)s" is waiting for %(who)s at "%(step)s". You are not the one who '
            'decides it, so I cannot do it for you.')) % {
                'what': title, 'who': who, 'step': step.title or ''})]
        values = ['%s:%s' % (request.id, s['user_id']) for s in seats[:3]]
        chips = [{'label': T(_lt('Remind %s')) % s['first'], 'sublabel': s['name'],
                  'value': v} for s, v in zip(seats[:3], values)]
        notes.append(cards.note('info', _lt(
            'I can remind them: they get a note on the request and a to-do.')))
        return cards.card(
            'refused', ctx.task, 'decide', title=_lt('This is not waiting for you'),
            subtitle=title, notes=notes, actions=actions, chips=chips,
            chip_slot='item', chip_action='remind',
            offer={'slot': 'item', 'values': values, 'actions': ['remind'], 'scope': scope})

    def _gone_card(self, ctx, request=None):
        state = ''
        if request is not None:
            state = dict(request._fields['state']._description_selection(ctx.env)).get(
                request.state) or request.state or ''
        text = T(_lt('This is no longer waiting for a decision (%s).')) % state.lower() \
            if state else T(_lt('I cannot find that request any more.'))
        return cards.card('refused', ctx.task, 'decide', title=_lt('Nothing to decide'),
                          subtitle=(request.title or '') if request is not None else '',
                          notes=[cards.note('info', text)], actions=self._inbox_door(ctx))

    def _inbox_door(self, ctx, style='outline', request_id=0, scope='me'):
        if not ctx.has_door(APPROVALS_DOOR):
            return []
        return [cards.door_action(APPROVALS_DOOR, _lt('Open my approvals'), style,
                                  hub=approvals_hub(request_id, scope))]

    def _conflict_card(self, ctx, request, conflict):
        """The independence rule, in the engine's own words. PayAI never uses
        an exception: if one exists, the screen is where it is used."""
        notes = [cards.note('bad', '%s %s' % (conflict.get('text') or '', T(_lt(
            'You were part of preparing or sending this in, so you cannot also '
            'approve it. Ask someone else, or ask for an exception to be set up.'))))]
        if conflict.get('grant_id'):
            notes.append(cards.note('info', _lt(
                'An exception exists for this. PayAI never uses one: open your approvals '
                'to approve it yourself with a written reason.')))
        return cards.card('refused', ctx.task, 'decide', title=_lt('Somebody else has to decide this'),
                          subtitle=request.get('title') or '', notes=notes,
                          actions=self._inbox_door(ctx, request_id=request.get('id') or 0))

    # ------------------------------------------------------------- plan
    def _read(self, ctx, request_id):
        """(payload, None) or (None, refusal card) — the drawer's own read."""
        try:
            pay = self._inbox(ctx).get_request(int(request_id))
        except (AccessError, UserError):
            return None, self._gone_card(ctx)
        if pay.get('state') != 'pending' or not pay.get('can_decide'):
            return None, self._not_mine_card(ctx, pay['id'])
        if self.engine_action == 'approve' and pay.get('conflict'):
            return None, self._conflict_card(ctx, pay, pay['conflict'])
        return pay, None

    @staticmethod
    def _decision_steps(pay):
        return [s for s in pay.get('steps') or []
                if s.get('included') and s.get('kind') not in ('notify', 'fast')]

    def _route(self, ctx, pay):
        """Where the request stands and who comes after this person — read
        off the request's OWN steps and seats, frozen when it was sent in,
        which are exactly what the engine opens next (`_activate_next`, with
        today's hand-overs applied the same way)."""
        steps = self._decision_steps(pay)
        current = next((s for s in steps if s.get('status') == 'active'), None)
        index = steps.index(current) + 1 if current else 0
        others = []
        if current and current.get('joint'):
            others = [s['name'] for s in current.get('seats') or []
                      if s.get('status') == 'open' and not s.get('mine')]
        nxt = None
        if current:
            for s in steps[index:]:
                if s.get('status') in ('pending', 'blocked'):
                    nxt = s
                    break
        next_names = []
        if nxt:
            company = ctx.env['biz.approval.request'].browse(pay['id']).company_id
            for seat in nxt.get('seats') or []:
                if seat.get('status') != 'open':
                    continue
                next_names.append(self._cover_name(ctx, seat, company))
        return {'current': current, 'index': index, 'total': len(steps), 'next': nxt,
                'next_names': [n for n in next_names if n], 'others': others}

    def _cover_name(self, ctx, seat, company):
        name = seat.get('name') or ''
        try:
            holder = ctx.env['res.users'].browse(int(seat.get('key', 'u0')[1:] or 0)).exists()
            cover = ctx.env['biz.approval.delegation'].covering(holder, company) if holder else None
            if cover and cover != holder:
                return T(_lt('%(who)s, covering for %(whose)s')) % {
                    'who': cover.name or '', 'whose': holder.name or ''}
        except Exception:                               # noqa: BLE001
            pass
        return name

    def _figures(self, ctx, pay):
        """The record's headline figures, as they were FROZEN when it was
        sent in (what the approver signs for): a pay run's people and net
        (the run band — one pay-band rule), a change's old → new, else the
        request's own count and amount."""
        request = ctx.env['biz.approval.request'].browse(pay['id'])
        facts = request.facts or {}
        symbol = request.currency_id.symbol or request.currency_id.name or ''

        def fact(key):
            raw = facts.get(key)
            return raw.get('value') if isinstance(raw, dict) else raw
        if request.res_model == PAYRUN_MODEL and fact('net_total') is not None:
            people = fact('employee_count') or fact('payslip_count') or 0
            try:
                people = int(float(people))
            except (TypeError, ValueError):
                people = 0
            text = T(_lt('1 person · %(net)s net')) if people == 1 \
                else T(_lt('%(n)s people · %(net)s net'))
            return text % {'n': num(people), 'net': money(fact('net_total'), symbol)}
        parts = []
        detail = pay.get('detail') or {}
        for row in (detail.get('rows') or [])[:2]:
            cells = [c for c in row.get('cells') or [] if c]
            if row.get('head') and cells:
                parts.append('%s: %s' % (row['head'], ' → '.join(cells[:2])))
        if not parts and pay.get('count'):
            parts.append(pay['count'])
        if request.amount and not parts:
            parts.append(money(request.amount, symbol))
        if not parts:
            for row in (pay.get('facts') or [])[:2]:
                parts.append(('%s %s %s' % (row.get('label') or '', row.get('value') or '',
                                            row.get('unit') or '')).strip())
        return ' · '.join(p for p in parts if p)

    def _what_happens(self, pay, route):
        """One sentence: what this decision does next (shown on the plan)."""
        raise NotImplementedError

    def _next_label(self, pay, route):
        raise NotImplementedError

    def plan(self, ctx, params):
        pay, refusal = self._read(ctx, params['item']['value'])
        if refusal:
            return refusal
        route = self._route(ctx, pay)
        current = route['current'] or {}
        reason = (params.get('reason') or {}).get('value') or ''
        slots = [
            slot_row('item', pay.get('process') or _lt('What'), pay.get('title') or '',
                     params['item'].get('origin')),
        ]
        figures = self._figures(ctx, pay)
        if figures:
            slots.append(slot_row('figures', _lt('Figures'), figures, 'default',
                                  origin_label=_lt('as sent in')))
        if current:
            slots.append(slot_row('step', _lt('Step'), T(_lt('%(step)s, %(i)s of %(n)s')) % {
                'step': current.get('title') or '', 'i': route['index'], 'n': route['total']},
                'default', origin_label=_lt('your seat')))
        slots.append(slot_row('next', _lt('Then'), self._next_label(pay, route), 'default',
                              origin_label=_lt('from the route')))
        if self.reason_required:
            slots.append(slot_row('reason', _lt('Reason'), reason,
                                  (params.get('reason') or {}).get('origin') or 'said', True))
        notes = [cards.note('info', self._what_happens(pay, route))]
        if ctx.voice:
            notes.append(cards.note('warn', _lt(
                'This one needs typing: a spoken yes never confirms a decision.')))
        # P4: the word in the person's own language; either word is accepted
        # (`words`, checked again on the server, marks and capitals folded).
        word = self.shown_word()
        typed = {'id': 'typed', 'word': word, 'words': list(self.confirm_words()),
                 'label': T(self.title_short), 'style': 'primary', 'icon': self.icon,
                 'hint': T(_lt('Type %s to confirm. A spoken yes does not count here.')) % word}
        if not self.reason_required:
            typed['note'] = {'label': T(_lt('Note')), 'value': reason,
                             'placeholder': T(_lt('Optional. It goes on the record.'))}
        actions = [typed]
        if ctx.has_door(APPROVALS_DOOR):
            actions.append({'id': 'door', 'door_id': APPROVALS_DOOR,
                            'hub': approvals_hub(pay['id']),
                            'label': T(_lt('Open my approvals instead')), 'style': 'outline',
                            'icon': 'panel'})
        actions.append({'id': 'cancel', 'label': T(_lt('Cancel')), 'style': 'ghost'})
        sub = T(_lt('Decide · your decision as %(step)s · PayAI cannot undo it')) % {
            'step': current.get('title') or T(_lt('approver'))}
        card = cards.card('plan', ctx.task, 'decide', title=T(self.title_on) % (pay.get('title') or ''),
                          subtitle=sub, slots=slots, notes=notes, actions=actions,
                          state='planned', icon=self.icon)
        seats = sorted(s.get('key') or '' for s in current.get('seats') or []
                       if s.get('status') == 'open')
        fp = fingerprint_of(pay['id'], pay.get('lock_revision'), current.get('key'),
                            pay.get('state'), seats)
        vals = {'request_id': pay['id'], 'step_key': current.get('key') or '',
                'lock_revision': pay.get('lock_revision'), 'action': self.engine_action,
                'reason': reason, 'next_names': route['next_names'],
                'next_step': (route['next'] or {}).get('title') or '',
                'others': route['others'], 'last': not route['next'],
                'process_key': pay.get('process_key') or '',
                'submitted_by': pay.get('submitted_by') or ''}
        speak = T(_lt('This is a decision. I need you to type the word %s on the card; '
                      'voice cannot confirm it.')) % word
        return {'card': card, 'vals': vals, 'fingerprint': fp, 'speak': speak}

    # ---------------------------------------------------------- Do it
    def confirm(self, ctx, task, params, data):
        vals = data.get('vals') or {}
        reason = vals.get('reason') or ''
        note = _clip(getattr(ctx, 'confirm_note', '') or '')
        if not self.reason_required and note:
            reason = note
        inbox = self._inbox(ctx)
        request = ctx.env['biz.approval.request'].browse(int(vals['request_id']))
        try:
            after = inbox.decide(request.id, vals['step_key'], self.engine_action, reason,
                                 expected_lock_revision=vals.get('lock_revision'),
                                 idempotency_key='payai-task-%s' % task.id)
        except (UserError, AccessError) as exc:
            request.invalidate_recordset()
            moved = False
            try:
                moved = (request.lock_revision != vals.get('lock_revision')
                         or request.current_step_key != vals['step_key']
                         or not inbox._is_mine(request))
            except Exception:                           # noqa: BLE001
                moved = True
            if moved:
                raise Stale(str(exc)) from exc
            raise
        decision = request.decision_ids.filtered(
            lambda d: d.idempotency_key == 'payai-task-%s' % task.id)[:1]
        return self._result_card(ctx, task, vals, after, reason, decision)

    def _result_card(self, ctx, task, vals, after, reason, decision):
        notes = [cards.note('ok', self._outcome(vals, after))]
        if after.get('block_reason') and after.get('state') == 'approved':
            notes.append(cards.note('warn', T(_lt(
                'Approved, but it could not be carried out yet: %s')) % after['block_reason']))
        actions = []
        scenario = LEARN_FOR.get(vals.get('process_key') or '')
        record = None
        try:
            record = self._inbox(ctx)._record_of(
                ctx.env['biz.approval.request'].browse(after['id']))
        except Exception:                               # noqa: BLE001
            record = None
        if record is not None and record._name == PAYRUN_MODEL and ctx.has_door(RUNS_DOOR):
            actions.append(cards.door_action(RUNS_DOOR, _lt('Open the run'), 'outline',
                                             hub={'tag': 'pb_pay_hub', 'lens': 'runs',
                                                  'focus': T(record.id)}))
        actions += self._inbox_door(ctx, request_id=after.get('id') or 0)
        if scenario:
            actions.append(learn_action(scenario))
        card = cards.card(
            'plan', task, 'decide', title=T(self.done_title), subtitle=after.get('title') or '',
            slots=cards.plan_slots(task), notes=notes, actions=actions, state='done',
            icon='check', result_ref={'request_id': after.get('id'),
                                      'decision_id': decision.id if decision else 0})
        card['audit_line'] = T(_lt(
            'Recorded: %(did)s by %(who)s via PayAI, typed confirmation, %(when)s.')) % {
                'did': T(self.did), 'who': ctx.user.name, 'when': _stamp(ctx)}
        return card

    def _outcome(self, vals, after):
        raise NotImplementedError


def slot_row(key, label, value_label, origin, editable=False, origin_label=''):
    return {'key': key, 'label': T(label), 'value_label': T(value_label or ''),
            'origin': origin or 'default', 'editable': editable,
            'origin_label': T(origin_label) if origin_label else ''}


def fingerprint_of(*parts):
    return json.dumps(parts, sort_keys=True, default=str)


#: "… because <reason>", "… — <reason>", "…: <reason>", "… with the note <note>".
_REASON_TAIL = (r'(?:(?:\s+(?:because|since|saying|reason:?|note:?|with\s+(?:the\s+|a\s+)?'
                r'(?:reason|note)(?:\s+that)?)|\s*[:—]|\s+-)\s+(?P<reason>.+))?$')


# =========================================================================
@payai_action
class ApproveItem(_Red):
    key = 'approve_item'
    title = _lt('Approve something waiting for you')
    title_short = _lt('Approve')
    title_on = _lt('Approve %s')
    done_title = _lt('Approved')
    summary = _lt('Approve a request that is waiting for your own decision, after showing '
                  'the plan; confirmed by typing APPROVE.')
    examples = (_lt('Approve the June Retail run'),)
    right_subject = _lt('Approving')
    confirm_word = 'APPROVE'
    confirm_word_vi = 'DUYỆT'
    icon = 'usercheck'
    did = _lt('approved')
    slots = (Slot('item', _lt('What'), 'item', True,
                  "What to approve, in the person's words: a pay run's month and scheme, "
                  "a person's change, a hiring request. Never an id."),
             Slot('reason', _lt('Note'), 'reason', False,
                  "An optional note the person said for the record."))
    phrases = (r'^approve\s+(?P<item>.+?)' + _REASON_TAIL,)

    def _next_label(self, pay, route):
        if route['others']:
            return T(_lt('%s still has to approve this step too')) % _joined(route['others'])
        if route['next']:
            names = _joined(route['next_names'])
            title = route['next'].get('title') or ''
            return '%s · %s' % (title, names) if names else title
        return T(_lt('Nobody: approving finishes it'))

    def _what_happens(self, pay, route):
        payrun = pay.get('process_key') == 'payrun'
        if route['others']:
            return T(_lt('Your approval is recorded; the step waits for %s as well.')) % \
                _joined(route['others'])
        if route['next']:
            names = _joined(route['next_names'])
            text = T(_lt('After you, it goes to %(step)s%(who)s.')) % {
                'step': route['next'].get('title') or '',
                'who': (' (%s)' % names) if names else ''}
            if payrun:
                text += ' ' + T(_lt('Nobody is paid by approving.'))
            return text
        if payrun:
            return T(_lt('You are the last step: the run is approved. Nobody is paid until '
                         'the payment is released.'))
        return T(_lt('You are the last step: approving lets it go ahead.'))

    def _outcome(self, vals, after):
        step = ''
        for s in after.get('steps') or []:
            if s.get('key') == vals.get('step_key'):
                step = s.get('title') or ''
        payrun = vals.get('process_key') == 'payrun'
        live = next((s for s in after.get('steps') or [] if s.get('status') == 'active'), None)
        if live and live.get('key') == vals.get('step_key'):
            waiting = [x['name'] for x in live.get('seats') or []
                       if x.get('status') == 'open']
            return T(_lt('Your approval as %(step)s is recorded. The step still waits for '
                         '%(who)s.')) % {'step': step, 'who': _joined(waiting)}
        if live:
            names = _joined([x['name'] for x in live.get('seats') or []
                             if x.get('status') == 'open'])
            text = T(_lt('Approved as %(step)s. It moves to %(next)s%(who)s.')) % {
                'step': step, 'next': live.get('title') or '',
                'who': (' (%s)' % names) if names else ''}
            if payrun:
                text += ' ' + T(_lt('Nobody has been paid yet.'))
            return text
        if payrun:
            return T(_lt('Approved as %s. That was the last step: the run is approved. '
                         'Nobody has been paid yet.')) % step
        return T(_lt('Approved as %s. That was the last step, so it goes ahead.')) % step


@payai_action
class SendBackItem(_Red):
    key = 'send_back_item'
    title = _lt('Send something back')
    title_short = _lt('Send back')
    title_on = _lt('Send back %s')
    done_title = _lt('Sent back')
    summary = _lt('Send a request that is waiting for your decision back to whoever sent '
                  'it in, with a reason; confirmed by typing SEND BACK.')
    examples = (_lt('Send the June Retail run back because the overtime is missing'),)
    right_subject = _lt('Sending back')
    confirm_word = 'SEND BACK'
    confirm_word_vi = 'TRẢ LẠI'
    icon = 'cornerleft'
    did = _lt('sent back')
    engine_action = 'return'
    reason_required = True
    slots = (Slot('item', _lt('What'), 'item', True,
                  "What to send back, in the person's words. Never an id."),
             Slot('reason', _lt('Reason'), 'reason', True,
                  "What should change, in the person's own words."))
    phrases = (
        r'^send\s+back\s+(?P<item>.+?)' + _REASON_TAIL,
        r'^send\s+(?P<item>.+?)\s+back(?:\s+to\s+\S+(?:\s+\S+)?)?' + _REASON_TAIL,
        r'^return\s+(?P<item>.+?)\s+to\s+(?:the\s+)?(?:sender|preparer|maker|\S+)' + _REASON_TAIL,
    )

    def _next_label(self, pay, route):
        return T(_lt('Back to %s')) % (pay.get('submitted_by') or T(_lt('whoever sent it in')))

    def _what_happens(self, pay, route):
        who = pay.get('submitted_by') or T(_lt('whoever sent it in'))
        if pay.get('process_key') == 'payrun':
            return T(_lt('The run goes back to draft with your reason, so %s can fix it and '
                         'send it again.')) % who
        return T(_lt('It goes back to %s with your reason, to change and send again.')) % who

    def _outcome(self, vals, after):
        who = vals.get('submitted_by') or T(_lt('whoever sent it in'))
        if vals.get('process_key') == 'payrun':
            return T(_lt('Sent back to %s with your reason. The run is a draft again.')) % who
        return T(_lt('Sent back to %s with your reason.')) % who


@payai_action
class RejectItem(_Red):
    key = 'reject_item'
    title = _lt('Reject something')
    title_short = _lt('Reject')
    title_on = _lt('Reject %s')
    done_title = _lt('Rejected')
    summary = _lt('Reject a request that is waiting for your decision, with a reason; '
                  'confirmed by typing REJECT.')
    examples = (_lt('Reject the May bonus run because it was paid twice'),)
    right_subject = _lt('Rejecting')
    confirm_word = 'REJECT'
    confirm_word_vi = 'TỪ CHỐI'
    icon = 'circlex'
    did = _lt('rejected')
    engine_action = 'reject'
    reason_required = True
    slots = (Slot('item', _lt('What'), 'item', True,
                  "What to reject, in the person's words. Never an id."),
             Slot('reason', _lt('Reason'), 'reason', True,
                  "Why, in the person's own words."))
    phrases = (r'^(?:reject|decline|refuse|turn\s+down)\s+(?P<item>.+?)' + _REASON_TAIL,)

    def _reason_question(self):
        return T(_lt('Why is it rejected? Type the reason.'))

    def _next_label(self, pay, route):
        return T(_lt('It ends here'))

    def _what_happens(self, pay, route):
        if pay.get('process_key') == 'payrun':
            return T(_lt('The run is rejected and every payslip in it is cancelled. It cannot '
                         'be sent again; a new run has to be prepared.'))
        return T(_lt('It is turned down and ends here. %s is told, with your reason.')) % (
            pay.get('submitted_by') or T(_lt('Whoever sent it in')))

    def _outcome(self, vals, after):
        if vals.get('process_key') == 'payrun':
            return T(_lt('Rejected. The run and its payslips are cancelled, and %s is told '
                         'why.')) % (vals.get('submitted_by') or T(_lt('whoever sent it in')))
        return T(_lt('Rejected. %s is told why.')) % (
            vals.get('submitted_by') or T(_lt('Whoever sent it in')))


# ------------------------------------------------------------------ remind
def remind(ctx, task, value, offer):
    """"Remind <name>" on a not-yours card: the engine's own reminder (the
    outbox's 'reminder' kind — the same note the overdue cron sends: a
    message on the request and a to-do for them), at most once a day per
    person and step, and an event in the approval trail under the asker's
    name. Never a decision, never a move."""
    try:
        request_id, user_id = [int(x) for x in str(value).split(':', 1)]
    except (TypeError, ValueError):
        raise AccessError(T(_lt('That button was not offered here.')))
    inbox = ctx.env['pb.approval.inbox']
    request = inbox._readable(request_id, (offer or {}).get('scope') or 'me')
    step = inbox._current_step(request)
    seat = step.seat_ids.filtered(
        lambda s: s.status == 'open' and s.acting_user_id.id == user_id)[:1]
    if request.state != 'pending' or not seat:
        return cards.card('blocked', task, 'decide', title=_lt('It has moved on'),
                          subtitle=request.title or '', transient=True,
                          notes=[cards.note('info', _lt(
                              'They are no longer the one deciding it, so I sent nothing.'))])
    whom = seat.acting_user_id
    day = fields.Date.context_today(ctx.env.user)
    # Already reminded today (by anybody, the overdue cron included)? Asked
    # of the approval trail the person may read, not of the queue.
    since = fields.Datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    fresh = not ctx.env['biz.approval.event'].search_count([
        ('request_id', '=', request.id), ('kind', '=', 'reminded'),
        ('create_date', '>=', since)])
    if fresh:
        ctx.env['biz.approval.outbox']._queue(
            'reminder', whom, request, payload={'step_title': step.title or ''},
            dedupe='payai-remind-%s-%s-%s' % (step.id, whom.id, day))
        try:
            ctx.env['biz.approval.event']._log(
                'reminded', T(_lt('%(who)s asked PayAI to remind %(whom)s about "%(step)s" '
                                  'on "%(what)s"')) % {
                    'who': ctx.user.name, 'whom': whom.name, 'step': step.title or '',
                    'what': request.title or ''},
                company=request.company_id, request=request)
        except Exception:                               # noqa: BLE001
            _logger.info("PayAI: reminder event not written", exc_info=True)
    text = T(_lt('%s gets a note on the request and a to-do. Recorded.')) % whom.name \
        if fresh else T(_lt('%s was already reminded about this today.')) % whom.name
    return cards.card('done', task, 'decide', title=T(_lt('Reminded %s')) % whom.name,
                      subtitle=request.title or '', transient=True,
                      notes=[cards.note('ok' if fresh else 'info', text)])

