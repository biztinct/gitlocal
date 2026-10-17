# -*- coding: utf-8 -*-
"""The advert's route — RETIRED in RECRUIT P3 (G-17, RC-D5).

A job description is no longer signed off: it is shared with the manager for
input and made final by the recruiter (`jd.py`). Nothing is registered with
the approval engine for `pb.hiring.jd` any more, so the shim is dormant for
it, and the 19.0.2.2.0 migration closes the catalogue row's bindings and
withdraws any advert still waiting in somebody's inbox.

The file stays so the install hook and the old migrations that import
`seed_all` keep importing something; it lays nothing.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

JD_PROCESS_KEY = 'hiring_jd'


class PbHiringJdApproval(models.Model):
    _inherit = 'pb.hiring.jd'

    # Not connected to any catalogue row: the Approval Matrix shows the
    # retired row as covered by the hiring request (set by the migration).
    _approval_process_key = None


def seed_all(env):
    """Retired: a job description has no route to lay."""
    return 0
