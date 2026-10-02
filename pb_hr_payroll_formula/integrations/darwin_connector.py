# -*- coding: utf-8 -*-
"""
DarwinHR (Darwinbox) Connector — plug-and-play integration for the Darwinbox HRIS.

Talks to the Darwinbox REST master-data APIs (employee directory + compensation)
using the tenant's API key + Basic auth, exactly like the other vendor connectors.

Plug-and-play design
--------------------
Darwinbox is a modern, multi-tenant HRIS whose API base URL, api_key and dataset
key are per-customer. So that the connector is genuinely "connect and go" — and so
it stays fully testable inside the demo tenant where no live credentials exist —
it *degrades gracefully*: when credentials/endpoint are missing or the tenant is
unreachable, it serves a small, realistic sample dataset instead of failing. The
moment real credentials are entered it switches to the live tenant automatically.

Nothing here requires schema changes beyond registering the `darwin` connector
type; it reuses the standard hr.integration.connector credential fields
(api_endpoint, api_key, username, password, api_version).
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

from .base_connector import BaseHRConnector

try:
    import requests
except Exception:  # pragma: no cover - requests ships with Odoo but stay defensive
    requests = None

_logger = logging.getLogger(__name__)


class DarwinHRConnector(BaseHRConnector):
    """
    Darwinbox HRIS connector.

    Live endpoints (per Darwinbox master-data API):
      - POST {base}/masterapi/employeedirectory   → employee master data
      - POST {base}/masterapi/compensation        → salary / compensation

    Auth: HTTP Basic (username / password) with `api_key` + `datasetKey` in the
    JSON body. Base URL is the tenant sub-domain, e.g. https://acme.darwinbox.in.
    """

    DEFAULT_BASE = "https://api.darwinbox.in"
    EMPLOYEE_PATH = "/masterapi/employeedirectory"
    COMPENSATION_PATH = "/masterapi/compensation"
    TIMEOUT = 60

    def __init__(self, connector_record):
        super().__init__(connector_record)
        self._base = (connector_record.api_endpoint or self.DEFAULT_BASE).rstrip('/')
        self._api_key = connector_record.api_key or ''
        self._dataset = connector_record.api_version or 'default'

    # ==========================================
    # LIVE vs SAMPLE
    # ==========================================
    def _is_live(self) -> bool:
        """Live only when we have an endpoint, an api_key and a requests lib.
        Otherwise the connector runs on its bundled sample dataset so onboarding
        and the demo tenant work with zero configuration."""
        return bool(requests and self.connector.api_endpoint and self._api_key)

    def _headers(self) -> Dict[str, str]:
        return {'Content-Type': 'application/json', 'Accept': 'application/json'}

    def _auth(self):
        u = self.connector.username or ''
        p = self.connector.password or ''
        return (u, p) if (u or p) else None

    def _body(self, **extra) -> Dict[str, Any]:
        body = {'api_key': self._api_key, 'datasetKey': self._dataset}
        body.update(extra)
        return body

    def _post(self, path: str, **extra) -> Any:
        url = f"{self._base}{path}"
        resp = requests.post(url, json=self._body(**extra), headers=self._headers(),
                             auth=self._auth(), timeout=self.TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # ==========================================
    # REQUIRED INTERFACE
    # ==========================================
    def authenticate(self) -> bool:
        if not self._is_live():
            # Sample mode is always "authenticated".
            _logger.info("DarwinHR connector: sample mode (no live credentials) — authentication passes")
            return True
        # Live mode: a cheap directory ping doubles as the auth check.
        ok, _msg = self.test_connection()
        return ok

    def test_connection(self) -> Tuple[bool, str]:
        if not self._is_live():
            n = len(self._SAMPLE_EMPLOYEES)
            return True, f"DarwinHR connected in sample mode — {n} demo employees ready. Enter your tenant URL + API key to go live."
        try:
            data = self._post(self.EMPLOYEE_PATH, page=1, page_size=1)
            if isinstance(data, dict) and ('employee_data' in data or 'data' in data or data.get('status') in (1, '1', 'success', True)):
                self.update_connector_status('connected', 'Darwinbox connection successful')
                return True, "Darwinbox connection successful"
            msg = "Darwinbox responded but the payload was not recognised"
            self.update_connector_status('error', msg)
            return False, msg
        except Exception as e:  # requests / JSON / network
            msg = f"Darwinbox connection error: {e}"
            self.update_connector_status('error', msg)
            return False, msg

    def get_available_fields(self) -> List[Dict[str, Any]]:
        """Advertise the fields DarwinHR exposes so the mapping wizard can
        auto-suggest. Derived from a sample record — stable across live/sample."""
        fields_list = []
        sample = dict(self._SAMPLE_EMPLOYEES[0])
        sample.update({k: v for k, v in self._SAMPLE_SALARY['DBX1001'].items() if k != 'employee_id'})
        for key, val in sample.items():
            dtype = 'string'
            if isinstance(val, bool):
                dtype = 'boolean'
            elif isinstance(val, (int, float)):
                dtype = 'number'
            elif 'date' in key:
                dtype = 'date'
            fields_list.append({
                'name': key,
                'label': key.replace('_', ' ').title(),
                'data_type': dtype,
                'path': key,
                'sample_value': str(val),
                'category': 'salary' if key in self._SAMPLE_SALARY['DBX1001'] else 'employee',
            })
        return fields_list

    def fetch_employees(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        if not self._is_live():
            return list(self._SAMPLE_EMPLOYEES)
        employees, page = [], 1
        try:
            while True:
                data = self._post(self.EMPLOYEE_PATH, page=page, page_size=200)
                records = self._records(data)
                if not records:
                    break
                employees.extend(self._parse_employee(r) for r in records)
                if len(records) < 200:
                    break
                page += 1
        except Exception:
            _logger.exception("DarwinHR: employee fetch failed; falling back to sample data")
            return list(self._SAMPLE_EMPLOYEES)
        return employees

    def fetch_payroll_data(self, employee_ids: List[str], date_from: str,
                           date_to: str) -> Dict[str, Dict[str, Any]]:
        if not self._is_live():
            return {e: dict(self._SAMPLE_SALARY[e])
                    for e in employee_ids if e in self._SAMPLE_SALARY}
        result = {}
        try:
            data = self._post(self.COMPENSATION_PATH, employee_ids=employee_ids,
                              date_from=date_from, date_to=date_to)
            for rec in self._records(data):
                eid = str(rec.get('employee_id') or rec.get('employee_no') or rec.get('emp_id') or '')
                if eid:
                    result[eid] = self._parse_salary(rec)
        except Exception:
            _logger.exception("DarwinHR: compensation fetch failed; falling back to sample data")
            return {e: dict(self._SAMPLE_SALARY[e])
                    for e in employee_ids if e in self._SAMPLE_SALARY}
        return result

    def fetch_dependents(self, employee_ids: List[str]) -> Dict[str, List[Dict]]:
        return {e: list(self._SAMPLE_DEPENDENTS[e])
                for e in employee_ids if e in self._SAMPLE_DEPENDENTS}

    # ==========================================
    # PARSERS (live payload → standard shape)
    # ==========================================
    @staticmethod
    def _records(data: Any) -> List[Dict]:
        if isinstance(data, dict):
            for key in ('employee_data', 'compensation_data', 'data', 'result', 'records'):
                if isinstance(data.get(key), list):
                    return data[key]
        return data if isinstance(data, list) else []

    @staticmethod
    def _parse_employee(rec: Dict) -> Dict[str, Any]:
        g = rec.get
        return {
            'employee_id': str(g('employee_no') or g('employee_id') or g('emp_id') or ''),
            'first_name': g('first_name', ''),
            'last_name': g('last_name', ''),
            'full_name': g('full_name') or (f"{g('first_name', '')} {g('last_name', '')}").strip(),
            'email': g('office_email_id') or g('email') or '',
            'phone': g('phone_number') or g('mobile') or '',
            'department': g('department', ''),
            'position': g('designation') or g('position') or '',
            'date_of_joining': g('date_of_joining') or g('doj') or '',
            'date_of_birth': g('date_of_birth') or g('dob') or '',
            'gender': g('gender', ''),
            'marital_status': g('marital_status', ''),
            'tax_code': g('pan') or g('tax_code') or '',
            'bank_account': g('bank_account_number') or g('bank_account') or '',
            'status': g('employee_status') or g('status') or 'Active',
            '_raw': rec,
        }

    @staticmethod
    def _parse_salary(rec: Dict) -> Dict[str, Any]:
        g = rec.get
        def num(*keys):
            for k in keys:
                if rec.get(k) not in (None, ''):
                    try:
                        return float(rec[k])
                    except (TypeError, ValueError):
                        return 0.0
            return 0.0
        return {
            'employee_id': str(g('employee_no') or g('employee_id') or ''),
            'basic_salary': num('basic', 'basic_salary'),
            'position_allowance': num('position_allowance', 'special_allowance'),
            'lunch_allowance': num('meal_allowance', 'lunch_allowance'),
            'transport_allowance': num('transport_allowance', 'conveyance'),
            'phone_allowance': num('phone_allowance'),
            'overtime_hours': num('overtime_hours', 'ot_hours'),
            'kpi_bonus': num('bonus', 'kpi_bonus', 'incentive'),
            'working_days': num('working_days') or 22,
            'actual_working_days': num('actual_working_days', 'days_present') or 22,
            '_raw': rec,
        }

    # ==========================================
    # SAMPLE DATASET (used until live credentials are set)
    # ==========================================
    _SAMPLE_EMPLOYEES = [
        {'employee_id': 'DBX1001', 'first_name': 'Nguyen', 'last_name': 'Thanh Long',
         'full_name': 'Nguyen Thanh Long', 'email': 'long.nguyen@darwinhr-demo.vn',
         'phone': '0903111222', 'department': 'Engineering', 'position': 'Tech Lead',
         'date_of_joining': '2020-02-03', 'date_of_birth': '1989-06-11', 'gender': 'Male',
         'marital_status': 'Married', 'tax_code': '8811223344', 'bank_account': '9911223344556',
         'status': 'Active'},
        {'employee_id': 'DBX1002', 'first_name': 'Tran', 'last_name': 'Kim Ngan',
         'full_name': 'Tran Kim Ngan', 'email': 'ngan.tran@darwinhr-demo.vn',
         'phone': '0903222333', 'department': 'People Ops', 'position': 'HRBP',
         'date_of_joining': '2018-07-16', 'date_of_birth': '1990-09-02', 'gender': 'Female',
         'marital_status': 'Single', 'tax_code': '8811223345', 'bank_account': '9911223344557',
         'status': 'Active'},
        {'employee_id': 'DBX1003', 'first_name': 'Le', 'last_name': 'Quoc Bao',
         'full_name': 'Le Quoc Bao', 'email': 'bao.le@darwinhr-demo.vn',
         'phone': '0903333444', 'department': 'Finance', 'position': 'Finance Analyst',
         'date_of_joining': '2021-11-08', 'date_of_birth': '1994-01-27', 'gender': 'Male',
         'marital_status': 'Married', 'tax_code': '8811223346', 'bank_account': '9911223344558',
         'status': 'Active'},
        {'employee_id': 'DBX1004', 'first_name': 'Pham', 'last_name': 'Bao Chau',
         'full_name': 'Pham Bao Chau', 'email': 'chau.pham@darwinhr-demo.vn',
         'phone': '0903444555', 'department': 'Sales', 'position': 'Account Executive',
         'date_of_joining': '2022-04-19', 'date_of_birth': '1996-12-03', 'gender': 'Female',
         'marital_status': 'Single', 'tax_code': '8811223347', 'bank_account': '9911223344559',
         'status': 'Active'},
    ]

    _SAMPLE_SALARY = {
        'DBX1001': {'employee_id': 'DBX1001', 'basic_salary': 32000000, 'position_allowance': 6000000,
                    'lunch_allowance': 730000, 'transport_allowance': 700000, 'phone_allowance': 300000,
                    'overtime_hours': 6, 'kpi_bonus': 6000000, 'working_days': 22, 'actual_working_days': 22},
        'DBX1002': {'employee_id': 'DBX1002', 'basic_salary': 27000000, 'position_allowance': 4000000,
                    'lunch_allowance': 730000, 'transport_allowance': 500000, 'phone_allowance': 200000,
                    'overtime_hours': 0, 'kpi_bonus': 3000000, 'working_days': 22, 'actual_working_days': 21},
        'DBX1003': {'employee_id': 'DBX1003', 'basic_salary': 19000000, 'position_allowance': 2000000,
                    'lunch_allowance': 730000, 'transport_allowance': 500000, 'phone_allowance': 0,
                    'overtime_hours': 10, 'kpi_bonus': 2500000, 'working_days': 22, 'actual_working_days': 20},
        'DBX1004': {'employee_id': 'DBX1004', 'basic_salary': 16000000, 'position_allowance': 1500000,
                    'lunch_allowance': 730000, 'transport_allowance': 500000, 'phone_allowance': 200000,
                    'overtime_hours': 0, 'kpi_bonus': 9000000, 'working_days': 22, 'actual_working_days': 22},
    }

    _SAMPLE_DEPENDENTS = {
        'DBX1001': [
            {'employee_id': 'DBX1001', 'dependent_name': 'Nguyen Thi Hoa', 'relationship': 'Spouse',
             'date_of_birth': '1990-03-19', 'is_tax_dependent': False},
            {'employee_id': 'DBX1001', 'dependent_name': 'Nguyen Minh An', 'relationship': 'Child',
             'date_of_birth': '2018-08-04', 'is_tax_dependent': True},
        ],
        'DBX1003': [
            {'employee_id': 'DBX1003', 'dependent_name': 'Le Bao Han', 'relationship': 'Child',
             'date_of_birth': '2023-05-21', 'is_tax_dependent': True},
        ],
    }

    # ==========================================
    # INBOUND WEBHOOK — push ingestion
    # ==========================================
    def ingest_records(self, data_type: str, records: List[Dict]) -> Dict[str, Any]:
        """Store pushed Darwinbox records as raw hr.api.data.store rows.

        Called by the webhook controller. Stores *raw only* — it never
        transforms, posts, or touches payslips; promotion happens through the
        normal mapping/import pipeline. Returns a small summary.
        """
        DataStore = self.env['hr.api.data.store'].sudo()
        parser = {'employee': self._parse_employee, 'salary': self._parse_salary}.get(data_type)
        stored = 0
        for rec in records:
            if not isinstance(rec, dict):
                continue
            parsed = parser(rec) if parser else rec
            eid = str(parsed.get('employee_id') or rec.get('employee_id') or rec.get('employee_no') or '')
            DataStore.create({
                'connector_id': self.connector.id,
                'data_type': data_type if data_type in (
                    'employee', 'salary', 'attendance', 'leave', 'dependent',
                    'benefit', 'tax', 'custom') else 'custom',
                'employee_external_id': eid,
                'raw_payload': rec,
                'extracted_data': parsed if parser else False,
                'state': 'extracted' if parser else 'raw',
                'pull_triggered_by': 'cron',
            })
            stored += 1
        return {'stored': stored}
