# -*- coding: utf-8 -*-
"""WDGAP IDB1-F — the payment list's full-read rule, on an upgrade.

`security/money_out_rules.xml` is `noupdate="1"`, so an upgrade does not
rewrite a rule it created before. IDB2 (19.0.1.8.0) shipped
`rule_payment_list_file_payroll` as "payroll manager only, everything", which
refused a payroll officer with administrator rights — somebody the bank file
lets prepare and download (ledger IDB1M-2). This writes the rule exactly as
the XML now declares it: the bank file's own groups (payroll officer and
payroll manager), everything only for those who also pass the bank file's
download gate, otherwise only the lists they were asked to decide.

Idempotent; touches nothing but this one rule.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

RULE_XMLID = 'pb_pay_delivery.rule_payment_list_file_payroll'
NAME = 'Payment list: payroll people who may download the bank file'
DOMAIN = ("[(1, '=', 1)] if user.env['pb.money.approval.mixin']._pay_groups_held(user) "
          "else [('seat_user_ids', 'in', [user.id])]")


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref(RULE_XMLID, raise_if_not_found=False)
    if not rule:
        _logger.warning('pb_pay_delivery: %s not found, nothing rewritten', RULE_XMLID)
        return
    groups = (env.ref('om_hr_payroll.group_hr_payroll_user')
              | env.ref('om_hr_payroll.group_hr_payroll_manager'))
    rule.write({
        'name': NAME,
        'groups': [(6, 0, groups.ids)],
        'domain_force': DOMAIN,
        'perm_read': True, 'perm_write': True,
        'perm_create': True, 'perm_unlink': True,
        'active': True,
    })
    _logger.info('pb_pay_delivery: payment list rule %s rewritten (IDB1-F)', rule.id)
