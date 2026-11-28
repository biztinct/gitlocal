# -*- coding: utf-8 -*-
# Order matters: the vocabulary first, then the templates the case copies from,
# then the case itself, then everything that hangs off it, and the facade last
# because it reads all of them.
from . import pip_common
from . import pip_template
from . import pip_objective
from . import pip_case
from . import checkin_ext
from . import feedback_ext
from . import letter_ext
from . import resignation_ext
from . import res_users_ext
from . import pip_automation
from . import pb_pip
