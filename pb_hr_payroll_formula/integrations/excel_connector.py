# -*- coding: utf-8 -*-
"""
Excel Connector - Import payroll data from Excel/CSV files.
"""

import base64
import csv
import io
import json
from typing import Dict, List, Any, Optional, Tuple
import logging

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from .base_connector import BaseHRConnector

_logger = logging.getLogger(__name__)


class ExcelConnector(BaseHRConnector):
    """
    Excel/CSV file connector for importing payroll data.

    Supports:
    - Excel files (.xlsx, .xls)
    - CSV files
    - Auto-detection of headers
    - Column mapping wizard
    - Data preview
    """

    def __init__(self, connector_record):
        super().__init__(connector_record)
        self.workbook = None
        self.headers = []
        self.data_rows = []

    # ==========================================
    # AUTHENTICATION (Not required for Excel)
    # ==========================================

    def authenticate(self) -> bool:
        """
        Excel connector doesn't require authentication.
        """
        return True

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test if Excel processing is available.
        """
        if not OPENPYXL_AVAILABLE:
            return False, "openpyxl library not installed. Install with: pip install openpyxl"

        return True, "Excel connector ready"

    # ==========================================
    # FILE PROCESSING
    # ==========================================

    def load_file(
        self,
        file_content: bytes,
        filename: str,
        header_row: int = None,
        data_start_row: int = None,
        sheet_name: str = None
    ) -> Dict[str, Any]:
        """
        Load Excel or CSV file content.

        Args:
            file_content: File content as bytes
            filename: Original filename
            header_row: Row number containing headers (1-based), overrides connector setting
            data_start_row: Row number where data starts (1-based), overrides connector setting
            sheet_name: Sheet name for Excel files, overrides connector setting

        Returns:
            Dictionary with 'headers' and 'rows' keys, or raises exception
        """
        # Store parameters for use in loading methods
        self._header_row = header_row
        self._data_start_row = data_start_row
        self._sheet_name = sheet_name

        try:
            if filename.lower().endswith('.csv'):
                success = self._load_csv(file_content)
            elif filename.lower().endswith(('.xlsx', '.xls')):
                success = self._load_excel(file_content)
            else:
                raise ValueError(f"Unsupported file format: {filename}")

            if success:
                return {
                    'headers': self.headers,
                    'rows': self.data_rows,
                    'total_rows': len(self.data_rows),
                    'total_columns': len(self.headers),
                }
            else:
                raise ValueError("Failed to load file")

        except Exception as e:
            _logger.exception(f"Failed to load file: {e}")
            raise

    def _load_csv(self, content: bytes) -> bool:
        """
        Load CSV file content.

        Args:
            content: CSV file content as bytes

        Returns:
            True if loaded successfully
        """
        try:
            # Try different encodings
            text = None
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    text = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            if text is None:
                _logger.error("Failed to decode CSV file")
                return False

            # Parse CSV
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)

            if not rows:
                return False

            # Get header row - prefer parameter, then connector setting, then default
            header_row = self._header_row or (getattr(self.connector, 'file_header_row', None) if self.connector else None) or 1
            data_start_row = self._data_start_row or (getattr(self.connector, 'file_data_start_row', None) if self.connector else None) or 2

            self.headers = rows[header_row - 1] if len(rows) >= header_row else []
            self.data_rows = rows[data_start_row - 1:] if len(rows) >= data_start_row else []

            # Update connector with filename if available
            if self.connector and hasattr(self.connector, 'write'):
                try:
                    self.connector.write({
                        'last_import_filename': 'imported.csv',
                        'connection_status': 'connected',
                    })
                except Exception:
                    pass  # Ignore if connector can't be updated

            return True

        except Exception as e:
            _logger.exception(f"CSV loading failed: {e}")
            return False

    def _load_excel(self, content: bytes) -> bool:
        """
        Load Excel file content.

        Args:
            content: Excel file content as bytes

        Returns:
            True if loaded successfully
        """
        if not OPENPYXL_AVAILABLE:
            _logger.error("openpyxl not available")
            return False

        try:
            # Load workbook
            self.workbook = openpyxl.load_workbook(
                io.BytesIO(content),
                data_only=True  # Get calculated values
            )

            # Get sheet - prefer parameter, then connector setting
            sheet_name = self._sheet_name or (getattr(self.connector, 'file_sheet_name', None) if self.connector else None)
            if sheet_name and sheet_name in self.workbook.sheetnames:
                sheet = self.workbook[sheet_name]
            else:
                sheet = self.workbook.active
                sheet_name = sheet.title

            # Get header row - prefer parameter, then connector setting, then default
            header_row = self._header_row or (getattr(self.connector, 'file_header_row', None) if self.connector else None) or 1
            data_start_row = self._data_start_row or (getattr(self.connector, 'file_data_start_row', None) if self.connector else None) or 2

            # Extract headers
            self.headers = []
            for cell in sheet[header_row]:
                self.headers.append(str(cell.value) if cell.value else f"Column_{cell.column}")

            # Extract data rows
            self.data_rows = []
            for row_idx, row in enumerate(sheet.iter_rows(min_row=data_start_row), start=data_start_row):
                row_data = [cell.value for cell in row]
                # Skip empty rows
                if any(v is not None for v in row_data):
                    self.data_rows.append(row_data)

            # Update connector if available
            if self.connector and hasattr(self.connector, 'write'):
                try:
                    self.connector.write({
                        'last_import_filename': sheet_name or 'Sheet1',
                        'connection_status': 'connected',
                    })
                except Exception:
                    pass  # Ignore if connector can't be updated

            return True

        except Exception as e:
            _logger.exception(f"Excel loading failed: {e}")
            return False

    # ==========================================
    # FIELD DISCOVERY
    # ==========================================

    def get_available_fields(self) -> List[Dict[str, Any]]:
        """
        Get list of available columns from the loaded file.

        Returns:
            List of field definitions based on headers
        """
        fields = []

        for idx, header in enumerate(self.headers):
            # Try to detect data type from first few rows
            data_type = self._detect_column_type(idx)

            # Get sample value
            sample = None
            if self.data_rows and len(self.data_rows[0]) > idx:
                sample = self.data_rows[0][idx]

            field = {
                'name': header,
                'label': header,
                'data_type': data_type,
                'path': header,
                'column_index': idx,
                'sample_value': sample,
            }
            fields.append(field)

        return fields

    def _detect_column_type(self, column_index: int) -> str:
        """
        Detect the data type of a column based on sample values.

        Args:
            column_index: Column index

        Returns:
            Detected data type: 'string', 'number', 'date', or 'boolean'
        """
        samples = []
        for row in self.data_rows[:10]:
            if len(row) > column_index and row[column_index] is not None:
                samples.append(row[column_index])

        if not samples:
            return 'string'

        # Check if all samples are numbers
        is_numeric = True
        for sample in samples:
            if isinstance(sample, (int, float)):
                continue
            if isinstance(sample, str):
                try:
                    float(sample.replace(',', '').replace(' ', ''))
                    continue
                except ValueError:
                    is_numeric = False
                    break
            else:
                is_numeric = False
                break

        if is_numeric:
            return 'number'

        # Check if all samples are dates (openpyxl returns datetime for date cells)
        from datetime import datetime
        if all(isinstance(s, datetime) for s in samples):
            return 'date'

        # Check if all samples are boolean
        bool_values = {'true', 'false', 'yes', 'no', '1', '0'}
        if all(str(s).lower() in bool_values for s in samples):
            return 'boolean'

        return 'string'

    # ==========================================
    # DATA FETCHING
    # ==========================================

    def fetch_employees(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Fetch employee data from loaded file.

        Each row is treated as an employee record.

        Args:
            filters: Optional filter criteria

        Returns:
            List of employee data dictionaries
        """
        employees = []

        for row_idx, row in enumerate(self.data_rows):
            # Create dictionary from row
            emp = {}
            for col_idx, value in enumerate(row):
                if col_idx < len(self.headers):
                    header = self.headers[col_idx]
                    emp[header] = value

            # Add row identifier
            emp['_row_index'] = row_idx + 1
            emp['id'] = str(row_idx + 1)

            employees.append(emp)

        return employees

    def fetch_payroll_data(
        self,
        employee_ids: List[str],
        date_from: str,
        date_to: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        For Excel connector, all data is already in fetch_employees.
        This returns empty as payroll data is combined with employee data.

        Args:
            employee_ids: List of row indices as strings
            date_from: Ignored for Excel
            date_to: Ignored for Excel

        Returns:
            Empty dict - use fetch_employees instead
        """
        return {}

    # ==========================================
    # PREVIEW AND VALIDATION
    # ==========================================

    def get_data_preview(self, max_rows: int = 10) -> Dict[str, Any]:
        """
        Get a preview of the loaded data.

        Args:
            max_rows: Maximum number of rows to return

        Returns:
            Preview data with headers and sample rows
        """
        return {
            'headers': self.headers,
            'rows': self.data_rows[:max_rows],
            'total_rows': len(self.data_rows),
            'total_columns': len(self.headers),
        }

    def validate_data(self, mappings: List[Any]) -> Dict[str, Any]:
        """
        Validate loaded data against field mappings.

        Args:
            mappings: List of hr.integration.field.mapping records

        Returns:
            Validation result with errors and warnings
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {
                'total_rows': len(self.data_rows),
                'empty_values': 0,
                'type_mismatches': 0,
            }
        }

        required_fields = [m.source_field for m in mappings if m.is_required]

        # Check required fields exist
        for field in required_fields:
            if field not in self.headers:
                result['errors'].append(f"Required field '{field}' not found in file")
                result['valid'] = False

        # Check data quality
        for row_idx, row in enumerate(self.data_rows):
            for mapping in mappings:
                field = mapping.source_field
                if field not in self.headers:
                    continue

                col_idx = self.headers.index(field)
                value = row[col_idx] if col_idx < len(row) else None

                # Check empty values for required fields
                if mapping.is_required and (value is None or value == ''):
                    result['stats']['empty_values'] += 1
                    if result['stats']['empty_values'] <= 5:
                        result['warnings'].append(
                            f"Row {row_idx + 1}: Required field '{field}' is empty"
                        )

                # Check type compatibility
                if value is not None and mapping.source_data_type == 'number':
                    try:
                        if isinstance(value, str):
                            float(value.replace(',', ''))
                    except ValueError:
                        result['stats']['type_mismatches'] += 1
                        if result['stats']['type_mismatches'] <= 5:
                            result['warnings'].append(
                                f"Row {row_idx + 1}: Field '{field}' has non-numeric value"
                            )

        return result

    # ==========================================
    # AUTO-MAPPING
    # ==========================================

    def suggest_mappings(self, rules: List[Any]) -> List[Dict[str, Any]]:
        """
        Suggest field mappings based on header names and rule codes.

        Args:
            rules: List of hr.formula.rule records

        Returns:
            List of suggested mappings
        """
        suggestions = []

        for header in self.headers:
            header_upper = header.upper().replace(' ', '_').replace('-', '_')

            best_match = None
            best_score = 0

            for rule in rules:
                if rule.column_type != 'input':
                    continue

                # Calculate similarity score
                score = self._calculate_similarity(header_upper, rule.code)

                # Also check against rule name
                name_score = self._calculate_similarity(
                    header_upper,
                    rule.name.upper().replace(' ', '_')
                )
                score = max(score, name_score)

                if score > best_score and score > 0.5:
                    best_score = score
                    best_match = rule

            if best_match:
                suggestions.append({
                    'source_field': header,
                    'target_rule_id': best_match.id,
                    'target_code': best_match.code,
                    'confidence': best_score,
                })

        return suggestions

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings.

        Uses simple character-based similarity.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity score between 0 and 1
        """
        if not str1 or not str2:
            return 0.0

        # Exact match
        if str1 == str2:
            return 1.0

        # Contains match
        if str1 in str2 or str2 in str1:
            return 0.8

        # Partial match
        set1 = set(str1)
        set2 = set(str2)
        intersection = set1.intersection(set2)

        if not set1 or not set2:
            return 0.0

        return len(intersection) / max(len(set1), len(set2))

    # ==========================================
    # FILE GENERATION
    # ==========================================

    def generate_template(self, rules: List[Any]) -> bytes:
        """
        Generate an Excel template file based on formula rules.

        Args:
            rules: List of hr.formula.rule records

        Returns:
            Excel file content as bytes
        """
        if not OPENPYXL_AVAILABLE:
            raise ImportError("openpyxl required for template generation")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Payroll Data"

        # Write headers
        input_rules = [r for r in rules if r.column_type == 'input']
        for col_idx, rule in enumerate(input_rules, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.value = rule.code
            cell.font = openpyxl.styles.Font(bold=True)

            # Add column comment with rule name
            cell.comment = openpyxl.comments.Comment(
                text=f"{rule.name}\n{rule.description or ''}",
                author="Formula Engine"
            )

        # Add sample row
        for col_idx, rule in enumerate(input_rules, start=1):
            ws.cell(row=2, column=col_idx).value = rule.default_value or 0

        # Save to bytes
        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
