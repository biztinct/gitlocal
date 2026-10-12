# -*- coding: utf-8 -*-
"""AMBER ACTIONS — PayAI prepares, the person presses Do it.

run_payroll, submit_run, update_pay_data, send_payslips, filing_prepare.

Every one follows the same shape (P2_HANDOVER §Scope):

  plan(ctx, params)     resolved words → the plan card, built from the SAME
                        read-only previews the screen shows (`plan_preview`,
                        `preview_changes`, the run's own approval check), plus
                        the exact `vals` that will be used and a fingerprint
                        of what the card promised;
  confirm(...)          server-executed Actions: the screen's own method, as
                        the person (PA-R2), inside the runner's savepoint;
  finish(...)           run_payroll only: the BROWSER drives the wizard's
                        chain (the shared run driver) and reports back;
  undo(...)             the compensating action the screen itself offers
                        (delete a draft run, withdraw a request, put a value
                        back), as the person, for ten minutes.

Nothing here is ever sudo, and no id comes from the browser or the model:
`vals` are built here and handed to the client by `rpc_confirm_task`.
"""
import json
import logging
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from .i18n import T

from . import cards
from .actions_green import RUNS_DOOR, _board_rows, _row_for, money, run_door
from .registry import Action, Slot, payai_action
from .resolve import (
    MAX_CHIPS, ambiguous, fold, missing, month_label, parse_amount, parse_day,
    parse_period, resolve_period, resolve_person, resolve_scheme, resolved,
    state_label, tok_match, tokens,
)

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

PAY_SCREEN = ('pb_payhub.item_pay_run',)
PEOPLE_SCREEN = ('pb_people_hub.item_people',)
COMPLIANCE_SCREEN = ('pb_compliance_hub.item_compliance',)
UNDO_MINUTES = 10

PAY_HUB_RUN = {'tag': 'pb_pay_hub', 'lens': 'run'}
RECORDS_HUB = {'xmlid': 'pb_people_hub.action_pb_people_hub', 'lens': 'records'}
FILINGS_DOOR = 'cmphub_filings'
DELIVER_DOOR = 'payhub_deliver'
#: The Pay & Deliver role (pb_pay_delivery/models/approval_common.py PAY_GROUPS).
PAY_GROUPS = ('om_hr_payroll.group_hr_payroll_manager',
              'account.group_account_invoice', 'account.group_account_user')
#: Who produces a filing (pb_govt_reports/models/pb_filing_flow.py).
FILING_GROUPS = ('pb_hr_payroll_base.group_payroll_base_officer',
                 'pb_hr_payroll_base.group_payroll_base_manager')


# ----------------------------------------------------------------- helpers
def fingerprint(*parts):
    return json.dumps(parts, sort_keys=True, default=str)


def slot_row(key, label, value_label, origin, editable=False, origin_label=''):
    """origin_label: optional words that replace the origin chip text, so a
    'default' chip can say WHY (e.g. "current company")."""
    return {'key': key, 'label': T(label), 'value_label': T(value_label or ''),
            'origin': origin or 'default', 'editable': editable,
            'origin_label': T(origin_label) if origin_label else ''}


def plan_actions(do_label=None, screen=None, can_do=True, do_style='primary'):
    """Do it · Open in the screen instead · Cancel — the plan card's row."""
    acts = []
    if can_do:
        acts.append({'id': 'do', 'label': T(do_label or _lt('Do it')), 'style': do_style})
    if screen:
        acts.append(screen)
    acts.append({'id': 'cancel', 'label': T(_lt('Cancel')), 'style': 'ghost'})
    return acts


def screen_action(label, hub=None, door_id='', prefill=None, context=None,
                  style='outline'):
    """"Open in the screen instead" — navigation only, filled in where the
    screen accepts it (PA19: never anything but a door)."""
    act = {'id': 'prefill' if prefill is not None else 'door', 'label': T(label),
           'style': style, 'icon': 'panel'}
    if hub:
        act['hub'] = dict(hub, context=context or {}) if context else dict(hub)
    if door_id:
        act['door_id'] = door_id
    if prefill is not None:
        act['prefill'] = prefill
    return act


def _has_any_group(user, groups):
    for xmlid in groups:
        try:
            if user.has_group(xmlid):
                return True
        except Exception:                               # noqa: BLE001
            continue
    return False


def _plain(exc):
    return T(exc.args[0] if getattr(exc, 'args', None) else exc)


def _day_label(day):
    return '%s %s' % (day.day, month_label(day)) if day else ''


def _period_words(period):
    """"1 to 30 June 2026"."""
    try:
        start = fields.Date.to_date(period['date_start'])
        end = fields.Date.to_date(period['date_end'])
    except Exception:                                   # noqa: BLE001
        return ''
    if start.month == end.month and start.year == end.year:
        return T(_lt('%(a)s to %(b)s %(month)s')) % {
            'a': start.day, 'b': end.day, 'month': month_label(start)}
    return '%s – %s' % (_day_label(start), _day_label(end))


def undo_block(minutes, label, note, can=True):
    until = fields.Datetime.now() + timedelta(minutes=minutes)
    return {'until_iso': fields.Datetime.to_string(until) + 'Z' if can else '',
            'label': T(label) if can else '', 'note': T(note), 'can': bool(can)}


class _Amber(Action):
    tier = 'prepare'
    priority = 20
    undo_minutes = UNDO_MINUTES


# =========================================================================
@payai_action
class RunPayroll(_Amber):
    key = 'run_payroll'
    title = _lt('Run payroll')
    summary = _lt('Prepare a draft pay run for a month and a scheme, after '
                  'showing the plan. Creates a draft only.')
    examples = (_lt('Run June payroll for Retail'), _lt('Run payroll for this month'))
    slots = (Slot('period', _lt('Period'), 'period', False,
                  "The month to run, in the person's words, e.g. 'June' or "
                  "'June 2026'. Empty means this month."),
             Slot('scheme', _lt('Scheme'), 'scheme', False,
                  "The payroll scheme or part of the business, in the "
                  "person's words, e.g. 'Retail'. Never an id."),
             Slot('people', _lt('People'), 'text', False,
                  "Who to include if the person said, e.g. 'active only'. "
                  "Empty means everyone the scheme covers."))
    screen_keys = PAY_SCREEN
    door_id = 'payhub_run'
    right_subject = _lt('Running payroll')
    right_label = _lt('Run payroll')
    drive = True
    phrases = (
        r'^(?:run|process|calculate|compute|start|prepare|do)\s+(?:the\s+)?'
        r'(?P<period>[^.]*?)\s*payroll\b(?:\s+(?:for|of)\s+(?P<scheme>.+))?$',
        r'^(?:run|process|start|prepare|create|make)\s+(?:a\s+|the\s+)?(?:new\s+)?'
        r'pay\s*run\b(?:\s+(?:for|of)\s+(?P<scheme>.+))?$',
    )

    def method_gate(self, env, user):
        Wizard = env['pb.payrun.wizard']
        return bool(Wizard._may_run_payroll(user))

    def _defaults(self, ctx):
        cache = ctx.cache
        if 'run_defaults' not in cache:
            cache['run_defaults'] = ctx.env['pb.payrun.wizard'].get_defaults()
        return cache['run_defaults']

    def normalise_texts(self, ctx, texts):
        """"Run payroll for Retail for June": the month rides in the scheme."""
        texts = dict(texts or {})
        scheme = texts.get('scheme') or ''
        if scheme and not texts.get('period'):
            today = fields.Date.context_today(ctx.env.user)
            got = parse_period(scheme, today)
            if got:
                texts['period'] = scheme
                rest = ' '.join(w for w in got[3].split()
                                if w not in ('for', 'of', 'in', 'the', 'payroll', 'run'))
                texts['scheme'] = rest.strip()
        return texts

    def resolve_slot(self, ctx, slot, text):
        if slot.key == 'period':
            if (text or '').strip():
                return resolve_period(ctx, text)
            d = self._defaults(ctx)
            start = fields.Date.to_date(d.get('date_start'))
            return resolved({'date_start': d.get('date_start'), 'date_end': d.get('date_end')},
                            month_label(start) if start else '', 'default')
        if slot.key == 'scheme':
            d = self._defaults(ctx)
            schemes = d.get('schemes') or []
            if not schemes:
                return resolved(0, T(_lt('Every running contract')), 'default')
            if not (text or '').strip():
                pre = d.get('formula_config_id') or 0
                card = next((s for s in schemes if s['id'] == pre), None)
                if card:
                    out = resolved(card['id'], card.get('name') or '', 'default')
                    out['card'] = card
                    return out
                return ambiguous([{'value': s['id'], 'label': s.get('name') or '',
                                   'sublabel': T(_lt('your division')) if s.get('mine')
                                   else (s.get('cycle_label') or '')}
                                  for s in schemes[:MAX_CHIPS]])
            return resolve_scheme(ctx, text, defaults=d)
        if slot.key == 'people':
            return resolved(text or '', text or '', 'said' if text else 'default')
        return super().resolve_slot(ctx, slot, text)

    def reask_slot(self, ctx, slot):
        # Empty words pick the pre-selected scheme; the pencil offers them all.
        if slot.key == 'scheme':
            schemes = self._defaults(ctx).get('schemes') or []
            if len(schemes) > 1:
                return ambiguous([{'value': s['id'], 'label': s.get('name') or '',
                                   'sublabel': T(_lt('your division')) if s.get('mine')
                                   else (s.get('cycle_label') or '')}
                                  for s in schemes[:MAX_CHIPS]])
        return super().reask_slot(ctx, slot)

    # ------------------------------------------------------------- plan
    def _statuses(self, ctx, people_text):
        """The wizard's own default ticks; words like 'active only' narrow them."""
        opts = self._defaults(ctx).get('statuses') or []
        if not opts:
            return None, ''
        chosen = [o['value'] for o in opts if o.get('default')]
        words = tokens(people_text or '')
        if words and not set(words) & {'everyone', 'all', 'everybody'}:
            hit = [o['value'] for o in opts
                   if any(tok_match(w, t) for w in words
                          for t in tokens('%s %s' % (o.get('value') or '', o.get('label') or '')))]
            if hit:
                return hit, ', '.join(hit)
        if words and set(words) & {'everyone', 'all', 'everybody'}:
            return [o['value'] for o in opts], T(_lt('every employment status'))
        return chosen, ''

    def _vals(self, ctx, params):
        d = self._defaults(ctx)
        per = params['period']['value']
        sch = params['scheme']
        card = sch.get('card') or next(
            (s for s in d.get('schemes') or [] if s['id'] == sch.get('value')), None) or {}
        start = fields.Date.to_date(per['date_start'])
        label = month_label(start)
        if card and d.get('is_demo') and per['date_start'] == d.get('date_start'):
            name = '%s — %s' % (d.get('name') or '', card.get('name') or '')
        elif card:
            name = '%s · %s' % (card.get('name') or '', label)
        else:
            name = 'Payroll %s' % label
        vals = {'name': name, 'date_start': per['date_start'], 'date_end': per['date_end'],
                'formula_config_id': int(sch.get('value') or 0)}
        if card.get('division'):
            vals['division'] = card['division']
        statuses, said = self._statuses(ctx, (params.get('people') or {}).get('value'))
        if statuses is not None:
            vals['statuses'] = statuses
        return vals, card, said

    def plan(self, ctx, params):
        W = ctx.env['pb.payrun.wizard']
        vals, card, said_statuses = self._vals(ctx, params)
        sheet = {}
        try:
            sheet = W.spreadsheet_gate({'formula_config_id': vals['formula_config_id']}) or {}
        except Exception:                               # noqa: BLE001
            sheet = {}
        if sheet.get('wanted'):
            vals['spreadsheet_skipped'] = True
        pv = W.plan_preview(vals)
        scheme_name = card.get('name') or T(_lt('this payroll'))
        period = params['period']
        month = month_label(fields.Date.to_date(vals['date_start']))
        if pv.get('existing'):
            return self._exists_card(ctx, pv, scheme_name, month)

        may_delete = self._may_delete(ctx)
        cur = (card.get('currency') or {}) if card else {}
        lanes = sheet.get('lanes') or {}
        slots = [
            slot_row('period', _lt('Period'), _period_words(vals), period.get('origin'), True),
            slot_row('scheme', _lt('Scheme'), scheme_name, params['scheme'].get('origin'), True),
            slot_row('company', _lt('Company'), ctx.env.company.name,
                     'default', origin_label=_lt('current company')),
        ]
        # The People slot shows what the wizard's scheme card shows: who the
        # scheme covers (incl. host employments it gains), not the raw list.
        covered = pv.get('covered', pv['total'])
        who = T(_lt('All %(n)s covered by this scheme')) % {'n': '{:,}'.format(covered)}
        if said_statuses:
            who = T(_lt('%(n)s people · %(which)s')) % {'n': '{:,}'.format(covered),
                                                       'which': said_statuses}
        slots.append(slot_row('people', _lt('People'), who,
                              'said' if said_statuses else 'default', True))
        notes = []
        if sheet.get('wanted'):
            comps = sheet.get('components') or []
            slots.append(slot_row('pay_data', _lt('Pay data'),
                                  _lt('Without this month\'s file'), 'assumed', True))
            notes.append(cards.note('warn', T(_lt(
                'This scheme expects a pay data file for %(n)s value(s). Files '
                'are not sent through chat, so if I run it now those values use '
                'their usual amounts. To load the file, open it in the screen '
                'instead.')) % {'n': len(comps)}))
        else:
            parts = []
            if lanes.get('api', True):
                parts.append(T(_lt('the connected system')))
            if lanes.get('records', True):
                parts.append(T(_lt('the employee records')))
            src = T(_lt('From %s, as usual')) % T(_lt(' and ')).join(parts) if parts \
                else T(_lt('As the scheme is set up'))
            # The chip says why it is default, unless the value already does.
            slots.append(slot_row('pay_data', _lt('Pay data'), src, 'default', True,
                                  origin_label=_lt('as the scheme is set up') if parts else ''))
        notes.insert(0, cards.note('ok', T(_lt(
            'No %(month)s run exists for %(scheme)s yet.')) % {
                'month': month, 'scheme': scheme_name}))
        if pv.get('not_covered') == 1:
            notes.append(cards.note('info', _lt(
                '1 person in this company is not covered by this scheme and stays '
                'out of this run.')))
        elif pv.get('not_covered'):
            notes.append(cards.note('info', T(_lt(
                '%(n)s people in this company are not covered by this scheme and '
                'stay out of this run.')) % {'n': '{:,}'.format(pv['not_covered'])}))
        if pv.get('adopt'):
            notes.append(cards.note('info', T(_lt(
                '%(n)s payslips already made for this month are taken into the '
                'run instead of being made again.')) % {'n': pv['adopt']}))
        can_do = bool(pv.get('total') or pv.get('adopt'))
        if not can_do:
            notes.append(cards.note('warn', _lt(
                'This scheme covers nobody yet, so the run would be empty. Open '
                'it in the screen to see who the scheme is mapped to.')))
        screen = screen_action(_lt('Open in the screen instead'), hub=PAY_HUB_RUN,
                               prefill=dict(vals),
                               style='primary' if sheet.get('wanted') else 'outline')
        do_label = _lt('Run without the file') if sheet.get('wanted') else _lt('Do it')
        sub = _lt('Prepare · creates a draft run · can be undone for 10 minutes') \
            if may_delete else _lt('Prepare · creates a draft run · a payroll manager can delete it')
        card_out = cards.card(
            'plan', ctx.task, 'prepare', title=self.title, subtitle=sub,
            slots=slots, notes=notes,
            actions=plan_actions(do_label, screen, can_do,
                                 do_style='outline' if sheet.get('wanted') else 'primary'),
            state='planned', icon='play')
        fp = fingerprint(vals, {k: pv.get(k) for k in (
            'covered', 'not_covered', 'total', 'adopt', 'existing', 'blockers')})
        speak = T(_lt('I will run %(month)s payroll for %(scheme)s, %(n)s people.')) % {
            'month': month, 'scheme': scheme_name, 'n': '{:,}'.format(pv['total'])}
        return {'card': card_out, 'vals': vals, 'fingerprint': fp, 'speak': speak,
                'extra': {'total': pv['total'], 'scheme': scheme_name, 'month': month,
                          'currency': cur.get('symbol') or cur.get('name') or ''}}

    def _exists_card(self, ctx, pv, scheme_name, month):
        first = pv['existing'][0]
        notes = [cards.note('warn', T(_lt('%(name)s is %(state)s.')) % {
            'name': r['name'], 'state': state_label(r['state']).lower()})
            for r in pv['existing'][:3]]
        notes.append(cards.note('info', _lt(
            'I never clear or re-run payroll that already exists. Open it on the '
            'Runs board: a draft can be fixed or deleted there, and an approved '
            'run can be sent back.')))
        actions = []
        door = run_door(ctx, first['id'], _lt('Open it'))
        if door:
            actions.append(door)
        return cards.card(
            'blocked', ctx.task, 'prepare',
            title=T(_lt('A %(month)s run for %(scheme)s already exists')) % {
                'month': month, 'scheme': scheme_name},
            subtitle=self.title, notes=notes, actions=actions)

    def _may_delete(self, ctx):
        try:
            return bool(ctx.env['hr.payslip.run'].has_access('unlink')
                        and ctx.env['hr.payslip'].has_access('unlink'))
        except Exception:                               # noqa: BLE001
            return False

    # ----------------------------------------------------- after the drive
    def _made_run(self, ctx, task, data, run_id):
        """The run THIS task made: created by this person after Do it, for
        this period and scheme. A run id from the browser is only accepted
        when it is one of these (PA-R3)."""
        vals = data.get('vals') or {}
        Run = ctx.env['hr.payslip.run']
        domain = [('date_start', '=', vals.get('date_start')),
                  ('date_end', '=', vals.get('date_end')),
                  ('create_uid', '=', ctx.user.id)]
        if task.confirmed_at:
            domain.append(('create_date', '>=', task.confirmed_at - timedelta(seconds=5)))
        if vals.get('formula_config_id') and 'pb_formula_config_id' in Run._fields:
            domain.append(('pb_formula_config_id', '=', vals['formula_config_id']))
        runs = Run.search(domain, order='id desc', limit=5)
        if run_id:
            runs = runs.filtered(lambda r: r.id == int(run_id))
        return runs[:1]

    def finish(self, ctx, task, data, run_id, info):
        info = info or {}
        stage = info.get('stage') or ''
        extra = data.get('extra') or {}
        if stage in ('blocked', 'confirm'):
            # The server said the month exists after all: the same blocked card
            # the plan would show now.
            W = ctx.env['pb.payrun.wizard']
            pv = W.plan_preview(data.get('vals') or {})
            if pv.get('existing'):
                return 'refused', self._exists_card(ctx, pv, extra.get('scheme') or '',
                                                     extra.get('month') or '')
        run = self._made_run(ctx, task, data, run_id)
        if stage != 'done' or not run:
            return 'failed', self._stopped_card(ctx, task, run, info)
        summary = ctx.env['pb.payrun.wizard'].get_summary(run.id)
        try:
            run.write({'pb_prepared_via': 'payai'})
        except (AccessError, UserError):
            _logger.info("PayAI: could not mark run %s as prepared through PayAI", run.id)
        try:
            exc = max(0, min(int(info.get('exceptions') or 0), int(summary.get('count') or 0) + 10000))
        except (TypeError, ValueError):
            exc = 0
        need = int(summary.get('flagged') or 0) + exc
        tiles = [
            {'value': '{:,}'.format(int(summary.get('count') or 0)),
             'label': T(_lt('payslips in draft'))},
            {'value': money(summary.get('total_net'), extra.get('currency') or ''),
             'label': T(_lt('net to pay'))},
            {'value': '{:,}'.format(need), 'label': T(_lt('need a look'))},
        ]
        actions = []
        door = run_door(ctx, run.id, _lt('Open the run'))
        if door:
            actions.append(door)
        actions.append({'id': 'followup', 'action': 'submit_run', 'slot': 'run',
                        'value': T(run.id), 'label': T(_lt('Send for approval')),
                        'style': 'outline', 'icon': 'send'})
        actions.append({'id': 'learn', 'scenario': 'payrun', 'mode': 'watch',
                        'label': T(_lt('Learn to do this yourself')), 'style': 'outline',
                        'icon': 'book'})
        n = int(summary.get('count') or 0)
        if self._may_delete(ctx):
            undo = undo_block(self.undo_minutes, _lt('Undo'), T(_lt(
                'Not what you meant? Undo deletes the draft run and its %(n)s '
                'payslips.')) % {'n': '{:,}'.format(n)})
        else:
            undo = undo_block(0, '', _lt(
                'Ask a payroll manager to delete it, or leave it as a draft.'), can=False)
        notes = []
        if need:
            notes.append(cards.note('warn', T(_lt(
                '%(n)s payslip(s) need a look before this goes for approval. Open '
                'the run to see them.')) % {'n': need}))
        card = cards.card(
            'plan', task, 'prepare', title=T(_lt('Run prepared: %s')) % (run.name or ''),
            subtitle=T(_lt('Draft · %(scheme)s · %(month)s')) % {
                'scheme': extra.get('scheme') or '', 'month': extra.get('month') or ''},
            slots=cards.plan_slots(task), result=tiles, notes=notes, actions=actions, undo=undo, state='done',
            icon='check', progress={'done': n, 'total': n, 'label': T(_lt('Done'))},
            result_ref={'run_id': run.id},
            offer={'slot': 'run', 'values': [T(run.id)], 'actions': ['submit_run']})
        card['audit_line'] = T(_lt(
            'Recorded: run %(id)s prepared by PayAI for %(who)s, %(when)s, from the '
            'words "%(words)s".')) % {
                'id': run.id, 'who': ctx.user.name, 'when': _stamp(ctx),
                'words': (task.utterance or '')[:120]}
        return 'done', card

    def _stopped_card(self, ctx, task, run, info):
        done = int(info.get('done') or 0)
        total = int(info.get('total') or 0)
        notes = []
        if run:
            notes.append(cards.note('warn', T(_lt(
                'The run stopped part-way: %(done)s of %(total)s payslips were made. '
                'The draft run is on the Runs board; open it to finish it.')) % {
                    'done': done, 'total': total}))
        else:
            notes.append(cards.note('bad', _lt(
                'The run stopped before anything was created. Nothing has changed.')))
        if info.get('error'):
            notes.append(cards.note('info', T(_lt('What it said: %s')) % str(info['error'])[:300]))
        actions = []
        if run:
            door = run_door(ctx, run.id, _lt('Open the run'))
            if door:
                actions.append(door)
        actions.append(screen_action(_lt('Open Run payroll'), hub=PAY_HUB_RUN))
        return cards.card('blocked', task, 'prepare', title=_lt('That did not finish'),
                          subtitle=self.title, slots=cards.plan_slots(task),
                          notes=notes, actions=actions,
                          state='failed', result_ref={'run_id': run.id if run else 0})

    def undo(self, ctx, task):
        ref = _ref(task)
        run = ctx.env['hr.payslip.run'].browse(int(ref.get('run_id') or 0)).exists()
        if not run:
            return 'undone', cards.card('done', task, 'prepare', title=_lt('Already gone'),
                                        subtitle=self.title, notes=[cards.note(
                                            'info', _lt('That draft run has already been deleted.'))])
        if run.state != 'draft':
            return None, cards.card(
                'blocked', task, 'prepare', title=_lt('It has moved on'), subtitle=run.name,
                notes=[cards.note('warn', T(_lt(
                    '"%(name)s" is %(state)s now, so it cannot be undone here.')) % {
                        'name': run.name, 'state': state_label(run.state).lower()})],
                actions=[a for a in [run_door(ctx, run.id, _lt('Open the run'))] if a])
        name, n = run.name or '', len(run.slip_ids)
        run.unlink()                                    # as the person — never sudo
        return 'undone', cards.card(
            'done', task, 'prepare', title=_lt('Undone'), subtitle=name,
            notes=[cards.note('ok', T(_lt(
                'The draft run and its %(n)s payslips were deleted. Nothing was '
                'sent anywhere.')) % {'n': n})],
            chips=[{'label': T(_lt('Prepare it again')), 'sublabel': '', 'value': '',
                    'ask': task.utterance or ''}] if task.utterance and '[person-' not in task.utterance else [],
            state='undone', icon='undo')

    def too_late(self, ctx, task, data):
        ref = _ref(task)
        actions = [a for a in [run_door(ctx, int(ref.get('run_id') or 0), _lt('Open the run'))] if a]
        return cards.card(
            'blocked', task, 'prepare', title=_lt('Too late to undo here'),
            subtitle=self.title,
            notes=[cards.note('warn', _lt(
                'Ten minutes have passed. The draft run is still on the Runs board; '
                'a payroll manager can delete it there.'))],
            actions=actions)


def _needs_from_steps(engine, version_id, context):
    """Whether anybody decides, from the version's own definition (as the person).

    Mirrors engine.preview: notify steps never count, fast steps always
    apply, any other step counts when its tier/condition includes it.
    """
    from odoo.addons.biz_approval_workflow.models import definition as D
    version = engine.env['biz.approval.workflow.version'].browse(
        int(version_id)).exists()
    if not version:
        raise UserError(T(_lt('No approval route is set up for this.')))
    d = D.normalise(version.definition)
    steps = [s for s in d['steps'] if s['kind'] == 'fast' or (
        s['kind'] != 'notify' and engine._step_included(d, s, context)[0])]
    return bool(steps) and not all(s['kind'] == 'fast' for s in steps)


def _route_steps(engine, version_id, context):
    """(first approvers, needs anybody, known) for one published route, as the
    person — the same reading for every Amber plan that promises an approval.

    The engine's own preview first (it names people, but is gated for people
    who set routes up); else the version's own steps with the engine's own
    inclusion test (no names). `known` False: neither could be read.
    """
    people, needs, known = [], True, False
    try:
        pv = engine.preview(version_id, context)
        steps = [s for s in pv.get('steps') or [] if s.get('included')
                 and s.get('kind') not in ('notify',)]
        needs = bool(steps) and not all(s.get('kind') == 'fast' for s in steps)
        if steps:
            people = [p.get('name') for p in steps[0].get('people') or [] if p.get('name')]
        known = True
    except Exception:                                   # noqa: BLE001
        try:
            needs = _needs_from_steps(engine, version_id, context)
            known = True
        except Exception:                               # noqa: BLE001
            pass                                        # setting up routes is not their job
    return people, needs, known


def _ref(task):
    try:
        return (json.loads(task.result_json or '{}').get('ref') or {})
    except (TypeError, ValueError):
        return {}


def _stamp(ctx):
    when = fields.Datetime.context_timestamp(ctx.env.user, fields.Datetime.now())
    return when.strftime('%d %b %Y %H:%M')


# =========================================================================
class _RunAmber(_Amber):
    screen_keys = PAY_SCREEN
    door_id = RUNS_DOOR

    def _run(self, ctx, params):
        return ctx.env['hr.payslip.run'].browse(params['run']['value'])

    def _row(self, ctx, run):
        return _row_for(ctx, run, _board_rows(ctx, run.ids))


@payai_action
class SubmitRun(_RunAmber):
    key = 'submit_run'
    title = _lt('Send a pay run for approval')
    summary = _lt('Send a draft pay run to its approvers, after showing the plan.')
    examples = (_lt('Send the June run for approval'),)
    slots = (Slot('run', _lt('Pay run'), 'run', True,
                  "Which pay run, in the person's words: a month and "
                  "optionally a scheme. Never an id."),)
    right_subject = _lt('Sending a pay run for approval')
    right_label = _lt('Pay Run')
    phrases = (
        r'^(?:send|submit|forward)\s+(?:the\s+)?(?P<run>.+?)\s+(?:for|to)\s+'
        r'(?:approval|sign[- ]?off|approve)$',
        r'^submit\s+(?:the\s+)?(?P<run>.*\b(?:run|payroll)s?\b.*)$',
    )

    def method_gate(self, env, user):
        return env['hr.payslip.run'].with_user(user).has_access('write')

    def param_gate(self, ctx, params):
        run = self._run(ctx, params)
        if run.state == 'draft':
            return None
        actions = [a for a in [run_door(ctx, run.id, _lt('Open the run'), 'outline')] if a]
        return cards.card(
            'refused', ctx.task, 'prepare', title=_lt('Already sent'),
            subtitle=run.name or '',
            notes=[cards.note('info', T(_lt(
                'Only a draft run can be sent for approval. "%(name)s" is %(state)s.')) % {
                    'name': run.name or '', 'state': state_label(run.state).lower()})],
            actions=actions)

    def _route(self, ctx, run):
        """(route name, first approvers, needs anybody, known) — best effort, as the person.

        `known` is False when neither the preview nor the version's own steps
        could be read: the plan then promises nothing about withdrawing.
        """
        engine = ctx.env['biz.approval.engine']
        try:
            context = run._approval_context()
            found = engine.resolve_binding(context['company_id'], 'payrun',
                                           context.get('scope_keys'), context.get('kind_key'))
        except Exception:                               # noqa: BLE001
            return '', [], True, False
        if found.get('error'):
            raise UserError((found['error'] or {}).get('message') or T(_lt(
                'No approval route is set up for this run.')))
        people, needs, known = _route_steps(engine, found['version_id'], context)
        return found.get('workflow_name') or '', people, needs, known

    def plan(self, ctx, params):
        run = self._run(ctx, params)
        try:
            run._approval_validate()
            route, people, needs, known = self._route(ctx, run)
        except UserError as exc:
            actions = [a for a in [run_door(ctx, run.id, _lt('Open the run'), 'outline')] if a]
            return cards.card('blocked', ctx.task, 'prepare', title=_lt('This run cannot be sent yet'),
                              subtitle=run.name or '', notes=[cards.note('bad', _plain(exc))],
                              actions=actions)
        row = self._row(ctx, run)
        slots = [
            slot_row('run', _lt('Run'), run.name or '', params['run'].get('origin'), True),
            slot_row('figures', _lt('Figures'), T(_lt('%(n)s people · %(net)s net')) % {
                'n': '{:,}'.format(int(row.get('employees') or 0)),
                'net': money(row.get('net'), row.get('currency'))}, 'default'),
        ]
        if route:
            slots.append(slot_row('route', _lt('Route'), route, 'default'))
        notes = []
        if not known:
            notes.append(cards.note('info', _lt(
                'It goes to the approvers set up for this kind of run. If this route '
                'needs nobody\'s approval, the run is approved as soon as it is sent, '
                'and that cannot be withdrawn.')))
        elif not needs:
            notes.append(cards.note('warn', _lt(
                'This route needs nobody\'s approval: the run is approved as soon '
                'as it is sent, and that cannot be withdrawn.')))
        elif people:
            notes.append(cards.note('info', T(_lt('It goes to %s first.')) % ', '.join(people[:3])))
        else:
            notes.append(cards.note('info', _lt(
                'It goes to the approvers set up for this kind of run.')))
        sub = _lt('Prepare · sends the run for approval · can be withdrawn for 10 minutes') \
            if known and needs else _lt('Prepare · sends the run for approval')
        screen = screen_action(_lt('Open the run instead'),
                               hub={'tag': 'pb_pay_hub', 'lens': 'runs', 'focus': T(run.id)},
                               door_id=RUNS_DOOR)
        card = cards.card('plan', ctx.task, 'prepare', title=self.title, subtitle=sub,
                          slots=slots, notes=notes, actions=plan_actions(None, screen),
                          state='planned', icon='send')
        fp = fingerprint(run.id, run.state, len(run.slip_ids.filtered(lambda s: s.state != 'cancel')),
                         round(float(row.get('net') or 0.0), 2))
        return {'card': card, 'vals': {'run_id': run.id}, 'fingerprint': fp,
                'speak': T(_lt('I will send %s for approval.')) % (run.name or ''),
                'extra': {'needs': needs if known else None}}

    def confirm(self, ctx, task, params, data):
        run = self._run(ctx, params)
        payload = ctx.env['biz.approval.engine'].submit(
            run, idempotency_key='payai-task-%s' % task.id) or {}
        run.invalidate_recordset()
        row = self._row(ctx, run)
        request_id = payload.get('id') or (run.approval_request_id.id if
                                           'approval_request_id' in run._fields else 0)
        actions = [a for a in [run_door(ctx, run.id, _lt('Open the run'))] if a]
        if run.state == 'done':
            return cards.card(
                'plan', task, 'prepare', title=_lt('Approved straight away'), subtitle=run.name,
                slots=cards.plan_slots(task),
                notes=[cards.note('ok', _lt(
                    'This route needs nobody\'s approval, so the run is approved. That is recorded.'))],
                actions=actions, state='done', icon='check',
                result_ref={'run_id': run.id, 'request_id': request_id})
        who = ((row.get('approval') or {}).get('with')) or ''
        return cards.card(
            'plan', task, 'prepare', title=_lt('Sent for approval'), subtitle=run.name,
            slots=cards.plan_slots(task),
            notes=[cards.note('ok', T(_lt('It is with %s now.')) % who if who else
                              _lt('It is waiting for its approval now.'))],
            actions=actions, state='done', icon='check',
            undo=undo_block(self.undo_minutes, _lt('Withdraw'), _lt(
                'Sent the wrong run? Withdrawing makes it a draft again.')),
            result_ref={'run_id': run.id, 'request_id': request_id})

    def undo(self, ctx, task):
        ref = _ref(task)
        request_id = int(ref.get('request_id') or 0)
        if not request_id or 'pb.approval.inbox' not in ctx.env:
            raise UserError(T(_lt('There is no request to withdraw.')))
        ctx.env['pb.approval.inbox'].cancel(request_id, T(_lt('Withdrawn through PayAI')))
        return 'undone', cards.card(
            'done', task, 'prepare', title=_lt('Withdrawn'),
            notes=[cards.note('ok', _lt('The run is a draft again and nobody is asked to approve it.'))],
            state='undone', icon='undo')

    def too_late(self, ctx, task, data):
        return cards.card('blocked', task, 'prepare', title=_lt('Too late to withdraw here'),
                          notes=[cards.note('warn', _lt(
                              'Ten minutes have passed. You can still withdraw it from '
                              'your approvals while nobody has decided.'))])


# =========================================================================
@payai_action
class SendPayslips(_RunAmber):
    key = 'send_payslips'
    title = _lt('Send payslips')
    summary = _lt("Email an approved run's payslips to its people, after showing the plan.")
    examples = (_lt('Send the June payslips'),)
    slots = (Slot('run', _lt('Pay run'), 'run', True,
                  "Which approved pay run, in the person's words. Never an id."),)
    door_id = DELIVER_DOOR
    right_subject = _lt('Sending payslips')
    right_label = _lt('Pay & Deliver')
    undo_minutes = 0
    phrases = (
        r'^(?:send|email|e-mail|deliver|mail)\s+(?:out\s+)?(?:the\s+)?'
        r'(?:(?P<run>.+?)\s+)?pay\s*slips?\b.*$',
    )

    def method_gate(self, env, user):
        if 'pb.pay.delivery' not in env:
            return False
        return bool(user._is_admin() or _has_any_group(user, PAY_GROUPS))

    def param_gate(self, ctx, params):
        run = self._run(ctx, params)
        if run.state == 'done':
            return None
        actions = [a for a in [run_door(ctx, run.id, _lt('Open the run'), 'outline')] if a]
        return cards.card(
            'refused', ctx.task, 'prepare', title=_lt('Not approved yet'), subtitle=run.name or '',
            notes=[cards.note('warn', T(_lt(
                'Payslips go out once the run is approved. "%(name)s" is %(state)s now.')) % {
                    'name': run.name or '', 'state': state_label(run.state).lower()})],
            actions=actions)

    def plan(self, ctx, params):
        run = self._run(ctx, params)
        Delivery = ctx.env['pb.pay.delivery']
        slips = run.slip_ids.filtered(lambda s: s.state == 'done')
        batch = Delivery._batch(run)
        sent = batch.sent_count if batch else 0
        if batch and batch.state == 'pending':
            return cards.card('blocked', ctx.task, 'prepare', title=_lt('Already waiting'),
                              subtitle=run.name, notes=[cards.note('info', T(_lt(
                                  'These payslips are already waiting to be approved, with %s.')) % (
                                      batch._waiting_for() or T(_lt('their approver'))))])
        slots = [slot_row('run', _lt('Run'), run.name or '', params['run'].get('origin'), True),
                 slot_row('people', _lt('People'), T(_lt('%s payslips')) % '{:,}'.format(len(slips)),
                          'default')]
        notes = [cards.note('warn', _lt(
            'Emails cannot be called back, so this cannot be undone.'))]
        if sent:
            notes.append(cards.note('info', T(_lt(
                '%s were sent before; those people are not emailed again.')) % sent))
        screen = screen_action(_lt('Open Pay & Deliver instead'),
                               hub={'tag': 'pb_pay_hub', 'lens': 'deliver'}, door_id=DELIVER_DOOR)
        card = cards.card('plan', ctx.task, 'prepare', title=self.title,
                          subtitle=_lt('Prepare · emails the payslips · cannot be undone'),
                          slots=slots, notes=notes, actions=plan_actions(None, screen),
                          state='planned', icon='send')
        fp = fingerprint(run.id, run.state, len(slips), batch.state if batch else '', sent)
        return {'card': card, 'vals': {'run_id': run.id}, 'fingerprint': fp,
                'speak': T(_lt('I will email %(n)s payslips for %(name)s.')) % {
                    'n': len(slips), 'name': run.name or ''}}

    def confirm(self, ctx, task, params, data):
        run = self._run(ctx, params)
        out = ctx.env['pb.pay.delivery'].send_payslips(run.id, False) or {}
        actions = []
        if ctx.has_door(DELIVER_DOOR):
            actions.append(cards.door_action(DELIVER_DOOR, _lt('Open Pay & Deliver'), 'outline',
                                             hub={'tag': 'pb_pay_hub', 'lens': 'deliver'}))
        if out.get('state') == 'pending':
            who = out.get('with_whom') or ''
            return cards.card('plan', task, 'prepare', title=_lt('Waiting for approval'),
                              subtitle=run.name, state='done', icon='check',
                              notes=[cards.note('ok', T(_lt(
                                  'Sending these payslips needs approval. It is with %s now.')) % who
                                  if who else _lt('Sending these payslips needs approval first.'))],
                              actions=actions, result_ref={'run_id': run.id,
                                                           'request_id': out.get('request_id') or 0})
        tiles = [{'value': '{:,}'.format(int(out.get('sent') or 0)), 'label': T(_lt('sent'))},
                 {'value': '{:,}'.format(int(out.get('failed') or 0)), 'label': T(_lt('failed'))},
                 {'value': '{:,}'.format(int(out.get('skipped') or 0)), 'label': T(_lt('skipped'))}]
        notes = []
        if out.get('failed'):
            notes.append(cards.note('warn', _lt(
                'Some emails did not go. Pay & Deliver lists who, and why.')))
        return cards.card('plan', task, 'prepare', title=_lt('Payslips sent'), subtitle=run.name,
                          result=tiles, notes=notes, actions=actions, state='done', icon='check',
                          result_ref={'run_id': run.id, 'request_id': out.get('request_id') or 0})


# =========================================================================
@payai_action
class UpdatePayData(_Amber):
    key = 'update_pay_data'
    title = _lt('Change a pay value')
    summary = _lt("Change one person's pay value through the normal approval "
                  "route, after showing the plan.")
    examples = (_lt('Give Linh an allowance of 500,000 from July'),
                _lt('Set the meal allowance of An Nguyen to 600,000'))
    slots = (Slot('person', _lt('Person'), 'person', True,
                  "The person's name as said. Never an id."),
             Slot('field', _lt('Value'), 'field', True,
                  "Which pay value, in the person's words, e.g. 'meal allowance'."),
             Slot('value', _lt('New amount'), 'value', True,
                  "The new amount or text exactly as said, e.g. '500,000'."),
             Slot('from', _lt('From'), 'day', False,
                  "From when, as said, e.g. 'July'. Empty means today."))
    screen_keys = PEOPLE_SCREEN
    door_id = 'peoplehub_records'
    right_subject = _lt('Changing pay values')
    right_label = _lt('Records')
    _KW = (r'(?=.*\b(?:allowance|salary|bonus|wage|deduction|overtime|pay|rate|'
           r'stipend|subsidy|support)\b)')
    _VERB = r'(?:give|set|change|update|raise|increase|lower|reduce|put|make)'
    _VAL = (r'(?P<value>[₫$]?\s*[0-9][0-9.,\s]*(?:k|m|mn|million|thousand|tr)?'
            r'(?:\s*(?:vnd|dong|₫|usd|inr))?)')
    _TAIL = (r'(?:\s+(?:a|per)\s+month|\s+monthly)?'
             r'(?:\s+(?:from|starting|effective|as\s+of|beginning)\s+(?P<from>.+))?$')
    phrases = (
        # "Set the meal allowance of An Nguyen to 600,000"
        r'^(?:set|change|update|make)\s+(?:the\s+)?(?P<field>.+?)\s+(?:of|for)\s+'
        r'(?P<person>.+?)\s+(?:to|at|as)\s+' + _VAL + _TAIL,
        # "Give Linh Nguyen an allowance of 500,000 from July" — the article
        # is where the name ends (a name may have three words).
        r'^' + _KW + _VERB + r'\s+(?P<person>.+?)\s+(?:an?|the|his|her|their)\s+'
        r'(?P<field>[^0-9₫$]+?)\s+(?:of|to|=|at|as)\s+' + _VAL + _TAIL,
        # "Set Linh's meal allowance to 600,000"
        r"^" + _KW + _VERB + r"\s+(?P<person>.+?)'s\s+(?P<field>[^0-9₫$]+?)\s+"
        r"(?:of|to|=|at|as)\s+" + _VAL + _TAIL,
        r'^' + _KW + _VERB + r'\s+(?P<person>.+?)\s+(?P<field>[^0-9₫$]+?)\s+'
        r'(?:of|to|=|at|as)\s+' + _VAL + _TAIL,
    )

    EDITABLE = ('amount', 'integer', 'float', 'monetary', 'char', 'text', 'text_component')
    NUMERIC = ('amount', 'integer', 'float', 'monetary')

    def method_gate(self, env, user):
        if 'pb.records.desk' not in env:
            return False
        desk = env['pb.records.desk'].with_user(user)
        if not desk._may_read():
            return False
        return bool(desk._may_write('hr.contract') or desk._may_write('hr.employee'))

    def _desk(self, ctx):
        return ctx.env['pb.records.desk']

    def _scheme_of(self, ctx, employee_id):
        cache = ctx.cache.setdefault('scheme_of', {})
        if employee_id not in cache:
            config_id = 0
            if 'pb.scheme.map' in ctx.env:
                try:
                    config_id = int(ctx.env['pb.scheme.map'].resolve(employee_id).get('config_id') or 0)
                except Exception:                       # noqa: BLE001
                    config_id = 0
            if config_id and not self._desk(ctx)._configs(config_id):
                config_id = 0
            cache[employee_id] = config_id
        return cache[employee_id]

    def _cards(self, ctx, config_id):
        cache = ctx.cache.setdefault('desk_cards', {})
        if config_id not in cache:
            cache[config_id] = self._desk(ctx)._cards(config_id)
        return cache[config_id]

    def resolve_slot(self, ctx, slot, text):
        if slot.kind == 'person':
            return resolve_person(ctx, text)
        if slot.kind == 'field':
            emp = (ctx.params.get('person') or {}).get('value')
            config_id = self._scheme_of(ctx, emp)
            rows = []
            for card in self._cards(ctx, config_id).values():
                if card['id'][:1] == 'b' or not card.get('editable') \
                        or card.get('ttype') not in self.EDITABLE:
                    continue
                comp = card.get('component') or {}
                rows.append({'value': card['id'], 'label': card['label'],
                             'sublabel': comp.get('code') or '',
                             'words': '%s %s %s' % (card['label'], comp.get('name') or '',
                                                    comp.get('code') or '')})
            q = tokens(text)
            if not q:
                return missing(T(_lt('Which pay value should I change?')))
            scored = []
            for row in rows:
                words = tokens(row['words'])
                hits = sum(1 for t in q if any(tok_match(t, w) for w in words))
                if hits:
                    scored.append((hits / len(q), all(t in words for t in q), row))
            scored.sort(key=lambda x: -x[0])
            full = [(e, r) for s, e, r in scored if s >= 1.0]
            if len(full) == 1:
                exact, row = full[0]
                out = resolved(row['value'], row['label'], 'said' if exact else 'assumed')
                out['config_id'] = config_id
                return out
            pool = [r for _e, r in full] or [r for s, e, r in scored if s >= 0.5]
            if not pool:
                return missing(T(_lt(
                    "I could not find a pay value called \"%s\" on this person's scheme.")) % text[:60])
            return ambiguous([{'value': r['value'], 'label': r['label'],
                               'sublabel': r['sublabel']} for r in pool])
        if slot.kind == 'value':
            field = ctx.params.get('field') or {}
            emp = (ctx.params.get('person') or {}).get('value')
            card = self._cards(ctx, self._scheme_of(ctx, emp)).get(field.get('value')) or {}
            if card.get('ttype') in self.NUMERIC:
                amount = parse_amount(text)
                if amount is None:
                    return missing(T(_lt('I could not read "%s" as an amount.')) % (text or '')[:40])
                return resolved(amount, '{:,.0f}'.format(amount) if amount == int(amount)
                                else '{:,.2f}'.format(amount), 'said')
            return resolved((text or '').strip(), (text or '').strip(), 'said')
        if slot.kind == 'day':
            day, origin, label = parse_day(ctx, text)
            if day is None:
                return missing(T(_lt('I could not read "%s" as a date.')) % (text or '')[:40])
            return resolved(fields.Date.to_string(day), label, origin)
        return super().resolve_slot(ctx, slot, text)

    def plan(self, ctx, params):
        emp_id = params['person']['value']
        config_id = self._scheme_of(ctx, emp_id)
        field_id = params['field']['value']
        value = params['value']['value']
        today = fields.Date.context_today(ctx.env.user)
        start = fields.Date.to_date((params.get('from') or {}).get('value') or today)
        records_screen = screen_action(
            _lt('Open in Records instead'), hub=RECORDS_HUB, door_id='peoplehub_records',
            context={'records_employee_ids': [emp_id], 'records_config_id': config_id,
                     'records_field_ids': [field_id]})
        if (start.year, start.month) > (today.year, today.month):
            return cards.card(
                'blocked', ctx.task, 'prepare', title=_lt('That date is still ahead'),
                subtitle=self.title, notes=[cards.note('warn', T(_lt(
                    'A change made here counts from today. For a change that starts on '
                    '%s, ask me again in that month.')) % _day_label(start))],
                actions=[records_screen])
        changes = [{'emp_id': emp_id, 'field_id': field_id, 'value': value}]
        pv = self._desk(ctx).preview_changes(config_id, changes)
        item = (pv.get('items') or [{}])[0]
        if item.get('status') == 'refused':
            return cards.card('blocked', ctx.task, 'prepare', title=_lt('This change cannot be made'),
                              subtitle=self.title, notes=[cards.note('bad', item.get('why') or '')],
                              actions=[records_screen])
        if item.get('status') == 'same':
            return cards.card('done', ctx.task, 'prepare', title=_lt('Already set to this'),
                              subtitle=item.get('emp_name') or '',
                              notes=[cards.note('ok', T(_lt('%(field)s is already %(value)s.')) % {
                                  'field': item.get('field_label') or '',
                                  'value': item.get('new_label') or ''})])
        cur = self._currency(ctx, config_id)
        card_meta = self._cards(ctx, config_id).get(field_id) or {}
        new_label = item.get('new_label') or ''
        if card_meta.get('ttype') in self.NUMERIC and isinstance(value, (int, float)):
            new_label = money(value, cur) if abs(value) >= 1e6 else '%s%s' % (cur, '{:,.0f}'.format(value))
        slots = [
            slot_row('person', _lt('Person'), item.get('emp_name') or params['person']['label'],
                     params['person'].get('origin')),
            slot_row('field', _lt('Value'), item.get('field_label') or params['field']['label'],
                     params['field'].get('origin')),
            slot_row('value', _lt('New amount'), new_label, params['value'].get('origin'), True),
            slot_row('from', _lt('From'), _day_label(start), (params.get('from') or {}).get('origin'),
                     True),
            slot_row('today', _lt('Today'), item.get('old_label') or T(_lt('(not set)')), 'default'),
        ]
        notes = [self._route_note(ctx, config_id, changes)]
        if (start.year, start.month) < (today.year, today.month):
            notes.append(cards.note('warn', _lt(
                'The new value counts from now on. Pay for earlier months is not '
                'worked out again; use Pay Run › Adjust for that.')))
        card = cards.card('plan', ctx.task, 'prepare', title=self.title,
                          subtitle=_lt('Prepare · goes through the normal approval route · can be reverted'),
                          slots=slots, notes=notes, actions=plan_actions(None, records_screen),
                          state='planned', icon='pencil')
        fp = fingerprint(config_id, changes, item.get('old_label'), item.get('new_label'),
                         item.get('status'))
        return {'card': card, 'vals': {'config_id': config_id, 'changes': changes},
                'fingerprint': fp,
                'speak': T(_lt('I will change %(field)s for %(who)s to %(value)s.')) % {
                    'field': item.get('field_label') or '', 'who': item.get('emp_name') or '',
                    'value': new_label}}

    def _route_note(self, ctx, config_id, changes):
        """Whether this change needs approval, and from whom — read the way the
        Records Desk's own apply will ask the engine (same process, same scope,
        same facts), as the person and without writing anything. When the
        route cannot be read, the plan says only what is certain."""
        people, needs, known = self._records_route(ctx, config_id, changes)
        if known and not needs:
            return cards.note('ok', _lt(
                'Pay changes here need no approval: it is saved as soon as you '
                'press Do it, and you can undo it for 10 minutes.'))
        if known and people:
            return cards.note('info', T(_lt(
                'This change needs approval. It goes to %s first, and nothing '
                'changes until they say yes.')) % ', '.join(people[:3]))
        if known:
            return cards.note('info', _lt(
                'This change needs approval. It goes to the approver set up for '
                'pay changes, and nothing changes until they say yes.'))
        return cards.note('info', _lt(
            'If pay changes here need approval, I send it to the approver and '
            'nothing changes until they say yes.'))

    def _records_route(self, ctx, config_id, changes):
        """(first approvers, needs anybody, known). The Desk's apply builds a
        `pb.records.apply` from the evaluated plan and submits it; here the
        same record is only built in memory (`new`), so its own
        `_approval_context()` (divisions, facts, kind) is the one the engine
        will read. Any failure → unknown, never a guess."""
        Apply = ctx.env.get('pb.records.apply')
        if Apply is None or not hasattr(Apply, '_approval_context'):
            return [], True, False
        engine = ctx.env['biz.approval.engine']
        try:
            desk = self._desk(ctx)
            _items, plan, _counts = desk._evaluate(config_id, changes)
            if not plan:
                return [], True, False
            rows = desk._plan_rows(plan)
            bank, salary = desk._plan_touches(rows)
            rec = Apply.new({
                'name': '/', 'user_id': ctx.user.id, 'note': T(_lt('via PayAI')),
                'source': 'desk',
                'config_id': config_id or False, 'plan_json': json.dumps(rows),
                'changes_json': json.dumps(changes),
                'people_count': len({r['emp_id'] for r in rows}),
                'values_count': len(rows), 'touches_bank': bank,
                'touches_salary': salary, 'company_id': ctx.env.company.id})
            context = rec._approval_context()
            found = engine.resolve_binding(
                context['company_id'], getattr(Apply, '_approval_process_key', 'records'),
                context.get('scope_keys'), context.get('kind_key'))
        except Exception:                               # noqa: BLE001
            _logger.info("PayAI: could not read the records route", exc_info=True)
            return [], True, False
        if found.get('error') or not found.get('version_id'):
            return [], True, False
        return _route_steps(engine, found['version_id'], context)

    def _currency(self, ctx, config_id):
        try:
            if config_id:
                cur = ctx.env['pb.payrun.wizard']._scheme_currency(
                    ctx.env['hr.formula.config'].browse(config_id))
                return cur.get('symbol') or cur.get('name') or ''
        except Exception:                               # noqa: BLE001
            pass
        return ctx.env.company.currency_id.symbol or ''

    def confirm(self, ctx, task, params, data):
        vals = data.get('vals') or {}
        out = self._desk(ctx).apply_changes(vals.get('config_id') or 0, vals.get('changes') or [],
                                            note=T(_lt('via PayAI')), source='desk')
        refused = out.get('refused') or []
        if not out.get('apply_id') and refused:
            raise UserError(refused[0].get('why') or T(_lt('The change was refused.')))
        ref = {'apply_id': out.get('apply_id') or 0, 'request_id': out.get('request_id') or 0,
               'pending': bool(out.get('pending'))}
        name = (params.get('person') or {}).get('label') or ''
        if out.get('pending'):
            who = out.get('with_whom') or ''
            return cards.card(
                'plan', task, 'prepare', title=_lt('Sent for approval'), subtitle=name,
                slots=cards.plan_slots(task),
                notes=[cards.note('ok', T(_lt(
                    'Sent to %(who)s for approval. %(name)s\'s pay does not change until '
                    'they approve.')) % {'who': who or T(_lt('the approver')), 'name': name})],
                state='done', icon='check',
                undo=undo_block(self.undo_minutes, _lt('Withdraw'), _lt('Withdraw the request?')),
                result_ref=ref)
        return cards.card(
            'plan', task, 'prepare', title=_lt('Changed'), subtitle=name,
            slots=cards.plan_slots(task),
            notes=[cards.note('ok', T(_lt('Saved as %s. It is on the Records history.')) % (
                out.get('reference') or ''))],
            state='done', icon='check',
            undo=undo_block(self.undo_minutes, _lt('Undo'), _lt(
                'Not what you meant? Undo puts the old value back.')),
            result_ref=ref)

    def undo(self, ctx, task):
        ref = _ref(task)
        if ref.get('pending'):
            # A routed change: "Withdraw" may only ever withdraw. It never
            # reverts values -- once the request is decided, the approver's
            # decision stands and the Records history is the place to undo it.
            return self._withdraw(ctx, task, ref)
        res = self._desk(ctx).undo_apply(int(ref.get('apply_id') or 0))
        if not res.get('ok'):
            raise UserError(res.get('msg') or T(_lt('That could not be undone.')))
        restored = int(res.get('restored') or 0)
        if not restored:
            # Nothing went back: a refusal, not an "Undone" card. Raising rolls
            # the Desk's undo bookkeeping back with the runner's savepoint.
            changed = int(res.get('skipped_changed_since') or 0)
            if changed == 1:
                # The Records Desk's own sentence (records_desk.js undoApply).
                raise UserError(T(_lt(
                    '1 was changed by somebody else since and was left alone')))
            if changed:
                raise UserError(T(_lt(
                    '%s were changed by somebody else since and were left alone')) % changed)
            raise UserError(T(_lt('Nothing could be put back.')))
        note = T(_lt('Put 1 value back')) if restored == 1 else \
            T(_lt('Put %s values back')) % restored
        changed = int(res.get('skipped_changed_since') or 0)
        if changed:
            note += ' · ' + (T(_lt(
                '1 was changed by somebody else since and was left alone')) if changed == 1
                else T(_lt('%s were changed by somebody else since and were left alone')) % changed)
        return 'undone', cards.card(
            'done', task, 'prepare', title=_lt('Undone'), state='undone', icon='undo',
            notes=[cards.note('ok', note)])

    def _withdraw(self, ctx, task, ref):
        request_id = int(ref.get('request_id') or 0)
        if not request_id or 'pb.approval.inbox' not in ctx.env:
            raise UserError(T(_lt('There is no request to withdraw.')))
        request = ctx.env['biz.approval.request'].browse(request_id).exists()
        if not request:
            raise UserError(T(_lt('There is no request to withdraw.')))
        if request.state in ('pending', 'blocked'):
            ctx.env['pb.approval.inbox'].cancel(request.id, T(_lt('Withdrawn through PayAI')))
            return 'undone', cards.card(
                'done', task, 'prepare', title=_lt('Withdrawn'), state='undone', icon='undo',
                notes=[cards.note('ok', _lt('The request was withdrawn. Nothing changed.'))])
        # Decided or closed since Do it. Never call undo_apply here.
        if request.state in ('approved', 'applied'):
            who = ''
            try:
                who = request.decision_ids[-1:].user_id.name or ''
            except AccessError:
                who = ''
            text = T(_lt('This change was approved by %s. Undo it from the Records '
                         'history.')) % who if who else T(_lt(
                             'This change was already approved. Undo it from the Records '
                             'history.'))
        else:
            label = dict(request._fields['state']._description_selection(ctx.env)).get(
                request.state) or request.state
            text = T(_lt('This request is already finished (%s). Nothing was withdrawn; '
                         'see the Records history.')) % label.lower()
        return None, cards.card(
            'blocked', task, 'prepare', title=_lt('It has moved on'),
            notes=[cards.note('warn', text)],
            actions=[screen_action(_lt('Open Records'), hub=RECORDS_HUB,
                                   door_id='peoplehub_records')])

    def too_late(self, ctx, task, data):
        return cards.card('blocked', task, 'prepare', title=_lt('Too late to undo here'),
                          notes=[cards.note('warn', _lt(
                              'Ten minutes have passed. The change is on the Records '
                              'history, where it can still be undone.'))],
                          actions=[screen_action(_lt('Open Records'), hub=RECORDS_HUB,
                                                 door_id='peoplehub_records')])


# =========================================================================
@payai_action
class FilingPrepare(_Amber):
    key = 'filing_prepare'
    title = _lt('Prepare a government filing')
    summary = _lt('Prepare a tax or social insurance filing for a period, as a '
                  'file to check. Nothing is sent to the authority.')
    examples = (_lt('Prepare the June tax filing'),)
    slots = (Slot('country', _lt('Country'), 'text', False,
                  "The country if the person named one. Empty means the company's."),
             Slot('filing', _lt('Filing'), 'filing', True,
                  "Which filing, in the person's words, e.g. 'tax' or 'social insurance'."),
             Slot('period', _lt('Period'), 'period', False,
                  "The month, in the person's words. Empty means the latest payroll month."))
    screen_keys = COMPLIANCE_SCREEN
    door_id = FILINGS_DOOR
    right_subject = _lt('Preparing filings')
    right_label = _lt('Compliance')
    undo_minutes = 0
    phrases = (
        r'^(?:prepare|generate|make|create|do)\s+(?:the\s+|a\s+|my\s+)?'
        r'(?P<period>(?:[a-z]+\s+(?:20\d\d\s+)?)?)'
        r'(?P<filing>(?:[a-z0-9-]+\s+){0,4}?(?:tax|pit|social\s+insurance|si|insurance|'
        r'bhxh|cpf|ssf|nssf|epf|government)\b.*?)\s*(?:filing|return|declaration|report)s?\b.*$',
        r'^(?:prepare|generate|make|create|do)\s+(?:the\s+|a\s+|my\s+)?(?P<period>.*?)\s*'
        r'(?:filing|return|declaration)s?\b.*$',
    )

    def method_gate(self, env, user):
        if 'pb.filing.flow' not in env:
            return False
        return bool(user._is_superuser() or _has_any_group(user, FILING_GROUPS))

    def _start(self, ctx, country=None):
        cache = ctx.cache.setdefault('filing_start', {})
        key = country or ''
        if key not in cache:
            cache[key] = ctx.env['pb.filing.flow'].start(country or None)
        return cache[key]

    def normalise_texts(self, ctx, texts):
        """"the June tax filing": the month and the filing ride in one phrase."""
        texts = dict(texts or {})
        combined = ' '.join(x for x in (texts.get('period'), texts.get('filing')) if x)
        if not combined:
            return texts
        today = fields.Date.context_today(ctx.env.user)
        got = parse_period(combined, today)
        if got:
            texts['period'] = combined
            texts['filing'] = got[3].strip()
        else:
            texts['period'] = ''
            texts['filing'] = combined
        return texts

    def resolve_slot(self, ctx, slot, text):
        if slot.key == 'country':
            board = self._start(ctx)
            cc = board.get('country_code') or ''
            if (text or '').strip():
                q = fold(text)
                for c in board.get('countries') or []:
                    code = (c.get('code') if isinstance(c, dict) else str(c)) or ''
                    label = (c.get('label') if isinstance(c, dict) else '') or ''
                    if q in (fold(code), fold(label)):
                        return resolved(code.upper(), label or code.upper(), 'said')
            return resolved(cc, board.get('country_label') or cc, 'default')
        if slot.kind == 'filing':
            cc = (ctx.params.get('country') or {}).get('value') or None
            board = self._start(ctx, cc)
            rows = [{'value': f['key'], 'label': f['label'], 'sublabel': f.get('group') or '',
                     'words': '%s %s %s %s' % (f['label'], f.get('native') or '', f['key'],
                                               f.get('group') or '')}
                    for f in board.get('filings') or []]
            q = [t for t in tokens(text) if t not in ('filing', 'return', 'declaration',
                                                      'report', 'the', 'my', 'a')]
            if not q:
                return ambiguous([{'value': r['value'], 'label': r['label'],
                                   'sublabel': r['sublabel']} for r in rows[:MAX_CHIPS]]) \
                    if rows else missing()
            scored = []
            for row in rows:
                words = tokens(row['words'])
                hits = sum(1 for t in q if any(tok_match(t, w) for w in words))
                if hits:
                    scored.append((hits / len(q), row))
            scored.sort(key=lambda x: -x[0])
            full = [r for s, r in scored if s >= 1.0]
            if len(full) == 1:
                return resolved(full[0]['value'], full[0]['label'], 'said')
            pool = full or [r for s, r in scored]
            if not pool:
                return missing(T(_lt('I could not find a filing called "%s".')) % (text or '')[:60])
            return ambiguous([{'value': r['value'], 'label': r['label'],
                               'sublabel': r['sublabel']} for r in pool])
        if slot.key == 'period':
            if (text or '').strip():
                return resolve_period(ctx, text)
            per = self._start(ctx).get('period') or {}
            if per.get('from'):
                return resolved({'date_start': per['from'], 'date_end': per['to']},
                                per.get('label') or '', 'default')
            return resolve_period(ctx, '')
        return super().resolve_slot(ctx, slot, text)

    def plan(self, ctx, params):
        cc = params['country']['value']
        board = self._start(ctx, cc)
        door = []
        if ctx.has_door(FILINGS_DOOR):
            door = [cards.door_action(FILINGS_DOOR, _lt('Open Government filings'), 'outline')]
        if not board.get('is_covered'):
            return cards.card('blocked', ctx.task, 'prepare', title=_lt('Not from here'),
                              subtitle=self.title, notes=[cards.note('info', _lt(
                                  'Filings for this country are prepared on the Government '
                                  'filings screen.'))], actions=door)
        # PA-R1, method half: the filing's own form must be one this person may
        # create (Government Reports permission), or Do it would fail after the
        # plan said yes. Checked here so the refusal comes before the plan.
        try:
            spec = ctx.env['pb.filing.flow']._adapter(cc)
            ctx.env[spec['model']].check_access('create')
        except AccessError:
            return cards.card('blocked', ctx.task, 'prepare', title=_lt('Not allowed yet'),
                              subtitle=self.title, notes=[cards.note('bad', _lt(
                                  'Preparing this filing needs the Government Reports '
                                  'permission. Ask your administrator to give it to you.'))],
                              actions=door)
        per = params['period']['value']
        start = fields.Date.to_date(per['date_start'])
        slots = [slot_row('country', _lt('Country'), params['country']['label'],
                          params['country'].get('origin'), True),
                 slot_row('filing', _lt('Filing'), params['filing']['label'],
                          params['filing'].get('origin'), True),
                 slot_row('period', _lt('Period'), month_label(start),
                          params['period'].get('origin'), True)]
        notes = [cards.note('info', _lt(
            'I prepare the file for you to check. Nothing is sent to the authority.')),
            cards.note('info', _lt(
                'If filings need approval here, it goes to the approver first.'))]
        screen = screen_action(_lt('Open Government filings instead'), door_id=FILINGS_DOOR,
                               hub={'xmlid': 'pb_compliance_hub.action_pb_compliance_hub',
                                    'lens': 'filings'})
        card = cards.card('plan', ctx.task, 'prepare', title=self.title,
                          subtitle=_lt('Prepare · makes a file to check · nothing is sent'),
                          slots=slots, notes=notes, actions=plan_actions(None, screen),
                          state='planned', icon='file')
        vals = {'country': cc, 'filing_key': params['filing']['value'],
                'date_start': per['date_start'], 'date_end': per['date_end']}
        return {'card': card, 'vals': vals, 'fingerprint': fingerprint(vals),
                'speak': T(_lt('I will prepare the %(filing)s for %(month)s.')) % {
                    'filing': params['filing']['label'], 'month': month_label(start)}}

    def confirm(self, ctx, task, params, data):
        vals = data.get('vals') or {}
        flow = ctx.env['pb.filing.flow']
        scope = flow.scope(vals['country'], vals['filing_key'])
        if scope.get('period_kind') == 'range':
            write = {'date_from': vals['date_start'], 'date_to': vals['date_end']}
        else:
            write = {'submission_period': vals['date_end']}
        ans = flow.generate(scope['wizard_id'], vals['country'], vals['filing_key'], write) or {}
        actions = []
        for art in (ans.get('artifacts') or [])[:3]:
            url = art.get('url') or ''
            if url.startswith('/web/content/'):
                actions.append({'id': 'download', 'url': url, 'style': 'outline',
                                'label': T(_lt('Download %s')) % (art.get('name') or '')})
        if ctx.has_door(FILINGS_DOOR):
            actions.append(cards.door_action(FILINGS_DOOR, _lt('Open Government filings'), 'outline'))
        if ans.get('pending'):
            title = _lt('Waiting for approval')
            note = cards.note('ok', T(_lt('It is with %s now.')) % ans['with_whom']
                              if ans.get('with_whom') else _lt('It is waiting for its approval.'))
        else:
            title = _lt('Filing prepared')
            note = cards.note('ok', ans.get('message') or _lt('The file is ready to check.'))
        return cards.card('plan', task, 'prepare', title=title, subtitle=params['filing']['label'],
                          notes=[note], actions=actions, state='done', icon='check',
                          result_ref={'proposal_id': ans.get('proposal_id') or 0,
                                      'request_id': ans.get('request_id') or 0})
