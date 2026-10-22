# -*- coding: utf-8 -*-
# Order matters in two places and nowhere else: `training_common` is imported
# by everything, and `pb_training_assignments` extends the facade declared in
# `pb_training` (it imports the class to widen `_VERBS` rather than restate it).
from . import training_common
from . import slide_channel_ext
from . import website_menu_ext
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

# ---------------------------------------------------------------- LEARNING L0
# The Overview reads helpers the two extensions above add, so it comes last.
from . import pb_training_overview

# ---------------------------------------------------------------- LEARNING L1
# The certificate record is the vault document with training fields
# (`document_ext`); the register, the wallet and the record PDF read it
# through the facades below, which extend the ones declared above.
from . import document_ext
from . import pb_training_certificates
from . import pb_my_training_certificates
from . import learning_record
from . import me_home_tile

# ---------------------------------------------------------------- LEARNING L2
# Required training: the rule table and its set-based evaluation
# (`requirement`), the three employee facts it reads, hours on the course /
# assignment / certificate, then the facades that read them — the Required
# lens (extends the certificates facade's verb tuple, so it comes after it),
# and the Numbers / Overview / My learning additions.
from . import hr_employee_ext
from . import hours
from . import requirement
from . import pb_training_required
from . import required_reports

# ---------------------------------------------------------------- LEARNING L3
# Learning paths: the three tables and the assignment links (`path`), then the
# PATHS board / Overview / My learning facade, which extends the Required
# facade's verb tuple and the Overview chain, so it comes last.
from . import path
from . import pb_training_paths

# ---------------------------------------------------------------- LEARNING L4
# Sessions, attendance and toolbox talks: the two tables, the course's
# delivery and the assignment / certificate links (`session`), then the
# SESSIONS board / Overview / Numbers / My learning facade, which extends the
# paths facade's verb tuple and the Overview chain, so it comes last.
from . import session
from . import pb_training_sessions

# ---------------------------------------------------------------- LEARNING L5
# Outside courses and course requests (with their route and the pre-booked
# allowance), course versions, test results and pools, course feedback and
# the manager's follow-up, skills a course gives — then the facades: the
# catalogue / requests / course drawer / Overview / Numbers one (it extends
# the sessions facade's verb tuple), and the SKILLS board with the learner's
# side, which comes last.
from . import outside_course
from . import request
from . import request_approval
from . import course_version
from . import test_results
from . import feedback
from . import skill_grant
from . import pb_training_catalogue
from . import pb_training_skills
