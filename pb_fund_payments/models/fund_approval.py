# -*- coding: utf-8 -*-
"""The default route a fund payment travels — the payment release's.

Paying a fund is money leaving the company exactly as a salary transfer is,
so the default is the same two signatures the payment release ships with
(`pb_pay_delivery/models/approval_seed.py` `release_definition`): Finance
first, then the Country director — two steps, two different people. It is a
published choice from the moment it exists; the business changes it in the
Approval Matrix, never in code.

The catalogue row (`data/approval_process.xml`) is marked as money, so the one
Approvals inbox never offers a fund payment for "approve selected" (WDGAP QF1
`_can_bulk`; `biz.approval.process` refuses bulk_ok on a money process).
"""
import logging

from odoo import api, models

from odoo.addons.pb_pay_delivery.models.approval_seed import release_definition

from .fund_payment import FUNDPAY_PROCESS_KEY

_logger = logging.getLogger(__name__)

WORKFLOW_NAME = 'Fund and tax payments'
ROLES = ('finance', 'director')
BINDING_NOTE = ('The route every payment to a fund or tax office follows unless '
                'somebody publishes another one.')


def fund_definition():
    """The payment release's two signatures, verbatim."""
    return release_definition()


class PbFundPaymentSeed(models.Model):
    _inherit = 'pb.fund.payment'

    @api.model
    def _approval_seed_default(self, company):
        return self.env['biz.approval.seed'].lay(
            company, FUNDPAY_PROCESS_KEY, WORKFLOW_NAME, fund_definition(),
            binding_note=BINDING_NOTE, model_name='pb.fund.payment',
            role_keys=ROLES,
            reason='Set up when fund and tax payments were switched on')


class ResCompanyFundSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.fund.payment'].sudo()._approval_seed_default(company)
            except Exception:       # noqa: BLE001 — a company must still be made
                _logger.exception('pb_fund_payments: %s has no fund-payment route',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with env.cr.savepoint():
                if env['pb.fund.payment'].sudo()._approval_seed_default(company):
                    done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('pb_fund_payments: %s has no fund-payment route',
                              company.name)
    _logger.info('pb_fund_payments: %s fund-payment routes published', done)
    return done
