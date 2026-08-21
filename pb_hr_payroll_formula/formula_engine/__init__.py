# -*- coding: utf-8 -*-

from . import excel_semantics
from . import rule_formula
from . import if_chain
from . import cell_refs
from .cell_refs import shift_rows
from .column_manager import ColumnManager
from .parser import FormulaParser
from .converter import FormulaConverter
from .evaluator import FormulaEvaluator
from .validator import FormulaValidator
from .header_detector import HeaderDetector, detect_header_row
from .merged_cell_parser import MergedCellParser, extract_component_types
from .cross_sheet_resolver import CrossSheetResolver, resolve_formula
from .comparison import coerce_number, compare_values, default_tolerance
