# -*- coding: utf-8 -*-
"""Take the retired cockpit's own records out, and nothing else.

The module stays installable and installed — its client-action tag is what old
sidebar rows and bookmarks point at. What has to go is the machinery it no
longer ships: the `pb.approval` facade's model row and its access rules, which
would otherwise sit in the registry naming a Python class that does not exist.

Deliberately does NOT uninstall anything, and does not touch the sidebar rows:
those still resolve, through the redirect this module now is.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'pb_approval' AND model IN ('ir.ui.view', 'ir.model.access')
    """)
    cr.execute("DELETE FROM ir_model WHERE model = 'pb.approval'")
    _logger.info('pb_approval: the pay-run approval cockpit is retired')
