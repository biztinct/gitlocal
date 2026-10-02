# -*- coding: utf-8 -*-
"""Two decisions a business makes once, and payroll obeys every month.

Both are per COMPANY rather than per scheme: "what counts as the hours we pay
for" is a statement about the business, and a company that ran two schemes with
two different answers to it would have two different truths about the same
week.

The default is ON, and that is only safe because no payroll is live yet (the
clean-replacement rule in the ledger). On a database where pay had already run
from live overtime, flipping this on silently would change what people are paid;
the migration therefore never flips it for an existing company — see
``migrations``.
"""

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    pb_timesheet_payroll = fields.Boolean(
        string='Payroll reads approved timesheets',
        default=True,
        help="Hours, worked days and overtime come from weeks that have been "
             "approved, instead of from whatever is recorded at the moment the "
             "pay run happens.")
    pb_timesheet_block_run = fields.Boolean(
        string='Block the run until every week is approved',
        default=False,
        help="Off by default: an unapproved week is a note on the pay run, not "
             "a refusal. Turn it on where nobody may be paid on hours that "
             "have not been signed off.")


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pb_timesheet_payroll = fields.Boolean(
        related='company_id.pb_timesheet_payroll', readonly=False)
    pb_timesheet_block_run = fields.Boolean(
        related='company_id.pb_timesheet_block_run', readonly=False)
