# -*- coding: utf-8 -*-

# No model in it — plain functions, no Odoo import — but it is imported here so
# that the two egress paths reach it as an ordinary sibling and so a syntax
# error in it fails the module load rather than the first prompt.
from . import ai_redaction
from . import payroll_ai_config
from . import payroll_ai_engine
from . import payroll_data_query
from . import payroll_chart_schema
from . import payroll_ai_conversation
from . import payroll_ai_dashboard
from . import payroll_ai_pulse
from . import payroll_ai_report
