# -*- coding: utf-8 -*-
"""FS-9 follow-on B (demo world only): a demo person's bank account takes the
Vietnamese bank file's number where the two differ, so the side panel stops
showing two numbers. Guards and direction: `ensure_demo_bank_accounts_agree`
(pb_demo is on the demo site only; `is_demo` rows only; nothing deleted, no
approval, no mail). Idempotent: a second run changes nothing."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['pb.demo.generator'].ensure_demo_bank_accounts_agree()
