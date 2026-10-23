# -*- coding: utf-8 -*-
"""
Base Connector - Abstract base class for HR system integrations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
import logging

_logger = logging.getLogger(__name__)


class BaseHRConnector(ABC):
    """
    Abstract base class for HR system connectors.

    All HR system integrations (Zoho, SAP, Workday, Oracle, Excel)
    should inherit from this class and implement the required methods.
    """

    def __init__(self, connector_record):
        """
        Initialize connector with Odoo record.

        Args:
            connector_record: hr.integration.connector record
        """
        self.connector = connector_record
        self.env = connector_record.env

    # ==========================================
    # ABSTRACT METHODS - Must be implemented
    # ==========================================

    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the external HR system.

        Returns:
            True if authentication successful, False otherwise
        """
        pass

    @abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test the connection to the external system.

        Returns:
            Tuple of (success, message)
        """
        pass

    @abstractmethod
    def get_available_fields(self) -> List[Dict[str, Any]]:
        """
        Get list of available fields from the source system.

        Returns:
            List of field definitions with structure:
            [
                {
                    'name': 'field_name',
                    'label': 'Human readable label',
                    'data_type': 'string|number|date|boolean',
                    'path': 'api.path.to.field',
                    'sample_value': 'example value',
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def fetch_employees(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Fetch employee data from the source system.

        Args:
            filters: Optional filter criteria

        Returns:
            List of employee dictionaries
        """
        pass

    @abstractmethod
    def fetch_payroll_data(
        self,
        employee_ids: List[str],
        date_from: str,
        date_to: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch payroll-related data for employees.

        Args:
            employee_ids: List of employee IDs
            date_from: Start date (ISO format)
            date_to: End date (ISO format)

        Returns:
            Dict mapping employee_id to payroll data dict
        """
        pass

    # ==========================================
    # COMMON METHODS - Default implementations
    # ==========================================

    def transform_data(
        self,
        raw_data: Dict[str, Any],
        mappings: List[Any]
    ) -> Dict[str, Any]:
        """
        Transform data using field mappings.

        Args:
            raw_data: Raw data from source system
            mappings: List of hr.integration.field.mapping records

        Returns:
            Transformed data dict with formula rule codes as keys
        """
        result = {}

        for mapping in mappings:
            source_field = mapping.source_field
            target_code = mapping.target_rule_id.code if mapping.target_rule_id else None

            if not target_code:
                continue

            # Get value from raw data
            value = self._get_nested_value(raw_data, source_field)

            # Apply transformation
            value = self._apply_transformation(value, mapping)

            # Apply validation
            value = self._apply_validation(value, mapping)

            result[target_code] = value

        return result

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """
        Get value from nested dictionary using dot notation path.

        Args:
            data: Dictionary to search
            path: Dot-separated path (e.g., 'employee.salary.basic')

        Returns:
            Value at path or None if not found
        """
        if not path or not data:
            return None

        keys = path.split('.')
        current = data

        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                current = current[idx] if idx < len(current) else None
            else:
                return None

            if current is None:
                return None

        return current

    def _apply_transformation(self, value: Any, mapping: Any) -> Any:
        """Delegate to the ONE transform ladder (S-I1 / WP-I review Major 2).

        The previous inline ladder here duplicated (and had drifted from) the
        mapping model's — raw exec for python, SILENT divide-by-zero -> 0.0. It
        was dead code, but one future caller away from reintroducing both
        hazards. mapping.transform_value handles coercion, required/default,
        the shared op ladder (safe_eval'd python, no env) and the min/max
        clamp, so _apply_validation below is intentionally a passthrough.
        """
        return mapping.transform_value(value, record=None)

    def _apply_validation(self, value: Any, mapping: Any) -> Any:
        """Passthrough — required/default and min/max clamping already happen
        inside mapping.transform_value (the one ladder). Kept only so existing
        transform_data call sites keep their shape."""
        return value

    def _to_float(self, value: Any) -> float:
        """
        Convert value to float safely.

        Args:
            value: Value to convert

        Returns:
            Float value or 0.0 if conversion fails
        """
        if value is None:
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            # Remove currency symbols, commas, spaces
            cleaned = value.replace(',', '').replace(' ', '')
            cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
            try:
                return float(cleaned) if cleaned else 0.0
            except ValueError:
                return 0.0

        return 0.0

    def sync_data(self, config_id: int) -> Dict[str, Any]:
        """
        Sync data from external system to formula configuration.

        Args:
            config_id: hr.formula.config record ID

        Returns:
            Sync result dict with counts and errors
        """
        result = {
            'success': False,
            'synced_count': 0,
            'error_count': 0,
            'errors': [],
        }

        try:
            # Authenticate
            if not self.authenticate():
                result['errors'].append("Authentication failed")
                return result

            # Get config and mappings (F114/D114.2: only confirmed 'active'
            # mappings feed sync — 'suggested' template guesses are excluded)
            config = self.env['hr.formula.config'].browse(config_id)
            mappings = self.connector._sync_mapping_ids()

            if not mappings:
                result['errors'].append("No active field mappings configured")
                return result

            # Fetch employee data
            employees = self.fetch_employees()

            for emp in employees:
                try:
                    # Transform data
                    transformed = self.transform_data(emp, mappings)

                    # Create or update sample data
                    self._create_sample_from_sync(config, emp, transformed)
                    result['synced_count'] += 1

                except Exception as e:
                    result['error_count'] += 1
                    result['errors'].append(f"Employee {emp.get('id', '?')}: {str(e)}")

            result['success'] = result['error_count'] == 0

        except Exception as e:
            _logger.exception("Sync failed")
            result['errors'].append(str(e))

        return result

    def _create_sample_from_sync(
        self,
        config: Any,
        employee_data: Dict,
        transformed_data: Dict
    ) -> Any:
        """
        Create sample data record from synced data.

        Args:
            config: hr.formula.config record
            employee_data: Raw employee data
            transformed_data: Transformed data dict

        Returns:
            Created hr.formula.sample.data record
        """
        import json

        # Generate anonymized name
        emp_id = employee_data.get('id', employee_data.get('employee_id', 'Unknown'))
        sample_name = f"Sync Sample {emp_id}"

        # Check if sample already exists
        existing = self.env['hr.formula.sample.data'].search([
            ('config_id', '=', config.id),
            ('name', '=', sample_name),
        ], limit=1)

        values = {
            'config_id': config.id,
            'name': sample_name,
            'description': f"Synced from {self.connector.name}",
            'source_type': 'manual',  # Created via sync
            'is_anonymized': True,
            'input_values_json': json.dumps(transformed_data),
        }

        if existing:
            existing.write(values)
            return existing
        else:
            return self.env['hr.formula.sample.data'].create(values)

    def get_connection_status(self) -> str:
        """
        Get current connection status.

        Returns:
            Status string: 'connected', 'disconnected', or 'error'
        """
        try:
            success, _ = self.test_connection()
            return 'connected' if success else 'disconnected'
        except Exception:
            return 'error'

    def update_connector_status(self, status: str, message: str = None):
        """
        Update connector record with connection status.

        This is a claim about the CONNECTION — "the credentials work", "the
        host refused us" — and about nothing else. It used to stamp
        `last_sync` as well, which is how a successful `Test connection` came
        to write the clock the cockpit header prints as "Last sync": on abm the
        header read `Connected · Last sync 2026-08-20 23:25` over seven feeds
        that each read `Never synced`, and the connector row carried a NULL
        `last_sync_status`, NULL `total_synced_records`, zero data-store rows
        and the message "Connection successful" (Integrations Cycle 7, WP-5).

        A test moves no data, so it may not touch a field named for data
        movement. `last_connection_test` is the fact this method is entitled to
        write; `last_sync` belongs to `action_pull_data` and to
        `_stamp_endpoint`, which stamp the feeds in the same breath.

        Args:
            status: Connection status
            message: Optional status message
        """
        from datetime import datetime

        vals = {
            'connection_status': status,
            'last_connection_test': datetime.now(),
        }

        if message:
            vals['last_sync_message'] = message

        if status == 'error' and message:
            vals['last_error'] = message

        self.connector.write(vals)
