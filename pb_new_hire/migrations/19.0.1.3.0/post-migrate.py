# -*- coding: utf-8 -*-
"""NEWHIRE P3b: the shipped paper rows are `noupdate`, so a database that
installed P3a keeps the four certificate rows without a label and shows the
vault's own category name ("Degree / Certificate"). Give them the plain
label the data file now ships — only where the row still has no label (a
label someone typed is never overwritten)."""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

LABELS = {
    'paper_vn_cert': 'Highest certificate',
    'paper_in_cert': 'Highest certificate',
    'paper_sg_cert': 'Highest certificate',
    'paper_my_cert': 'Highest certificate',
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    done = 0
    for xmlid, label in LABELS.items():
        row = env.ref('pb_new_hire.%s' % xmlid, raise_if_not_found=False)
        if row and not row.label:
            row.label = label
            done += 1
    _logger.info('pb_new_hire: %s paper row(s) got their plain label', done)
