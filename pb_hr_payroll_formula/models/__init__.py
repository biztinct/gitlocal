# -*- coding: utf-8 -*-

from . import formula_config
from . import formula_config_tests
from . import formula_rule
from . import formula_rule_version
from . import shadow_run
from . import formula_simulation
from . import formula_period_comparison
from . import formula_scenario
from . import formula_rate_table
from . import formula_snippet
from . import formula_budget
from . import formula_rule_note
from . import formula_scheme_assignment
from . import formula_release
from . import formula_legislation
from . import formula_config_template
from . import formula_review
from . import formula_sample_data
from . import formula_test_result
# W84 — extends hr.formula.sample.data / hr.formula.config; MUST import after the
# base sample model so the _inherit target is already registered (Odoo 19 adds
# model classes to the registry in import order).
from . import formula_boundary
from . import integration_connector
from . import integration_field_mapping
from . import integration_mapping_template
from . import integration_endpoint
from . import formula_mapping_template
from . import api_data_store
from . import api_transformation_rule
from . import payslip_config
from . import payslip_import_mapping
from . import hr_employee
from . import hr_payslip_line
from . import hr_payslip_formula
from . import hr_payslip_run
from . import hr_payroll_structure_formula
from . import hr_contract
from . import contract_component_change
from . import payroll_import_batch
from . import payroll_import_line
from . import payroll_cycle_carryover
from . import payroll_cycle_component_mapping
from . import payroll_cycle_mapping_suggestion
from . import payroll_proration_line
from . import payroll_retro_adjustment
