# -*- coding: utf-8 -*-
from . import test_payai_p1
from . import test_payai_p2
from . import test_payai_p3
from . import test_payai_p4
# PAYAI FIX-1 — one file per review-fix cluster (P3 + P4 findings).
from . import test_payai_fix_red
from . import test_payai_fix_amber
from . import test_payai_fix_runner
from . import test_payai_fix_client
from . import test_payai_fix_access
from . import test_payai_fix_vi
# ONECHAT OC1 — the helper's router on payobook's shape; ask_only; markers after a plan.
from . import test_onechat_router
# ONECHAT OC2 — the one chat's browser halves, run in node.
from . import test_onechat_client
# ONECHAT OC3 — voice on the command path; Q6 (spoken names/amounts need a tap).
from . import test_onechat_voice
