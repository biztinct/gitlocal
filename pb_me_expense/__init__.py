# Part of Payobook. See LICENSE file for full copyright and licensing details.
from . import models
from . import controllers


# ---------------------------------------------------------------- approvals
# A fresh install runs no migration: lay the default expense route (Their
# manager → Finance approver) for every company that already exists. Cloned
# from pb_business_trip's hook (ledger E3). Idempotent — a company created
# later gets its route the first time somebody there sends a claim
# (`pb.me.expense.send` → `_ensure_route`).
def post_init_hook(env):
    from .models.expense_claim import seed_all
    seed_all(env)
