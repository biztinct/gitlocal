# -*- coding: utf-8 -*-
"""LEARN REFRESH step 6: lay the walkthrough examples on the apex demo
database (pay-run route with demo seats, an open pay review, a settlement
waiting to be checked). A no-op anywhere else; idempotent."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['pb.demo.generator'].ensure_walkthrough_world()
