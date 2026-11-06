# -*- coding: utf-8 -*-
from . import test_anchor_registry
from . import test_assets
from . import test_bundle
from . import test_coach
from . import test_mission
from . import test_tenant_override
from . import test_progress_security
from . import test_retirement
# Phase D2.
from . import test_composer
from . import test_explain
from . import test_questions
# LEARNOS Phase 1b — the scenario engine and its one structural promise.
from . import test_scenario
# LEARNOS Phase 3 — the real-tenant welcome card, and the boundary between it
# and the demo greeting test_retirement owns.
from . import test_welcome
# LEARNOS Phase 5 — the free-roam practice sandbox: the orm allowlist and the
# watermark that no state can switch off.
from . import test_practice
# LEARNOS Phase 6 — the "what next" decision table and the streak, both
# pure functions so both actually execute offline.
from . import test_nextbest
# IA Cycle 6 — W108: screen identity vs rail reachability, split apart
# (and the gate that would have caught the cutover going dark).
from . import test_reachability
# RIZE W2 E1 — the Learn mission became a hub with a soft lens registry.
from . import test_learn_hub
# LEARN REFRESH step 5 — final station set, role paths, folded keys.
from . import test_refresh_paths
# PAYAI FIX-1 — a lesson step about an optional feature (PayAI) shows only
# where the reader's company has it; the ten minutes belong to the offer.
from . import test_feature_gate
# ONECHAT OC1 — the helper's router (base layer) and the resolver seams it reads.
from . import test_helper_route
# ONECHAT OC2 — the one chat: no tabs, no next step, PayAI by name (source).
from . import test_onechat_ui
# ONECHAT OC4 — Learn content follows the one PayAI chat (keys, lessons, phrases).
from . import test_onechat_content
# LEARNREV P0 T2 — "Open the lesson" opens this screen's lesson.
from . import test_learnrev_lesson_door
# LEARNREV P1 — the content engine: the truth gate and the Guide.
from . import test_guide_truth
from . import test_guide
# LEARNREV P2 — the Guide panel (node) and its server halves.
from . import test_guide_client
from . import test_learnrev_p2
# LEARNREV P3 — the Library: field index, menu order, retired page words,
# the LR30 gate rule, Explain never rewritten when it is the Guide's (S10).
from . import test_learnrev_p3
# LEARNREV P4 — checked Try, country, the replica gate, the panel player.
from . import test_learnrev_p4
# LEARNREV P5a — manifests for 8 more screens (providers), the feedback loop.
from . import test_learnrev_p5
from . import test_learnrev_p5_s3a
from . import test_learnrev_p5_s3b
from . import test_learnrev_p5_s3c
from . import test_learnrev_p5_s3d
# LEARNREV P5b — thumbs on every step, every lesson in the four lines.
from . import test_learnrev_p5b
