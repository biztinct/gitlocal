# -*- coding: utf-8 -*-
# ORDER MATTERS, and only in one place: `goal_set.py` declares the model the
# adapter in `goal_set_approval.py` inherits, so the plain model comes first.
# Everything else is independent and is listed in the order somebody reads it:
# the year, the sheet, the goal, the number on it, the template, then the two
# facades and the machinery around them.
#
# B2 adds the year AFTER the goals are agreed, and its order matters in three
# more places: `checkin.py` declares the month helpers `review.py` and
# `automation.py` both import; `scoring.py` puts `_all_goals()` on the sheet
# and `close.py` uses it; `change.py` declares the model `change_approval.py`
# inherits. Everything else is independent.
from . import goals_common
from . import cycle
from . import goal_set
from . import goal
from . import kr
from . import template
from . import checkin
from . import review
from . import scoring
from . import change
from . import close
from . import goal_set_approval
from . import change_approval
from . import approval_engine_ext
from . import journey_ext
from . import automation
from . import analytics
from . import pb_goals
from . import pb_goals_year
from . import pb_goals_home
from . import pb_my_goals
from . import pb_my_goals_year
