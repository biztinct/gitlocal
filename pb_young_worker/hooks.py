# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Seed the Vietnam Labor Code young-worker defaults on install.

The caps ARE data (VN_BANDS in models/young_worker_rule.py), but a static XML
record can't reliably target the right company: the live demo runs under
'Payobook Vietnam JSC', which is not base.main_company. So we seed a rule for
every company that lacks one — the records are ordinary config, editable and
deactivatable per company by a payroll manager. Under-18 gates only fire where
a band matches, so seeding a non-VN company is harmless (and its HR can simply
deactivate the rule). Companies created AFTER install are seeded by the
res.company create override (models/res_company.py).
"""

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    companies = env['res.company'].sudo().with_context(active_test=False).search([])
    seeded = env['pb.young.worker.rule']._seed_vn_defaults(companies)
    _logger.info("pb_young_worker: seeded VN young-worker rules for %s company(ies)",
                 len(seeded))
