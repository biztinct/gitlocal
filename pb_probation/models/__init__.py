# -*- coding: utf-8 -*-
# Order matters: the policy and the training tables are read by the review, the
# review is extended by the automation, and the facade reads all of them.
from . import probation_common
from . import probation_policy
from . import training
from . import hr_employee
from . import probation_review
from . import feedback_ext
from . import journey_case_ext
from . import buddy_ext
from . import probation_automation
from . import pb_probation
