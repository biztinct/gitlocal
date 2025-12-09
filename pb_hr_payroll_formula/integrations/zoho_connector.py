# -*- coding: utf-8 -*-
"""
Zoho People Connector - Full implementation for Zoho People API integration.
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

from .base_connector import BaseHRConnector

_logger = logging.getLogger(__name__)


class ZohoConnector(BaseHRConnector):
    """
    Zoho People API connector for fetching employee and payroll data.

    Supports:
    - OAuth 2.0 authentication with refresh tokens
    - Employee data fetching
    - Attendance and time data
    - Custom field discovery
    """

    BASE_URL = "https://people.zoho.com/people/api"
    AUTH_URL = "https://accounts.zoho.com/oauth/v2"

    def __init__(self, connector_record):
        super().__init__(connector_record)
        self.access_token = None
        self.token_expiry = None

    # ==========================================
    # AUTHENTICATION
    # ==========================================

    def authenticate(self) -> bool:
        """
        Authenticate with Zoho using OAuth 2.0.

        Uses refresh token to get new access token if needed.

        Returns:
            True if authentication successful
        """
        try:
            # Check if we have a valid access token
            if self._is_token_valid():
                return True

            # Try to refresh the token
            if self.connector.refresh_token:
                return self._refresh_access_token()

            _logger.error("No valid access token or refresh token")
            return False

        except Exception as e:
            _logger.exception("Zoho authentication failed")
            self.update_connector_status('error', str(e))
            return False

    def _is_token_valid(self) -> bool:
        """Check if current access token is still valid."""
        if not self.connector.access_token:
            return False

        if not self.connector.token_expiry:
            return False

        # Check if token expires in next 5 minutes
        if self.connector.token_expiry <= datetime.now() + timedelta(minutes=5):
            return False

        self.access_token = self.connector.access_token
        return True

    def _refresh_access_token(self) -> bool:
        """
        Refresh the access token using refresh token.

        Returns:
            True if refresh successful
        """
        try:
            url = f"{self.AUTH_URL}/token"

            data = {
                'refresh_token': self.connector.refresh_token,
                'client_id': self.connector.client_id,
                'client_secret': self.connector.client_secret,
                'grant_type': 'refresh_token',
            }

            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            result = response.json()

            if 'access_token' not in result:
                _logger.error(f"Token refresh failed: {result}")
                return False

            # Update connector with new token
            self.access_token = result['access_token']
            expires_in = result.get('expires_in', 3600)

            self.connector.sudo().write({
                'access_token': self.access_token,
                'token_expiry': datetime.now() + timedelta(seconds=expires_in),
                'connection_status': 'connected',
            })

            return True

        except requests.exceptions.RequestException as e:
            _logger.error(f"Token refresh request failed: {e}")
            self.update_connector_status('error', f"Token refresh failed: {e}")
            return False

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            'Authorization': f'Zoho-oauthtoken {self.access_token}',
            'Content-Type': 'application/json',
        }

    # ==========================================
    # CONNECTION TEST
    # ==========================================

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection to Zoho People API.

        Returns:
            Tuple of (success, message)
        """
        try:
            if not self.authenticate():
                return False, "Authentication failed"

            # Try to fetch a simple endpoint
            url = f"{self.BASE_URL}/forms"
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                self.update_connector_status('connected', 'Connection successful')
                return True, "Connection successful"
            else:
                msg = f"API returned status {response.status_code}"
                self.update_connector_status('error', msg)
                return False, msg

        except requests.exceptions.RequestException as e:
            msg = f"Connection error: {str(e)}"
            self.update_connector_status('error', msg)
            return False, msg

    # ==========================================
    # FIELD DISCOVERY
    # ==========================================

    def get_available_fields(self) -> List[Dict[str, Any]]:
        """
        Get list of available fields from Zoho People.

        Fetches form fields from Employee form and related forms.

        Returns:
            List of field definitions
        """
        if not self.authenticate():
            return []

        fields = []

        try:
            # Get Employee form fields
            employee_fields = self._get_form_fields('P_Employee')
            fields.extend(employee_fields)

            # Get Salary form fields
            salary_fields = self._get_form_fields('P_Salary')
            fields.extend(salary_fields)

            # Get Attendance form fields
            attendance_fields = self._get_form_fields('P_Attendance')
            fields.extend(attendance_fields)

        except Exception as e:
            _logger.error(f"Failed to fetch fields: {e}")

        return fields

    def _get_form_fields(self, form_name: str) -> List[Dict[str, Any]]:
        """
        Get fields for a specific Zoho form.

        Args:
            form_name: Zoho form link name

        Returns:
            List of field definitions
        """
        fields = []

        try:
            url = f"{self.BASE_URL}/forms/{form_name}/components"
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )

            if response.status_code != 200:
                return fields

            data = response.json()
            components = data.get('response', {}).get('result', [])

            for comp in components:
                field = {
                    'name': comp.get('compLinkName', ''),
                    'label': comp.get('labelName', comp.get('compLinkName', '')),
                    'data_type': self._map_zoho_type(comp.get('compType', '')),
                    'path': f"{form_name}.{comp.get('compLinkName', '')}",
                    'form': form_name,
                    'required': comp.get('isMandatory', False),
                }
                fields.append(field)

        except Exception as e:
            _logger.warning(f"Failed to get fields for {form_name}: {e}")

        return fields

    def _map_zoho_type(self, zoho_type: str) -> str:
        """Map Zoho component type to standard data type."""
        type_mapping = {
            'Text': 'string',
            'Textarea': 'string',
            'Email': 'string',
            'Phone': 'string',
            'Number': 'number',
            'Currency': 'number',
            'Decimal': 'number',
            'Percent': 'number',
            'Date': 'date',
            'DateTime': 'date',
            'Checkbox': 'boolean',
            'Picklist': 'string',
            'Lookup': 'string',
        }
        return type_mapping.get(zoho_type, 'string')

    # ==========================================
    # EMPLOYEE DATA
    # ==========================================

    def fetch_employees(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Fetch employee data from Zoho People.

        Args:
            filters: Optional filter criteria (e.g., department, status)

        Returns:
            List of employee data dictionaries
        """
        if not self.authenticate():
            return []

        employees = []

        try:
            url = f"{self.BASE_URL}/forms/P_Employee/records"

            params = {
                'sIndex': 1,
                'limit': 200,
            }

            # Apply filters
            if filters:
                if 'status' in filters:
                    params['searchField'] = 'Employeestatus'
                    params['searchOperator'] = 'Is'
                    params['searchText'] = filters['status']

            while True:
                response = requests.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=60
                )

                if response.status_code != 200:
                    _logger.error(f"Failed to fetch employees: {response.status_code}")
                    break

                data = response.json()
                records = data.get('response', {}).get('result', [])

                if not records:
                    break

                for record in records:
                    emp = self._parse_employee_record(record)
                    employees.append(emp)

                # Check for more records
                if len(records) < params['limit']:
                    break

                params['sIndex'] += params['limit']

        except Exception as e:
            _logger.exception("Failed to fetch employees")

        return employees

    def _parse_employee_record(self, record: Dict) -> Dict[str, Any]:
        """
        Parse a Zoho employee record into standard format.

        Args:
            record: Raw Zoho record

        Returns:
            Standardized employee dictionary
        """
        return {
            'id': record.get('Zoho_ID', record.get('recordId', '')),
            'employee_id': record.get('EmployeeID', ''),
            'name': record.get('Name', ''),
            'first_name': record.get('FirstName', ''),
            'last_name': record.get('LastName', ''),
            'email': record.get('EmailID', ''),
            'department': record.get('Department', ''),
            'designation': record.get('Designation', ''),
            'date_of_joining': record.get('Dateofjoining', ''),
            'employment_status': record.get('Employeestatus', ''),
            'reporting_to': record.get('Reporting_To', ''),
            'location': record.get('Location', ''),
            # Raw data for custom field access
            '_raw': record,
        }

    # ==========================================
    # PAYROLL DATA
    # ==========================================

    def fetch_payroll_data(
        self,
        employee_ids: List[str],
        date_from: str,
        date_to: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch payroll-related data for employees.

        Args:
            employee_ids: List of Zoho employee IDs
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            Dict mapping employee_id to payroll data
        """
        if not self.authenticate():
            return {}

        payroll_data = {}

        for emp_id in employee_ids:
            try:
                data = {
                    'employee_id': emp_id,
                    'salary': self._get_employee_salary(emp_id),
                    'attendance': self._get_employee_attendance(emp_id, date_from, date_to),
                    'leave': self._get_employee_leave(emp_id, date_from, date_to),
                }
                payroll_data[emp_id] = data

            except Exception as e:
                _logger.warning(f"Failed to fetch payroll data for {emp_id}: {e}")
                payroll_data[emp_id] = {'error': str(e)}

        return payroll_data

    def _get_employee_salary(self, employee_id: str) -> Dict[str, Any]:
        """
        Get salary details for an employee.

        Args:
            employee_id: Zoho employee ID

        Returns:
            Salary data dictionary
        """
        try:
            url = f"{self.BASE_URL}/forms/P_Salary/records"
            params = {
                'searchField': 'Employee_ID.Zoho_ID',
                'searchOperator': 'Is',
                'searchText': employee_id,
            }

            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                records = data.get('response', {}).get('result', [])
                if records:
                    return records[0]

        except Exception as e:
            _logger.warning(f"Failed to get salary for {employee_id}: {e}")

        return {}

    def _get_employee_attendance(
        self,
        employee_id: str,
        date_from: str,
        date_to: str
    ) -> List[Dict[str, Any]]:
        """
        Get attendance records for an employee.

        Args:
            employee_id: Zoho employee ID
            date_from: Start date
            date_to: End date

        Returns:
            List of attendance records
        """
        try:
            url = f"{self.BASE_URL}/attendance/getAttendanceByDate"
            params = {
                'empId': employee_id,
                'sdate': date_from,
                'edate': date_to,
            }

            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('response', {}).get('result', [])

        except Exception as e:
            _logger.warning(f"Failed to get attendance for {employee_id}: {e}")

        return []

    def _get_employee_leave(
        self,
        employee_id: str,
        date_from: str,
        date_to: str
    ) -> List[Dict[str, Any]]:
        """
        Get leave records for an employee.

        Args:
            employee_id: Zoho employee ID
            date_from: Start date
            date_to: End date

        Returns:
            List of leave records
        """
        try:
            url = f"{self.BASE_URL}/leave/getLeaveDetails"
            params = {
                'empId': employee_id,
                'fromDate': date_from,
                'toDate': date_to,
            }

            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('response', {}).get('result', [])

        except Exception as e:
            _logger.warning(f"Failed to get leave for {employee_id}: {e}")

        return []

    # ==========================================
    # OAUTH FLOW HELPERS
    # ==========================================

    def get_authorization_url(self) -> str:
        """
        Get OAuth authorization URL for initial setup.

        Returns:
            Authorization URL to redirect user to
        """
        redirect_uri = self.connector.oauth_redirect_uri or \
                       f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/zoho/callback"

        scope = self.connector.oauth_scope or \
                "ZOHOPEOPLE.forms.READ,ZOHOPEOPLE.attendance.READ,ZOHOPEOPLE.leave.READ"

        params = {
            'client_id': self.connector.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scope,
            'access_type': 'offline',
            'prompt': 'consent',
        }

        param_str = '&'.join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}/auth?{param_str}"

    def exchange_code_for_tokens(self, code: str) -> bool:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            True if exchange successful
        """
        try:
            redirect_uri = self.connector.oauth_redirect_uri or \
                           f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/zoho/callback"

            url = f"{self.AUTH_URL}/token"
            data = {
                'code': code,
                'client_id': self.connector.client_id,
                'client_secret': self.connector.client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            }

            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            result = response.json()

            if 'access_token' not in result:
                _logger.error(f"Token exchange failed: {result}")
                return False

            expires_in = result.get('expires_in', 3600)

            self.connector.sudo().write({
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token', ''),
                'token_expiry': datetime.now() + timedelta(seconds=expires_in),
                'connection_status': 'connected',
            })

            return True

        except Exception as e:
            _logger.exception("Token exchange failed")
            self.update_connector_status('error', str(e))
            return False
