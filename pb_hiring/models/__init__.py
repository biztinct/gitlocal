# -*- coding: utf-8 -*-
from . import (
    hiring_common,
    country_rule,
    requisition,
    requisition_approval,
    jd,
    jd_approval,
    referral,
    posting,
    stage_log,
    interview,
    panel_feedback,
    # A3. The order matters in one place only: `offer` declares the model that
    # `bgv`, `docreq`, `offer_approval` and `offer_closure` extend or point at,
    # and `requisition_a3` names them all.
    bgv,
    offer,
    offer_approval,
    offer_closure,
    docreq,
    cover,
    cover_approval,
    requisition_a3,
    vendor_ext,
    analytics,
    hr_applicant_ext,
    hr_job_ext,
    pb_hiring,
    pb_hiring_a3,
    hiring_automation,
)

from . import journey
from . import board_p1   # RECRUIT P1 — after journey, whose verbs it extends
from . import forms_p2   # RECRUIT P2 — after board_p1, whose drawer and set-up it extends
from . import requests_p3  # RECRUIT P3 — the request facet, budget, the offer rule
from . import facade_p3    # RECRUIT P3 — the screens' payloads and verbs
from . import privacy_p4   # RECRUIT P4 — shares, private notes, retention, money groups
from . import facade_p4    # RECRUIT P4 — the last layer of every payload; the bank
from . import scorecards_p5  # RECRUIT P5 — scorecards per role family and round
from . import google_p5      # RECRUIT P5 — Google Calendar + Meet, the scheduling link
from . import facade_p5      # RECRUIT P5 — proxy entry, Calendly rule, finalists
from . import joining_p6     # RECRUIT P6 — signed is not joined; Before they join
from . import facade_p6      # RECRUIT P6 — the drawer, the card, set-up, the verbs
from . import analytics_p6   # RECRUIT P6 — filters, funnel, ageing, leadership, exports
from . import channels_p7    # RECRUIT P7 — channels, tracked links, the connector seam
from . import agency_p7      # RECRUIT P7 — agency submissions, the 6-month rule, agency mails
from . import facade_p7      # RECRUIT P7 — the Publish panel, set-up Channels and Agencies
from . import analytics_p7   # RECRUIT P7 — each agency's own figures on Hiring numbers
from . import comms_p8       # RECRUIT P8 — one door for candidate email, three languages, the Emails screen
from . import automation_p8  # RECRUIT P8 — the automations the talent lead owns, the run log, the clocks
from . import hooks_p8       # RECRUIT P8 — the event hooks, G-44, the share email, check-started to-do
from . import guide_record   # RECRUIT close-out — "What was built" card (admins)
