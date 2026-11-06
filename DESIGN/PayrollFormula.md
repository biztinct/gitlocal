# Implementation Plan: Excel Formula-Based Payroll Calculation Module

## Overview

Create a new state-of-the-art Odoo 16 module `pb_hr_payroll_formula` that provides:
- Excel-like formula-based salary rule configuration with stunning visual UI
- Full Excel-like grid interface with drag-drop, formula bar, and cell editing
- Multi-system HR integration framework (Zoho, Excel import, stubs for SAP/Workday/Oracle)
- Advanced sample data testing with anonymized employee comparison

**Design Principles**: Modern, visually appealing, extremely user-friendly, state-of-the-art UX

---

## Module Structure

```
pb_hr_payroll_formula/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── formula_config.py              # Main configuration model
│   ├── formula_rule.py                # Excel formula salary rules
│   ├── formula_sample_data.py         # Sample data for testing
│   ├── formula_test_result.py         # Test comparison results
│   ├── integration_connector.py       # Base connector model
│   ├── integration_field_mapping.py   # Field mapping model
│   └── hr_payslip_formula.py          # Payslip computation extension
├── formula_engine/
│   ├── __init__.py
│   ├── column_manager.py              # A, B, C...Z, AA, AB column management
│   ├── parser.py                      # Excel formula parser
│   ├── converter.py                   # Excel-to-Python using 'formulas' library
│   ├── evaluator.py                   # Runtime formula evaluation
│   └── validator.py                   # Formula validation & circular ref detection
├── integrations/
│   ├── __init__.py
│   ├── base_connector.py              # Abstract base class
│   ├── zoho_connector.py              # Enhanced Zoho People connector
│   ├── excel_connector.py             # Excel file import connector
│   ├── sap_connector.py               # SAP stub
│   ├── workday_connector.py           # Workday stub
│   └── oracle_connector.py            # Oracle HCM stub
├── wizards/
│   ├── __init__.py
│   ├── formula_import_wizard.py       # Import from existing rules
│   ├── sample_data_wizard.py          # Generate sample data from employees
│   └── integration_sync_wizard.py     # Sync data from external systems
├── views/
│   ├── formula_config_views.xml       # Main configuration views
│   ├── formula_rule_views.xml         # Rule views
│   ├── integration_views.xml          # Connector & mapping views
│   ├── sample_data_views.xml          # Sample data views
│   ├── menu_views.xml                 # Menu structure
│   └── assets.xml                     # Asset bundles
├── static/
│   ├── src/
│   │   ├── js/
│   │   │   ├── excel_grid_widget.js   # Main Excel grid OWL component
│   │   │   ├── formula_bar.js         # Formula bar component
│   │   │   ├── column_header.js       # Draggable column headers
│   │   │   ├── cell_editor.js         # Cell editing component
│   │   │   ├── formula_autocomplete.js # Formula suggestions
│   │   │   └── grid_actions.js        # Grid action handlers
│   │   ├── xml/
│   │   │   ├── excel_grid_templates.xml
│   │   │   └── formula_components.xml
│   │   └── scss/
│   │       ├── excel_grid.scss        # Excel grid styles
│   │       ├── formula_bar.scss       # Formula bar styles
│   │       ├── dark_theme.scss        # Dark mode
│   │       └── animations.scss        # Smooth animations
│   └── description/
│       └── icon.png
├── security/
│   ├── ir.model.access.csv
│   └── formula_security.xml
├── data/
│   ├── formula_functions_data.xml     # Supported Excel functions
│   └── demo_formula_config.xml        # Demo configuration
└── tests/
    ├── __init__.py
    ├── test_formula_engine.py
    ├── test_column_manager.py
    └── test_integration.py
```

---

## Phase 1: Core Models (Database Layer)

### 1.1 Model: `hr.formula.config`
**File**: `models/formula_config.py`

```python
# Main configuration linking structure to formula rules
class HrFormulaConfig(models.Model):
    _name = 'hr.formula.config'
    _description = 'Excel Formula Configuration'
    _order = 'sequence, name'

    # Basic Info
    name = fields.Char('Configuration Name', required=True)
    code = fields.Char('Reference Code', required=True)
    country_code = fields.Selection([...])  # VN, ID, IN, SG, MY, TH, KH
    structure_id = fields.Many2one('hr.payroll.structure')

    # Formula Rules (One2many)
    rule_ids = fields.One2many('hr.formula.rule', 'config_id')

    # Sample Data
    sample_data_ids = fields.One2many('hr.formula.sample.data', 'config_id')
    test_result_ids = fields.One2many('hr.formula.test.result', 'config_id')

    # Integration
    connector_id = fields.Many2one('hr.integration.connector')

    # State & Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('testing', 'Testing'),
        ('validated', 'Validated'),
        ('active', 'Active'),
        ('archived', 'Archived')
    ])
    validation_status = fields.Selection([
        ('pending', 'Pending'),
        ('passed', 'All Tests Passed'),
        ('failed', 'Tests Failed'),
        ('warning', 'Warnings')
    ])
    last_validated = fields.Datetime()

    # UI Settings
    theme = fields.Selection([
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto')
    ], default='light')
    grid_row_height = fields.Integer(default=32)
    show_formula_bar = fields.Boolean(default=True)
    show_column_letters = fields.Boolean(default=True)
```

### 1.2 Model: `hr.formula.rule`
**File**: `models/formula_rule.py`

```python
# Individual formula-based salary rule
class HrFormulaRule(models.Model):
    _name = 'hr.formula.rule'
    _description = 'Excel Formula Salary Rule'
    _order = 'sequence, id'

    # Link to config
    config_id = fields.Many2one('hr.formula.config', ondelete='cascade')
    salary_rule_id = fields.Many2one('hr.salary.rule')  # Link to standard rule

    # Column Identity
    column_letter = fields.Char('Column Letter', compute='_compute_column_letter', store=True)
    sequence = fields.Integer('Sequence', default=10)

    # Rule Definition
    name = fields.Char('Label/Name', required=True)
    code = fields.Char('Code', required=True)
    category_id = fields.Many2one('hr.salary.rule.category')

    # Formula
    excel_formula = fields.Char('Excel Formula')  # e.g., =A1+B1*0.08
    python_formula = fields.Text('Python Code', compute='_compute_python_formula')
    formula_dependencies = fields.Char('Dependencies', compute='_compute_dependencies')

    # Column Type
    column_type = fields.Selection([
        ('input', 'Input (from data source)'),
        ('formula', 'Calculated (formula)'),
        ('constant', 'Constant Value')
    ], default='formula')

    # For input columns
    data_source_field = fields.Char('Source Field Mapping')
    default_value = fields.Float('Default Value')

    # For constant columns
    constant_value = fields.Float('Constant Value')

    # Display
    column_width = fields.Integer('Width (px)', default=120)
    number_format = fields.Selection([
        ('number', 'Number'),
        ('currency', 'Currency'),
        ('percentage', 'Percentage'),
        ('integer', 'Integer')
    ], default='currency')
    decimal_places = fields.Integer(default=2)

    # Validation
    is_valid = fields.Boolean('Valid', compute='_compute_validation')
    validation_message = fields.Char('Validation Message')
    has_circular_ref = fields.Boolean('Circular Reference')

    # Visibility
    appears_on_payslip = fields.Boolean(default=True)
    is_visible_in_grid = fields.Boolean(default=True)
```

### 1.3 Model: `hr.formula.sample.data`
**File**: `models/formula_sample_data.py`

```python
# Sample employee data for formula testing
class HrFormulaSampleData(models.Model):
    _name = 'hr.formula.sample.data'
    _description = 'Formula Sample Data'

    config_id = fields.Many2one('hr.formula.config', ondelete='cascade')

    # Sample Identity
    name = fields.Char('Sample Name')  # e.g., "Employee A", "High Earner"
    description = fields.Text('Description')

    # Source (if from real employee)
    source_employee_id = fields.Many2one('hr.employee')
    source_payslip_id = fields.Many2one('hr.payslip')
    is_anonymized = fields.Boolean('Anonymized', default=True)

    # Sample Values (JSON for flexibility)
    input_values_json = fields.Text('Input Values JSON')
    expected_values_json = fields.Text('Expected Values JSON')

    # Computed Results
    computed_values_json = fields.Text('Computed Values JSON', compute='_compute_results')

    # Validation
    all_passed = fields.Boolean('All Passed', compute='_compute_validation')
    discrepancy_count = fields.Integer('Discrepancies', compute='_compute_validation')
    max_discrepancy = fields.Float('Max Discrepancy %', compute='_compute_validation')
```

### 1.4 Model: `hr.integration.connector`
**File**: `models/integration_connector.py`

```python
# HR System Integration Connector
class HrIntegrationConnector(models.Model):
    _name = 'hr.integration.connector'
    _description = 'HR System Integration Connector'

    name = fields.Char('Connector Name', required=True)
    connector_type = fields.Selection([
        ('zoho', 'Zoho People'),
        ('excel', 'Excel File Import'),
        ('sap', 'SAP SuccessFactors'),
        ('workday', 'Workday'),
        ('oracle', 'Oracle HCM')
    ], required=True)

    # Connection Settings
    api_endpoint = fields.Char('API Endpoint')
    auth_type = fields.Selection([
        ('oauth2', 'OAuth 2.0'),
        ('api_key', 'API Key'),
        ('basic', 'Basic Auth')
    ])

    # Credentials (encrypted storage recommended)
    client_id = fields.Char('Client ID')
    client_secret = fields.Char('Client Secret', groups="base.group_system")
    access_token = fields.Text('Access Token', groups="base.group_system")
    refresh_token = fields.Text('Refresh Token', groups="base.group_system")

    # Field Mappings
    field_mapping_ids = fields.One2many('hr.integration.field.mapping', 'connector_id')

    # Status
    connection_status = fields.Selection([
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Error')
    ])
    last_sync = fields.Datetime('Last Sync')
    last_error = fields.Text('Last Error')
```

### 1.5 Model: `hr.integration.field.mapping`
**File**: `models/integration_field_mapping.py`

```python
# Field mapping between source system and formula rules
class HrIntegrationFieldMapping(models.Model):
    _name = 'hr.integration.field.mapping'
    _description = 'Integration Field Mapping'

    connector_id = fields.Many2one('hr.integration.connector', ondelete='cascade')

    # Source
    source_field = fields.Char('Source Field Path')
    source_field_label = fields.Char('Source Label')
    source_data_type = fields.Selection([
        ('string', 'Text'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('boolean', 'Boolean')
    ])

    # Target
    target_rule_id = fields.Many2one('hr.formula.rule')
    target_column_letter = fields.Char(related='target_rule_id.column_letter')

    # Transformation
    transformation_type = fields.Selection([
        ('direct', 'Direct Mapping'),
        ('multiply', 'Multiply'),
        ('divide', 'Divide'),
        ('python', 'Python Expression')
    ], default='direct')
    transformation_value = fields.Float('Factor')
    transformation_code = fields.Text('Python Code')

    # Validation
    is_required = fields.Boolean('Required')
    default_value = fields.Float('Default if Empty')
```

---

## Phase 2: Formula Engine

### 2.1 Column Manager
**File**: `formula_engine/column_manager.py`

```python
class ColumnManager:
    """Manages Excel-style column letters (A, B, C...Z, AA, AB, etc.)"""

    @staticmethod
    def index_to_letter(index: int) -> str:
        """Convert 0-based index to column letter"""
        result = ""
        while index >= 0:
            result = chr(index % 26 + ord('A')) + result
            index = index // 26 - 1
        return result

    @staticmethod
    def letter_to_index(letter: str) -> int:
        """Convert column letter to 0-based index"""
        result = 0
        for char in letter.upper():
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1

    @staticmethod
    def update_formula_references(formula: str, old_letter: str, new_letter: str) -> str:
        """Update cell references when columns are reordered"""
        # Replace references like A1, AA1 with new letters
        import re
        pattern = rf'\b{old_letter}(\d+)\b'
        return re.sub(pattern, f'{new_letter}\\1', formula)
```

### 2.2 Formula Converter (using `formulas` library)
**File**: `formula_engine/converter.py`

```python
import formulas
from formulas import Parser

class FormulaConverter:
    """Convert Excel formulas to Python using formulas library"""

    def __init__(self, column_mapping: dict):
        self.column_mapping = column_mapping  # {'A': 'BASIC', 'B': 'HRA', ...}
        self.parser = Parser()

    def convert(self, excel_formula: str) -> str:
        """Convert Excel formula to Python expression"""
        # Use formulas library to parse
        ast = self.parser.ast(excel_formula)

        # Convert to Python with column mappings
        python_code = self._ast_to_python(ast)
        return python_code

    def validate(self, formula: str) -> tuple[bool, str]:
        """Validate formula syntax"""
        try:
            self.parser.ast(formula)
            return True, "Valid"
        except Exception as e:
            return False, str(e)

    def get_dependencies(self, formula: str) -> list[str]:
        """Extract column references from formula"""
        # Parse and extract cell references
        import re
        refs = re.findall(r'([A-Z]+)\d+', formula.upper())
        return list(set(refs))
```

### 2.3 Formula Evaluator
**File**: `formula_engine/evaluator.py`

```python
class FormulaEvaluator:
    """Evaluate converted formulas at runtime"""

    def __init__(self):
        self.results_cache = {}

    def evaluate_all(self, rules: list, input_values: dict) -> dict:
        """Evaluate all rules in dependency order"""
        # Build dependency graph
        sorted_rules = self._topological_sort(rules)

        results = input_values.copy()
        for rule in sorted_rules:
            if rule.column_type == 'input':
                continue  # Already in input_values
            elif rule.column_type == 'constant':
                results[rule.code] = rule.constant_value
            else:  # formula
                results[rule.code] = self._evaluate_single(rule, results)

        return results

    def _evaluate_single(self, rule, context: dict) -> float:
        """Evaluate single formula with context"""
        try:
            # Use safe_eval with restricted context
            result = safe_eval(rule.python_formula, context)
            return float(result)
        except Exception as e:
            raise FormulaEvaluationError(f"Error in {rule.code}: {e}")
```

---

## Phase 3: Excel-Like Grid UI (State-of-the-Art)

### 3.1 Main Grid Widget
**File**: `static/src/js/excel_grid_widget.js`

```javascript
/** @odoo-module **/
import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ExcelFormulaGrid extends Component {
    static template = "pb_hr_payroll_formula.ExcelFormulaGrid";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            columns: [],
            rows: [],
            selectedCell: null,
            selectedColumn: null,
            formulaBarValue: "",
            isDragging: false,
            dragSource: null,
            dropTarget: null,
            isEditing: false,
            editingCell: null,
            zoom: 100,
            theme: "light",
            showGridlines: true,
            frozenColumns: 1,  // Freeze row labels
        });

        this.gridRef = useRef("grid");
        this.formulaBarRef = useRef("formulaBar");

        onMounted(() => this.initializeGrid());
        onWillUnmount(() => this.cleanup());
    }

    // Column letter generation
    getColumnLetter(index) {
        let letter = "";
        while (index >= 0) {
            letter = String.fromCharCode((index % 26) + 65) + letter;
            index = Math.floor(index / 26) - 1;
        }
        return letter;
    }

    // Drag & Drop handlers
    onColumnDragStart(ev, columnIndex) { ... }
    onColumnDragOver(ev, targetIndex) { ... }
    onColumnDrop(ev, targetIndex) { ... }

    // Cell editing
    onCellDoubleClick(cell) { ... }
    onCellKeyDown(ev, cell) { ... }

    // Formula bar
    onFormulaBarInput(ev) { ... }
    onFormulaBarKeyDown(ev) { ... }

    // Actions
    async reorderColumns(fromIndex, toIndex) { ... }
    async saveFormula(column, formula) { ... }
    async validateFormulas() { ... }
    async runTestWithSampleData() { ... }
}

registry.category("fields").add("excel_formula_grid", ExcelFormulaGrid);
```

### 3.2 Grid Template (Modern UI)
**File**: `static/src/xml/excel_grid_templates.xml`

Key UI elements:
- Frozen column headers with gradient backgrounds
- Smooth drag-and-drop with visual feedback
- Formula bar with syntax highlighting
- Cell editing with autocomplete
- Status bar with validation indicators
- Zoom controls
- Theme toggle (light/dark)

### 3.3 Modern SCSS Styling
**File**: `static/src/scss/excel_grid.scss`

```scss
// Variables for theming
$grid-header-bg: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
$grid-cell-hover: rgba(102, 126, 234, 0.1);
$grid-selected: rgba(102, 126, 234, 0.2);
$grid-border: #e0e0e0;
$formula-bar-bg: #fafafa;

// Light theme
.excel-formula-grid {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);

    // Header row with column letters
    .grid-header {
        background: $grid-header-bg;
        color: white;

        .column-header {
            cursor: grab;
            transition: all 0.2s ease;

            &:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }

            &.dragging {
                opacity: 0.5;
                cursor: grabbing;
            }

            &.drop-target {
                background: rgba(255, 255, 255, 0.3);
                border: 2px dashed white;
            }
        }
    }

    // Formula bar
    .formula-bar {
        background: $formula-bar-bg;
        border-bottom: 1px solid $grid-border;
        padding: 12px 16px;
        display: flex;
        align-items: center;
        gap: 12px;

        .cell-reference {
            font-weight: 600;
            color: #667eea;
            min-width: 60px;
        }

        .formula-input {
            flex: 1;
            font-family: 'Fira Code', monospace;
            border: none;
            background: white;
            padding: 8px 12px;
            border-radius: 6px;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
        }
    }

    // Grid cells
    .grid-cell {
        border-right: 1px solid $grid-border;
        border-bottom: 1px solid $grid-border;
        padding: 8px 12px;
        transition: background 0.15s ease;

        &:hover {
            background: $grid-cell-hover;
        }

        &.selected {
            background: $grid-selected;
            outline: 2px solid #667eea;
        }

        &.formula-cell {
            background: #f0f7ff;
        }

        &.input-cell {
            background: #f0fff4;
        }

        &.error {
            background: #fff0f0;
            border-color: #ff4d4f;
        }
    }

    // Row types
    .label-row {
        font-weight: 600;
        background: #f8f9fa;
    }

    .formula-row {
        font-family: 'Fira Code', monospace;
        font-size: 0.9em;
        color: #1890ff;
    }

    .sample-row {
        &.header {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
    }
}

// Dark theme
.excel-formula-grid.dark {
    background: #1a1a2e;
    color: #eee;

    .grid-header {
        background: linear-gradient(135deg, #4a00e0 0%, #8e2de2 100%);
    }

    .formula-bar {
        background: #16213e;
        border-color: #333;
    }

    .grid-cell {
        border-color: #333;

        &:hover {
            background: rgba(138, 43, 226, 0.2);
        }
    }
}

// Animations
@keyframes cellHighlight {
    0% { background: rgba(102, 126, 234, 0.4); }
    100% { background: transparent; }
}

.cell-updated {
    animation: cellHighlight 0.5s ease-out;
}
```

---

## Phase 4: Integration Framework

### 4.1 Base Connector
**File**: `integrations/base_connector.py`

```python
from abc import ABC, abstractmethod

class BaseHRConnector(ABC):
    """Abstract base class for HR system integrations"""

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the HR system"""
        pass

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        """Test the connection"""
        pass

    @abstractmethod
    def get_available_fields(self) -> list[dict]:
        """Get list of available fields from source"""
        pass

    @abstractmethod
    def fetch_employees(self, filters: dict = None) -> list[dict]:
        """Fetch employee data"""
        pass

    @abstractmethod
    def fetch_payroll_data(self, employee_ids: list, date_from, date_to) -> dict:
        """Fetch payroll-related data"""
        pass

    def transform_data(self, raw_data: dict, mappings: list) -> dict:
        """Transform data using field mappings"""
        # Common transformation logic
        pass
```

### 4.2 Enhanced Zoho Connector
**File**: `integrations/zoho_connector.py`
- Full implementation with OAuth 2.0
- Employee data fetch
- Attendance/time data
- Field discovery

### 4.3 Excel Connector
**File**: `integrations/excel_connector.py`
- Excel/CSV file upload
- Auto-detect headers
- Column mapping wizard
- Data preview

### 4.4 Stub Connectors
**Files**: `sap_connector.py`, `workday_connector.py`, `oracle_connector.py`
- Placeholder implementations
- Document API requirements
- Ready for future development

---

## Phase 5: Dashboard & Workflow Integration

### 5.1 Extend Payroll Dashboard
**File**: Modify `pb_hr_payroll_base/models/payroll_dashboard_base.py`

Add fields:
```python
calculation_method = fields.Selection([
    ('spreadsheet', 'Spreadsheet Import'),
    ('formula', 'Formula Engine'),
    ('hybrid', 'Both Available')
], default='spreadsheet')

formula_config_id = fields.Many2one('hr.formula.config')
```

### 5.2 Payslip Computation Integration
**File**: `models/hr_payslip_formula.py`

Extend `hr.payslip` to support formula-based computation:
```python
class HrPayslipFormula(models.Model):
    _inherit = 'hr.payslip'

    calculation_method_used = fields.Selection([...])
    formula_config_id = fields.Many2one('hr.formula.config')
    formula_log = fields.Text('Computation Log')

    def compute_sheet_with_formulas(self):
        """Alternative compute using formula engine"""
        # Get input values from integrated source
        # Run formula engine
        # Create payslip lines
```

---

## Phase 6: Sample Data Testing (Advanced)

### 6.1 Sample Data Generation Wizard
**File**: `wizards/sample_data_wizard.py`

```python
class SampleDataWizard(models.TransientModel):
    _name = 'hr.formula.sample.data.wizard'

    config_id = fields.Many2one('hr.formula.config')
    source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('employees', 'From Employees'),
        ('payslips', 'From Existing Payslips')
    ])

    # For employee/payslip source
    employee_ids = fields.Many2many('hr.employee')
    payslip_ids = fields.Many2many('hr.payslip')
    anonymize = fields.Boolean('Anonymize Data', default=True)
    sample_count = fields.Integer('Number of Samples', default=5)

    def action_generate_samples(self):
        """Generate sample data from real employees/payslips"""
        # Anonymize names
        # Extract input values
        # Extract expected results from actual payslips
        # Create sample records
```

### 6.2 Comparison Report
Show side-by-side comparison:
- Expected values (from real payslips)
- Calculated values (from formula engine)
- Discrepancy percentage
- Pass/Fail status per column

---

## Phase 7: Menu & Access Structure

### Menu Structure
```
Payroll (om_hr_payroll.menu_hr_payroll_root)
└── Formula Configuration (NEW)
    ├── Formula Configurations
    │   └── [List of configs by country]
    ├── Integration Connectors
    │   ├── Zoho People
    │   ├── Excel Import
    │   └── Other Systems
    ├── Sample Data Testing
    │   └── Test Results
    └── Settings
        └── Supported Functions
```

### Security Groups
- `group_formula_user` - View & use formulas
- `group_formula_manager` - Create/edit formulas
- `group_formula_admin` - Full access including integrations

---

## Critical Files to Modify

| File | Changes |
|------|---------|
| `pb_hr_payroll_base/models/payroll_dashboard_base.py` | Add `calculation_method`, `formula_config_id` fields |
| `pb_hr_payroll_base/views/payroll_dashboard.xml` | Add calculation method selector |
| `om_hr_payroll/models/hr_payslip.py` | Add hook for formula-based computation |

---

## Implementation Order

### Week 1: Foundation
1. Create module structure
2. Implement core models (`formula_config`, `formula_rule`, `sample_data`)
3. Implement Column Manager
4. Basic views for configuration

### Week 2: Formula Engine
1. Integrate `formulas` library
2. Implement parser, converter, evaluator
3. Formula validation & circular reference detection
4. Unit tests for formula engine

### Week 3: Excel Grid UI
1. OWL component structure
2. Column headers with drag-drop
3. Formula bar with autocomplete
4. Cell editing
5. Theme support (light/dark)
6. SCSS styling (modern, state-of-the-art)

### Week 4: Integrations
1. Base connector framework
2. Enhanced Zoho connector
3. Excel file import connector
4. Field mapping UI
5. Stub connectors for SAP/Workday/Oracle

### Week 5: Testing & Dashboard
1. Sample data wizard
2. Comparison engine
3. Dashboard integration
4. Payslip computation hook

### Week 6: Polish & Documentation
1. Animations & transitions
2. Error handling & user feedback
3. Performance optimization
4. User documentation

---

## Dependencies

**Python packages** (add to requirements.txt):
```
formulas>=1.2.0
openpyxl>=3.0.0
```

**Module dependencies** (`__manifest__.py`):
```python
'depends': [
    'om_hr_payroll',
    'pb_hr_payroll_base',
    'web',
]
```

---

## Success Criteria

1. **Functional**: Formulas compute same results as spreadsheet method
2. **UI/UX**: Intuitive Excel-like experience with modern aesthetics
3. **Performance**: Handle 100+ columns, 50+ sample rows smoothly
4. **Validation**: Catch all formula errors before payroll execution
5. **Integration**: Seamless data flow from external systems
6. **Backward Compatible**: Existing spreadsheet flow unaffected
