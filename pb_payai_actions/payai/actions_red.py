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
    revision the plan read and a secret, per-task key as the idempotency key
    (`_decision_key`); a done card only when that decision really exists
    (`_recorded`). The engine re-checks the seat, the account, the record
    and the independence rule.

Nothing here is ever sudo (PA-R2). Two reads go through the inbox's own
gated helpers (`_readable`, `_current_step`), the same ones its drawer uses.
"""
import json
import logging
import secrets
from datetime import datetime, time

import pytz

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from .i18n import T, num, stamp

from . import cards, gate
from .actions_amber import learn_action
from .actions_green import RUNS_DOOR, money
from .registry import ACTIONS, Action, Slot, Stale, payai_action
from .resolve import (
    MAX_CHIPS, ambiguous, division_names, fold, item_query, missing, month_label,
    resolved, tok_match, tokens,
)

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

#: FIX-1b (P3:sec-4) — the left-menu entry that really carries the Approvals
#: inbox. The inbox is a tab of Home (`pb_home_hub` mounts it as the
#: "approvals" lens, and Home's entry claims the old `pb_approval` tag); the
#: retired `pb_sidebar.item_approvals` is inactive and opened the payroll
#: cockpit, not the inbox. So a person's Approvals screen is locked in the
#: Access home by locking Home for them (its permissions or roles, a lent role
#: counts) or the Overview block it sits in — `gate.screen_state` reads all
#: of it. There is no lever for the Approvals tab ALONE: its gate is
#: `APPROVAL_GATE = []` in home_hub.js, empty on purpose (every internal user
#: decides something) and pinned empty by pb_home_hub's own tests.
HOME_SCREEN = ('pb_home_hub.item_home',)
#: The Approvals tab inside Home, as the Access home's passport names it (the
#: ⌘K row `homehub_approvals`), and its permissions — a copy of
#: `APPROVAL_GATE` that `test_payai_fix_red` holds equal to the source, so a
#: gate put on the tab one day is a gate on PayAI's decisions that same day.
APPROVALS_SURFACE = 'homehub_approvals'
APPROVALS_SURFACE_GROUPS = ()
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
#: FIX-1b (owner ruling 2026-10-13) — a request whose decision changes
#: somebody's access (`gate.access_request`).
ACCESS_REQUEST_TEXT = _lt('PayAI does not open or change access, so it does not decide or '
                          'chase requests about access. Decide it yourself on the Approvals '
                          'screen.')
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
#: P3:ux-5 — what that walkthrough really teaches, on the button: after a
#: decision "Learn to do this yourself" would promise a lesson in approving.
LEARN_LABEL = {'sc_payslips': _lt('Learn to read a pay run')}


def _clip(text, size=MAX_REASON):
    return ' '.join((text or '').split())[:size]


def _stamp(ctx):
    when = fields.Datetime.context_timestamp(ctx.env.user, fields.Datetime.now())
    return stamp(when)


def _names(seats):
    return [s['name'] for s in seats if s.get('name')]


def _joined(names, joint=True):
    """Names in one phrase. `joint` False — any ONE of them decides (the
    engine closes the other seats as soon as one approves), so "A or B", as
    the inbox's own card words it; "A and B" only when all must (P3:corr-6)."""
    names = [n for n in names if n]
    if len(names) <= 1:
        return ''.join(names)
    text = _lt('%(first)s and %(last)s') if joint else _lt('%(first)s or %(last)s')
    return T(text) % {'first': ', '.join(names[:-1]), 'last': names[-1]}


def _seat_label(seat):
    """A seat of the drawer's payload as the drawer names it: the person, and
    whom they stand in for only when the seat ITSELF already says so. Never a
    hand-over read from anywhere else — the asker may not see it (P3:crit-5)."""
    name = seat.get('name') or ''
    if seat.get('covering_for'):
        return T(_lt('%(who)s, covering for %(whose)s')) % {
            'who': name, 'whose': seat['covering_for']}
    return name


def _waiting_label(seat):
    """A seat still open on the asker's own step: their OTHER seat reads as
    "you, for <whose>" (P3:corr-5), everybody else by name."""
    if seat.get('mine'):
        return T(_lt('you, for %s')) % (seat.get('covering_for') or seat.get('name') or '')
    return _seat_label(seat)


def _day_start_utc(env):
    """(midnight of the person's own day as a naive UTC timestamp, that day).

    The SAME day the reminder's dedupe key names (`context_today`), so the
    "already reminded today" check and the outbox never disagree (P3:corr-3)."""
    day = fields.Date.context_today(env.user)
    try:
        tz = pytz.timezone(env.context.get('tz') or env.user.tz or 'UTC')
    except pytz.UnknownTimeZoneError:
        tz = pytz.utc
    start = tz.localize(datetime.combine(day, time.min))
    return start.astimezone(pytz.utc).replace(tzinfo=None), day


def _file_under(ctx, company):
    """File the PayAI task row under the company the request belongs to
    (P3:sec-1), so ITS payroll managers see it in their PayAI audit — the
    runner opens the row under the top-bar company, and the inbox lists
    every ticked company. Done wherever a request is read for a card (the
    plan, its refusals, the fresh plan made at Do it, a not-yours card and
    its Remind). No task (a read-only probe): nothing to file."""
    _file_task(getattr(ctx, 'task', None), company)


def _file_task(task, company):
    # Bookkeeping on PayAI's own row: it lives in the runner, never under an
    # Action's name (PA-R2, P3:test-11 — no Action module calls sudo).
    from . import runner
    runner.file_task_under(task, company)


class _Refused(Exception):
    """The engine refused inside Do it; `moved` says whether the plan's world
    moved (→ a fresh card) or the refusal is the real answer (→ show it)."""

    def __init__(self, exc, moved):
        super().__init__(str(exc))
        self.exc = exc
        self.moved = moved


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


def _item_words(ctx, text):
    """(period, words, problem) for the words that say WHICH waiting request
    is meant — `resolve.item_query`, the Red Actions' seam (FIX-1 P4 vi-2,
    vi-4, vi-12): a name that folds to a little word (Minh, Thắng, Đặng, Đỗ)
    narrows, and a month that cannot be read ("tháng 13", "thang sau" typed
    with no marks) comes back as `problem`, to be asked."""
    today = fields.Date.context_today(ctx.env.user)
    return item_query(text or '', today, ITEM_STOP)


def match_cards(ctx, inbox, text, cards_):
    """[(exact, card)] whose words cover every word said. None when nothing
    narrowing was said at all (no words, no month). A month that cannot be
    read matches nothing (`_resolve_item` asks about it first)."""
    per, query, problem = _item_words(ctx, text)
    if problem:
        return []
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
    surface_key = APPROVALS_SURFACE
    surface_groups = APPROVALS_SURFACE_GROUPS
    #: P3:sec-1 — the "PayAI can decide" switch is the REQUEST's company's
    #: (`_read`, `remind`); the gate asks only that it is on somewhere the
    #: person works (`gate.allowed`).
    switch_per_record = True
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

    def _not_access(self, ctx, cards_):
        """(cards PayAI may decide, the cards left out). FIX-1b (owner
        ruling 2026-10-13): a request whose decision changes somebody's
        access — an access request under the roles process — is never
        offered, matched, decided or chased through PayAI."""
        Request = ctx.env['biz.approval.request']
        kept, left = [], []
        for c in cards_:
            if gate.access_request(ctx.env, Request.browse(c['id']), c.get('process_key')):
                left.append(c)
            else:
                kept.append(c)
        return kept, left

    def _resolve_item(self, ctx, text):
        _per, _words, problem = _item_words(ctx, text)
        if problem:
            # P4 vi-2 / vi-12: a month that cannot be read is asked about —
            # never matched against every waiting pay run.
            out = missing(problem)
            out['door_id'] = APPROVALS_DOOR
            return out
        inbox = self._inbox(ctx)
        mine = (inbox.list_requests(tab='mine', scope='me') or {}).get('cards') or []
        mine, hidden = self._not_access(ctx, mine)
        hits = match_cards(ctx, inbox, text, mine)
        if hits is None:
            # "Approve it": nothing narrowing said — what is waiting for me.
            if len(mine) == 1:
                return resolved(mine[0]['id'], mine[0]['title'] or '', 'assumed')
            if mine:
                return ambiguous([_chip(c) for c in mine[:MAX_CHIPS]])
            return self._nothing_waiting(ctx, hidden=hidden)
        full = [c for _e, c in hits]
        if len(full) == 1:
            exact = hits[0][0]
            return resolved(full[0]['id'], full[0]['title'] or '', 'said' if exact else 'assumed')
        if full:
            return ambiguous([_chip(c) for c in full[:MAX_CHIPS]])
        if hidden and match_cards(ctx, inbox, text, hidden):
            # FIX-1b: what they named IS a request about access — said
            # plainly, never decided.
            return self._nothing_waiting(ctx, hidden=hidden)
        # Not in MY inbox: is it something I can see, waiting for somebody else?
        mine_ids = {c['id'] for c in mine}
        for scope in self._scopes(inbox):
            try:
                others = (inbox.list_requests(tab='all', scope=scope) or {}).get('cards') or []
            except (AccessError, UserError):
                continue
            others = [c for c in others if c['id'] not in mine_ids]
            others, others_access = self._not_access(ctx, others)
            if others_access and match_cards(ctx, inbox, text, others_access):
                return self._nothing_waiting(ctx, hidden=others_access)
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
        return self._nothing_waiting(ctx, text, hidden=hidden)

    def _scopes(self, inbox):
        scopes = ['me']
        try:
            if inbox._can_org():
                scopes.append('org')
        except Exception:                               # noqa: BLE001
            pass
        return scopes

    def _nothing_waiting(self, ctx, text='', hidden=()):
        """`hidden`: the requests about access left out of what PayAI may
        decide. With nothing named (or the named thing IS one of them, see
        `_resolve_item`) the access sentence answers; when something else
        was named and not found, the person is told THAT first — never a
        reply about access alone, as if what they named were one."""
        if hidden and not (text or '').strip():
            # FIX-1b: only access requests wait — said plainly, never decided.
            out = missing(T(ACCESS_REQUEST_TEXT))
            out['door_id'] = APPROVALS_DOOR
            return out
        if hidden:
            out = missing(T(_lt(
                'I could not find "%s" waiting for your decision. Only requests about '
                'access are waiting for you, and PayAI does not decide those: decide '
                'them yourself on the Approvals screen.')) % text[:60])
            out['door_id'] = APPROVALS_DOOR
            return out
        note = T(_lt('Nothing is waiting for your decision right now.'))
        if (text or '').strip():
            note = T(_lt('I could not find "%s" waiting for your decision, and nothing '
                         'else is waiting for you right now.')) % text[:60]
        out = missing(note)
        out['door_id'] = APPROVALS_DOOR
        return out

    def _access_card(self, ctx, title=''):
        """FIX-1b: the plain refusal for a request about access — no door to
        it, nothing decided, nobody reminded."""
        return cards.card('refused', ctx.task, 'never', title=_lt('Not through PayAI'),
                          subtitle=title or '',
                          notes=[cards.note('bad', ACCESS_REQUEST_TEXT)])

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
        _file_under(ctx, request.company_id)
        # P3:ux-11 — a door to the item itself: "Open my approvals" lands on
        # "My turn", where a request that is not yours is not listed.
        actions = self._run_door(ctx, request) + \
            self._inbox_door(ctx, request_id=request.id, scope=scope)
        title = request.title or ''
        if request.state == 'blocked':
            return cards.card(
                'refused', ctx.task, 'decide', title=_lt('Nobody can decide this yet'),
                subtitle=title, notes=[cards.note('warn', request.block_reason or T(_lt(
                    'Nobody could be found to decide it.')))], actions=actions)
        if request.state != 'pending' or not seats:
            return self._gone_card(ctx, request)
        who = _joined([s['name'] for s in seats], step.kind == 'joint')
        facts = {'what': title, 'who': who, 'step': step.title or ''}
        uid = ctx.env.uid
        later = self._my_later_step(ctx, request, step)
        if step.seat_ids.filtered(lambda s: s.acting_user_id.id == uid and s.status == 'approved'):
            # P3:ux-9 — they DID decide this step: their part is in.
            card_title = _lt('You have already approved your part')
            text = T(_lt('"%(what)s" now waits for %(who)s at "%(step)s".')) % facts
        elif later:
            # P3:corr-7 — not their turn YET: a later step is theirs.
            card_title = _lt('It comes to you after this step')
            text = T(_lt('"%(what)s" is waiting for %(who)s at "%(step)s". It comes to you '
                         'at "%(mine)s" after that.')) % dict(facts, mine=later.title or '')
        else:
            card_title = _lt('This is not waiting for you')
            text = T(_lt(
                '"%(what)s" is waiting for %(who)s at "%(step)s". You are not the one who '
                'decides it, so I cannot do it for you.')) % facts
        notes = [cards.note('info', text)]
        values = ['%s:%s' % (request.id, s['user_id']) for s in seats[:3]]
        chips = [{'label': T(_lt('Remind %s')) % s['first'], 'sublabel': s['name'],
                  'value': v} for s, v in zip(seats[:3], values)]
        notes.append(cards.note('info', _lt(
            'I can remind them: they get a note on the request and a to-do.')))
        return cards.card(
            'refused', ctx.task, 'decide', title=card_title,
            subtitle=title, notes=notes, actions=actions, chips=chips,
            chip_slot='item', chip_action='remind',
            offer={'slot': 'item', 'values': values, 'actions': ['remind'], 'scope': scope})

    @staticmethod
    def _my_later_step(ctx, request, step):
        """The first decision step AFTER the live one where the asker holds a
        seat (read off the request's own steps, as the drawer shows them)."""
        uid = ctx.env.uid
        for later in request.step_ids.sorted('sequence'):
            if (later.sequence, later.id) <= (step.sequence, step.id) or not later.included \
                    or later.kind in ('notify', 'fast') or later.status != 'pending':
                continue
            if later.seat_ids.filtered(lambda s: s.status == 'open' and uid in (
                    s.acting_user_id.id, s.user_id.id)):
                return later
        return None

    def _gone_card(self, ctx, request=None):
        state = ''
        if request is not None:
            state = dict(request._fields['state']._description_selection(ctx.env)).get(
                request.state) or request.state or ''
        text = T(_lt('This is no longer waiting for a decision (%s).')) % state.lower() \
            if state else T(_lt('I cannot find that request any more.'))
        actions = self._inbox_door(ctx)
        if request is not None:
            actions = self._run_door(ctx, request) + \
                self._inbox_door(ctx, request_id=request.id)
        return cards.card('refused', ctx.task, 'decide', title=_lt('Nothing to decide'),
                          subtitle=(request.title or '') if request is not None else '',
                          notes=[cards.note('info', text)], actions=actions)

    def _run_door(self, ctx, request):
        """"Open the run" on the Runs board, for a pay run (navigation only,
        PA19: the board re-reads the run with the person's own rights)."""
        if request is None or not ctx.has_door(RUNS_DOOR):
            return []
        try:
            record = self._inbox(ctx)._record_of(request)
        except Exception:                               # noqa: BLE001
            record = None
        if not record or record._name != PAYRUN_MODEL:
            return []
        return [cards.door_action(RUNS_DOOR, _lt('Open the run'), 'outline',
                                  hub={'tag': 'pb_pay_hub', 'lens': 'runs',
                                       'focus': T(record.id)})]

    def _inbox_door(self, ctx, style='outline', request_id=0, scope='me'):
        if not ctx.has_door(APPROVALS_DOOR):
            return []
        return [cards.door_action(APPROVALS_DOOR, _lt('Open my approvals'), style,
                                  hub=approvals_hub(request_id, scope))]

    def _conflict_card(self, ctx, request, conflict):
        """The independence rule, in the inbox drawer's own words (its `text`
        and `note`, P3:ux-7). PayAI never uses an exception: if one exists,
        the screen is where it is used."""
        notes = [cards.note('bad', ' '.join(
            x for x in (conflict.get('text') or '', conflict.get('note') or '') if x))]
        if conflict.get('grant_id'):
            notes.append(cards.note('info', _lt(
                'PayAI never uses an exception: open your approvals to use it there.')))
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
        # FIX-1b (owner ruling 2026-10-13): deciding an access request gives
        # or takes a role — never through PayAI, on the plan or at Do it.
        if gate.access_request(ctx.env, ctx.env['biz.approval.request'].browse(pay['id']),
                               pay.get('process_key')):
            return None, self._access_card(ctx, pay.get('title'))
        # P3:sec-1 — the switch of the company the REQUEST belongs to, not of
        # the company in the top bar: the inbox lists every ticked company.
        # Asked on the plan and again at Do it (the runner re-plans).
        company = ctx.env['biz.approval.request'].browse(pay['id']).company_id
        _file_under(ctx, company)
        if not gate.tier_on(ctx.env, self.tier, company):
            from . import runner
            return None, runner._refusal_card(ctx, self, 'tier_off')
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
        off the request's OWN steps and seats, exactly as the drawer shows
        them (a hand-over is named only once the seat carries it, P3:crit-5),
        and what the engine's `_activate_next` will do with them:

          * a joint step: the person's approval counts for ONE of their open
            seats (`decide` takes the first); others still open — the step
            waits (`others`), and so does their own second seat (`again`,
            P3:corr-5);
          * a later decision step that is blocked, or the next one with no
            seat at all, stops the request there (`stuck`, P3:corr-2);
          * else the next pending step and its people (`next`).
        """
        steps = self._decision_steps(pay)
        current = next((s for s in steps if s.get('status') == 'active'), None)
        index = steps.index(current) + 1 if current else 0
        others, again = [], []
        if current and current.get('joint'):
            open_seats = [s for s in current.get('seats') or [] if s.get('status') == 'open']
            mine = [s for s in open_seats if s.get('mine')]
            others = [_seat_label(s) for s in open_seats if not s.get('mine')]
            again = [s.get('covering_for') or s.get('name') or '' for s in mine[1:]]
        nxt = stuck = None
        if current:
            later = steps[index:]
            stuck = next((s for s in later if s.get('status') == 'blocked'), None)
            if stuck is None:
                nxt = next((s for s in later if s.get('status') == 'pending'), None)
                if nxt is not None and not nxt.get('seats'):
                    stuck, nxt = nxt, None
        next_names = [_seat_label(s) for s in (nxt or {}).get('seats') or []
                      if s.get('status') == 'open']
        return {'current': current, 'index': index, 'total': len(steps), 'next': nxt,
                'next_names': [n for n in next_names if n],
                'next_joint': bool(nxt and nxt.get('joint')),
                'stuck': stuck, 'others': others, 'again': again}

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
        # P3:ux-6 — a step is a step name ("HR Manager check"), not a role.
        sub = T(_lt('Decide · your decision at %(step)s · PayAI cannot undo it')) % {
            'step': current['title']} if current.get('title') else \
            T(_lt('Decide · your decision · PayAI cannot undo it'))
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
                'others': route['others'],
                'last': not route['next'] and not route['stuck'],
                'process_key': pay.get('process_key') or '',
                'submitted_by': pay.get('submitted_by') or '',
                # The secret half of the idempotency key (`_decision_key`):
                # kept server-side on the task, never on the card.
                'nonce': secrets.token_hex(16)}
        speak = T(_lt('This is a decision. I need you to type the word %s on the card; '
                      'voice cannot confirm it.')) % word
        # `company_id`: the company the decision is made IN (the request's);
        # `_read` has already filed the task row under it (P3:sec-1).
        company = ctx.env['biz.approval.request'].browse(pay['id']).company_id
        return {'card': card, 'vals': vals, 'fingerprint': fp, 'speak': speak,
                'company_id': company.id}

    # ---------------------------------------------------------- Do it
    def confirm(self, ctx, task, params, data):
        vals = data.get('vals') or {}
        reason = vals.get('reason') or ''
        # P3:crit-1 — what is in the Note box is what goes on the record, as
        # on the Approvals screen. The card pre-fills the box with the planned
        # words, so an untouched box keeps them; a cleared box records none.
        # Every confirm through the runner carries the box (`confirm_note`;
        # `rpc_confirm_task` and `runner.confirm` both turn a missing note
        # into ''), so a caller that sends no note also records none — on
        # purpose: words the approver may have removed never reach the record.
        # Only a direct call that never went through `runner.confirm` (no
        # `confirm_note` on the context at all) keeps the planned words.
        note = getattr(ctx, 'confirm_note', None)
        if not self.reason_required and note is not None:
            reason = _clip(note)
        inbox = self._inbox(ctx)
        request = ctx.env['biz.approval.request'].browse(int(vals['request_id']))
        key = self._decision_key(task, request, vals)
        try:
            # Its own savepoint, so what is read to judge a refusal is read
            # BEFORE the engine's half-written work is rolled back, and the
            # rest of Do it never sees that work.
            with ctx.env.cr.savepoint():
                try:
                    after = inbox.decide(request.id, vals['step_key'], self.engine_action,
                                         reason, expected_lock_revision=vals.get('lock_revision'),
                                         idempotency_key=key)
                except (UserError, AccessError) as exc:
                    raise _Refused(exc, self._moved(ctx, inbox, request, vals, key)) from exc
        except _Refused as refused:
            ctx.env.invalidate_all()
            if refused.moved:
                raise Stale(str(refused.exc)) from refused.exc
            raise refused.exc
        decision = self._recorded(ctx, request, key)
        if not decision:
            # The engine answered without recording anything (its
            # idempotency check matched a decision that is not this one):
            # nothing happened, so no done card, no "Recorded" line.
            ctx.env.invalidate_all()
            _logger.warning("PayAI: decide returned without a decision under task %s's key "
                            "on request %s", task.id, request.id)
            raise UserError(T(_lt(
                'Nothing was recorded: your decision did not go through, and the request '
                'still waits for you. Decide it on the Approvals screen.')))
        return self._result_card(ctx, task, vals, after, reason, decision)

    @staticmethod
    def _decision_key(task, request, vals):
        """The engine's idempotency key for this task's decision.

        The engine looks a key up across EVERY request and every person, and
        anybody can record a decision under a key of their choosing through
        the inbox's public `decide` — so a key another person can guess
        (the task id is on every card) would let them make this decision
        silently do nothing. The key is tied to the task AND the request and
        carries a random part the plan stored on the task (`vals['nonce']`),
        which never leaves the server. A plan made before the nonce existed
        gets a fresh random part: Do it runs once per task (the runner locks
        the task row and answers a second press from its stored card)."""
        nonce = vals.get('nonce') or secrets.token_hex(16)
        return 'payai-task-%s-%s-%s' % (task.id, request.id, nonce)

    @staticmethod
    def _recorded(ctx, request, key):
        """The decision Do it recorded: on THIS request, under THIS task's
        key, by THIS person — the only proof the done card may stand on."""
        return ctx.env['biz.approval.decision'].search(
            [('request_id', '=', request.id), ('idempotency_key', '=', key),
             ('user_id', '=', ctx.env.uid)], limit=1)

    @staticmethod
    def _moved(ctx, inbox, request, vals, key):
        """Did the plan's world move (P3:corr-1)? Asked inside the decision's
        savepoint, before it is rolled back.

        A decision row under this task's key means the engine ACCEPTED the
        decision and something after it failed (the record's own
        `_approval_return`, the next step, the drawer's re-read): that is a
        real failure, shown as it is — never "things changed", which would
        loop. Without one, the engine refused at its door: the plan is stale
        only when the lock, the live step or the seat really moved."""
        try:
            if ctx.env['biz.approval.decision'].search_count(
                    [('request_id', '=', request.id), ('idempotency_key', '=', key)]):
                return False
        except Exception:                               # noqa: BLE001
            _logger.info("PayAI: decision read failed while judging a refusal", exc_info=True)
        try:
            request.invalidate_recordset()
            return bool(request.lock_revision != vals.get('lock_revision')
                        or request.current_step_key != vals['step_key']
                        or not inbox._is_mine(request))
        except Exception:                               # noqa: BLE001
            # Unreadable: show the engine's own sentence rather than loop.
            _logger.info("PayAI: request unreadable while judging a refusal", exc_info=True)
            return False

    def _result_card(self, ctx, task, vals, after, reason, decision):
        # P3:corr-2 — a request the engine BLOCKED is not "approved".
        tone = 'warn' if after.get('state') == 'blocked' else 'ok'
        notes = [cards.note(tone, self._outcome(vals, after))]
        if after.get('block_reason') and after.get('state') == 'approved':
            notes.append(cards.note('warn', T(_lt(
                'Approved, but it could not be carried out yet: %s')) % after['block_reason']))
        scenario = LEARN_FOR.get(vals.get('process_key') or '')
        actions = self._run_door(ctx, ctx.env['biz.approval.request'].browse(after['id'])) \
            if after.get('id') else []
        actions += self._inbox_door(ctx, request_id=after.get('id') or 0)
        if scenario:
            learn = learn_action(scenario)
            if scenario in LEARN_LABEL:
                learn['label'] = T(LEARN_LABEL[scenario])
            actions.append(learn)
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
        if route.get('again'):
            return T(_lt('Your seat for %s still waits on this step')) % _joined(route['again'])
        if route['others']:
            return T(_lt('%s still has to approve this step too')) % _joined(route['others'])
        if route.get('stuck'):
            return T(_lt('%s · nobody can decide it yet')) % (
                route['stuck'].get('title') or T(_lt('The next step')))
        if route['next']:
            names = _joined(route['next_names'], route.get('next_joint'))
            title = route['next'].get('title') or ''
            return '%s · %s' % (title, names) if names else title
        return T(_lt('Nobody: approving finishes it'))

    def _what_happens(self, pay, route):
        payrun = pay.get('process_key') == 'payrun'
        if route.get('again'):
            return T(_lt('You hold %(n)s seats on this step. This approval counts for one; '
                         'ask me again to approve the one you hold for %(whose)s.')) % {
                'n': num(len(route['again']) + 1), 'whose': _joined(route['again'])}
        if route['others']:
            return T(_lt('Your approval is recorded; the step waits for %s as well.')) % \
                _joined(route['others'])
        if route.get('stuck'):
            text = T(_lt('After you it stops at %s: nobody can decide that step yet, so it '
                         'waits there until whoever looks after approvals sets it up.')) % (
                route['stuck'].get('title') or T(_lt('the next step')))
            if payrun:
                text += ' ' + T(_lt('Nobody is paid by approving.'))
            return text
        if route['next']:
            names = _joined(route['next_names'], route.get('next_joint'))
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
        """What the ENGINE did with the approval, read off its answer
        (P3:corr-2): still waiting on this step, moved on, blocked, or
        approved. Worded around the step's name (P3:ux-6)."""
        step = ''
        for s in after.get('steps') or []:
            if s.get('key') == vals.get('step_key'):
                step = s.get('title') or ''
        payrun = vals.get('process_key') == 'payrun'
        state = after.get('state')
        if state == 'blocked':
            return T(_lt('Your approval is recorded, but it cannot move on: %s')) % (
                after.get('block_reason') or T(_lt('nobody could be found to decide the next '
                                                   'step.')))
        live = next((s for s in after.get('steps') or [] if s.get('status') == 'active'), None)
        facts = {'step': step}
        if live and live.get('key') == vals.get('step_key'):
            facts['who'] = _joined([_waiting_label(x) for x in live.get('seats') or []
                                    if x.get('status') == 'open'], live.get('joint'))
            text = _lt('Your approval at %(step)s is recorded. The step still waits for '
                       '%(who)s.') if step else \
                _lt('Your approval is recorded. The step still waits for %(who)s.')
            return T(text) % facts
        if live:
            names = _joined([_seat_label(x) for x in live.get('seats') or []
                             if x.get('status') == 'open'], live.get('joint'))
            facts.update({'next': live.get('title') or '',
                          'who': (' (%s)' % names) if names else ''})
            text = T(_lt('Approved at %(step)s. It moves to %(next)s%(who)s.') if step
                     else _lt('Approved. It moves to %(next)s%(who)s.')) % facts
            if payrun:
                text += ' ' + T(_lt('Nobody has been paid yet.'))
            return text
        if state in ('approved', 'applied'):
            if payrun:
                return T(_lt('Approved at %(step)s. That was the last step: the run is '
                             'approved. Nobody has been paid yet.') if step else
                         _lt('Approved. That was the last step: the run is approved. '
                             'Nobody has been paid yet.')) % facts
            return T(_lt('Approved at %(step)s. That was the last step, so it goes ahead.')
                     if step else _lt('Approved. That was the last step, so it goes ahead.')) \
                % facts
        # Anything else (the request ended some other way meanwhile): only
        # what is certain.
        return T(_lt('Your approval is recorded.'))


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
    """P3:ux-4 — the Approvals inbox's own words for this act: its button is
    "Turn it down", its badge "Turned down". The typed word follows the
    inbox's ("TURN DOWN"; Vietnamese TỪ CHỐI is already the inbox's "Từ
    chối"); REJECT, the word P3 shipped, is still accepted."""
    key = 'reject_item'
    title = _lt('Turn something down')
    title_short = _lt('Turn down')
    title_on = _lt('Turn down %s')
    done_title = _lt('Turned down')
    summary = _lt('Turn down a request that is waiting for your decision, with a reason; '
                  'confirmed by typing TURN DOWN.')
    examples = (_lt('Turn down the May bonus run because it was paid twice'),)
    right_subject = _lt('Turning down')
    confirm_word = 'TURN DOWN'
    confirm_word_vi = 'TỪ CHỐI'
    #: Accepted as well, never shown: the word P3 shipped.
    confirm_word_old = 'REJECT'
    icon = 'circlex'
    did = _lt('turned down')
    engine_action = 'reject'
    reason_required = True
    slots = (Slot('item', _lt('What'), 'item', True,
                  "What to turn down (reject), in the person's words. Never an id."),
             Slot('reason', _lt('Reason'), 'reason', True,
                  "Why, in the person's own words."))
    phrases = (r'^(?:reject|decline|refuse|turn\s+down)\s+(?P<item>.+?)' + _REASON_TAIL,
               # FIX-1 (P3 crit-4): the inbox's own "Turn it down" word order.
               r'^turn\s+(?P<item>.+?)\s+down(?:\s+instead)?' + _REASON_TAIL)

    def confirm_words(self):
        return super().confirm_words() + (self.confirm_word_old,)

    def _reason_question(self):
        return T(_lt('Why is it turned down? Type the reason.'))

    def _next_label(self, pay, route):
        return T(_lt('It ends here'))

    def _what_happens(self, pay, route):
        if pay.get('process_key') == 'payrun':
            return T(_lt('The run is turned down and every payslip in it is cancelled. It '
                         'cannot be sent again; a new run has to be prepared.'))
        return T(_lt('It is turned down and ends here. %s is told, with your reason.')) % (
            pay.get('submitted_by') or T(_lt('Whoever sent it in')))

    def _outcome(self, vals, after):
        if vals.get('process_key') == 'payrun':
            return T(_lt('Turned down. The run and its payslips are cancelled, and %s is '
                         'told why.')) % (vals.get('submitted_by') or T(_lt('whoever sent it in')))
        return T(_lt('Turned down. %s is told why.')) % (
            vals.get('submitted_by') or T(_lt('Whoever sent it in')))


# ------------------------------------------------------------------ remind
def remind(ctx, task, value, offer):
    """"Remind <name>" on a not-yours card: the engine's own reminder (the
    outbox's 'reminder' kind — the same note the overdue cron sends: a
    message on the request and a to-do for them), at most once a day per
    person and step, and an event in the approval trail under the asker's
    name. Never a decision, never a move.

    P3:sec-2/corr-3/ux-8:
      * the gate is asked again on the press (switch, screen, right — and
        the switch of the request's own company), not only when the card
        was made;
      * "already reminded today" means THIS person on THIS step, today in
        the asker's own day (the day the outbox's dedupe key names): the
        overdue cron's reminder of the step, or a PayAI reminder for them;
      * "sent" / "Recorded" only when THIS press made the outbox row (and,
        for "Recorded", the trail line was written). The outbox's `_queue`
        hands back the EXISTING row on a repeat key, so a row already under
        the key — a press by somebody in a time zone where the day began
        earlier, or an earlier press whose trail line failed — is "already
        reminded", never a second claim (P3:sec-2).
    """
    action = ACTIONS.get(task.action_key) if task else None
    if action is None:
        raise AccessError(T(_lt('That button was not offered here.')))
    ok, why = gate.allowed(ctx.env, ctx.user, action)
    if not ok:
        return _refused_now(ctx, action, why)
    try:
        request_id, user_id = [int(x) for x in str(value).split(':', 1)]
    except (TypeError, ValueError):
        raise AccessError(T(_lt('That button was not offered here.')))
    inbox = ctx.env['pb.approval.inbox']
    request = inbox._readable(request_id, (offer or {}).get('scope') or 'me')
    if gate.access_request(ctx.env, request):
        # FIX-1b: nobody is chased about an access request through PayAI.
        card = action._access_card(ctx, request.title or '')
        card['transient'] = True
        return card
    _file_task(task, request.company_id)                 # P3:sec-1
    if not gate.tier_on(ctx.env, action.tier, request.company_id):
        return _refused_now(ctx, action, 'tier_off')
    step = inbox._current_step(request)
    seat = step.seat_ids.filtered(
        lambda s: s.status == 'open' and s.acting_user_id.id == user_id)[:1]
    if request.state != 'pending' or not seat:
        return cards.card('blocked', task, 'decide', title=_lt('It has moved on'),
                          subtitle=request.title or '', transient=True,
                          notes=[cards.note('info', _lt(
                              'They are no longer the one deciding it, so I sent nothing.'))])
    whom = seat.acting_user_id
    since, day = _day_start_utc(ctx.env)
    # The overdue cron reminds every open seat of the step at once.
    already = bool(step.reminded_at and step.reminded_at >= since)
    if not already:
        events = ctx.env['biz.approval.event'].search([
            ('request_id', '=', request.id), ('kind', '=', 'reminded'),
            ('create_date', '>=', since)])
        already = any((e.payload or {}).get('step_id') == step.id
                      and (e.payload or {}).get('user_id') == whom.id for e in events)
    Outbox = ctx.env['biz.approval.outbox']
    key = 'payai-remind-%s-%s-%s' % (step.id, whom.id, day)
    if not already:
        # The outbox itself: a row under today's key (whoever pressed first,
        # whatever their time zone), or a PayAI reminder for this person and
        # step made since the start of the asker's day under another day's
        # key (a press from a time zone already on the next date).
        from . import runner
        already = runner.payai_reminder_queued(ctx.env, key, step, whom, since)
    if already:
        return cards.card('done', task, 'decide', title=T(_lt('Reminded %s')) % whom.name,
                          subtitle=request.title or '', transient=True,
                          notes=[cards.note('info', T(_lt(
                              '%s was already reminded about this today.')) % whom.name)])
    # Nothing is under the key (asked just above), so a row back from
    # `_queue` is the one this press made.
    row = Outbox._queue('reminder', whom, request, payload={'step_title': step.title or ''},
                        dedupe=key)
    if not row:
        # `_queue` takes nothing for a sign-in that cannot receive it.
        return cards.card('blocked', task, 'decide', title=_lt('Nothing was sent'),
                          subtitle=request.title or '', transient=True,
                          notes=[cards.note('warn', T(_lt(
                              'I could not remind %s: their sign-in cannot receive '
                              'reminders. Nothing was sent.')) % whom.name)])
    recorded = True
    try:
        ctx.env['biz.approval.event']._log(
            'reminded', T(_lt('%(who)s asked PayAI to remind %(whom)s about "%(step)s" '
                              'on "%(what)s"')) % {
                'who': ctx.user.name, 'whom': whom.name, 'step': step.title or '',
                'what': request.title or ''},
            company=request.company_id, request=request,
            payload={'step_id': step.id, 'user_id': whom.id, 'via': 'payai'})
    except Exception:                                   # noqa: BLE001
        recorded = False
        _logger.info("PayAI: reminder event not written", exc_info=True)
    text = T(_lt('%s gets a note on the request and a to-do. Recorded.')) if recorded \
        else T(_lt('%s gets a note on the request and a to-do.'))
    return cards.card('done', task, 'decide', title=T(_lt('Reminded %s')) % whom.name,
                      subtitle=request.title or '', transient=True,
                      notes=[cards.note('ok', text % whom.name)])


def _refused_now(ctx, action, reason):
    """The gate said no on a follow-up press: the runner's own refusal card,
    added below the card it answers (nothing was sent)."""
    from . import runner
    card = runner._refusal_card(ctx, action, reason)
    card['transient'] = True
    return card
