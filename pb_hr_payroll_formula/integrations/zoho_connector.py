# -*- coding: utf-8 -*-
"""
Zoho People Connector - Full implementation for Zoho People API integration.
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
from urllib.parse import urlencode, urljoin

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
    # CONFIGURED URL RESOLUTION
    # ==========================================

    def _base_url(self) -> str:
        """The tenant's configured API root, with the legacy root as fallback."""
        return (self.connector.api_endpoint or self.BASE_URL).rstrip('/')

    def _auth_url(self, leaf: str) -> str:
        """Resolve OAuth URLs from connector configuration before defaults."""
        configured = (self.connector.oauth_token_url if leaf == 'token'
                      else self.connector.oauth_authorize_url)
        if configured:
            return configured.strip()
        return f"{self.AUTH_URL}/{leaf}"

    def _redirect_uri(self) -> str:
        """Return the exact provider callback without accidental double slashes."""
        if self.connector.oauth_redirect_uri:
            return self.connector.oauth_redirect_uri.strip()
        web_base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '').rstrip('/')
        return f"{web_base}/zoho/callback"

    def _endpoint_url(self, code: str, fallback_path: str) -> str:
        """Resolve one feed through its connector-specific catalogue record.

        Existing databases are safe: an absent endpoint or blank path uses the
        exact path the connector used before feeds became executable.
        """
        endpoint = self.connector.endpoint_ids.filtered(
            lambda row: row.active and row.code == code)[:1]
        path = (endpoint.path if endpoint and endpoint.path else fallback_path)
        if path.startswith(('http://', 'https://')):
            return path
        return urljoin(self._base_url() + '/', path.lstrip('/'))

    def _feed_request(self, code: str, fallback_path: str, params=None,
                      timeout=30):
        endpoint = self.connector.endpoint_ids.filtered(
            lambda row: row.active and row.code == code)[:1]
        method = (endpoint.http_method if endpoint else 'get') or 'get'
        return requests.request(
            method.upper(), self._endpoint_url(code, fallback_path),
            headers=self._get_headers(),
            params=params if method == 'get' else None,
            json=params if method == 'post' else None,
            timeout=timeout,
        )

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
            url = self._auth_url('token')

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
            url = urljoin(self._base_url() + '/', 'forms')
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
            # Form metadata has no feed of its own. It intentionally follows
            # the configured base while the data calls below follow feed paths.
            url = urljoin(self._base_url() + '/', f"forms/{form_name}/components")
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
                response = self._feed_request(
                    'zohoemployees', 'forms/P_Employee/records',
                    params=params, timeout=60)

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
            params = {
                'searchField': 'Employee_ID.Zoho_ID',
                'searchOperator': 'Is',
                'searchText': employee_id,
            }

            response = self._feed_request(
                'zohosalary', 'forms/P_Salary/records', params=params)

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
            params = {
                'empId': employee_id,
                'sdate': date_from,
                'edate': date_to,
            }

            response = self._feed_request(
                'zohoattdaily', 'attendance/getAttendanceByDate', params=params)

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
            params = {
                'empId': employee_id,
                'fromDate': date_from,
                'toDate': date_to,
            }

            response = self._feed_request(
                'zoholeave', 'leave/getLeaveDetails', params=params)

            if response.status_code == 200:
                data = response.json()
                return data.get('response', {}).get('result', [])

        except Exception as e:
            _logger.warning(f"Failed to get leave for {employee_id}: {e}")

        return []

    # ==========================================
    # FEED-SCOPED EXECUTION
    # ==========================================

    @staticmethod
    def _result_rows(payload) -> List[Dict[str, Any]]:
        """Normalise the common Zoho response envelopes without inventing data."""
        value = payload
        if isinstance(value, dict) and isinstance(value.get('summaryReport'), list):
            value = value.get('summaryReport') or []
        if isinstance(value, dict) and 'response' in value:
            value = value.get('response') or {}
        if isinstance(value, dict) and 'result' in value:
            value = value.get('result') or []
        if isinstance(value, list):
            rows = []
            for row in value:
                if not isinstance(row, dict):
                    continue
                nested = [item for group in row.values() if isinstance(group, list)
                          for item in group if isinstance(item, dict)]
                rows.extend(nested or [row])
            return rows
        if isinstance(value, dict):
            # Some report APIs key the result by employee/email.
            rows = []
            for key, row in value.items():
                if isinstance(row, dict):
                    rows.append(dict(row, _result_key=key))
                elif isinstance(row, list):
                    rows.extend(item for item in row if isinstance(item, dict))
            return rows or [value]
        return []

    @staticmethod
    def _period(value: str, fmt: str = '%d-%m-%Y') -> str:
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').strftime(fmt)
        except (TypeError, ValueError):
            return str(value or '')

    def fetch_endpoint_records(
        self, endpoint, employees: List[Dict[str, str]], date_from: str, date_to: str
    ) -> List[Dict[str, Any]]:
        """Execute the selected feed, returning store-ready envelopes.

        Every envelope has `payload` and an optional `employee_external_id`.
        The endpoint record supplies the URL; the operation supplies only the
        parameter strategy and response normalisation.
        """
        operation = endpoint.operation or 'catalog_only'
        if operation == 'catalog_only':
            raise ValueError("This feed is catalogue-only and has no runtime handler.")

        if operation == 'employee':
            return [
                {'payload': row,
                 'employee_external_id': str(row.get('id') or row.get('employee_id') or '')}
                for row in self.fetch_employees()
            ]

        refs = [item if isinstance(item, dict) else {'id': str(item), 'email': ''}
                for item in employees]
        rows = []
        if operation in ('salary', 'attendance_daily', 'leave'):
            for ref in refs:
                employee_id = ref.get('id') or ''
                if operation == 'salary':
                    values = self._get_employee_salary(employee_id)
                    values = [values] if values else []
                elif operation == 'attendance_daily':
                    values = self._get_employee_attendance(
                        employee_id, date_from, date_to)
                else:
                    values = self._get_employee_leave(
                        employee_id, date_from, date_to)
                for value in values:
                    rows.append({'payload': value,
                                 'employee_external_id': str(employee_id)})
            return rows

        params = {}
        if operation == 'attendance_summary':
            params = {
                'startDate': self._period(date_from),
                'endDate': self._period(date_to),
                'dateFormat': 'dd-MM-yyyy',
            }
        elif operation == 'overtime':
            for ref in refs:
                email = ref.get('email') or ''
                if not email:
                    continue
                params = {
                    'sIndex': 1, 'limit': 200,
                    'searchColumn': 'EMPLOYEEMAILALIAS',
                    'searchValue': email, 'dateFormat': 'dd-MM-yyyy',
                    'fromDate': self._period(date_from),
                    'toDate': self._period(date_to),
                }
                response = self._feed_request(
                    endpoint.code, endpoint.path or '', params=params, timeout=60)
                response.raise_for_status()
                for value in self._result_rows(response.json()):
                    rows.append({
                        'payload': value,
                        'employee_external_id': str(ref.get('id') or email),
                    })
            return rows
        elif operation == 'timesheet':
            params = {
                'startDate': self._period(date_from),
                'endDate': self._period(date_to),
                'dateFormat': 'dd-MM-yyyy',
            }

        response = requests.request(
            (endpoint.http_method or 'get').upper(),
            self._endpoint_url(endpoint.code, endpoint.path or ''),
            headers=self._get_headers(),
            params=params if (endpoint.http_method or 'get') == 'get' else None,
            json=params if (endpoint.http_method or 'get') == 'post' else None,
            timeout=60,
        )
        response.raise_for_status()
        email_to_id = {str(ref.get('email') or '').lower(): ref.get('id')
                       for ref in refs if ref.get('email')}
        for value in self._result_rows(response.json()):
            ext = (value.get('employeeId') or value.get('EmployeeID') or
                   value.get('empId') or value.get('emailId') or '')
            ext = email_to_id.get(str(ext).lower(), ext)
            rows.append({'payload': value, 'employee_external_id': str(ext)})
        return rows

    # ==========================================
    # OAUTH FLOW HELPERS
    # ==========================================

    def get_authorization_url(self, state: str = '') -> str:
        """
        Get OAuth authorization URL for initial setup.

        Returns:
            Authorization URL to redirect user to
        """
        redirect_uri = self._redirect_uri()

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
        if state:
            params['state'] = state

        param_str = urlencode(params)
        return f"{self._auth_url('auth')}?{param_str}"

    def exchange_code_for_tokens(self, code: str, token_url: str = '') -> bool:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            True if exchange successful
        """
        try:
            redirect_uri = self._redirect_uri()

            # A safe location-specific URL from the callback is used only when
            # the connector has no explicit token URL of its own.
            url = self.connector.oauth_token_url or token_url or self._auth_url('token')
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

            vals = {
                'access_token': result['access_token'],
                'token_expiry': datetime.now() + timedelta(seconds=expires_in),
                'connection_status': 'connected',
            }
            # Zoho may omit a refresh token on a later consent. Never erase a
            # working one merely because this response did not repeat it.
            if result.get('refresh_token'):
                vals['refresh_token'] = result['refresh_token']
            self.connector.sudo().write(vals)

            return True

        except Exception as e:
            _logger.exception("Token exchange failed")
            self.update_connector_status('error', str(e))
            return False
