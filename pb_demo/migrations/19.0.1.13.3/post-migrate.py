# -*- coding: utf-8 -*-
"""Copy the demo employees' bank and account number into the Vietnam bank
fields Pay & Deliver reads (payobook run 1524 showed "Total net ₫0"). Adds
only; a no-op where there are no demo employees; idempotent."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['pb.demo.generator'].ensure_demo_bank_details()
