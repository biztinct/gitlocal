# Part of Payobook. See LICENSE file for full copyright and licensing details.
# The audit glue (adds biz.audit.mixin to hr models) has no ordering constraint
# among these — the base models are core, the mixin lives in the dependency.
from . import hr_employee_audit
from . import hr_contract_audit
from . import hr_version_audit
from . import employee_document
from . import employee_timeline
from . import pb_people_360
