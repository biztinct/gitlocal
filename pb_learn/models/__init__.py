# -*- coding: utf-8 -*-
# The static content plane first: every other model below reads it.
from . import learn_content
# Read-only window onto the running system — live values and the capstone
# predicates. Before learn_intent, whose answers interpolate live values.
from . import learn_live
from . import learn_intent
from . import learn_tenant_override
from . import learn_progress
# Phase D2. learn.question.record delegates the scrub to learn.intent.
#
# LEARNOS Phase 6 MOVED THIS ABOVE learn_runtime, which now imports the
# tenant-flag helper from it. The alternative was a third copy of a
# three-line "is this parameter truthy" reader, and the ledger's rule about
# conventions broken three times applies to helpers as well as to prose.
from . import learn_question
from . import learn_runtime
# LEARNOS Phase 4. The one screen that can switch the composer on; imports
# COMPOSE_FLAG from learn_intent, so it comes after it.
from . import learn_companion
