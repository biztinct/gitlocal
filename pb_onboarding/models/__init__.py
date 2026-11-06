# -*- coding: utf-8 -*-
# Order matters only where one module's class is referenced at import time;
# these are all independent, so the order is the reading order: the settings
# tables first, the people, then the machinery, then the cockpit facade.
from . import onboarding_common
from . import hrbp_rule
from . import orientation_batch
from . import hr_employee
from . import newhire_pulse
from . import buddy_nomination
from . import journey_ext
from . import journey_case_ext
from . import onboarding_automation
from . import zoho_pipeline_ext
from . import pb_onboarding
