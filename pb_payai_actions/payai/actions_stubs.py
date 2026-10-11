# -*- coding: utf-8 -*-
"""AMBER / RED ACTIONS — declared now, built in P2 (prepare) and P3 (decide).

Each one is a full catalogue entry (tier, screen, right, door, phrasings) so
the gate, the refusals, "What can you do?" and the audit already know about
it. `execute` is not built: a sentence that names one gets the honest answer
("I cannot do that for you yet") with the screen's door — or, when the
person lacks the right, the ordinary refusal. Stubs are never offered to the
model as tools (registry.OFFERED_TIERS).
"""
from odoo.tools.translate import LazyTranslate

from .registry import Action, Slot, payai_action

_lt = LazyTranslate(__name__)

PAY_SCREEN = ('pb_payhub.item_pay_run',)
HOME_SCREEN = ('pb_home_hub.item_home',)
COMPLIANCE_SCREEN = ('pb_compliance_hub.item_compliance',)


class _Stub(Action):
    stub = True
    priority = 20

    def execute(self, ctx, params):
        raise NotImplementedError(self.key)


def _runner(env, user):
    Wizard = env['pb.payrun.wizard']
    return bool(Wizard._may_run_payroll(user)) if hasattr(Wizard, '_may_run_payroll') \
        else env['hr.payslip.run'].with_user(user).has_access('create')


def _approver(env, user):
    # Deciding is a seat on a route, asked per request in P3. The screen-level
    # question is whether the person can read approval requests at all.
    if 'biz.approval.request' not in env:
        return False
    return bool(env['biz.approval.request'].with_user(user).has_access('read'))


@payai_action
class RunPayroll(_Stub):
    key = 'run_payroll'
    title = _lt('Run payroll')
    tier = 'prepare'
    summary = _lt('Prepare a draft pay run for a month and scheme.')
    examples = (_lt('Run June payroll for Retail'),)
    slots = (Slot('period', _lt('Period'), 'period', False),
             Slot('scheme', _lt('Scheme'), 'scheme', False))
    screen_keys = PAY_SCREEN
    door_id = 'payhub_run'
    right_subject = _lt('Running payroll')
    right_label = _lt('Run payroll')
    soon_text = _lt('I cannot run payroll for you yet — that arrives in the next '
                    'release. Here is the screen.')
    phrases = (
        r'^(?:run|process|calculate|compute|start|prepare|do)\s+(?:the\s+)?'
        r'(?P<period>[^.]*?)\s*payroll\b(?:\s+(?:for|of)\s+(?P<scheme>.+))?$',
        r'^(?:run|process|start|prepare|create|make)\s+(?:a\s+|the\s+)?(?:new\s+)?'
        r'pay\s*run\b(?:\s+(?:for|of)\s+(?P<scheme>.+))?$',
    )

    def method_gate(self, env, user):
        return _runner(env, user)


@payai_action
class SubmitRun(_Stub):
    key = 'submit_run'
    title = _lt('Send a pay run for approval')
    tier = 'prepare'
    summary = _lt('Send a draft pay run to its approvers.')
    examples = (_lt('Send the June run for approval'),)
    slots = (Slot('run', _lt('Pay run'), 'run'),)
    screen_keys = PAY_SCREEN
    door_id = 'payhub_runs'
    right_subject = _lt('Sending a pay run for approval')
    right_label = _lt('Pay Run')
    soon_text = _lt('I cannot send a run for approval for you yet — that arrives '
                    'in the next release. Here is the Runs board.')
    phrases = (
        r'^(?:send|submit|forward)\s+(?:the\s+)?(?P<run>.+?)\s+(?:for|to)\s+'
        r'(?:approval|sign[- ]?off|approve)$',
        r'^submit\s+(?:the\s+)?(?P<run>.*\b(?:run|payroll)s?\b.*)$',
    )

    def method_gate(self, env, user):
        return env['hr.payslip.run'].with_user(user).has_access('write')


@payai_action
class UpdatePayData(_Stub):
    key = 'update_pay_data'
    title = _lt('Change a pay value')
    tier = 'prepare'
    summary = _lt("Change one person's pay value through the normal approval route.")
    examples = (_lt('Give Linh an allowance of 500,000 from July'),)
    slots = (Slot('person', _lt('Person'), 'person'),)
    screen_keys = PAY_SCREEN
    door_id = 'peoplehub_records'
    right_subject = _lt('Changing pay values')
    right_label = _lt('Records')
    soon_text = _lt('I cannot change pay values for you yet — that arrives in the '
                    'next release. Here is the screen where you can.')
    phrases = (
        r'^(?=.*\b(?:allowance|salary|bonus|wage|deduction|overtime|pay\s+value|'
        r'pay\s+rate|rate)\b)(?:give|set|change|update|raise|increase|lower|'
        r'reduce|add|put)\s+(?P<person>.+)$',
    )

    def method_gate(self, env, user):
        if 'pb.records.change' in env and \
                env['pb.records.change'].with_user(user).has_access('create'):
            return True
        return env['hr.payslip.run'].with_user(user).has_access('write')


@payai_action
class SendPayslips(_Stub):
    key = 'send_payslips'
    title = _lt('Send payslips')
    tier = 'prepare'
    summary = _lt("Email an approved run's payslips to its people.")
    examples = (_lt('Send the June payslips'),)
    slots = (Slot('run', _lt('Pay run'), 'run'),)
    screen_keys = PAY_SCREEN
    door_id = 'payhub_deliver'
    right_subject = _lt('Sending payslips')
    right_label = _lt('Pay & Deliver')
    soon_text = _lt('I cannot send payslips for you yet — that arrives in the next '
                    'release. Here is Pay & Deliver.')
    phrases = (
        r'^(?:send|email|e-mail|deliver|mail)\s+(?:out\s+)?(?:the\s+)?'
        r'(?:(?P<run>.+?)\s+)?pay\s*slips?\b.*$',
    )

    def method_gate(self, env, user):
        return env['hr.payslip.run'].with_user(user).has_access('write')


@payai_action
class FilingPrepare(_Stub):
    key = 'filing_prepare'
    title = _lt('Prepare a government filing')
    tier = 'prepare'
    summary = _lt('Prepare a tax or social insurance filing for a period.')
    examples = (_lt('Prepare the June tax filing'),)
    slots = (Slot('period', _lt('Period'), 'period', False),)
    screen_keys = COMPLIANCE_SCREEN
    door_id = 'cmphub_filings'
    right_subject = _lt('Preparing filings')
    right_label = _lt('Compliance')
    soon_text = _lt('I cannot prepare filings for you yet — that arrives in the '
                    'next release. Here is Government filings.')
    phrases = (
        r'^(?:prepare|file|generate|make|create|do|submit)\s+(?:the\s+|a\s+|my\s+)?'
        r'(?P<period>.*?)\s*(?:tax|pit|social\s+insurance|si|insurance|government)?\s*'
        r'(?:filing|return|declaration)s?\b.*$',
    )

    def method_gate(self, env, user):
        return env['hr.payslip'].with_user(user).has_access('read')


class _Decide(_Stub):
    tier = 'decide'
    screen_keys = HOME_SCREEN
    door_id = 'homehub_approvals'
    right_label = _lt('Approvals')
    soon_text = _lt('I cannot record approval decisions for you yet — that arrives '
                    'in a later release. Here are your approvals.')
    slots = (Slot('item', _lt('What'), 'run'),)

    def method_gate(self, env, user):
        return _approver(env, user)


@payai_action
class ApproveItem(_Decide):
    key = 'approve_item'
    title = _lt('Approve something waiting for you')
    summary = _lt('Approve a request that is waiting for your decision.')
    examples = (_lt('Approve the June Retail run'),)
    right_subject = _lt('Approving')
    phrases = (r'^approve\s+(?P<item>.+)$',)


@payai_action
class SendBack(_Decide):
    key = 'send_back'
    title = _lt('Send something back')
    summary = _lt('Send a request back to whoever prepared it, with a reason.')
    examples = (_lt('Send the June run back'),)
    right_subject = _lt('Sending back')
    phrases = (r'^send\s+back\s+(?P<item>.+)$',
               r'^send\s+(?P<item>.+?)\s+back(?:\s+.*)?$',
               r'^return\s+(?P<item>.+?)\s+to\s+.+$')


@payai_action
class RejectItem(_Decide):
    key = 'reject_item'
    title = _lt('Reject something')
    summary = _lt('Reject a request that is waiting for your decision.')
    examples = (_lt('Reject the May bonus run'),)
    right_subject = _lt('Rejecting')
    phrases = (r'^(?:reject|decline|refuse)\s+(?P<item>.+)$',)


@payai_action
class NeverThroughPayAI(_Stub):
    """Destructive asks. Never through PayAI, whatever the right."""
    key = 'never_destructive'
    title = _lt('Delete or clear records')
    tier = 'never'
    priority = 15
    summary = _lt('Deleting pay runs or payslips is never done through PayAI.')
    examples = (_lt('Delete the May run'),)
    door_id = 'payhub_runs'
    phrases = (
        r'^(?=.*\b(?:runs?|pay\s*runs?|payslips?|payroll|records?|employees?|'
        r'contracts?|batch(?:es)?)\b)'
        r'(?:delete|remove|erase|wipe|purge|destroy|drop|clean\s+and\s+run)\s+'
        r'(?:out\s+)?(?:all\s+)?(?:the\s+)?(?P<what>.+)$',
    )
