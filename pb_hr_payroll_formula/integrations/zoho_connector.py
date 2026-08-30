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


class ZohoApiError(RuntimeError):
    """Zoho answered, and the answer was a refusal.

    A distinct type because the interesting property of a Zoho failure is that
    it does NOT arrive as an HTTP status. `forms/P_Employee/records` — the path
    this connector shipped with — answers `200 OK` with the body
    `[{"message":"Invalid View Name","errorcode":7012,"Response status":2}]`,
    and `attendance/getUserReport` answers `200 OK` with `{"error":"Invalid
    User."}`. Anything that only checks `status_code` reads those as success.
    """


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

    # The paths this connector falls back to when a feed row carries none.
    # Every one of them was executed against a live Zoho People tenant on
    # 2026-08-26 — see `docs/ZOHO_API_PATHS.md` for the responses. The four
    # marked (was …) replace a path that Zoho refuses; they are corrected on
    # existing databases by migration 19.0.1.84.0.
    EMPLOYEE_PATH = 'forms/employee/getRecords'            # was forms/P_Employee/records
    SALARY_PATH = 'forms/salary_details/getRecords'        # was forms/P_Salary/records
    LEAVE_PATH = 'forms/leave/getRecords'                  # was leave/getLeaveDetails
    ATTENDANCE_DAILY_PATH = 'attendance/getUserReport'     # was attendance/getAttendanceByDate
    ATTENDANCE_SUMMARY_PATH = 'attendance/getSummaryReport'
    OVERTIME_PATH = 'forms/overtime_request/getRecords'
    TIMESHEET_PATH = 'timetracker/gettimesheet'

    # Zoho's form APIs page at 200 rows. The cap is a runaway guard, not a
    # policy: a feed that legitimately exceeds it says so in the log rather
    # than returning a quietly truncated list.
    PAGE_SIZE = 200
    MAX_PAGES = 200

    # The Zoho form each catalogued feed reads, for field discovery. The link
    # names are the tenant's own (`GET /forms`), NOT the `P_`-prefixed internal
    # names this connector used to guess at: `P_Salary` and `P_Attendance` are
    # both rejected with "Form name is invalid".
    FORM_BY_ENDPOINT = {
        'zohoemployees': 'employee',
        'zohosalary': 'salary_details',
        'zoholeave': 'leave',
        'zohoovertime': 'overtime_request',
    }

    def __init__(self, connector_record):
        super().__init__(connector_record)
        self.access_token = None
        self.token_expiry = None
        # One whole-form leave read per pull, not one per employee — see
        # `_leave_rows`.
        self._leave_cache_key = None
        self._leave_cache = []
        # RD51 — the whole salary form, read once per pull. `None` means "not
        # read yet"; an empty dict means "read and it told us nothing", and the
        # two must stay distinguishable or a failed read would be cached as an
        # answer.
        self._salary_cache = None

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
    # RESPONSE CONTRACT
    # ==========================================

    # Zoho reports "there is nothing here" as an ERROR: code 7024, message
    # "No records found", `status: 1`, HTTP 200. It is returned by an employee
    # with no overtime this month exactly as it is by a form that is empty, and
    # by the page AFTER the last page of any paginated feed. Reading it as a
    # failure would make an ordinary quiet month look broken — which is the
    # mirror image of the bug this file is being corrected for, so it gets the
    # same care.
    EMPTY_ERROR_CODES = {7024}

    @classmethod
    def _zoho_is_empty(cls, payload) -> bool:
        """Is this Zoho's way of saying the result set is empty?"""
        codes = set()
        if isinstance(payload, dict):
            body = payload.get('response')
            body = body if isinstance(body, dict) else payload
            errors = body.get('errors')
            if isinstance(errors, dict):
                errors = [errors]
            if isinstance(errors, list):
                codes = {e.get('code') for e in errors if isinstance(e, dict)}
        elif isinstance(payload, list):
            codes = {item.get('errorcode') for item in payload
                     if isinstance(item, dict)}
        codes.discard(None)
        return bool(codes) and codes <= cls.EMPTY_ERROR_CODES

    @classmethod
    def _zoho_error(cls, payload) -> str:
        """The sentence Zoho refused with, or '' if this payload is data.

        Four shapes, all observed on one tenant in one afternoon, all of them
        arriving with a 2xx status on at least one endpoint:

          `[{"message": …, "errorcode": 7012, "Response status": 2}]`
              a form/view name the tenant does not have;
          `{"response": {"errors": {"code": 7201, "message": …}, "status": 1}}`
              a path that does not exist (usually served as 404, but the body
              is the only thing that says *why*);
          `{"response": {"errors": [{"code": 9002, …}], "status": 1}}`
              the same, with the errors as a list — `timetracker/gettimesheet`
              answers this, with 200, when the `user` parameter is missing;
          `{"error": "Invalid User."}`
              `attendance/getUserReport` given an id it does not recognise.

        `status` 0 and `Response status` 1 mean success, so neither is tested
        for truthiness — only for the explicit failure value. An emptiness
        signal is not a refusal and is filtered out first.
        """
        if cls._zoho_is_empty(payload):
            return ''
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                if 'errorcode' in item or str(item.get('Response status')) == '2':
                    return str(item.get('message') or
                               item.get('errorcode') or 'Zoho refused the call')
            return ''
        if not isinstance(payload, dict):
            return ''
        if isinstance(payload.get('error'), str) and payload['error']:
            return payload['error']
        body = payload.get('response')
        body = body if isinstance(body, dict) else payload
        errors = body.get('errors')
        if isinstance(errors, dict):
            errors = [errors]
        if isinstance(errors, list) and errors:
            parts = [str(e.get('message') or e.get('code'))
                     for e in errors if isinstance(e, dict)]
            joined = '; '.join(p for p in parts if p)
            if joined:
                return joined
        if str(body.get('status')) == '1':
            return str(body.get('message') or 'Zoho refused the call')
        return ''

    def _payload(self, response, what: str):
        """The decoded body of a Zoho response, or `ZohoApiError`.

        Every read goes through here. Before this existed each fetch method
        did its own `if status_code == 200: data.get('response', {})…` inside a
        bare `except: return []`, which is how a wrong path became an empty
        result set instead of a message: the malformed body raised
        `AttributeError: 'list' object has no attribute 'get'`, the except
        swallowed it, the feed stamped `success` and the cockpit showed
        `0 staged · 0 pulled` with no error anywhere a user could see.
        """
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if payload is not None and self._zoho_is_empty(payload):
            # Normalised to a real empty result set rather than handed on: the
            # body still carries an `errors` key, and `_result_rows` would
            # otherwise turn that key into a fabricated row.
            return {'response': {'result': []}}
        problem = self._zoho_error(payload) if payload is not None else ''
        if problem:
            raise ZohoApiError("%s: %s" % (what, problem))
        if response.status_code >= 400:
            raise ZohoApiError("%s: Zoho returned HTTP %s" % (
                what, response.status_code))
        if payload is None:
            raise ZohoApiError(
                "%s: Zoho returned a non-JSON response (HTTP %s)" % (
                    what, response.status_code))
        return payload

    def _paged_form_rows(self, code: str, fallback_path: str, what: str,
                         params: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Every row of a Zoho FORM feed, following `sIndex`/`limit`.

        Form responses nest one level deeper than they look —
        `result: [{"<recordId>": [{…the fields…}]}]` — which `_result_rows`
        unwraps. Paging stops on a short page, and `MAX_PAGES` bounds a feed
        whose vendor ignores the window (Zoho's form search silently ignores
        `searchField`/`searchOperator` on a date column, so several of these
        feeds are whole-form reads by nature).
        """
        rows: List[Dict[str, Any]] = []
        sindex = 1
        for page in range(self.MAX_PAGES):
            request_params = dict(params or {},
                                  sIndex=sindex, limit=self.PAGE_SIZE)
            response = self._feed_request(code, fallback_path,
                                          params=request_params, timeout=60)
            page_rows = self._result_rows(self._payload(response, what))
            rows.extend(page_rows)
            if len(page_rows) < self.PAGE_SIZE:
                return rows
            sindex += self.PAGE_SIZE
        _logger.warning(
            "Zoho feed %s stopped at the %s-page limit (%s rows). Narrow the "
            "feed or raise MAX_PAGES.", code, self.MAX_PAGES, len(rows))
        return rows

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
        for form_name in self.FORM_BY_ENDPOINT.values():
            fields.extend(self._get_form_fields(form_name))
        return fields

    def _get_form_fields(self, form_name: str) -> List[Dict[str, Any]]:
        """
        Get fields for a specific Zoho form.

        Args:
            form_name: Zoho form link name, as listed by `GET /forms`

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
            components = self._payload(
                response, f"the {form_name} form layout")
            components = components.get('response', {}).get('result', []) \
                if isinstance(components, dict) else []

            # Zoho's component keys are ALL LOWERCASE — `labelname`,
            # `displayname`, `comptype`, `ismandatory`. This method used to
            # read `compLinkName`/`labelName`/`compType`/`isMandatory`, so
            # every field came back nameless and was dropped: "Fetch fields"
            # answered "That system returned no fields for this feed" on a
            # form that had just described sixty of them.
            for comp in components:
                if not isinstance(comp, dict):
                    continue
                name = (comp.get('labelname') or '').strip()
                if not name:
                    continue
                field = {
                    'name': name,
                    'label': (comp.get('displayname') or '').strip() or name,
                    'data_type': self._map_zoho_type(comp.get('comptype', '')),
                    'path': f"{form_name}.{name}",
                    'form': form_name,
                    'required': bool(comp.get('ismandatory')),
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
            raise ZohoApiError(
                "Zoho would not authenticate this connection. Check the "
                "client id, client secret and refresh token.")

        params = {
            # The legacy ABM application asked for ISO dates and parsed them as
            # ISO (om_hr_payroll/models/hr_zoho_staging.py:317). Without this
            # Zoho answers dd/MM/yyyy and every date lands as text.
            'dateFormat': 'yyyy-MM-dd',
        }
        if filters and 'status' in filters:
            params.update({
                'searchField': 'Employeestatus',
                'searchOperator': 'Is',
                'searchText': filters['status'],
            })
        rows = self._paged_form_rows(
            'zohoemployees', self.EMPLOYEE_PATH, "the employee form", params)
        return [self._parse_employee_record(row) for row in rows]

    def _parse_employee_record(self, record: Dict) -> Dict[str, Any]:
        """
        Parse a Zoho employee record into standard format.

        Args:
            record: One employee's field dict, already unwrapped out of the
                `{"<recordId>": [ … ]}` envelope by `_result_rows`.

        Returns:
            Standardized employee dictionary
        """
        first = record.get('FirstName') or ''
        last = record.get('LastName') or ''
        return {
            # `Zoho_ID` arrives as a JSON number on some forms, so it is made a
            # string here rather than at each of the four places that compare it.
            'id': str(record.get('Zoho_ID') or record.get('recordId') or ''),
            'employee_id': record.get('EmployeeID', ''),
            'name': record.get('Name') or ' '.join(p for p in (first, last) if p),
            'first_name': first,
            'last_name': last,
            'email': record.get('EmailID', ''),
            'department': record.get('Department', ''),
            'designation': record.get('Designation', ''),
            'date_of_joining': record.get('Dateofjoining', ''),
            'employment_status': record.get('Employeestatus', ''),
            'reporting_to': record.get('Reporting_To', ''),
            'location': record.get('LocationName', record.get('Location', '')),
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
        date_to: str,
        kinds: Optional[List[str]] = None,
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
            raise ZohoApiError(
                "Zoho would not authenticate this connection. Check the "
                "client id, client secret and refresh token.")

        payroll_data = {}

        # RD49 — DON'T FETCH WHAT NOTHING READS.
        #
        # This loop is the slow part of a sync: one employee at a time, THREE
        # requests each. For 152 people that is 456 sequential HTTP round trips
        # and several minutes of somebody waiting to run payroll.
        #
        # A third of them were pure waste. `kinds` is the set of feed kinds the
        # connector's wires actually point at, and on the reference tenant no
        # component reads a leave field at all — yet leave was pulled for every
        # employee, every time. `None` means "no caller opinion" and keeps the
        # historic behaviour of fetching everything, so nothing changes for a
        # caller that has not been taught to ask.
        wanted = set(kinds) if kinds else {'salary', 'attendance', 'leave'}
        skipped = {'salary', 'attendance', 'leave'} - wanted
        if skipped:
            _logger.info(
                "Zoho payroll pull: skipping %s for %s employees — no active "
                "mapping reads them (saves ~%s requests)",
                ', '.join(sorted(skipped)), len(employee_ids),
                len(skipped) * len(employee_ids))

        for emp_id in employee_ids:
            try:
                data = {'employee_id': emp_id}
                if 'salary' in wanted:
                    data['salary'] = self._get_employee_salary(emp_id)
                if 'attendance' in wanted:
                    data['attendance'] = self._get_employee_attendance(
                        emp_id, date_from, date_to)
                if 'leave' in wanted:
                    data['leave'] = self._get_employee_leave(
                        emp_id, date_from, date_to)
                payroll_data[emp_id] = data

            except Exception as e:
                _logger.warning(f"Failed to fetch payroll data for {emp_id}: {e}")
                payroll_data[emp_id] = {'error': str(e)}

        return payroll_data

    def _salary_index(self) -> Dict[str, Dict[str, Any]]:
        """The WHOLE salary form, read once and indexed by employee.

        RD51 — this is the expensive half of a sync. `_get_employee_salary`
        asks Zoho for ONE employee's salary row, so a 152-person tenant makes
        152 sequential requests for a form that fits in one page of 200. The
        whole form is one or two requests, and matching is arithmetic.

        (Leave was already read this way — `_leave_rows`, whole form, cached.
        Attendance genuinely has no bulk endpoint on this plan: `getUserReport`
        is per user. So salary is the one that can be collapsed.)

        INDEXED UNDER EVERY NAME THE CALLER MIGHT USE. A salary row carries the
        employee's NUMBER in `Employee_ID` ('11708') and the employee record's
        Zoho id in `Employee_ID.ID` ('811648000007178001'), and callers hold
        one or the other depending on which feed they came from. Indexing both
        is cheaper than being wrong about which one arrives.

        ORDER IS PRESERVED, not re-sorted. The per-employee search returned
        `rows[0]`, so the bulk read keeps the FIRST row per employee for the
        same reason — an employee with a salary history would otherwise
        silently change which revision payroll used. Extra rows are counted and
        logged, because "this tenant has salary history" is something the
        person running payroll should be told rather than have decided for
        them.
        """
        if self._salary_cache is not None:
            return self._salary_cache
        index: Dict[str, Dict[str, Any]] = {}
        extras = 0
        try:
            rows = self._paged_form_rows(
                'zohosalary', self.SALARY_PATH, "the salary form",
                {'dateFormat': 'yyyy-MM-dd'})
        except Exception as exc:            # noqa: BLE001
            # A failed bulk read must not lose the sync: the caller falls back
            # to asking per employee, which is what it did before this existed.
            _logger.warning("Zoho salary bulk read failed (%s); "
                            "falling back to one request per employee.", exc)
            self._salary_cache = {}
            return self._salary_cache
        for row in rows:
            keys = {str(row.get('Employee_ID') or '').strip(),
                    str(row.get('Employee_ID.ID') or '').strip()}
            claimed = False
            for key in keys:
                if not key:
                    continue
                if key in index:
                    continue
                index[key] = row
                claimed = True
            if not claimed and keys - {''}:
                extras += 1
        _logger.info(
            "Zoho salary form read in bulk: %s rows, %s employees indexed, "
            "%s later revisions ignored (the first row per employee wins, as "
            "the per-employee search did).", len(rows), len(index), extras)
        self._salary_cache = index
        return index

    def _get_employee_salary(self, employee_id: str) -> Dict[str, Any]:
        """
        Get salary details for an employee.

        Args:
            employee_id: Zoho employee ID

        Returns:
            Salary data dictionary
        """
        # RD51 — the whole form, read once and matched here. See `_salary_index`
        # for why this replaced a per-employee request entirely.
        index = self._salary_index()
        hit = index.get(str(employee_id or '').strip())
        if hit is not None:
            return hit
        # RD51 — THE FALLBACK IS DELIBERATELY EMPTY, NOT A SEARCH.
        #
        # What used to be here searched `searchField='Employee_ID.Zoho_ID'`.
        # That field DOES NOT EXIST on the salary form — the real ones are
        # `Employee_ID` (the employee number) and `Employee_ID.ID` (the record
        # id). Zoho does not reject an unknown search field: it ignores it and
        # returns the first page of the whole form. So `rows[0]` was THE SAME
        # ROW for every employee, and every person in the tenant was given one
        # person's salary — ₫12,500,000 across all 152 contracts on the
        # reference tenant, where Zoho actually holds 60 different values
        # between ₫10,033,520 and ₫117,978,000.
        #
        # A search that cannot be trusted to filter must not be used as a
        # fallback: it would silently reinstate the defect for exactly the
        # employees the bulk read could not place. Returning nothing is honest,
        # and `_transform_data_to_formula_inputs` already treats a missing
        # value as "this source said nothing" and falls through to the next
        # rung of the ladder.
        _logger.warning(
            "Zoho salary: no row for employee %s in the salary form. Returning "
            "nothing rather than guessing — the per-employee search this "
            "replaced returned the same row for everybody.", employee_id)
        return {}

    def _get_employee_attendance(
        self,
        employee_id: str,
        date_from: str,
        date_to: str,
        employee_number: Optional[str] = None,
        email: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get day-by-day attendance for one employee.

        Zoho's `empId` here is the EMPLOYEE NUMBER on the employee form
        (`EmployeeID`, e.g. `11708`) — passing the record id (`Zoho_ID`,
        `811648…`) is answered with `{"error": "Invalid User."}` and an HTTP
        200. `emailId` is accepted as an alternative and is what the caller
        supplies when a record has no employee number.

        Args:
            employee_id: Zoho record id, used only as a last resort
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            employee_number: the employee's `EmployeeID`, preferred
            email: the employee's `EmailID`, used when there is no number

        Returns:
            List of attendance records, one per day
        """
        params = {
            'sdate': self._period(date_from),
            'edate': self._period(date_to),
            'dateFormat': 'dd-MM-yyyy',
        }
        if employee_number:
            params['empId'] = employee_number
        elif email:
            params['emailId'] = email
        else:
            params['empId'] = employee_id
        response = self._feed_request(
            'zohoattdaily', self.ATTENDANCE_DAILY_PATH, params=params)
        # The response is keyed BY DATE rather than being a list;
        # `_result_rows` carries each key through as `_result_key`.
        return self._result_rows(
            self._payload(response, "the daily attendance report"))

    def _leave_rows(self, date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """Every leave record overlapping the window, for the whole company.

        There is no per-employee leave API on this plan: `leave/getLeaveDetails`
        and `leave/getRecords` are both 404s, and the leave FORM ignores
        `searchField=From&searchOperator=Between` (a January-2020 window returns
        the same first page as no window at all). So the window is applied
        HERE, on `From`/`To`, and the whole-form read is done once per pull and
        cached — asking per employee would be one full-form read per employee.
        """
        cache_key = (date_from, date_to)
        if getattr(self, '_leave_cache_key', None) == cache_key:
            return self._leave_cache
        rows = self._paged_form_rows(
            'zoholeave', self.LEAVE_PATH, "the leave form",
            {'dateFormat': 'yyyy-MM-dd'})
        window = [row for row in rows
                  if self._overlaps(row.get('From'), row.get('To'),
                                    date_from, date_to)]
        self._leave_cache_key = cache_key
        self._leave_cache = window
        return window

    # The date each overtime row is ABOUT, in the order it should be trusted.
    # `OT_Date` is the day worked; the start/end stamps are the fallback for a
    # row that predates it.
    OVERTIME_DATE_KEYS = ('OT_Date', 'Start_Date_Time', 'End_Date_Time')

    @classmethod
    def _within_window(cls, rows: List[Dict[str, Any]],
                       date_from: str, date_to: str) -> List[Dict[str, Any]]:
        """Overtime rows that fall inside the period, filtered HERE.

        Zoho's overtime form accepts `fromDate`/`toDate` and ignores them, in
        exactly the way its form search accepts a date filter and ignores it.
        Measured on ABM: asking for June 2026, July 2026 and August 2026 each
        returned the SAME 201 rows, whose `OT_Date` values run from August 2024
        to March 2026 — not one of them in any month asked for.

        Unfiltered, every one of those hours would have been added to whichever
        month was being run, and to every other month as well. A silently
        ignored parameter is worse than an unsupported one, so the window is
        applied here where it can be seen.

        A row whose date cannot be read is DROPPED rather than kept — the
        opposite of the leave rule, and deliberately: a leave record with an
        unreadable date is a payroll input that would be lost, while an
        overtime row with no date has no claim on any particular month and
        keeping it would put it in all of them.
        """
        def day(value):
            text = str(value or '').strip()[:10]
            for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y'):
                try:
                    return datetime.strptime(text, fmt).date()
                except (TypeError, ValueError):
                    continue
            return None

        start, end = day(date_from), day(date_to)
        if not (start and end):
            return rows
        kept, undated = [], 0
        for row in rows:
            when = next((day(row.get(k)) for k in cls.OVERTIME_DATE_KEYS
                         if day(row.get(k))), None)
            if when is None:
                undated += 1
                continue
            if start <= when <= end:
                kept.append(row)
        if undated:
            _logger.info(
                "Overtime: %s row(s) carried no readable date and were left "
                "out of %s–%s.", undated, start, end)
        return kept

    @staticmethod
    def _ref_index(refs: List[Dict[str, str]]) -> Dict[str, str]:
        """Every identifier a Zoho row might carry, pointing at the record id.

        The employee master and the salary form key their rows on the Zoho
        RECORD id (`811648…`). The attendance summary keys its rows on the
        employee NUMBER (`11708`) and the email address, and the generic reader
        resolved only email — so an attendance row arrived under `11708`, an
        employee row under `811648…`, and the two never joined. On ABM that put
        42 attendance rows into the import as 42 extra people with no name and
        no salary, while 152 real employees had no worked hours.

        One index, all three spellings, so a feed can be keyed on whichever of
        them the vendor happens to use.
        """
        index = {}
        for ref in refs:
            record_id = str(ref.get('id') or '')
            if not record_id:
                continue
            for identifier in (ref.get('email'), ref.get('employee_id'), record_id):
                key = str(identifier or '').strip().lower()
                if key:
                    index.setdefault(key, record_id)
        return index

    @classmethod
    def _resolve_ext(cls, value: Dict[str, Any], index: Dict[str, str]) -> str:
        """The record id this row belongs to, from whichever key it carries."""
        candidates = [value.get('employeeId'), value.get('EmployeeID'),
                      value.get('empId'), value.get('emailId'),
                      value.get('_result_key')]
        for candidate in candidates:
            key = str(candidate or '').strip().lower()
            if key and key in index:
                return index[key]
        # Nothing matched a known employee. The raw identifier is kept rather
        # than blanked, so the row is still traceable to whatever the vendor
        # called it instead of silently becoming unattributed.
        for candidate in candidates:
            if str(candidate or '').strip():
                return str(candidate).strip()
        return ''

    @staticmethod
    def _overlaps(row_from, row_to, date_from, date_to) -> bool:
        """Does `[row_from, row_to]` touch `[date_from, date_to]`?

        A row whose dates cannot be read is KEPT. Dropping a leave record
        because its date did not parse would silently shorten a payroll input,
        which is the failure mode this whole file is being corrected for.
        """
        def iso(value):
            try:
                return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
            except (TypeError, ValueError):
                return None
        start, end = iso(row_from), iso(row_to)
        window_start, window_end = iso(date_from), iso(date_to)
        if not (window_start and window_end):
            return True
        start = start or end
        end = end or start
        if not start:
            return True
        return start <= window_end and end >= window_start

    def _get_employee_leave(
        self,
        employee_id: str,
        date_from: str,
        date_to: str
    ) -> List[Dict[str, Any]]:
        """
        Get leave records for one employee, out of the company-wide form read.

        Args:
            employee_id: Zoho employee record id
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)

        Returns:
            List of leave records
        """
        wanted = str(employee_id or '')
        return [row for row in self._leave_rows(date_from, date_to)
                if str(row.get('Employee_ID.ID') or '') == wanted]

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
        if operation in ('salary', 'attendance_daily', 'leave', 'overtime',
                         'timesheet'):
            # Each of these asks Zoho about ONE employee at a time, so a feed
            # run before the Employees feed has landed has nobody to ask about
            # and would otherwise report a clean zero — the same silence this
            # file is being corrected for, one step further along.
            self._require_employee_refs(refs, endpoint)

        if operation in ('salary', 'attendance_daily', 'leave'):
            failures = []
            for ref in refs:
                employee_id = ref.get('id') or ''
                try:
                    if operation == 'salary':
                        values = self._get_employee_salary(employee_id)
                        values = [values] if values else []
                    elif operation == 'attendance_daily':
                        values = self._get_employee_attendance(
                            employee_id, date_from, date_to,
                            employee_number=ref.get('employee_id'),
                            email=ref.get('email'))
                    else:
                        values = self._get_employee_leave(
                            employee_id, date_from, date_to)
                except ZohoApiError as error:
                    failures.append(str(error))
                    continue
                for value in values:
                    rows.append({'payload': value,
                                 'employee_external_id': str(employee_id)})
            self._report_failures(failures, refs, rows)
            return rows

        params = {}
        if operation == 'attendance_summary':
            params = {
                'startDate': self._period(date_from),
                'endDate': self._period(date_to),
                'dateFormat': 'dd-MM-yyyy',
            }
        elif operation in ('overtime', 'timesheet'):
            failures, addressable = [], 0
            for ref in refs:
                email = ref.get('email') or ''
                if not email:
                    continue
                addressable += 1
                if operation == 'overtime':
                    params = {
                        'sIndex': 1, 'limit': self.PAGE_SIZE,
                        'searchColumn': 'EMPLOYEEMAILALIAS',
                        'searchValue': email, 'dateFormat': 'dd-MM-yyyy',
                        'fromDate': self._period(date_from),
                        'toDate': self._period(date_to),
                    }
                    what = "the overtime form"
                else:
                    # `timetracker/gettimesheet` answers HTTP 200 with
                    # "No user parameter specified." unless `user` is given —
                    # the reason this feed shipped catalogue-only.
                    params = {
                        'user': email,
                        'fromDate': self._period(date_from),
                        'toDate': self._period(date_to),
                        'dateFormat': 'dd-MM-yyyy',
                    }
                    what = "the timesheet report"
                try:
                    response = self._feed_request(
                        endpoint.code, endpoint.path or '', params=params,
                        timeout=60)
                    values = self._result_rows(self._payload(response, what))
                except ZohoApiError as error:
                    failures.append(str(error))
                    continue
                if operation == 'overtime':
                    values = self._within_window(values, date_from, date_to)
                for value in values:
                    rows.append({
                        'payload': value,
                        'employee_external_id': str(ref.get('id') or email),
                    })
            if not addressable:
                raise ZohoApiError(
                    "%s is looked up by employee email address, and none of "
                    "the %s stored employee records has one. Re-sync the "
                    "Employees feed." % (endpoint.name or endpoint.code,
                                         len(refs)))
            self._report_failures(failures, refs, rows)
            return rows

        response = requests.request(
            (endpoint.http_method or 'get').upper(),
            self._endpoint_url(endpoint.code, endpoint.path or ''),
            headers=self._get_headers(),
            params=params if (endpoint.http_method or 'get') == 'get' else None,
            json=params if (endpoint.http_method or 'get') == 'post' else None,
            timeout=60,
        )
        payload = self._payload(response, endpoint.name or endpoint.code)
        index = self._ref_index(refs)
        for value in self._result_rows(payload):
            rows.append({'payload': value,
                         'employee_external_id': self._resolve_ext(value, index)})
        return rows

    # ------------------------------------------------ per-employee feed rails
    @staticmethod
    def _require_employee_refs(refs, endpoint):
        """A per-employee feed with no employees is a failure, not a zero.

        Every Zoho feed except Employees and the attendance summary is a
        per-employee lookup, so all six of them return a clean, wordless zero
        on a connector whose employee store is empty. That is exactly what the
        broken employee path produced, and the cockpit reported it as
        `0 staged · 0 pulled` on six cards at once with no cause named
        anywhere.
        """
        if not refs:
            raise ZohoApiError(
                "%s is pulled one employee at a time and this connection has "
                "no stored employees yet. Sync the Employees feed first."
                % (endpoint.name or endpoint.code))

    @staticmethod
    def _report_failures(failures, refs, rows):
        """Say what went wrong when a per-employee sweep partly or wholly failed.

        Partial failure stays a warning in the log and lets the good rows
        through; total failure is raised, because a feed that could not read a
        single employee has nothing to distinguish it from an empty period.
        """
        if not failures:
            return
        if not rows:
            raise ZohoApiError(
                "None of the %s employees could be read. First error: %s"
                % (len(refs), failures[0]))
        _logger.warning(
            "Zoho feed: %s of %s employees failed, %s rows kept. First "
            "error: %s", len(failures), len(refs), len(rows), failures[0])

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
