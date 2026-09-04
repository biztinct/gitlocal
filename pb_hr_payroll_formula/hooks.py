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
    """Run certification for each template xmlid; raise (blocking install) on
    the first failure. Prefer :func:`certify_module_templates` in pack hooks —
    it discovers the module's own templates and can't be pasted wrong."""
    for xmlid in template_xmlids:
        template = env.ref(xmlid, raise_if_not_found=True)
        report = template.run_certification(raise_on_fail=True)
        _logger.info(
            "F113 certification PASSED for %s (%s): %d tests",
            template.code, xmlid, report.get('total', 0))


def certify_module_templates(env, module_name):
    """Certify every hr.formula.config.template record OWNED by ``module_name``
    (via ir.model.data), raising on the first failure. Pack hooks call this
    with their own package name, so a copy-pasted pack module can never
    silently certify another country's template — a pack with zero template
    records is itself an install-blocking error (the paste-without-edit case)."""
    imd = env['ir.model.data'].sudo().search([
        ('module', '=', module_name),
        ('model', '=', 'hr.formula.config.template'),
    ])
    if not imd:
        raise ValueError(
            "F113: module %r ships no hr.formula.config.template record — "
            "nothing to certify. Check the pack's data files." % module_name)
    templates = env['hr.formula.config.template'].browse(imd.mapped('res_id'))
    for template in templates:
        report = template.run_certification(raise_on_fail=True)
        _logger.info(
            "F113 certification PASSED for %s (module %s): %d tests",
            template.code, module_name, report.get('total', 0))


def rd49_schedule_monthly_fetch(env):
    """Make sure the scheduled-fetch DISPATCHER ticks (SC-2: hourly).

    The per-connector cadence lives on the connectors themselves; this only
    guarantees the dispatcher record has an hourly interval and a `nextcall`
    that is not stuck in the past. In a hook and not in the data file because
    `ir.cron.nextcall` is required and an eval expression there fails the
    whole module load when anything about it is wrong — the `numbercall`
    incident, which aborted every module in the same upgrade.
    """
    env['hr.integration.connector']._rd49_schedule_first_run()
