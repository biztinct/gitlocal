# -*- coding: utf-8 -*-
"""GREEN ACTIONS — look only. Nothing here changes a record.

open_screen, run_status, download_run_excel, what_can_you_do.
Every one runs as the asking person (PA-R2); every id comes from a resolver
that searched as that person (PA-R3).
"""
import logging

from odoo.exceptions import UserError
from odoo.tools.translate import LazyTranslate

from .i18n import T, num, short_amount

from . import cards, registry
from .registry import Action, Slot, payai_action
from .resolve import door_title, resolve_run, run_scheme_label, state_label

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

RUNS_DOOR = 'payhub_runs'
RUN_SCREENS = ('pb_payhub.item_pay_run', 'pb_sidebar.item_pay_runs')


def money(amount, symbol=''):
    """₫18.6 bn / ₫4.2 m / ₫950,000 — short enough for a tile (P4: written
    "₫18,6 tỷ" / "₫950.000" for a Vietnamese reader)."""
    amount = float(amount or 0.0)
    sign = '-' if amount < 0 else ''
    return '%s%s%s' % (sign, symbol or '', short_amount(abs(amount)))


def run_door(ctx, run_id, label, style='primary'):
    """The Runs board, opened on this run — only if the person holds it."""
    if not ctx.has_door(RUNS_DOOR):
        return None
    return cards.door_action(
        RUNS_DOOR, label, style,
        hub={'tag': 'pb_pay_hub', 'lens': 'runs', 'focus': T(run_id)})


def _board_rows(ctx, run_ids):
    """The Runs board's own rows for these runs (same figures as the board)."""
    try:
        data = ctx.env['pb.payruns'].get_board_data()
    except Exception:                                   # noqa: BLE001
        _logger.info("PayAI: board data unavailable", exc_info=True)
        return {}
    wanted = set(run_ids)
    return {b['id']: b for b in data.get('batches') or [] if b['id'] in wanted}


def _row_for(ctx, run, rows):
    """A board row, or one built from the run's own fields (same totals)."""
    row = rows.get(run.id)
    if row:
        return row
    return {
        'id': run.id, 'name': run.name or '', 'state': run.state,
        'stage_label': state_label(run.state),
        'employees': getattr(run, 'pb_employee_count', 0) or len(run.slip_ids),
        'net': getattr(run, 'pb_total_net', 0.0) or 0.0,
        'currency': ctx.env.company.currency_id.symbol or '',
        'currency_name': ctx.env.company.currency_id.name or '',
        'approval': {},
    }


# ======================================================================
@payai_action
class WhatCanYouDo(Action):
    key = 'what_can_you_do'
    title = _lt('What can you do?')
    tier = 'look'
    priority = 10
    summary = _lt('List what PayAI can do for this person, here.')
    examples = (_lt('What can you do?'), _lt('Help'))
    phrases = (
        r'^(?:so\s+)?what\s+(?:else\s+)?(?:can|could)\s+you\s+do(?:\s+for\s+me)?(?:\s+here)?$',
        r'^(?:help|commands|list\s+(?:your\s+)?commands|show\s+(?:me\s+)?(?:your\s+)?commands)$',
        r'^what\s+are\s+your\s+(?:commands|skills|abilities)$',
    )

    def execute(self, ctx, params):
        now, soon = registry.describe(ctx.env, ctx.user)
        groups = []
        if now:
            groups.append({'tone': 'ok', 'label': T(_lt('I can do these now')),
                           'items': [{'label': T(r['label']), 'example': T(r['example'])}
                                     for r in now if r['key'] != self.key]})
        if soon:
            groups.append({'tone': 'neutral',
                           'label': T(_lt('Coming in the next release')),
                           'items': [{'label': T(r['label']), 'example': T(r['example'])}
                                     for r in soon]})
        return cards.card(
            'done', ctx.task, 'look',
            title=_lt('Here is what I can do for you'),
            subtitle=_lt('Tap an example to try it. I only ever do what you could do yourself on the screen.'),
            groups=groups,
        )


# ======================================================================
@payai_action
class OpenScreen(Action):
    key = 'open_screen'
    title = _lt('Open a screen')
    tier = 'look'
    priority = 90
    summary = _lt('Open any screen the person can already reach, by its name.')
    examples = (_lt('Open the Runs board'), _lt('Go to Payslips'),
                _lt('Take me to my approvals'))
    slots = (Slot('door', _lt('Screen'), 'door', True,
                  "The screen to open, in the person's own words, for "
                  "example 'runs board' or 'payslips'. Never an id."),)
    right_subject = _lt('Opening that screen')
    right_label = _lt('screen')
    phrases = (
        r'^(?:open(?:\s+up)?|go\s+to|goto|take\s+me\s+to|bring\s+(?:me\s+)?to|'
        r'navigate\s+to|jump\s+to|switch\s+to|bring\s+up|pull\s+up|'
        r'show\s+(?:me\s+)?the)\s+(?P<door>.+?)(?:\s+(?:screen|page|tab))?$',
    )

    def method_gate(self, env, user):
        return user._is_internal()

    def param_gate(self, ctx, params):
        door_id = params['door']['value']
        row = ctx.door_row(door_id)
        if not row or not ctx.holds_door(row):
            return 'screen_off'
        return None

    def execute(self, ctx, params):
        door = params['door']
        row = ctx.door_row(door['value'])
        where = door_title(row)
        return cards.card(
            'done', ctx.task, 'look',
            title=T(_lt('Opening %s.')) % where,
            subtitle=_lt('Looking only, so there is nothing to confirm.'),
            actions=[cards.door_action(door['value'], T(_lt('Open %s')) % where,
                                       'outline', auto=True)],
            result_ref={'door_id': door['value']},
        )


# ======================================================================
class _RunLook(Action):
    tier = 'look'
    screen_keys = RUN_SCREENS
    door_id = RUNS_DOOR
    right_subject = _lt('Seeing pay runs')
    right_label = _lt('Pay Run')

    def method_gate(self, env, user):
        return env['hr.payslip.run'].with_user(user).has_access('read')


@payai_action
class RunStatus(_RunLook):
    key = 'run_status'
    title = _lt('Show where a pay run is')
    priority = 40
    summary = _lt("Show a pay run's people, net pay, stage and who it is "
                  "waiting for — one run, or every run in a month.")
    examples = (_lt('Show the June run'), _lt('Status of this month\'s payroll'),
                _lt('Where is the May Retail run?'))
    slots = (Slot('run', _lt('Pay run'), 'run', False,
                  "Which pay run, in the person's words: a month and "
                  "optionally a scheme or division, e.g. 'June 2026 Retail'. "
                  "Empty means this month."),)
    phrases = (
        r'^(?!.*\b(?:board|screen|page|tab|list|excel|spreadsheet)\b)'
        r'(?:show|display|give|get|check|see|view)\s+(?:me\s+)?(?:the\s+)?'
        r'(?:status\s+(?:of\s+)?(?:the\s+)?)?'
        r'(?P<run>.*\b(?:pay\s*runs?|runs?|payroll|payrolls)\b.*?)(?:\s+status)?$',
        r'^(?:status|state|progress)\s+(?:of\s+)?(?:the\s+)?(?P<run>.+)$',
        r'^(?P<run>.*\b(?:pay\s*runs?|runs?|payroll)\b.*?)\s+status$',
        r'^where\s+is\s+(?:the\s+)?(?P<run>.*\b(?:pay\s*run|run|payroll)\b.*)$',
        r'^how\s+is\s+(?:the\s+)?(?P<run>.*\b(?:pay\s*run|run|payroll)\b.*?)\s+(?:doing|going)$',
    )

    def resolve_slot(self, ctx, slot, text):
        # "this month" with several runs is answered as a month, not asked.
        return resolve_run(ctx, text, allow_many=True)

    def execute(self, ctx, params):
        res = params['run']
        if res.get('many'):
            return self._month(ctx, res)
        run = ctx.env['hr.payslip.run'].browse(res['value'])
        rows = _board_rows(ctx, run.ids)
        row = _row_for(ctx, run, rows)
        tiles = [
            {'value': num(int(row.get('employees') or 0)),
             'label': T(_lt('people'))},
            {'value': money(row.get('net'), row.get('currency')),
             'label': T(_lt('net pay'))},
            {'value': row.get('stage_label') or state_label(run.state),
             'label': T(_lt('stage'))},
        ]
        notes = []
        approval = row.get('approval') or {}
        if run.state == 'approval_pending':
            who = approval.get('with') or ''
            if who:
                step = ''
                if approval.get('step_total'):
                    step = T(_lt(' (sign-off %(i)s of %(n)s)')) % {
                        'i': approval.get('step_index') or 1, 'n': approval['step_total']}
                notes.append(cards.note('info', T(_lt('Waiting for %(who)s%(step)s.')) % {
                    'who': who, 'step': step}))
            else:
                notes.append(cards.note('info', _lt('Waiting for approval.')))
        elif run.state == 'draft':
            notes.append(cards.note('warn', _lt('Still a draft. Nobody has sent it for approval yet.')))
        elif run.state == 'done':
            notes.append(cards.note('ok', _lt('Approved. The Excel can be downloaded.')))
        elif run.state == 'cancel':
            notes.append(cards.note('bad', _lt('This run was rejected.')))
        actions = []
        door = run_door(ctx, run.id, _lt('Open the run'))
        if door:
            actions.append(door)
        offer = {}
        if run.state == 'done':
            actions.append({'id': 'followup', 'action': 'download_run_excel',
                            'slot': 'run', 'value': T(run.id),
                            'label': T(_lt('Download Excel')), 'style': 'outline'})
            offer = {'slot': 'run', 'values': [T(run.id)],
                     'actions': ['download_run_excel']}
        scheme = run_scheme_label(run)
        return cards.card(
            'done', ctx.task, 'look',
            title=run.name or '',
            subtitle=' · '.join(x for x in (scheme, res.get('period', {}).get('label') or '') if x),
            result=tiles, notes=notes, actions=actions,
            result_ref={'run_ids': run.ids}, offer=offer,
        )

    def _month(self, ctx, res):
        runs = ctx.env['hr.payslip.run'].browse(res['value'])
        rows = _board_rows(ctx, runs.ids)
        people = 0
        nets = {}
        notes = []
        chips = []
        for run in runs:
            row = _row_for(ctx, run, rows)
            people += int(row.get('employees') or 0)
            cur = row.get('currency_name') or ''
            sym = row.get('currency') or ''
            nets.setdefault(cur, [sym, 0.0])[1] += float(row.get('net') or 0.0)
            chips.append({'label': run.name or '',
                          'sublabel': ' · '.join(x for x in (
                              run_scheme_label(run), state_label(run.state)) if x),
                          'value': T(run.id)})
        tiles = [{'value': T(len(runs)), 'label': T(_lt('runs'))},
                 {'value': num(people), 'label': T(_lt('people'))}]
        if len(nets) == 1:
            sym, total = list(nets.values())[0]
            tiles.append({'value': money(total, sym), 'label': T(_lt('net pay'))})
        else:
            # Never add two kinds of money together (GROUP / one-pay-band rule).
            notes.append(cards.note('info', _lt(
                'These runs pay in more than one currency, so there is no single total.')))
        by_state = {}
        for run in runs:
            by_state[run.state] = by_state.get(run.state, 0) + 1
        notes.append(cards.note('info', ', '.join(
            '%s %s' % (n, state_label(s).lower()) for s, n in by_state.items())))
        actions = []
        if ctx.has_door(RUNS_DOOR):
            actions.append(cards.door_action(
                RUNS_DOOR, _lt('Open the Runs board'), 'outline',
                hub={'tag': 'pb_pay_hub', 'lens': 'runs'}))
        return cards.card(
            'done', ctx.task, 'look',
            title=T(_lt('Pay runs for %s')) % res['label'],
            subtitle=_lt('Pick one to see it on its own.'),
            result=tiles, notes=notes, actions=actions,
            chips=chips[:6], chip_action='run_status', chip_slot='run',
            result_ref={'run_ids': runs.ids},
            offer={'slot': 'run', 'values': [c['value'] for c in chips[:6]],
                   'actions': ['run_status']},
        )


@payai_action
class DownloadRunExcel(_RunLook):
    key = 'download_run_excel'
    title = _lt("Download an approved run's Excel")
    priority = 30
    summary = _lt('Download the payslip Excel of an approved pay run.')
    examples = (_lt('Download the June run'), _lt('Excel for the May Retail run'))
    slots = (Slot('run', _lt('Pay run'), 'run', True,
                  "Which pay run, in the person's words: a month and "
                  "optionally a scheme or division. Never an id."),)
    phrases = (
        r'^(?:download|export|get|give\s+me|send\s+me|grab)\s+(?:me\s+)?(?:the\s+)?'
        r'(?:excel|spreadsheet|workbook|xlsx)(?:\s+(?:file|sheet))?'
        r'(?:\s+(?:for|of|from)\s+(?:the\s+)?(?P<run>.+))?$',
        r'^(?:download|export)\s+(?:the\s+)?(?P<run>(?=.*\b(?:run|payroll)s?\b).+?)'
        r'(?:\s+(?:to|as|in)\s+excel)?$',
        r'^(?:excel|spreadsheet)\s+(?:for|of)\s+(?:the\s+)?(?P<run>.+)$',
    )

    def param_gate(self, ctx, params):
        run = ctx.env['hr.payslip.run'].browse(params['run']['value'])
        if run.state == 'done':
            return None
        actions = []
        door = run_door(ctx, run.id, _lt('Open the run'), 'outline')
        if door:
            actions.append(door)
        return cards.card(
            'refused', ctx.task, 'look',
            title=_lt('Not ready to download yet'),
            subtitle=run.name or '',
            notes=[cards.note('warn', T(_lt(
                'The Excel is available once the run is approved. It is %(state)s now.')) % {
                    'state': state_label(run.state).lower()})],
            actions=actions,
        )

    def execute(self, ctx, params):
        run = ctx.env['hr.payslip.run'].browse(params['run']['value'])
        act = run.action_download_payslip_xlsx()
        url = (act or {}).get('url') or ''
        if not url.startswith('/web/content/'):
            raise UserError(T(_lt('The Excel could not be prepared. Open the run and try from there.')))
        return cards.card(
            'done', ctx.task, 'look',
            title=T(_lt('Here is the Excel for %s.')) % (run.name or ''),
            subtitle=_lt('Every payslip in the run, one row per person.'),
            actions=[{'id': 'download', 'url': url, 'auto': True,
                      'label': T(_lt('Download again')), 'style': 'outline'}],
            result_ref={'run_ids': run.ids},
        )
