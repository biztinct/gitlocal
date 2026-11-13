# -*- coding: utf-8 -*-
import logging

from . import models
from . import controllers

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Land the seed demo drivers in the demo's OPERATING company.

    The demo drivers are created via data XML without a company, so they default
    to the install-time company (often "Your Company"). The manager cockpit is
    company-scoped, so a driver in a company the manager isn't viewing is
    invisible. We move the seed drivers (+ their users and route sims) to the
    company with the most employees — the real operating/demo company — with no
    hard-coded id or name. No-op on a fresh DB with no employees.
    """
    groups = env['hr.employee'].sudo().read_group(
        [('company_id', '!=', False)], ['company_id'], ['company_id'])
    if not groups:
        return
    top = max(groups, key=lambda g: g.get('company_id_count') or g.get('__count') or 0)
    company_id = top['company_id'][0] if top.get('company_id') else False
    if not company_id:
        return

    xmlids = (
        'pb_driver_checkin.demo_user_driver_hanoi',
        'pb_driver_checkin.demo_emp_driver_hanoi',
        'pb_driver_checkin.demo_user_driver_hcmc',
        'pb_driver_checkin.demo_emp_driver_hcmc',
        'pb_driver_checkin.route_sim_hanoi',
        'pb_driver_checkin.route_sim_hcmc',
    )
    for xmlid in xmlids:
        rec = env.ref(xmlid, raise_if_not_found=False)
        if not rec:
            continue
        try:
            if rec._name == 'res.users':
                rec.sudo().write({
                    'company_ids': [(4, company_id)],
                    'company_id': company_id,
                })
            else:
                rec.sudo().write({'company_id': company_id})
        except Exception as e:  # pragma: no cover - demo convenience only
            _logger.warning("pb_driver_checkin: could not set company on %s: %s", xmlid, e)
    _logger.info("pb_driver_checkin: seed drivers assigned to company %s", company_id)
