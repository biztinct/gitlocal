# -*- coding: utf-8 -*-
from . import test_column_roles
from . import test_excel_onramp
from . import test_mapping_catalogue
from . import test_mapping_create_guard
from . import test_mapping_defects
from . import test_mapping_studio
from . import test_mapping_values
from . import test_one_mapping_home
from . import test_payslip_template_import

# JOURNEY J3 — two-way ⇆ presentation and the source-conflict guardrail.
from . import test_journey_guardrails

# JOURNEY J4 — the Transformations tab: fields → rule → output → component.
from . import test_journey_transformations

# JOURNEY J5 — the Journey view: five lanes, one read, no writes.
from . import test_journey_view

# JOURNEY J6 — the four defects reported against the live Transformations board.
from . import test_journey_j6_defects

# JOURNEY J7 — the two legibility defects reported against the live shared board.
from . import test_journey_j7_legibility

# JOURNEY J8 — the contract-component lane, and the clipped arrowhead.
from . import test_journey_j8_components

# JOURNEY J9 — every source on the card, ranked; the (kind, key) fold; the three
# places the either/or restriction was enforced.
from . import test_journey_j9_display

# JOURNEY J10 — EMPLOYEE / CONTRACT RECORD and BANK ACCOUNT on the card,
# beside whatever else it declares, at rank 4.
from . import test_journey_j10_record_source

# NETROLE P2 — the import ends with a category conversation: the chain, the
# payload, the default tick, and the promise that a person's own column band is
# never silently overruled.
from . import test_category_review

# RD46 — preview the formulas against a REAL person: the copy rule (a preview
# never writes to a payslip), the scheme-scoped picker, and the two doors.
from . import test_rd46_person_preview

# RD47 — two display faults: a real earning drawn as a deduction (substring
# matching, again), and a formula payslip that could not be saved at all.
from . import test_rd47_group_and_required
