# -*- coding: utf-8 -*-
# Order matters in two places and nowhere else: `training_common` is imported
# by everything, and `pb_training_assignments` extends the facade declared in
# `pb_training` (it imports the class to widen `_VERBS` rather than restate it).
from . import training_common
from . import slide_channel_ext
from . import survey_user_ext
from . import pb_my_training
from . import pb_training

# ---------------------------------------------------------------- E2
from . import schedule
from . import assignment
from . import delay
from . import delay_approval
from . import probation_link
from . import journey_ext
from . import automation
from . import pb_training_assignments
from . import pb_my_training_due

# ---------------------------------------------------------------- E3
# Same rule: `pb_training_claims` widens the tuple `pb_training_assignments`
# widened, so it is imported after it; `certificate` extends the assignment
# declared above it; `claim_approval` extends the claim.
from . import allowance
from . import claim
from . import claim_approval
from . import incentive_ext
from . import certificate
from . import analytics
from . import pack
from . import pb_training_claims
from . import pb_my_training_claims
