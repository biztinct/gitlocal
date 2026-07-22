# Part of Payobook. See LICENSE file for full copyright and licensing details.

from . import models


def _add_finance_reviewer_groups(env):
    """Graft the finance groups onto the reviewer record rules.

    account.* can't be hard-referenced in the security XML (account is not a
    dependency of this module) — without this, a pure-finance approver (no
    payroll group) falls under the own-only rule and cannot even READ the
    request they must approve. Same fallback doctrine as the tier resolution.
    """
    for rule_xmlid in ('pb_bank_ocr.bcr_rule_reviewers_all',
                       'pb_bank_ocr.bank_hist_rule_reviewers_all'):
        rule = env.ref(rule_xmlid, raise_if_not_found=False)
        if not rule:
            continue
        for group_xmlid in ('account.group_account_invoice',
                            'account.group_account_user'):
            group = env.ref(group_xmlid, raise_if_not_found=False)
            if group:
                rule.groups = [(4, group.id)]
