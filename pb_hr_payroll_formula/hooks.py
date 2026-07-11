# -*- coding: utf-8 -*-
"""F113 — shared post-install certification helper for country pack modules.

A country pack (pb_pack_vn, pb_pack_sg, …) ships one or more
``hr.formula.config.template`` records plus its B4 legislation pack, then calls
``certify_pack_templates`` from its own ``post_init_hook``. The helper runs every
template's sample-test suite through the validated evaluator; any failure raises
and thereby BLOCKS the module install (design D113.3). This is the mechanical
meaning of "maintained": a pack proves itself on every install and every update.
"""
import logging

_logger = logging.getLogger(__name__)


def certify_pack_templates(env, template_xmlids):
    """Run certification for each template xmlid; raise (blocking install) on the
    first failure. ``env`` is a live Environment (Odoo passes it to post_init
    hooks in 17+; older signatures pass a cursor+registry — the pack wrapper
    normalises that)."""
    for xmlid in template_xmlids:
        template = env.ref(xmlid, raise_if_not_found=True)
        report = template.run_certification(raise_on_fail=True)
        _logger.info(
            "F113 certification PASSED for %s (%s): %d tests",
            template.code, xmlid, report.get('total', 0))
