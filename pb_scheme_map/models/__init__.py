# -*- coding: utf-8 -*-
# The assignment gains its fields before anything resolves through them.
from . import formula_scheme_assignment
from . import pb_scheme_map
from . import pb_person_scheme
from . import hr_employee
from . import hr_payslip_run
from . import pb_scheme_board
from . import pb_person_scheme_board
from . import person_scheme_panel
# PSCHEME P2b — shared seams (usual scheme, company move, take-back)
from . import pb_person_scheme_tools

from . import import_evidence
# PSCHEME P2a — many people at once, the one-time fill, the board's person
# counts and the team drawer, the country net and the contract that follows.
from . import pb_person_scheme_many
from . import pb_person_scheme_fill
from . import pb_person_scheme_team
from . import pb_person_scheme_follow
