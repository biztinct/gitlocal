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
import difflib
import json
import logging
import re
import unicodedata
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import LazyTranslate

from .i18n import T, num, stamp

from . import cards
from .actions_green import RUNS_DOOR, _board_rows, _row_for, money, run_door
from .phrases_vi import PHRASES_VI
from .registry import MARKED_ONLY, Action, Slot, payai_action
from .resolve import (
    _VI_LABEL_BEFORE_COUNT, MAX_CHIPS, MONTHS, ambiguous, division_names, fold, missing,
    month_label,
    parse_amount, parse_day, parse_period, period_problem, resolve_period, resolve_person,
    resolve_run, resolve_scheme, resolved, state_label, tok_match, tokens,
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


def learn_action(scenario):
    """"Learn to do this yourself" (P3 §2): the Learn walkthrough of the
    screen this card did the work of, in watch mode. The key is the
    scenario's own (`pb_learn/static/content/learn_content.json`): P2 sent
    'payrun', which no scenario carries, so the button did nothing."""
    return {'id': 'learn', 'scenario': scenario, 'mode': 'watch',
            'label': T(_lt('Learn to do this yourself')), 'style': 'outline', 'icon': 'book'}


def undo_block(minutes, label, note, can=True):
    until = fields.Datetime.now() + timedelta(minutes=minutes)
    return {'until_iso': fields.Datetime.to_string(until) + 'Z' if can else '',
            'label': T(label) if can else '', 'note': T(note), 'can': bool(can)}


#: P3 crit-3 — "Send back the June run because two payslips are missing" and
#: "Send the June run back as the payslips are wrong" are a send-back (the
#: Red action), never an email of payslips or a send for approval.
#:
#: Only a REAL send-back counts — "back" right after "send", or right after
#: the thing being sent. A "back" further on in the sentence is somebody
#: else's: "Send the June payslips now that Mai is back", "…, I am back",
#: "…to the staff who are back", "…, they want them back by Friday", "…to
#: Mai, she is back from leave" are ordinary payslip sends.
#: Never a send-back: "back pay" and "Back Office" (a run's or a team's
#: name: "back" goes on with more of the name, or a hyphen), and "back to me"
#: / "back to us" (the payslips come to the asker).
_BACK_NAME = (r'back\b(?![\s-]*(?:pay|office)\b)(?!-)'
              r'(?!\s+to\s+(?:me|myself|us)\b)')
#: A word that cannot sit inside the thing being sent back when nothing
#: after "back" says it is a send-back: it starts another clause or names
#: who the payslips go TO.
_CLAUSE_WORD = (
    r'(?:to|into|that|who|whom|which|whose|when|whenever|where|while|now|once|'
    r'after|before|until|till|since|because|as|if|unless|and|or|but|then|so|'
    r'also|is|are|am|was|were|be|been|being|has|have|had|will|would|can|could|'
    r'should|want|wants|wanted|need|needs|needed|let|i|he|she|we|they|you|'
    r'come|came|comes|coming|get|gets|got|go|goes|went|call|ring|phone|write|'
    r'report|reply|text|message|check|circle|loop|hear|bring|brought|send|sent|'
    r'give|gave|pass|passed)\b')
#: FIX-1 fifth pass: the word right before a send-back's "back" is the end
#: of the thing being sent ("the Sales and Marketing run", "the run that Mai
#: prepared", "it"). It is never a "be" or a coming/going word ("Mai is
#: back", "people who came back", "get back"), a word that makes "back" a
#: place ("at the back", "from the back"), or a short form ("Mai's back",
#: "they're back").
_NOT_BEFORE_BACK = (
    r'(?:the|a|an|at|in|on|from|of|by|with|out|way|right|straight|is|are|am|'
    r'was|were|be|been|being|get|gets|got|getting|gotten|come|comes|came|'
    r'coming|go|goes|went|going|gone|report|reported|reporting|check|checked|'
    r'checking|call|called|ring|rang|phone|phoned|write|wrote|writes|reply|'
    r'replied|text|texted|message|hear|heard|step|stepped|move|moved|look|'
    r'looked|fall|fell|bounce|bounced|turn|turned|head|headed|walk|walked|'
    r'fly|flew|drive|drove|hold|held|sit|sat|stand|stood|lie|lay|'
    r'feel|felt|settle|settled|lean|leaned|kick|kicked|relax|heading|walking|'
    r'moving|stepping|driving|flying|looking|falling|turning|sitting|leaning|'
    r'me|us|him|her|you|welcome|'
    # FIX-1 sixth pass: "from two months back", "a while back" (= ago), and
    # a word that says how or when somebody is back ("now back", "just
    # back", "not yet back", "anyone else back", "round back"). "Last month"
    # stays the thing sent ("the payslips from last month back"); "a month
    # back" is `_AGO`.
    r'now|just|finally|already|all|also|recently|newly|yet|not|still|else|'
    r'safely|fully|round|around|ago|soon|later|again|far|long|home|'
    r'days|weeks|months|years|fortnights|hours|minutes|while|ways)\b'
    r'|\S+[\'’](?:s|re|m|ve|d|ll)\b')
#: "a month back", "one week back": a time ago, never the thing sent.
_AGO = (r'(?:a|an|one)\s+(?:day|week|month|year|fortnight|hour|minute)\s+'
        r'back\b')
#: A word that never sits inside the thing being sent back, however the
#: sentence ends: a second order ("…and send me a note back", "…and call me
#: back", "…and get them back", "…, I want them back").
_SECOND_ORDER = (r'(?:send|sends|sent|email|emailed|e-mail|mail|mailed|let|'
                 r'tell|told|ask|asked|call|ring|phone|text|ping|write|get|'
                 r'gets|got|want|wants|need|needs|bring|brought|take|took|'
                 r'keep|kept|hand|handed|give|gave|pass|passed)\b')
#: What can follow a send-back's "back" when the thing being sent back is
#: long or has "and" / "to" / "that" in it ("Send the Sales and Marketing
#: run back because the payslips are wrong", "Send the run that Mai
#: prepared back", "Send the June run to Mai back because …"): the end of
#: the sentence, a reason, a break in the sentence, "to <whoever>" then one
#: of those, or "and/so" + the fix.
_SEND_BACK_END = (
    r'(?:\s+to\s+(?!(?:normal|work|school|the\s+office|office|me|myself|us)\b)'
    r'[^\s,;.:!?—]+(?:\s+[^\s,;.:!?—]+){0,2}?)?'
    r'(?:\s*$|\s+(?:please|now|today|asap|immediately|right\s+away|straight\s+away)\b'
    r'|\s*[,;:.!?—]|\s+-\s|\s+(?:because|since|as|cos|cause|'
    r'due\s+to|and|so)\b|\s+for\s+(?:fixing|a\s+fix|fixes|correction|corrections|'
    r'changes|review|rework|amendment|amendments|another\s+look)\b)')
#: One word of the thing being sent; a send-back's own "back" never is one
#: ("Back Office" and "back pay" are).
_ITEM_WORD = r'(?!' + _BACK_NAME + r')[^\s,;.:!?—]+'
#: FIX-1 sixth pass — a long sentence ("to", "who", "and" … in it) is a
#: send-back only when the words right before "back" end the THING being
#: sent: "the Sales and Marketing run", "the run (that) Mai prepared", "the
#: June run to Mai". Never a word that says somebody is back ("…to everyone
#: who is now back", "…to people just back", "…when the team is all back").
_THING = (r'(?:(?:pay\s*)?runs?|payrolls?|(?:pay\s*)?slips?|batch(?:es)?|requests?|'
          r'it|them|ones?)\b')
#: Words that are a group of people, never one person the run goes back to.
_GROUP = (r'(?:everyone|everybody|anyone|anybody|someone|somebody|all|both|staff|'
          r'people|employees?|workers?|team|teams|those|these|them|us|me|him|her|'
          r'others?|ones?|folks?|guys|drivers?)\b')
#: Who made the thing: "Mai", "I", "the preparer".
_MAKER = (r'(?:(?:i|we|you|he|she|they)\b|(?:the\s+)?(?!' + _CLAUSE_WORD + r'|' + _GROUP
          + r')[^\W\d_]+)')
#: What they did to it: "prepared", "made", "set up" — never a coming or
#: going word ("returned", "came") or a second order ("wanted", "called").
_MADE = (r'(?!' + _SECOND_ORDER + r'|(?:needed|wanted|called|texted|phoned|pinged|'
         r'returned|arrived|joined|moved|headed|walked|stepped|turned|reported|'
         r'checked|replied|settled|landed)\b)'
         r'(?:[^\W\d_]+ed|made|ran|did|built|wrote|began|drew\s+up|set\s+up|'
         r'put\s+together)\b')
_SENT_THING = (
    _THING + r'(?:\s+(?:(?:that|which)\s+)?' + _MAKER
    + r'(?:\s+(?:has|had|have|just|already))?\s+' + _MADE
    + r'|\s+to\s+(?:the\s+)?(?!(?:the|a|an|my|our|your|their)\b|' + _CLAUSE_WORD + r'|'
    + _GROUP + r'|' + _BACK_NAME + r')[^\s,;.:!?—]+)?')
#: Either up to 12 words of ONE thing being sent ("the June 2031 Retail
#: End-Month pay run"), then "back" (with anything after it); or up to 20
#: words with no break and no second order, ending in the thing being sent
#: (`_SENT_THING`), then "back" ("straight back", "right back") and an
#: ending that makes it a send-back.
#: FIX-1 seventh pass: "Send the June payslips for staff back from leave",
#: "… - Mai back Monday" — after "for <people>" or a lone dash, "back" says
#: who is back unless an ending makes it a send-back ("… back to Mai",
#: "… back because …"; any reason: `_RETURN_WITH_REASON`).
_FOR_PEOPLE = (r'for\s+(?:(?:the|all|our|my|those|these|any|every|returning)\s+)*'
               + _GROUP)
_DASH = r'[-–](?=\s|$)'
_SEND_BACK_AHEAD = (
    r'(?:' + _BACK_NAME
    + r'|(?:(?!' + _CLAUSE_WORD + r'|' + _AGO + r'|' + _FOR_PEOPLE + r'|' + _DASH + r')'
    + _ITEM_WORD + r'\s+){0,11}?'
    + r'(?!' + _CLAUSE_WORD + r'|' + _NOT_BEFORE_BACK + r'|' + _DASH + r')' + _ITEM_WORD + r'\s+'
    + _BACK_NAME
    # …and with them, only when an ending makes it a send-back: "Send the
    # payslips for the people in Retail back to Mai".
    + r'|(?:(?!' + _CLAUSE_WORD + r'|' + _AGO + r')' + _ITEM_WORD + r'\s+){0,11}?'
    + r'(?!' + _CLAUSE_WORD + r'|' + _NOT_BEFORE_BACK + r')' + _ITEM_WORD + r'\s+'
    + _BACK_NAME + _SEND_BACK_END
    + r'|(?:(?!' + _SECOND_ORDER + r')' + _ITEM_WORD + r'\s+){0,19}?'
    + _SENT_THING + r'(?:\s+(?:straight|right))?\s+' + _BACK_NAME + _SEND_BACK_END
    + r')')
_NOT_SEND_BACK = r'(?!' + _SEND_BACK_AHEAD + r')'

#: FIX-1 seventh pass (P3 crit-3, still broken after the sixth): the word
#: lists above cannot tell every send-back from a "back" that is somebody
#: else's — "Send it all back because the payslips are wrong", "Send the run
#: Mai sent in back because …", "Send the run waiting for me back because …",
#: "Email the June payslips back to Mai because they are wrong" all reached
#: Send payslips. A sentence that says WHY something goes back ("because",
#: "wrong", "missing", "fix" … anywhere after a standalone "back") is never
#: an email of payslips, whatever words sit before "back" — only "Mai is
#: back", "they came back", "two weeks back" are somebody else's "back".
#: Payslip emails cannot be undone, so an unsure sentence goes to the
#: send-back phrases or the model, never to Send payslips.
_FIX_WORD = (r'(?:because|cos|coz|cause|bc|due\s+to|wrong|missing|incorrect|inaccurate|'
             r'mistakes?|errors?|erroneous|faulty|broken|fix|fixed|fixes|fixing|'
             r'correct|corrected|correcting|corrections?|redo|re-do|rework|reworked|'
             r'amend|amended|amendments?)\b')
#: The word before a "back" that is somebody coming or going back, a time
#: ago, or a place ("at the back") — never a send-back.
_BACK_OF_SOMEBODY = (
    r'(?:is|are|am|was|were|be|been|being|get|gets|got|getting|come|comes|came|'
    r'coming|go|goes|went|going|gone|days?|weeks?|months?|years?|fortnights?|'
    r'hours?|minutes?|while|the|at|from|'
    # FIX-1 ninth pass (regressions of the seventh): people who are back,
    # not a thing sent back — "…, welcome back everyone, mistakes fixed",
    # "…to everyone back at work, errors corrected", "…to people who were
    # away, now back, …", "…to the team who returned back, …", "…to staff
    # back in the office, …", "…to those back from leave, …".
    r'welcome|now|returned|everyone|everybody|staff'
    r')\s'
    # FIX-1 eleventh pass (regressions of the seventh): a second order's own
    # "back" ("…and report back if anything is wrong", "…, call me back if
    # something is wrong", "…and write back if any are wrong"), and the
    # people the payslips go TO who are back ("…to employees back from
    # leave, errors corrected", "…to the drivers back on shift, mistakes
    # fixed"). Never when "back" goes on "to <whoever>" or with the reason
    # ("…to the team back to Lan for corrections", "…I had to report back
    # because …"), and never after "for" ("…for the drivers back with a note
    # that …"): those keep the guard.
    r'|(?:(?:report|write|reply|call|ring|phone|text|message|hear|check|circle|loop)\s'
    r'|(?<=\b(?:call|ring|text)\s)(?:me|us)\s|(?<=\b(?:phone|write)\s)(?:me|us)\s'
    r'|(?<=\bget\s)(?:me|us|them)\s'
    r'|(?:(?<=\bto\s)|(?<=\bto\sthe\s))(?:people|employees?|workers?|drivers?|guys|'
    r'folks?|teams?|others)\s)'
    r'(?!back\s+(?:to(?!\s+(?:me|myself|us)\b)|because|since|as|cos|coz|cause|bc|'
    r'due\s+to)\b)'
    # "Send the June payslips, back from leave staff included, …": a break
    # right before a "back from / at / in / on" is somebody being back.
    r'|\S+,\s(?=back\s+(?:from|at|in|on)\s)'
    r'|(?<=\bto\s)(?:those|these)\s'
    r'|\S+[\'’](?:s|re|m)\s')
_PLAIN_BACK = r'back\b(?![\s-]*(?:pay|office)\b)(?!-)'
_RETURN_WITH_REASON = (
    r'(?!(?:' + _PLAIN_BACK + r'|.*?(?<!\S)(?!' + _BACK_OF_SOMEBODY + r')\S+\s+'
    + _PLAIN_BACK + r').*?\b' + _FIX_WORD + r')')

#: FIX-1 eighth pass (P3 crit-3, still broken after the seventh): a reason
#: need not use any of `_FIX_WORD`'s words — "Send it all back, the payslips
#: show last month's rates", "Send the run Mai sent in back, the payslips
#: need another look", "Send all back, payslips show old rates" all reached
#: Send payslips with "it all back, the" as the run. A payslip send names
#: the payslips right after what it sends ("Send the June payslips", "Send
#: out the Retail payslips"); a "back" BEFORE the first "payslips" is never
#: part of that — the sentence sends something back (or is unsure), so it
#: goes to the send-back phrases or the model, never to an email that
#: cannot be undone. "back pay", "Back Office", "back-pay", "payback",
#: "welcome-back" are names, not a "back".
_NO_BACK_BEFORE_SLIPS = (
    r'(?!(?:(?!pay\s*slips?\b).)*?(?<![\w\'’-])back\b(?![\s-]*(?:pay|office)\b)(?!-))')

#: FIX-1 sixth pass (P3 crit-3, the Vietnamese half): "Gửi phiếu lương tháng
#: 6 trả lại cho Mai vì sai" sends something BACK — never an email of the
#: payslips or a send for approval. "trả lại" / "trả về" / "gửi trả"
#: anywhere in the sentence takes it off the payslip and approval phrases
#: (the model, which knows the send-back, reads it instead). Written with
#: marks; the registry folds it with the phrase.
_VI_SEND_BACK = r'(?!.*(?<!\w)(?:trả\s+(?:lại|về)|gửi\s+trả)(?!\w))'


def _vi_not_send_back(key):
    """The Vietnamese phrases of `key` (`phrases_vi.PHRASES_VI`, kept there)
    with `_VI_SEND_BACK` right after their start."""
    out = []
    for phrase in PHRASES_VI.get(key, ()):
        head = MARKED_ONLY if phrase.startswith(MARKED_ONLY) else ''
        body = phrase[len(head):]
        caret = '^' if body.startswith('^') else ''
        out.append(head + caret + _VI_SEND_BACK + body[len(caret):])
    return tuple(out)


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
                  "person's words, e.g. 'Retail'. Only the scheme: any "
                  "people named go in 'people'. Never an id."),
             Slot('people', _lt('People'), 'people', False,
                  "Who to include if the person said: named people, e.g. "
                  "'Vu Khanh Chi only', or a status, e.g. 'active only'. "
                  "Never part of the scheme. Empty means everyone the scheme "
                  "covers."))
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
        """"Run payroll for Retail for June": the month rides in the scheme.
        "… for Retail End-Month for Vũ Khánh Chi only": so do the people
        (P3-W1) — split off into their own slot.

        FIX-1 (P3 wf-4): the people are split off FIRST, on the words as
        typed, and a month is only read from the scheme's part — "Mây" (a
        name) is never the month May."""
        texts = dict(texts or {})
        self._period_words_to_scheme(ctx, texts)
        scheme = (texts.get('scheme') or '').strip()
        if not scheme:
            return texts
        if not (texts.get('people') or '').strip():
            return self._split_people(ctx, texts)
        # The people came in their own slot: only a month and an "only" can
        # ride here. FIX-1 (P3 wf-3, second pass): "Retail End-Month only" /
        # "… for May only" lose their "only" here too, as on the phrase
        # path, so the scheme resolves without a question; the period gets
        # the month's own words ("May"), never the whole text.
        scheme = self._bare(scheme)
        texts['scheme'] = scheme
        if not texts.get('period'):
            got = self._month_in(scheme)
            if got:
                texts['period'] = _month_words(scheme, got[3]) or scheme
                texts['scheme'] = _without_month(scheme, got[3])
        return texts

    #: Words before "payroll" that name neither a month nor a scheme ("Run
    #: my payroll", "Run the monthly payroll", "Chạy lương kỳ này").
    _PERIOD_FILLER = frozenset((
        'my', 'our', 'your', 'their', 'a', 'an', 'this', 'that', 'next', 'new',
        'monthly', 'regular', 'usual', 'normal', 'whole', 'full', 'current',
        'latest', 's', 'nay', 'toi', 'chung', 'ta', 'minh'))

    #: FIX-1 eighth pass: words that belong to the month phrase itself —
    #: "the end of May", "mid-month", "May month", "this pay period", "June
    #: and July", "June '31", "13th month", "cuối / giữa / đầu tháng 5", "kỳ
    #: 1", "đợt 2". They stay in the period; they never make a scheme.
    _MONTH_PHRASE = frozenset((
        'end', 'ending', 'mid', 'middle', 'early', 'late', 'beginning', 'begin',
        'start', 'starting', 'first', 'second', 'third', 'last', 'half', 'month',
        'period', 'pay', 'cycle', 'year', 'quarter', 'week', 'fortnight', 'day',
        'of', 'to', 'and', 'or', 'through', 'thru', 'until', 'till', 'this',
        'next', 'previous', 'prior', 'current', 'same', 'th', 'st', 'nd', 'rd'))
    #: The Vietnamese ones, as written with marks ("năm" is the year; "Nam"
    #: is a name).
    _MONTH_PHRASE_VI = frozenset((
        'cuối', 'giữa', 'đầu', 'tháng', 'năm', 'kỳ', 'đợt', 'sau', 'trước',
        'tới', 'qua', 'đến', 'và', 'hoặc', 'nửa', 'này'))
    #: …and typed without marks ("cuoi thang 5"), "nam" left out.
    _MONTH_PHRASE_VI_BARE = frozenset(
        fold(w) for w in _MONTH_PHRASE_VI if fold(w) != 'nam')

    def _month_phrase_word(self, word):
        """True for a word that is part of a month phrase (`_MONTH_PHRASE`), a
        number ("2031", "'31", "13th", "1-31"), a filler word ("my", "the"),
        or an English month written without marks ("July" in "June and
        July"). "Mây" (marks on it) is a name, never the month May."""
        low = unicodedata.normalize('NFC', word).lower().strip('\'’,.;:!?()')
        if low in self._MONTH_PHRASE_VI:
            return True
        marked = low != fold(low)
        if not marked and fold(low) in self._MONTH_PHRASE_VI_BARE:
            return True
        stop = self._MONTH_PHRASE.union(self._PERIOD_FILLER, _GLUE)
        # Unstemmed ("this" is no plural of "thi"); "months" / "periods" too.
        for tok in re.findall(r'[0-9a-z]+', fold(low)):
            if tok in stop or tok[:-1] in stop and tok.endswith('s') \
                    or any(c.isdigit() for c in tok):
                continue
            if tok in MONTHS and not marked:
                continue
            return False
        return True

    @staticmethod
    def _labels_a_number(words, i):
        """FIX-1 final round (safety check): "khối 2 / tổ 2 / nhóm 2 / tuần 2
        / quý 3" in the period slot labels a team, week or quarter, as
        `resolve._not_a_count` reads it ("chạy lương khối 2 tháng trước" is
        last month's). The label stays with its number in the period, as
        before FIX-1 — never the scheme "Lương khối văn phòng", and never
        leaving "2 tháng trước" (two months ago) behind."""
        if i + 1 >= len(words) or not words[i + 1].strip(',.;:').isdigit():
            return False
        folded = fold(words[i].strip(',.;:'))
        if folded not in _VI_LABEL_BEFORE_COUNT:
            return False
        return not (folded == 'ca' and i and fold(words[i - 1]) == 'tang')

    def _period_words_to_scheme(self, ctx, texts):
        """FIX-1 seventh pass (regression of wf-4): "Run Retail End-Month
        payroll for May" puts "Retail End-Month" in the period slot and
        "May" in the scheme slot (the phrase reads the words before
        "payroll" as the month). Words there that are no part of a month
        phrase are the SCHEME's ("Retail End-Month", "Bán lẻ", "June Retail
        End-Month" → "Retail End-Month"): they move to the scheme and the
        period keeps the rest. Before, the scheme was blanked and the month
        thrown away: a ready plan for this month on the wizard's default
        scheme.

        FIX-1 eighth pass (regressions of the seventh): the words of the
        month phrase itself — "the end of May", "mid-month", "May month",
        "cuối tháng 5", "kỳ 1 tháng 5", "June and July", "2031" — stay in the
        period, on every path (phrase, model, pencil). Only a period with
        some OTHER word in it moves anything, and then the longest stretch
        of words around those that one scheme covers moves ("Retail
        End-Month", "Pay for Performance"), never words on the far side of
        the month. The two halves are joined as one scheme when one scheme
        covers them together ("Run Retail payroll for Mid-Month"); otherwise
        with "for", so a month or people said after "payroll" are read as
        before."""
        period = (texts.get('period') or '').strip()
        if not period:
            return
        # A month that cannot be read ("tháng 13", "thang sau") stays for
        # the period question; it is no scheme.
        if period_problem(period, fields.Date.today()):
            return
        words = period.split()
        got = self._month_in(period)
        kept = got[3].split() if got else [fold(w) for w in words]
        month = []
        for w in words:
            f = fold(w)
            if f in kept:
                kept.remove(f)
                month.append(False)
            else:
                month.append(True)
        other = [i for i, w in enumerate(words)
                 if not month[i] and not self._month_phrase_word(w)
                 and not self._labels_a_number(words, i)]
        if not other:
            return
        lo, hi = other[0], other[-1]
        if any(month[lo:hi + 1]):
            # A month in the middle of the other words: all the words that
            # are no month go, as said.
            span = [i for i in range(len(words)) if not month[i]]
        else:
            a_min = lo
            while a_min > 0 and not month[a_min - 1]:
                a_min -= 1
            b_max = hi
            while b_max < len(words) - 1 and not month[b_max + 1]:
                b_max += 1
            spans = sorted(((a, b) for a in range(a_min, lo + 1)
                            for b in range(hi, b_max + 1)),
                           key=lambda ab: ab[0] - ab[1])
            # FIX-1 eleventh pass: a name ends in a word the month phrase also
            # has ("Nguyễn Văn An" — "an"): the whole name moves, never
            # "Nguyễn Văn" (three people) with the "An" left behind.
            a, b = next((ab for ab in spans if self._said_scheme(
                ctx, ' '.join(words[ab[0]:ab[1] + 1])) or self._names_people(
                ctx, ' '.join(words[ab[0]:ab[1] + 1]))), (lo, hi))
            span = list(range(a, b + 1))
        said = ' '.join(words[i] for i in span).strip(' ,')
        scheme = (texts.get('scheme') or '').strip()
        both = '%s %s' % (said, scheme)
        if not self._words_to_move(ctx, said, scheme, texts.get('people')):
            return
        left = ' '.join(w for i, w in enumerate(words) if i not in span).strip(' ,')
        if not any(month) and not tokens(left, stop=self._PERIOD_FILLER.union(_GLUE)):
            left = ''
        texts['period'] = left
        if not scheme:
            texts['scheme'] = said
        elif self._said_scheme(ctx, self._bare(said), self._bare(scheme)):
            texts['scheme'] = both
        else:
            # FIX-1 eleventh pass (regression of the eighth): only the scheme
            # slot's FIRST part (up to its first "for" / "with" …) is read
            # with the period's words; the rest keeps its own cut. "Run Retail
            # payroll for Mid-Month for Mai" is Retail Mid-Month for Mai, never
            # "Retail for Mid-Month" (no scheme with the "for" in it) and a
            # person called "Mid-Month". A first part of nothing but
            # month-phrase words is the period ("Run Retail End-Month payroll
            # for 13th month" / "… for this pay period for Mai" / "… for 2031
            # for Mai", tenth pass), never a person's name either.
            cut = self._CUT.search(scheme)
            head = (scheme[:cut.start()] if cut else scheme).strip(' ,')
            tail = scheme[cut.start():] if cut else ''
            bare = self._bare(head)
            if tail and bare and self._said_scheme(ctx, self._bare(said), bare):
                texts['scheme'] = '%s %s%s' % (said, head, tail)
            elif bare and all(self._month_phrase_word(w) for w in head.split()) \
                    and not self._covers_scheme(ctx, bare) \
                    and not (left and self._month_in(head)):
                texts['scheme'] = said + tail
                texts['period'] = self._month_phrase_period(left, head)
            elif self._period_name(ctx, said) or (
                    bare and not self._covers_scheme(ctx, bare) and (
                        self._names_somebody(ctx, head) or self._status_hit(ctx, head)
                        or self._month_in(bare))):
                texts['scheme'] = '%s for %s' % (said, scheme)
            else:
                # FIX-1 twelfth pass (regression of the eleventh): what comes
                # after "payroll" is no name, no status and no month ("Run
                # Retail payroll for End-Month staff", "… for the store
                # team"), or is a scheme of its own ("Run Pay for Performance
                # payroll for Retail for Mai"). Joined with "for", it was cut
                # off as a person nobody is called and the plan was refused.
                # The words stay where they were said, as before FIX-1: the
                # scheme question asks which.
                texts['period'], texts['scheme'] = period, scheme

    def _month_phrase_period(self, left, head):
        """The period for month-phrase words said after "payroll" (`head`),
        with what the period slot kept (`left`). A month that only reads
        with its "for" ("for May month") keeps just the month's words; a
        month said before "payroll" ("Run May Retail End-Month payroll for
        this pay period") stays that month, with a year said after it ("…
        for 2031") when the two read together."""
        if left:
            both = '%s %s' % (left, head)
            return both if self._month_in(both) else left
        if not self._month_in(head):
            joined = 'for %s' % head
            got = self._month_in(joined)
            if got:
                return _month_words(joined, got[3]) or head
        return head

    def _words_to_move(self, ctx, said, scheme, people=''):
        """FIX-1 ninth pass (regressions of the seventh and eighth): may the
        period's other words (`said`) move to the scheme? Only when they are
        plainly the scheme's or somebody's — never a word the period merely
        carries ("May 2031 bonus", "salaries for May", "tháng 5 nhé", "May
        please", "nhân viên tháng 5"): those stay in the period, as before
        FIX-1, so the model's and the pencil's month is read as said.

        - The scheme slot already names a scheme on its own (the model's or
          the pencil's slots; "Run Retail payroll for Mid-Month"): the words
          move only when they are somebody's name, or add words the scheme
          slot lacks and one scheme covers the two together. "May payroll
          Retail" next to "Retail End-Month" adds nothing: nothing moves.
        - The scheme slot is empty ("Chạy lương Bán lẻ tháng 5", "Run Retail
          End-Month payroll"): only words one scheme covers, or a name.
        - The scheme slot holds no scheme ("Run Retail End-Month payroll for
          May", "… for May for Mai"): words one scheme covers, a name, or —
          when a month rides in the scheme slot, as on the phrase path — any
          words ("Run Warehouse payroll for May" asks which scheme).

        FIX-1 twelfth pass (regressions of the seventh): the scheme's words
        count only AS WRITTEN (`_said_scheme`) — "luôn" (right away) is not
        "Lương …", "lẹ" (quickly) and "lễ" (holiday) are not "Bán lẻ". A name
        moves only as `_period_name` reads one ("mai" in small letters is also
        "tomorrow"), and never when the people slot is already filled (the
        model's or the pencil's slots). Those words stay in the period, as
        before FIX-1."""
        if self._period_name(ctx, said):
            return not (people or '').strip()
        if not scheme:
            return self._said_scheme(ctx, self._bare(said))
        if self._covers_scheme(ctx, self._bare(scheme)):
            have = tokens(self._bare(scheme))
            adds = any(not any(tok_match(t, w) for w in have)
                       for t in tokens(self._bare(said)) if t not in self._SCHEME_FILLER)
            return adds and self._said_scheme(ctx, self._bare(said), self._bare(scheme))
        return bool(self._said_scheme(ctx, self._bare(said)) or self._month_in(scheme))

    # "… for May only", "… for May just": the trailing word is never part
    # of a month, a scheme or a name.
    _ONLY = re.compile(r'(?:^|\s+)(?:only|just)\s*$', re.I)
    _LEAD_ONLY = re.compile(r'^\s*(?:just|only)\s+', re.I)
    # FIX-1 sixth pass: "… for May only please" — a polite word at either
    # end is never part of a month, a scheme or a name either.
    _POLITE = re.compile(r'(?:^|[\s,]+)(?:please|pls|plz|thanks|thank\s+you|thx)\s*$'
                         r'|^\s*please\s+', re.I)
    # "May Retail End-Month": `parse_period` does not take "may" leading other
    # words ("may" is too common a word); here it leads a scheme's name.
    # Unmarked only — "Mây" is a name (P3 wf-4).
    _LEAD_MAY = re.compile(r'^\s*(may)\s+(\S.*)$', re.I)
    # P4 — "Bán lẻ chỉ Vũ Khánh Chi", "Bán lẻ, riêng Vũ Khánh Chi", "Vũ Khánh
    # Chi thôi". On the MARKED text: "chỉ" (only) is not the name "Chi".
    _ONLY_VI = re.compile(r'(?:^|\s+)(?:mà\s+)?thôi\s*$|^\s*(?:chỉ|riêng)\s+', re.I)
    #: Where one part of "<scheme> for <people>" ends and the next begins.
    #: "just for" / "only for" / "just with" are ONE cut (FIX-1 third pass:
    #: "… just for Mai" left "for Mai" as the person's name).
    _CUT = re.compile(r'\s+(?:(?:just|only)\s+)?(?:for|with)\s+|\s+just\s+'
                      r'|\s*,?\s+(?:cho\s+riêng|riêng|chỉ\s+cho|chỉ|cho|với)\s+', re.I)
    #: Words that never decide whether a part names a scheme.
    _SCHEME_FILLER = frozenset(('the', 'scheme', 'payroll'))

    def _bare(self, words):
        """The words without "only" / "just" / "chỉ" / "thôi" around them."""
        words = self._POLITE.sub('', words or '')
        words = self._LEAD_ONLY.sub('', self._ONLY.sub('', words))
        return self._ONLY_VI.sub('', words).strip(' ,')

    @staticmethod
    def _month_in(text):
        """`parse_period` on `text`, except that a word written WITH marks
        that folds to an English month ("Mây" → may) is a name, never the
        month (P3 wf-4). Same (start, end, origin, rest) as `parse_period`;
        `rest` lines up with `text` for `_without_month`."""
        hidden = {}

        def hide(m):
            word = m.group(0)
            if fold(word) in MONTHS and word.lower() != fold(word):
                key = 'zqhide%s' % chr(97 + len(hidden))
                hidden[key] = fold(word)
                return key
            return word
        probe = re.sub(r'[^\W\d_]+', hide, text or '')
        # Only WHETHER a month is there and the words it leaves are used here;
        # the period slot reads the month again with the person's own today.
        got = parse_period(probe, fields.Date.today())
        if not got or not hidden:
            return got
        rest = got[3]
        for key, word in hidden.items():
            rest = rest.replace(key, word)
        return got[0], got[1], got[2], rest

    def _covers_scheme(self, ctx, words, whole=False):
        """True when ONE scheme the person may run has every one of these
        words — its name, code or part of the business, a near spelling
        counting. A part that only shares a word with a scheme ("Văn" in
        "Lương khối văn phòng") is not a scheme (P3 wf-1).

        `whole`: the words must also name that scheme in FULL — every word of
        its name, its code, or every word of its part of the business
        ("Retail") — not just some of its words ("Phong" of "Lương khối văn
        phòng"). Asked of words that are also somebody's name."""
        q = [t for t in tokens(words or '') if t not in self._SCHEME_FILLER]
        if not q:
            return False
        try:
            schemes = self._defaults(ctx).get('schemes') or []
        except (UserError, AccessError):
            return False
        for s in schemes:
            have = tokens(' '.join(x for x in (
                s.get('name') or '', s.get('code') or '',
                (s.get('division') or '').replace('_', ' '),
                division_names(s.get('division'))) if x))
            if not all(any(tok_match(t, w) for w in have) for t in q):
                continue
            if not whole:
                return True
            for full in (s.get('name') or '', s.get('code') or '',
                         (s.get('division') or '').replace('_', ' '),
                         division_names(s.get('division'))):
                need = [w for w in tokens(full) if w not in self._SCHEME_FILLER]
                if need and all(any(tok_match(t, w) for t in q) for w in need):
                    return True
        return False

    def _period_name(self, ctx, said):
        """True when the period slot's other words (`said`) are people: each
        name somebody's whole name, or found by its words (`_names_somebody`)
        AND written as a name, every word with a capital ("Run Mai payroll for
        Retail"). FIX-1 twelfth pass: "Chạy lương tháng 5 mai nhé" — "mai"
        (tomorrow) — stays in the period, as before FIX-1."""
        if self._names_people(ctx, said):
            return True
        names = self._names(said)
        return bool(names) and all(w[:1].isupper() for n in names for w in n.split()) \
            and self._names_somebody(ctx, said)

    def _said_scheme(self, ctx, said, rest=''):
        """True when ONE scheme the person may run has every word of `said`
        exactly as written — no near spelling, and a word typed WITH marks
        has that scheme word's own marks ("lẹ" / "lễ" are not "lẻ", "luôn" is
        not "lương") — and every word of `rest` the way `_covers_scheme`
        reads it. Asked of the words that leave the period slot (FIX-1
        twelfth pass): those were never a scheme before FIX-1, so only a
        scheme's own words may make one there."""
        said_words = [w for w in _marked_words(said)
                      if not set(tokens(w)) <= self._SCHEME_FILLER]
        if not said_words:
            return False
        q = [t for t in tokens(rest or '') if t not in self._SCHEME_FILLER]
        try:
            schemes = self._defaults(ctx).get('schemes') or []
        except (UserError, AccessError):
            return False
        for s in schemes:
            text = ' '.join(x for x in (
                s.get('name') or '', s.get('code') or '',
                (s.get('division') or '').replace('_', ' '),
                division_names(s.get('division'))) if x)
            own = _marked_words(text)
            if not all(any(tokens(w) == tokens(o) and (w == fold(w) or w == o)
                           for o in own) for w in said_words):
                continue
            have = tokens(text)
            if all(any(tok_match(t, w) for w in have) for t in q):
                return True
        return False

    def _split_people(self, ctx, texts):
        """"<scheme> for <people>", "<people> only" → the scheme slot and the
        people slot (P3-W1). FIX-1 (P3 wf-1…wf-4, wf-7) — decided in this
        order, part by part ("for", "with", "just", "chỉ", "cho" … cut them):

        1. a part that is exactly the name of somebody a run could pay (marks
           and capitals aside) is PEOPLE, whatever words it shares with a
           scheme or a status;
        2. the longest run of the other parts that one scheme's words cover
           word for word is the SCHEME — "Pay for Performance" stays whole,
           "Retail End-Month only" loses its "only". A part whose every word
           is in somebody's name ("Phong", "Dũng") counts only when it names
           the scheme in full: "Phong only" is Trần Thanh Phong, never
           "Lương khối văn phòng" (FIX-1 second pass);
           A month riding at either end of that run ("Pay for Performance
           December", "December Pay for Performance") goes to the period
           and the rest is still the whole scheme (FIX-1 third pass);
        3. a part that is nothing but a month is the PERIOD; a month word
           inside a name is never one;
        4. whatever is left is the people's words (names or a status). A
           part after "with" that is nobody's name and no status ("Retail
           with overtime") stays there — the run is never silently widened
           or narrowed — and is remembered, so the reply can say a run is
           narrowed only to people or a status.
        """
        scheme = texts['scheme'].strip()
        bounds, cuts, start = [], [''], 0
        for m in self._CUT.finditer(scheme):
            bounds.append((start, m.start()))
            cuts.append(m.group(0))
            start = m.end()
        bounds.append((start, len(scheme)))
        n = len(bounds)

        def part(i, j=None):
            return scheme[bounds[i][0]:bounds[i if j is None else j][1]].strip(' ,')

        people = {i for i in range(n) if self._names_people(ctx, part(i))}
        # Every word in somebody's name, not exactly their name: a person
        # unless the part names a scheme in full.
        named = {i for i in range(n) if i not in people
                 and self._names_somebody(ctx, part(i))}
        # The period keeps the BARE words: "May only" is no month to
        # `parse_period` ("may" alone is too common a word), "May" is (FIX-1
        # fourth pass — the period silently fell back to this month).
        months = {}
        for i in range(n):
            if i in people:
                continue
            words = self._bare(part(i))
            got = self._month_in(words)
            # FIX-1 eighth pass: "the month of May", "mid May", "the end of
            # May" are nothing but a month too (`_month_phrase_word`).
            if got and all(self._month_phrase_word(w)
                           for w in _without_month(words, got[3]).split()):
                months[i] = words
        best = None                 # (first part, last part, scheme words, period words)
        for size in range(n, 0, -1):
            for i in range(n - size + 1):
                j = i + size - 1
                if any(k in people or k in months for k in range(i, j + 1)):
                    continue
                words = self._bare(part(i, j))
                whole = any(k in named for k in range(i, j + 1))
                if self._covers_scheme(ctx, words, whole):
                    best = (i, j, words, '')
                    break
                # A month in the run (any size: "Pay for Performance
                # December" spans two parts) — the rest must be the scheme.
                got = self._month_in(words)
                rest = _without_month(words, got[3]) if got else ''
                if rest and self._covers_scheme(ctx, rest, whole):
                    best = (i, j, rest, words)
                    break
                # FIX-1 sixth pass: "May Retail End-Month only" — the month
                # the person said, then the whole scheme.
                lead = self._LEAD_MAY.match(words)
                if lead and self._covers_scheme(ctx, lead.group(2), whole):
                    best = (i, j, lead.group(2).strip(), lead.group(1))
                    break
            if best:
                break
        others = [k for k in range(n) if k not in people and k not in months
                  and not (best and best[0] <= k <= best[1])]
        period = next((months[k] for k in sorted(months)), '')
        if best:
            texts['scheme'] = best[2]
            period = best[3] or period
            who = sorted(people.union(others))
        elif n == 1 and not people and not months:
            if self._EVERYONE_SAID.match(fold(self._bare(scheme))):
                # GAPS (FIX-1 later list): "Run June payroll for everyone",
                # "Chạy lương tháng 6 cho toàn bộ nhân viên" — nobody left
                # out, which is what no people means (everyone the scheme
                # covers); never a scheme called "everyone". Only after no
                # scheme was found by these words (a scheme named "All staff"
                # keeps its name).
                texts['scheme'] = ''
                return texts
            if named or self._ONLY.search(scheme) or self._ONLY_VI.search(scheme):
                # "Run December payroll for An only", "… for Phong": no
                # scheme said — somebody's name is.
                texts.update(scheme='', people=scheme)
                return texts
            # One part that is not a scheme word for word: kept for the
            # scheme question; a month riding in it still goes to the period.
            got = self._month_in(scheme)
            if got and not texts.get('period'):
                texts.update(period=scheme, scheme=_without_month(scheme, got[3]))
            return texts
        else:
            # No part is a scheme word for word: the first part that is not
            # people or a month is what was said for the scheme (the scheme
            # question asks which); the people keep their own words.
            # A part that is somebody's name is never taken for the scheme.
            first = next((k for k in others if k not in named), None)
            words = part(first) if first is not None else ''
            bare = self._bare(words)
            got = self._month_in(bare) if bare else None
            if got and _without_month(bare, got[3]):
                period = period or bare
                words = _without_month(bare, got[3])
            texts['scheme'] = words
            who = sorted(people.union(k for k in others if k != first))
        if period and (not texts.get('period') or self._no_month_said(texts['period'])):
            # GAPS (FIX-1 later list): "Run monthly payroll for next month" —
            # "monthly" before "payroll" names no month, so the month said
            # after it is the period (it was dropped, and the plan showed
            # this month as the default).
            texts['period'] = period
        if who:
            texts['people'] = ', '.join(part(k) for k in who)
            wishes = ctx.cache.setdefault('run_wishes', set())
            for k in who:
                if k in people or k in named or not re.search(
                        r'\b(?:with|với)\b', cuts[k], re.I):
                    continue
                if self._status_hit(ctx, part(k)):
                    continue
                wishes.update(fold(name) for name in self._names(part(k)))
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
            return self._resolve_people(ctx, text)
        return super().resolve_slot(ctx, slot, text)

    # ----------------------------------------------------------- people
    #: Words around a status that are not part of it ("active staff only",
    #: "staff on probation", "nhân viên chính thức").
    _STATUS_FILLER = frozenset((
        'only', 'just', 'the', 'people', 'person', 'staff', 'employee', 'worker',
        'who', 'are', 'is', 'still', 'currently', 'status', 'those', 'one',
        'and', 'or', 'on', 'in', 'under', 'with', 'of', 'at',
        'nguoi', 'cac', 'nhung', 'va', 'hoac', 'nhan', 'vien', 'la'))
    _EVERYONE = frozenset(('everyone', 'all', 'everybody'))
    #: GAPS: the whole of a "for …" part that means nobody left out (folded).
    _EVERYONE_SAID = re.compile(
        r'^(?:everyone|everybody|all|all\s+(?:of\s+)?(?:the\s+)?(?:staff|employees|people|'
        r'workers|team|company)|every\s+(?:employee|person|one)|'
        r'the\s+(?:whole|entire)\s+(?:team|company|staff)|'
        r'toan\s+bo(?:\s+(?:nhan\s+vien|cong\s+ty|moi\s+nguoi))?|'
        r'tat\s+ca(?:\s+(?:nhan\s+vien|moi\s+nguoi))?|moi\s+nguoi|'
        r'ca\s+cong\s+ty|toan\s+(?:the\s+nhan\s+vien|cong\s+ty))$')

    def _no_month_said(self, period):
        """GAPS: True when the period's words name no month — only filler or
        month-phrase words ("monthly", "my", "the"), no number."""
        words = (period or '').split()
        for word in words:
            # A capital on a little word is a name ("Run the An payroll …"),
            # unless the word is itself a month-phrase word ("Mid-Month").
            if word[:1].isupper() and not all(
                    t in self._MONTH_PHRASE for t in re.findall(r'[a-z]+', fold(word))):
                return False
        return bool(words) and not re.search(r'\d', period) \
            and not any(t in MONTHS for t in re.findall(r'[a-z]+', fold(period))) \
            and not self._month_in(self._bare(period)) \
            and all(self._month_phrase_word(w) for w in words)

    def _status_words(self, text):
        return [w for w in tokens(self._bare(text or '')) if w not in self._STATUS_FILLER]

    def _status_opts(self, ctx):
        """[(value, its words)] for every employment status the wizard ticks."""
        return [(o.get('value'), [w for w in tokens('%s %s' % (o.get('value') or '',
                                                               o.get('label') or ''))
                                  if w not in self._STATUS_FILLER])
                for o in self._defaults(ctx).get('statuses') or []]

    def _status_hit(self, ctx, text):
        """True when the words name employment statuses ("active only") —
        EVERY word, not one of them: "Nguyễn Thị Thu" shares "thu" with
        "Thử việc" and is a person (P3 wf-7)."""
        words = self._status_words(text)
        if not words:
            return False
        if set(words) & self._EVERYONE:
            return True
        known = [t for _v, ws in self._status_opts(ctx) for t in ws]
        return all(any(tok_match(w, t) for t in known) for w in words)

    def _status_said(self, ctx, text):
        """The statuses said IN FULL — every word of each ("thử việc" is
        Thử việc, never also Đang làm việc for sharing "việc") — when the
        words are nothing but whole statuses; else []."""
        words = self._status_words(text)
        if not words:
            return []
        hit, used = [], set()
        for value, ws in self._status_opts(ctx):
            if ws and all(any(tok_match(w, t) for w in words) for t in ws):
                hit.append(value)
                used.update(w for w in words if any(tok_match(w, t) for t in ws))
        return hit if used >= set(words) else []

    def _names(self, text):
        """"Chi, An and Lan only" → ['Chi', 'An', 'Lan']."""
        return [n.strip() for n in re.split(r'\s*,\s*|\s+and\s+|\s+và\s+|\s*&\s*',
                                            self._bare(text)) if n.strip()]

    def _people_pool(self, ctx, config_id=0):
        """Everybody a run for this scheme could pay — the wizard's own list
        (`_eligible_employees`, no status ticks), all of them, not the screen
        search's first 40 (P3 wf-6) — with the names read AS THE PERSON
        (PA-R2): the employee records, or the employee directory when the
        person may not open the records. Once per request."""
        cache = ctx.cache.setdefault('run_people', {})
        key = int(config_id or 0)
        if key not in cache:
            try:
                ids = ctx.env['pb.payrun.wizard']._eligible_employees(
                    formula_config_id=key or None)
            except (UserError, AccessError):
                ids = []
            cache[key] = self._people_rows(ctx, ids)
        return cache[key]

    @staticmethod
    def _people_rows(ctx, ids):
        ids = list(ids or [])
        if not ids:
            return []
        for model, names in (('hr.employee', ['name', 'barcode', 'department_id']),
                             ('hr.employee.public', ['name', 'department_id'])):
            if model not in ctx.env:
                continue
            Model = ctx.env[model]
            if model == 'hr.employee' and 'departure_date' in Model._fields:
                names = names + ['departure_date']
            try:
                found = Model.search_read([('id', 'in', ids)], names, order='name')
            except AccessError:
                continue
            out = []
            for r in found:
                words = re.findall(r'[0-9a-z]+', fold(r.get('name') or ''))
                marked = _marked_words(r.get('name'))
                dept = r.get('department_id')
                out.append({'id': r['id'], 'name': r.get('name') or '',
                            'code': r.get('barcode') or '',
                            'department': dept[1] if isinstance(dept, (list, tuple)) else '',
                            'left': r.get('departure_date') or '',
                            'words': words, 'wordset': set(words),
                            'marked': set(marked)})
            return out
        return []

    @staticmethod
    def _match_people(pool, name):
        """(rows, exact) — the people called exactly this (marks and capitals
        aside, or by their code), else everybody with every one of these
        name words."""
        want = re.findall(r'[0-9a-z]+', fold(name))
        if not want:
            return [], False
        code = fold(name).strip()
        exact = [r for r in pool
                 if r['words'] == want or (r['code'] and fold(r['code']) == code)]
        if exact:
            return exact, True
        return [r for r in pool if all(t in r['wordset'] for t in want)], False

    def _names_people(self, ctx, text):
        """True when the words are exactly the names of people a run could
        pay — every name of a list ("Chi, An and Lan")."""
        names = self._names(text)
        if not names:
            return False
        pool = self._people_pool(ctx, 0)
        return all(self._match_people(pool, name)[1] for name in names)

    def _names_somebody(self, ctx, text):
        """True when every name of the words finds somebody a run could pay —
        exactly, or by every one of its words ("Phong" → Trần Thanh Phong).
        A word typed WITH marks must match the name's own marks here: "văn
        phòng" (office) is not Trần Văn Phong, "Vận tải" not Nguyễn Văn Tài;
        typed without marks it matches either."""
        names = self._names(text)
        if not names:
            return False
        pool = self._people_pool(ctx, 0)
        for name in names:
            rows, _exact = self._match_people(pool, name)
            said = _marked_words(name)
            marked = [w for w in said if w != fold(w)]
            if not any(all(w in r.get('marked', ()) for w in marked) for r in rows):
                return False
        return True

    def _resolve_people(self, ctx, text):
        """Named people (P3-W1), found among the people THIS scheme pays —
        the wizard's own list, as the person. A status ("active only") stays
        a status, read by `_statuses` as before — when it is said in full, or
        when every word names one and no name finds anybody (P3 wf-7). A name
        found only by some of its words is 'assumed', never 'said' (P3 wf-6)."""
        text = ' '.join((text or '').split())
        empty = {'text': '', 'employee_ids': [], 'names': []}
        names = self._names(text)
        if not text or not names:
            return resolved(empty, '', 'default')
        config_id = int((ctx.params.get('scheme') or {}).get('value') or 0)
        pool = self._people_pool(ctx, config_id)
        # FIX-1 (P3 wf-7), in this order: somebody called exactly this; a
        # status said in full ("thử việc only", "active staff"); somebody
        # with every one of these name words ("Thu only" is Nguyễn Thị Thu
        # even with a "Thử việc" status); only then status words.
        found = [self._match_people(pool, name) for name in names]
        if not all(exact for _rows, exact in found):
            words = set(self._status_words(text))
            if (words & self._EVERYONE) or self._status_said(ctx, text) \
                    or (not all(rows for rows, _exact in found)
                        and self._status_hit(ctx, text)):
                return resolved(dict(empty, text=text), text, 'said')
        ids, labels, all_exact = [], [], True
        for name in names[:MAX_CHIPS]:
            rows, exact = self._match_people(pool, name)
            if not rows:
                if fold(name) in ctx.cache.get('run_wishes', ()):
                    # "Retail with overtime": not a person, not a status.
                    return missing(T(_lt(
                        'I could not find "%s" among the people this scheme pays, and a '
                        'run can only be narrowed to people or an employment status.'))
                        % name[:60])
                return missing(T(_lt(
                    'I could not find "%s" among the people this scheme pays.')) % name[:60])
            if len(rows) > 1:
                if len(names) == 1 and len(rows) <= MAX_CHIPS:
                    return ambiguous([{'value': r['id'], 'label': r['name'],
                                       'sublabel': r.get('department') or r.get('code') or ''}
                                      for r in rows])
                if len(names) == 1:
                    return missing(T(_lt(
                        '%(n)s people this scheme pays are called "%(name)s". Type more '
                        'of the name, or open the screen to pick them.')) % {
                            'n': num(len(rows)), 'name': name[:60]})
                return missing(T(_lt(
                    'More than one person here is called "%s". Ask for one person at a '
                    'time, or open the screen to pick them.')) % name[:60])
            ids.append(rows[0]['id'])
            labels.append(rows[0]['name'])
            all_exact = all_exact and exact
        return resolved({'text': '', 'employee_ids': ids, 'names': labels},
                        ', '.join(labels), 'said' if all_exact else 'assumed')

    def _named_outside(self, ctx, config_id, ids, names, statuses):
        """P3 wf-5 — somebody NAMED whose employment status the usual ticks
        leave out (a leaver's final pay). Their status joins the ticks for
        this run — the named list still limits the run to them — and the
        card says so, instead of a silent "0 of N". (statuses, [who])."""
        cache = ctx.cache
        if 'run_signals' not in cache:
            try:
                cache['run_signals'] = ctx.env['pb.payrun.wizard']._employee_signals() or {}
            except (UserError, AccessError):
                cache['run_signals'] = {}
        signals = cache['run_signals']
        if not signals:
            return statuses, []
        label = {o.get('value'): o.get('label') or o.get('value')
                 for o in self._defaults(ctx).get('statuses') or []}
        rows = {r['id']: r for r in self._people_pool(ctx, config_id)}
        extra, who = [], []
        for k, eid in enumerate(ids):
            status = (signals.get(eid) or {}).get('status') or ''
            if status in statuses:
                continue
            if status not in extra:
                extra.append(status)
            row = rows.get(eid) or {}
            who.append({'name': (names[k] if k < len(names) else '') or row.get('name') or '',
                        # '' is the wizard's own "Not stated" tick.
                        'status': label.get(status) or status or T(_lt('Not stated')),
                        'left': row.get('left') or ''})
        return list(statuses) + extra, who

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
        """The wizard's own default ticks; words like 'active only' narrow them.
        A status said in full is that status alone (FIX-1: "thử việc" never
        also ticks Đang làm việc and Nghỉ việc for sharing "việc")."""
        opts = self._defaults(ctx).get('statuses') or []
        if not opts:
            return None, ''
        chosen = [o['value'] for o in opts if o.get('default')]
        words = tokens(people_text or '')
        if words and set(words) & self._EVERYONE:
            return [o['value'] for o in opts], T(_lt('every employment status'))
        if words:
            hit = self._status_said(ctx, people_text)
            if not hit:
                words = self._status_words(people_text)
                hit = [v for v, ws in self._status_opts(ctx)
                       if any(tok_match(w, t) for w in words for t in ws)]
            if hit:
                return hit, ', '.join(hit)
        return chosen, ''

    def _vals(self, ctx, params):
        d = self._defaults(ctx)
        per = params['period']['value']
        sch = params['scheme']
        card = sch.get('card') or next(
            (s for s in d.get('schemes') or [] if s['id'] == sch.get('value')), None) or {}
        start = fields.Date.to_date(per['date_start'])
        # The run's NAME is written the way the screen writes it (the wizard
        # names runs "<scheme> · June 2026" in English, whoever runs it).
        label = month_label(start, 'en_US')
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
        people = (params.get('people') or {}).get('value') or {}
        if not isinstance(people, dict):            # a plan made before P3
            people = {'text': T(people)}
        statuses, said = self._statuses(ctx, people.get('text'))
        named = {'usual': statuses, 'outside': []}
        if people.get('employee_ids'):
            vals['employee_ids'] = [int(e) for e in people['employee_ids']]
            if statuses is not None:
                statuses, named['outside'] = self._named_outside(
                    ctx, vals['formula_config_id'], vals['employee_ids'],
                    people.get('names') or [], statuses)
        if statuses is not None:
            vals['statuses'] = statuses
        return vals, card, said, named

    def plan(self, ctx, params):
        W = ctx.env['pb.payrun.wizard']
        vals, card, said_statuses, named = self._vals(ctx, params)
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
        who = T(_lt('All %(n)s covered by this scheme')) % {'n': num(covered)}
        people_origin = 'said' if said_statuses else 'default'
        if said_statuses:
            who = T(_lt('%(n)s people · %(which)s')) % {'n': num(covered),
                                                       'which': said_statuses}
        if vals.get('employee_ids'):
            # P3-W1: "Vũ Khánh Chi (1 of 902)" — the named people out of all
            # the scheme covers, as the wizard's scheme card counts them.
            whole_vals = {k: v for k, v in vals.items() if k != 'employee_ids'}
            if named['usual'] is not None:
                # "of 152" counts with the usual ticks, not a leaver's status.
                whole_vals['statuses'] = named['usual']
            whole = W.scheme_preview(whole_vals) or {}
            names = (params['people'].get('value') or {}).get('names') or []
            who = T(_lt('%(names)s (%(n)s of %(all)s)')) % {
                'names': ', '.join(names) or params['people'].get('label') or '',
                'n': num(pv['total']),
                'all': num(whole.get('covered', covered))}
            people_origin = params['people'].get('origin') or 'said'
        slots.append(slot_row('people', _lt('People'), who, people_origin, True))
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
        for row in named['outside'][:MAX_CHIPS]:
            # P3 wf-5: a named leaver is in the run, and the card says so.
            left = fields.Date.to_date(row['left']) if row['left'] else None
            if left:
                text = T(_lt('%(name)s left on %(date)s (marked %(status)s). They are '
                             'in this run because you named them.')) % {
                    'name': row['name'], 'date': _day_label(left), 'status': row['status']}
            else:
                text = T(_lt('%(name)s is marked %(status)s, which a usual run leaves '
                             'out. They are in this run because you named them.')) % {
                    'name': row['name'], 'status': row['status']}
            notes.append(cards.note('warn', text))
        if pv.get('not_covered') == 1:
            notes.append(cards.note('info', _lt(
                '1 person in this company is not covered by this scheme and stays '
                'out of this run.')))
        elif pv.get('not_covered'):
            notes.append(cards.note('info', T(_lt(
                '%(n)s people in this company are not covered by this scheme and '
                'stay out of this run.')) % {'n': num(pv['not_covered'])}))
        if pv.get('adopt'):
            notes.append(cards.note('info', T(_lt(
                '%(n)s payslips already made for this month are taken into the '
                'run instead of being made again.')) % {'n': pv['adopt']}))
        can_do = bool(pv.get('total') or pv.get('adopt'))
        if not can_do:
            notes.append(cards.note('warn', _lt(
                'This scheme covers nobody yet, so the run would be empty. Open '
                'it in the screen to see who the scheme is mapped to.')))
        prefill = dict(vals)
        if named['outside']:
            # The screen takes the ticks, not the named list: the usual ones.
            prefill['statuses'] = named['usual']
        screen = screen_action(_lt('Open in the screen instead'), hub=PAY_HUB_RUN,
                               prefill=prefill,
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
            'month': month, 'scheme': scheme_name, 'n': num(pv['total'])}
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
            # P3-W2: no article before a month ("A October" was the walk's
            # finding) — the scheme leads the sentence instead.
            title=T(_lt('%(scheme)s already has a run for %(month)s')) % {
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
            {'value': num(int(summary.get('count') or 0)),
             'label': T(_lt('payslips in draft'))},
            {'value': money(summary.get('total_net'), extra.get('currency') or ''),
             'label': T(_lt('net to pay'))},
            {'value': num(need), 'label': T(_lt('need a look'))},
        ]
        actions = []
        door = run_door(ctx, run.id, _lt('Open the run'))
        if door:
            actions.append(door)
        actions.append({'id': 'followup', 'action': 'submit_run', 'slot': 'run',
                        'value': T(run.id), 'label': T(_lt('Send for approval')),
                        'style': 'outline', 'icon': 'send'})
        actions.append(learn_action('sc_payrun'))
        n = int(summary.get('count') or 0)
        if self._may_delete(ctx):
            undo = undo_block(self.undo_minutes, _lt('Undo'), T(_lt(
                'Not what you meant? Undo deletes the draft run and its %(n)s '
                'payslips.')) % {'n': num(n)})
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


_GLUE = ('for', 'of', 'in', 'the', 'payroll', 'run', 'from',
         # P4 — "cho Bán lẻ tháng 6", "của … trong tháng 6"
         'cho', 'cua', 'trong', 'vao', 'ky', 'luong', 'bang', 'dot')


def _month_words(text, rest_folded):
    """The words of `text` that `parse_period` read as the month (the ones
    `rest_folded` no longer has): "Retail End-Month for May 2031" → "May
    2031". Cut by spaces, never folded."""
    kept = rest_folded.split()
    out = []
    for w in text.split():
        f = fold(w)
        if f in kept:
            kept.remove(f)
        else:
            out.append(w)
    return ' '.join(out).strip()


def _without_month(text, rest_folded):
    """`text` with the month words `parse_period` took out (`rest_folded` is
    what it left), and the little words that only led into the month ("for
    June", "in 2026"). Cut by spaces, never folded: a person's name keeps its
    own spelling for the people slot (P3-W1)."""
    words = text.split()
    kept = rest_folded.split()
    out, gone = [], []
    for w in words:
        f = fold(w)
        if f in kept:
            kept.remove(f)
            out.append(w)
        else:
            gone.append(len(out))          # a month word stood here
    # drop the glue word right before each month word, then the ends
    for pos in sorted(set(gone), reverse=True):
        if 0 < pos <= len(out) and fold(out[pos - 1]) in _GLUE:
            del out[pos - 1]
    while out and fold(out[0]) in _GLUE:
        out.pop(0)
    while out and fold(out[-1]) in _GLUE:
        out.pop()
    return ' '.join(out).strip()


def _marked_words(text):
    """The words as written, marks kept, small letters ("Trần Văn Phong" →
    ['trần', 'văn', 'phong'])."""
    return re.findall(r'[^\W_]+', unicodedata.normalize('NFC', (text or '').lower()))


def _ref(task):
    try:
        return (json.loads(task.result_json or '{}').get('ref') or {})
    except (TypeError, ValueError):
        return {}


def _stamp(ctx):
    when = fields.Datetime.context_timestamp(ctx.env.user, fields.Datetime.now())
    return stamp(when)


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
    right_label = _lt('Payroll')
    phrases_vi = _vi_not_send_back('submit_run')
    phrases = (
        r'^(?:send\s+' + _NOT_SEND_BACK + r'|(?:submit|forward)\s+)'
        r'(?:the\s+)?(?P<run>.+?)\s+(?:for|to)\s+(?:approval|sign[- ]?off|approve)$',
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
                'n': num(int(row.get('employees') or 0)),
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
        actions.append(learn_action('sc_payrun'))
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
    phrases_vi = _vi_not_send_back('send_payslips')
    phrases = (
        # FIX-1 eighth pass: "Email the June payslips back to Mai to update"
        # is a send-back as much as "Send … back …" is (`_NOT_SEND_BACK` on
        # every verb), and no "back" stands before the payslips.
        r'^(?:send|email|e-mail|deliver|mail)\s+' + _NOT_SEND_BACK
        + _NO_BACK_BEFORE_SLIPS + _RETURN_WITH_REASON + r'(?:out\s+)?(?:the\s+)?'
        r'(?:(?P<run>.+?)\s+)?pay\s*slips?\b.*$',
    )

    def method_gate(self, env, user):
        if 'pb.pay.delivery' not in env:
            return False
        return bool(user._is_admin() or _has_any_group(user, PAY_GROUPS))

    def resolve_slot(self, ctx, slot, text):
        # P3-W4: payslips go out for approved runs only, so a draft is never
        # offered as a chip; none approved → "No approved run for <month>
        # yet" with the Runs board door.
        if slot.kind == 'run':
            return resolve_run(ctx, text, states=('done',))
        return super().resolve_slot(ctx, slot, text)

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
                 slot_row('people', _lt('People'), T(_lt('%s payslips')) % num(len(slips)),
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
        tiles = [{'value': num(int(out.get('sent') or 0)), 'label': T(_lt('sent'))},
                 {'value': num(int(out.get('failed') or 0)), 'label': T(_lt('failed'))},
                 {'value': num(int(out.get('skipped') or 0)), 'label': T(_lt('skipped'))}]
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
                return self._closest_fields(ctx, text, rows, emp, config_id)
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
                return resolved(amount, num(amount) if amount == int(amount)
                                else num(amount, 2), 'said')
            return resolved((text or '').strip(), (text or '').strip(), 'said')
        if slot.kind == 'day':
            day, origin, label = parse_day(ctx, text)
            if day is None:
                return missing(T(_lt('I could not read "%s" as a date.')) % (text or '')[:40])
            return resolved(fields.Date.to_string(day), label, origin)
        return super().resolve_slot(ctx, slot, text)

    def _records_door(self, emp_id, config_id):
        return screen_action(
            _lt('Open People › Records'), hub=RECORDS_HUB, door_id='peoplehub_records',
            context={'records_employee_ids': [emp_id] if emp_id else [],
                     'records_config_id': config_id})

    @staticmethod
    def _scheme_name(ctx, config_id):
        """The scheme's name as the person may read it, or '' (PA31)."""
        if not config_id or 'hr.formula.config' not in ctx.env:
            return ''
        try:
            cfg = ctx.env['hr.formula.config'].browse(int(config_id)).exists()
            if not cfg:
                return ''
            cfg.check_access('read')
            return cfg.display_name or ''
        except AccessError:
            return ''

    def _closest_fields(self, ctx, text, rows, emp_id, config_id):
        """P3-W3 — no pay value by that name on this person's scheme: never a
        dead end. The closest ones (by spelling, ≤ 6) as chips, each showing
        what the person has today, and the door to Records."""
        door = self._records_door(emp_id, config_id)
        if not rows:
            # P4-W2: say WHY in plain words, naming the scheme; the card keeps
            # the one Records door and the "What can you do?" chip.
            scheme = self._scheme_name(ctx, config_id)
            if scheme:
                text = T(_lt(
                    'Nothing on %s can be changed from here yet: Records has no pay '
                    'value on it that you may change. Open People › Records to see '
                    'what you can change.')) % scheme
            else:
                text = T(_lt(
                    "Nothing on this person's scheme can be changed from here yet: "
                    "Records has no pay value on it that you may change. Open People "
                    "› Records to see what you can change."))
            out = missing(text)
            out['actions'] = [door]
            out['door_id'] = 'peoplehub_records'
            return out
        said, words = fold(text), tokens(text)

        def closeness(row):
            shared = sum(1 for t in words if any(tok_match(t, w) for w in tokens(row['words'])))
            return (-shared, -difflib.SequenceMatcher(None, said, fold(row['label'])).ratio())
        ranked = sorted(rows, key=closeness)[:MAX_CHIPS]
        today = self._current_labels(ctx, config_id, emp_id, [r['value'] for r in ranked])
        cands = []
        for r in ranked:
            now = today.get(r['value'])
            # P3 wf-11: "not set" only when the value was READ and is empty; a
            # value that could not be read says nothing rather than something false.
            sub = '' if now is None else (T(_lt('now %s')) % now) if now else T(_lt('not set'))
            cands.append({'value': r['value'], 'label': r['label'], 'sublabel': sub})
        out = ambiguous(cands, note=T(_lt(
            'I could not find "%s" on this person\'s scheme. These are the closest '
            'pay values they have — pick one, or open Records.')) % (text or '')[:60])
        out['actions'] = [door]
        return out

    def _current_labels(self, ctx, config_id, emp_id, field_ids):
        """{card id: what Records shows for this person today}; a card whose
        value could not be read is left OUT (its chip then says nothing).

        P3 wf-11: read through the Records Desk's own page read
        (`search_people`, its own gate) so the chips and the screen agree;
        only if that page cannot be read, cell by cell as the person — one
        unreadable cell never blanks the others."""
        out = {}
        desk = self._desk(ctx)
        try:
            emp_id = int(emp_id or 0)
            page = desk.search_people(config_id, filters={'employee_ids': [emp_id]},
                                      field_ids=list(field_ids), limit=1,
                                      with_facets=False) or {}
            row = next((r for r in page.get('rows') or [] if r.get('id') == emp_id), None)
            if row is not None:
                values = row.get('values') or {}
                for fid in field_ids:
                    if fid in values:
                        out[fid] = (values[fid] or {}).get('label') or ''
                return out
        except Exception:                               # noqa: BLE001
            _logger.info("PayAI: the Records page could not be read", exc_info=True)
        try:
            cards_ = self._cards(ctx, config_id)
            emp = ctx.env['hr.employee'].browse(int(emp_id or 0)).exists()
            if not emp:
                return out
            probe = desk._probe(config_id)
            contract = probe._get_latest_contract(emp) or ctx.env['hr.contract']
        except Exception:                               # noqa: BLE001
            _logger.info("PayAI: could not read today's pay values", exc_info=True)
            return out
        for fid in field_ids:
            card = cards_.get(fid)
            if not card:
                continue
            try:
                out[fid] = (desk._read_cell(probe, card, emp, contract) or {}).get('label') or ''
            except Exception:                           # noqa: BLE001
                _logger.info("PayAI: could not read pay value %s", fid, exc_info=True)
        return out

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
            new_label = money(value, cur) if abs(value) >= 1e6 else '%s%s' % (cur, num(value))
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
                                                      'report', 'the', 'my', 'a',
                                                      # P4 — "tờ khai", "báo cáo", "hồ sơ"
                                                      'to', 'khai', 'bao', 'cao', 'ho', 'so')]
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
