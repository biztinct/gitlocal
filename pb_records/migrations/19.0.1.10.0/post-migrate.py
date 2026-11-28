# -*- coding: utf-8 -*-
"""UPDATES P3a — lay the bank-details route ("a second person") for every
company that does not have one yet. Idempotent: `lay` leaves a company that
already has a published route alone, so an edited route is never
overwritten."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Apply = env['pb.records.apply']
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            with cr.savepoint():
                if Apply._approval_seed_bank(company):
                    done += 1
        except Exception:   # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_records: %s has no bank-details route yet',
                              company.name)
    _logger.info('pb_records: %s companies have a bank-details route', done)
