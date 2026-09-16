# Part of Payobook. See LICENSE file for full copyright and licensing details.
from . import pb_timeoff
from . import hr_leave_approval
# AFTER the approval adapter on purpose. Both classes override `hr.leave
# .create`; the last one loaded sits FIRST in the MRO, so the backdating
# refusal is asked before the route is asked to carry anything. It would be
# safe either way — the refusal raises before `super()` is reached in one
# order and from inside it in the other, and neither reaches the submit — but
# "safe either way" is a thing to write down rather than a thing to rely on.
from . import leave_rules
from . import pb_holidays
from . import carry_watch
