# -*- coding: utf-8 -*-

# EMPTY ON PURPOSE, and the emptiness is the point.
#
# This package imported three modules — `test_formula_engine`,
# `test_column_manager`, `test_integration` — and NONE of the three files
# exists. Only this `__init__.py` is in the directory.
#
# It failed the same way the two om_hr_payroll suites did, and with the same
# blast radius: the import runs inside `odoo/tests/loader.py::get_test_modules`,
# before any test executes, over every installed module and regardless of
# `--test-tags`, so the whole run exited 255 and every other suite on the
# database went with it. The message it produced named the wrong cause —
#
#     ImportError: cannot import name 'test_formula_engine' from partially
#     initialized module '…tests' (most likely due to a circular import)
#
# — because Python reports a missing sibling inside a package that is mid-import
# as a circular-import guess. There is no circular import here; the files are
# simply gone.
#
# Left as an empty package rather than deleted: `pb_hr_payroll_formula` is the
# formula engine, the most consequential module in this codebase, and the fact
# that it currently has NO tests should be visible to whoever opens this
# directory looking for them — not hidden by removing the directory too.
#
# IA Cycle 4 adds the first one. The paragraph above still holds for the engine
# itself; what is imported below covers only the two Odoo-19 exception guards
# this cycle fixed. Every name added here MUST be a file that exists — see the
# blast radius described above.

from . import test_odoo19_exceptions
from . import test_integration_endpoints
from . import test_zoho_catalog
from . import test_transform_preview
from . import test_endpoint_field_catalog
from . import test_rule_composer
# COLROLES — column roles + typed contract components. The pure-Python classifier
# table (`test_column_role_classifier.py`) is deliberately NOT imported here: it runs
# under a bare python3 and needs no database.
from . import test_column_roles
# VALUEKIND — same split as the roles above: the ladder itself is a pure-Python
# table (`test_value_kind_classifier.py`, deliberately NOT imported here), and
# what the ladder's answer touches is asserted with a database.
from . import test_value_kinds
# COLROLES P3 — bank destinations, the mapping's two shapes, the input exclusion.
# The pure sanitizer table (`test_bank_account_util.py`) is likewise NOT imported.
from . import test_bank_destinations
# MAPFIX A — orphan-safe code rename. The pure generator table
# (`test_component_code.py`) is deliberately NOT imported here: it runs under a bare
# python3 and needs no database.
from . import test_code_rename

# JOURNEY J3 — the empty-feed guard, per-feed transformation rules, the
# batch-free API read, and the broom.
from . import test_journey_truth

# JOURNEY J9 — the binding, plural: the ranked walk, its neutrality rail, the
# migration and the per-source dangling check.
from . import test_journey_j9_sources

# JOURNEY J10 — the record destination as a ranked source, and the three
# writebacks resolving through the SAME order the payslip does.
from . import test_journey_j10_writeback

# The Zoho response contract — an HTTP-200 refusal must not read as an empty
# result set (the ABM "Sync said nothing and pulled nothing" incident).
from . import test_zoho_response_contract

# The July-run defects: a scheme that never learned its connector (so 25
# confirmed wires were skipped in silence), and a pull that never carried the
# period (so July's run refreshed August's numbers).
from . import test_feed_binding_and_period

# Run the same import twice and get the same people: the source key, the
# name-merge guard, the unique-barcode trap and one contract per employee.
from . import test_import_identity

# A payslip with no salary structure computes through its scheme instead of
# through silence — the ABM June 2026 "146 employees, 0.00" defect.
from . import test_structureless_payslip

# NETROLE — a component's category comes from what net pay does with it:
# the signed-graph classifier, its parser, details, and employer cost.
from . import test_net_role_classifier

# NETROLE P2 — an hours count is on a positive path to net pay and is still not
# an allowance: the quantity gate, the band signal, and the shelf that moves
# while the walk stays exactly where Phase 1 left it.
from . import test_net_role_quantity

# RECORDS R1 — a pay file that feeds one run and is then forgotten: the
# neutrality rail (md5 + counter), the writeback that does not happen, and the
# row for someone who is not in Payobook yet.
from . import test_records_r1_one_time

# RECORDS RD45 — ranks 4 and 5 on the file-less path: a component mapped to an
# employee or contract field could not be read at all unless the run carried a
# pay-data file, which is what made ABM's June deductions read ₫0.00.
from . import test_records_r5_record_rung

# RD49 — stop fetching feeds nothing reads, and fetch last month on a schedule
# so a pay run never waits for the sync.
from . import test_rd49_sync_cost

# RD51 — the per-employee Zoho salary search ignored its filter and returned the
# same row for everybody: one person's pay for 152 people.
from . import test_rd51_salary_identity

# RD54/RD56 — the records come into step from the connected system without
# anybody remembering to, and the refresh never makes payroll.
from . import test_rd54_record_refresh

# RD60 — the collateral of a record refresh: "the newest batch" was load-bearing
# in four places, and the connected system spells one employee key two ways.
from . import test_rd60_signal_and_identity
