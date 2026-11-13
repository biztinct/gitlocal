# -*- coding: utf-8 -*-
from . import models
from . import controllers


# ---------------------------------------------------------------- approvals
# A fresh install runs no migration, and the approval catalogue may be
# installed either side of this module — so each end asks the other. This is
# our half: lay the default route for every company that already exists. The
# configuration module's own `end-` relay is the other half, for a database
# where this module went in first. Both are idempotent (ledger AM70/AM75).
def post_init_hook(env):
    from .models.incentive_approval import seed_all
    seed_all(env)
    # P7 — and the "reopen a pay month" route.
    from .models.month_approval import seed_all as seed_month
    seed_month(env)
