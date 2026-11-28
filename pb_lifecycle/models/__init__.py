# -*- coding: utf-8 -*-
from . import lifecycle_common
from . import ics
from . import journey_template
from . import letter
from . import journey_case
from . import journey_task
from . import checkin
from . import feedback
from . import lifecycle_reminders
from . import pb_journeys
# Approval Matrix P7 — sending a letter is the act.
from . import letter_approval
from . import workflow_models
from . import workflow_studio
from . import workflow_progress
from . import workflow_configuration
from . import workflow_record_context
# WORKFLOW-2 P2: the module contract ("already happens") and user-made stages.
from . import workflow_contract
from . import workflow_stage
# WORKFLOW-2 P3b: the eight new step types (after the facade they extend).
from . import workflow_steps
# WORKFLOW-2 P4a: everyone takes part (teams, cover, employee home, links),
# late work through the approval engine's job, tasks in the one inbox.
from . import workflow_people
from . import workflow_people_design
from . import workflow_inbox
from . import workflow_home
# WORKFLOW-2 P4b: progress where people already are (record screens and the
# employee home), where time goes, "The candidate" and the late-task role.
from . import workflow_strip
from . import workflow_time
from . import workflow_reach
from . import workflow_schedule_run

# WORKFLOW-2 P5c: the areas' date timetables (D31) and Repeat for each line.
from . import workflow_timetable
from . import workflow_repeat

# WORKFLOW-2 P6a: Approvals' route words in Studio, translated and plain.
from . import workflow_route_words
