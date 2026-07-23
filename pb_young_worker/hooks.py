# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Seed the Vietnam Labor Code young-worker defaults on install.

The caps ARE data (below), but a static XML record can't reliably target the
right company: the live demo runs under 'Payobook Vietnam JSC', which is not
base.main_company. So we seed a rule for every company that lacks one — the
records are ordinary config, editable and deactivatable per company by a payroll
manager. Under-18 gates only fire where a band matches, so seeding a non-VN
company is harmless (and its HR can simply deactivate the rule).
"""

import logging

_logger = logging.getLogger(__name__)

# Vietnam Labor Code (Arts. 143–147): under-15 and 15-to-under-18 protections.
VN_BANDS = [
    {'age_min': 0, 'age_max': 15, 'max_hours_day': 4.0, 'max_hours_week': 20.0,
     'ot_blocked': True, 'night_blocked': True, 'note': 'Under 15'},
    {'age_min': 15, 'age_max': 18, 'max_hours_day': 8.0, 'max_hours_week': 40.0,
     'ot_blocked': True, 'night_blocked': True, 'note': '15 to under 18'},
]


def post_init_hook(env):
    Rule = env['pb.young.worker.rule'].sudo()
    companies = env['res.company'].sudo().with_context(active_test=False).search([])
    seeded = 0
    for co in companies:
        if Rule.search_count([('company_id', '=', co.id)]):
            continue
        Rule.create({
            'name': 'Young Worker Rules (VN)',
            'company_id': co.id,
            'night_from': 22.0,
            'night_to': 6.0,
            'band_ids': [(0, 0, dict(b)) for b in VN_BANDS],
        })
        seeded += 1
    _logger.info("pb_young_worker: seeded VN young-worker rules for %s company(ies)", seeded)
