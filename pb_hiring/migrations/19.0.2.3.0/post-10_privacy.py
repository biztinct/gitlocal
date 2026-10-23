# -*- coding: utf-8 -*-
"""RECRUIT P4 — private until shared.

1. The nightly anonymise leg ships OFF on every database
   (`pb_hiring.retention_enabled` = '0', written explicitly so the setting is
   visible and the head of hiring switches it on after reading the preview).
2. Every candidate gets the date their application is kept until (the new
   stored `pb_retention_until`). The ORM fills a new stored computed column
   on the upgrade that adds it; this recomputes once more, after the data
   files, so the per-market rules and the company's months are both in.

Nothing is shared by this migration: a candidate is private to the hiring
team until a recruiter shares them, and a role's default only applies to
candidates who arrive from now on (RECRUIT P4, test 6).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

KEY = 'pb_hiring.retention_enabled'


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT id FROM ir_config_parameter WHERE key = %s", (KEY,))
    row = cr.fetchone()
    if row:
        cr.execute("UPDATE ir_config_parameter SET value = '0' WHERE id = %s", (row[0],))
    else:
        cr.execute("INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, "
                   "create_date, write_date) VALUES (%s, '0', 1, 1, "
                   "now() at time zone 'utc', now() at time zone 'utc')", (KEY,))
    env = api.Environment(cr, SUPERUSER_ID, {})
    Applicant = env['hr.applicant'].with_context(active_test=False)
    apps = Applicant.search([])
    env.add_to_compute(Applicant._fields['pb_retention_until'], apps)
    apps._recompute_recordset(['pb_retention_until'])
    _logger.info('pb_hiring 2.3.0: clean-up switched off; %s candidates have a '
                 'kept-until date', len(apps))
