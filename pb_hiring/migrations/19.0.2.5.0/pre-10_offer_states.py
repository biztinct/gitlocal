# -*- coding: utf-8 -*-
"""RECRUIT P6 — `closed` is now `joined` (ruling R8: signed is not joined).

Before the module's code loads, so the new selection never meets a value it
does not know. The old `closed` meant exactly what `joined` means now: the
closure had made the employee, the contract and the checklist.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("UPDATE pb_hiring_offer SET state = 'joined' WHERE state = 'closed'")
    _logger.info('pb_hiring P6: %s closed offers are now "They have joined"', cr.rowcount)
