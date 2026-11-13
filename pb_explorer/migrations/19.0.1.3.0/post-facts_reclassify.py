# -*- coding: utf-8 -*-
"""The derived fact tables were built under the OLD classification.

VALUEKIND P4 changed what a fact row's `category_type` MEANS: it now comes from
the scheme's own pay role (`hr_payslip_line.pay_role`) rather than from
`hr_salary_rule_category.category_type`, and each row now records whether it is
a roll-up already counted inside another component. Every row built before this
upgrade predates both, so leaving them in place would report the old numbers
from a table that looks perfectly fresh — `_token()` fingerprints the PAYSLIPS,
and no payslip changed.

Flagging beats rebuilding here. A rebuild of every run inside an upgrade is
minutes of work nobody asked for, and `ensure_fresh` rebuilds a run on the next
read anyway; `dirty` is exactly the signal it exists to honour.

THIS MIGRATION LIVES IN pb_explorer ON PURPOSE. The first attempt put it in
pb_hr_payroll_formula's own migration, guarded by `'pb.fact.builder' in env` —
and that guard was False, because module load order runs that migration before
pb_explorer's models are in the registry. The flag was never set, the upgrade
logged nothing, and the Explorer went on answering with the old numbers. A
module's derived data is that module's own migration to run (C18.125).
"""
import logging

from odoo.tools.sql import table_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not table_exists(cr, 'pb_fact_run'):
        return
    cr.execute("UPDATE pb_fact_run SET dirty = TRUE WHERE dirty IS NOT TRUE")
    _logger.info(
        "pb_explorer: %s run(s) of analytics facts flagged for rebuild — pay "
        "roles and roll-ups are now read from the scheme, so every row built "
        "before this upgrade is stale by construction.", cr.rowcount)
