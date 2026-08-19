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
