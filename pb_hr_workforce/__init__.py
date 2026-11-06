from . import models


# ---------------------------------------------------------------- approvals
# A fresh install runs no migration, and the approval catalogue may be
# installed either side of this module — so each end asks the other. This is
# our half: lay the default route for every company that already exists. The
# configuration module's own `end-` relay is the other half, for a database
# where this module went in first. Both are idempotent (ledger AM70/AM75).
def post_init_hook(env):
    from .models.overtime_request_approval import seed_all
    seed_all(env)
