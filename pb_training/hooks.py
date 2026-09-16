# -*- coding: utf-8 -*-
"""Install-time setup: the switches, and the white-label sweep.

`post_init_hook` fires on INSTALL ONLY — never on `-u`, a known Odoo 19 trap —
which is exactly right for both jobs here. The switches want their shipped
value once and never again (an upgrade that re-set them would undo whatever
the company had chosen), and the sweep is about the rows the two engines seed
at install time. Neither is ever fatal: a module that refuses to install
because a demo course could not be renamed is a worse outcome than a demo
course somebody renames a minute later.

WHAT THE SWEEP TOUCHES, AND WHY EACH ONE IS NOT ALREADY COVERED
---------------------------------------------------------------
The global seams cover a great deal and the sweep deliberately does not
duplicate them. `biz_debrand` rewrites every SERVER-RENDERED QWeb template at
`ir.ui.view._get_view_etrees`, so the survey pages, the certification report
and the course pages are already clean by the time a learner sees them; and
its `_()` patch covers every Python string in both engines. What neither
reaches is a value stored in a ROW:

  1. `mail.template` (subject, body, sender). The content engine ships a
     "Powered by <vendor>" footer on its course mails and the test engine
     ships four templates of its own. These are rendered from a RECORD and
     never from a view, so the tree seam never sees them. `biz_mail_debrand`
     already owns exactly this job — it scrubs every template in every
     language — but it only runs when IT is installed or upgraded, and
     installing two new modules that seed eight new templates is neither. So
     the sweep calls its own idempotent entry point rather than writing a
     second scrubber that would drift from it.
  2. `survey.survey` titles and descriptions, and `slide.channel` names. Both
     engines seed demo records on a database that has demo data, and this one
     does. A row a demo seeded is not a row a customer typed, so rewriting it
     is right — the rule the seams draw between source text and customer text
     puts seeded demo content on the source side.
  3. The stock demo courses' VISIBILITY. Four of the seven ship
     `visibility = 'public'`, which on this build means the whole internet can
     read them at `/slides`. The gate in `slides_gate.py` closes the door; this
     closes the window beside it, so turning the gate off for a week does not
     silently republish seven courses to the public.

Everything the sweep changes is logged by name, because a hook that quietly
rewrites eleven rows on somebody else's data is a hook nobody can audit.
"""

import logging

from .models.training_common import DEFAULTS

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _seed_switches(env)
    _sweep_mail_templates(env)
    _sweep_rows(env)
    _close_the_public_courses(env)


def _seed_switches(env):
    """Materialise the shipped defaults so an administrator can see them.

    Every reader still goes through `flag()`/`number()`, which fall back to the
    same table in code — so a database where these rows are missing behaves
    identically. They exist to be FOUND.
    """
    icp = env['ir.config_parameter'].sudo()
    for key, value in DEFAULTS.items():
        if icp.get_param(key) is False or icp.get_param(key) is None:
            icp.set_param(key, value)


def _sweep_mail_templates(env):
    """Hand the new templates to the seam that already owns this job."""
    try:
        env['res.config.settings'].sudo()._biz_mail_debrand_apply()
        _logger.info('pb_training: outgoing-mail templates re-scrubbed')
    except Exception:                   # noqa: BLE001 — never fail an install
        _logger.warning('pb_training: the mail templates could not be '
                        're-scrubbed; check biz_mail_debrand', exc_info=True)


def _brand(env):
    """(brand, website, product) from the debranding layer, or None."""
    try:
        from odoo.addons.biz_debrand.models.brand import source_brand
        return source_brand(env)
    except Exception:                   # noqa: BLE001 — optional dependency
        return None


def _sweep_rows(env):
    """Rewrite the vendor name out of seeded course and test titles."""
    brand = _brand(env)
    if not brand:
        _logger.info('pb_training: no debranding layer on this database — '
                     'seeded titles left alone')
        return
    from odoo.addons.biz_debrand.models.brand import debrand_text
    name, website, product = brand
    touched = []
    for model, fields in (('slide.channel', ('name', 'description_short')),
                          ('survey.survey', ('title', 'description'))):
        try:
            records = env[model].sudo().with_context(
                active_test=False).search([])
        except Exception:               # noqa: BLE001
            continue
        for record in records:
            vals = {}
            for field in fields:
                value = record[field]
                if not value or not isinstance(value, str):
                    continue
                clean = debrand_text(value, name, website, product)
                if clean != value:
                    vals[field] = clean
            if vals:
                try:
                    record.write(vals)
                    touched.append('%s,%s' % (model, record.id))
                except Exception:       # noqa: BLE001
                    _logger.warning('pb_training: %s %s could not be '
                                    'renamed', model, record.id,
                                    exc_info=True)
    _logger.info('pb_training: %s seeded title(s) debranded%s', len(touched),
                 (': %s' % ', '.join(touched)) if touched else '')


def _close_the_public_courses(env):
    """A demo course is not a reason to publish a course to the internet."""
    try:
        public = env['slide.channel'].sudo().with_context(
            active_test=False).search([('visibility', '=', 'public')])
    except Exception:                   # noqa: BLE001
        return
    if not public:
        return
    names = public.mapped('name')
    try:
        public.write({'visibility': 'connected'})
    except Exception:                   # noqa: BLE001
        _logger.warning('pb_training: the public courses could not be '
                        'closed', exc_info=True)
        return
    _logger.info('pb_training: %s course(s) moved from public to signed-in '
                 'only: %s', len(public), ', '.join(names))
