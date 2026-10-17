# -*- coding: utf-8 -*-
# `tests` is NOT imported here: the framework discovers the package on its own
# when tests are enabled, and importing it in normal operation would load a
# suite into every customer's registry for nothing.
from . import models
from . import controllers


# ---------------------------------------------------------------- approvals
# A fresh install runs no migration, and the approval catalogue may be
# installed either side of this module — so each end asks the other. This is
# our half: lay the default route for every company that already exists. The
# configuration module's own `end-` relay is the other half, for a database
# where this module went in first. Both are idempotent (ledger AM70/AM75).
def post_init_hook(env):
    from .models.support_approval import seed_all
    seed_all(env)
