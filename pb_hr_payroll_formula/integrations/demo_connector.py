# -*- coding: utf-8 -*-
"""
Demo Connector — Stub HRIS for learning and testing the Pull→Store→Transform pipeline.

Returns realistic Vietnamese HR data without any external API.
Use this to practice field mappings and transformation rules.
"""

import logging
from datetime import date
from typing import Dict, List, Any, Optional, Tuple

from .base_connector import BaseHRConnector

_logger = logging.getLogger(__name__)


class DemoConnector(BaseHRConnector):
    """
    Demo HR connector that returns fake but realistic data.

    Simulates a typical HRIS API with:
      - 5 employees with Vietnamese names
      - Salary components (basic, allowances, deductions)
      - Dependents (spouse, children)
      - Attendance records
      - Leave records

    No authentication needed — always succeeds.
    """

    # =====================================================
    # DEMO EMPLOYEE DATA
    # =====================================================
    DEMO_EMPLOYEES = [
        {
            'employee_id': 'EMP001',
            'first_name': 'Nguyen', 'last_name': 'Van Anh',
            'full_name': 'Nguyen Van Anh',
            'email': 'anh.nguyen@demo-company.vn',
            'phone': '0901234567',
            'department': 'Engineering',
            'position': 'Senior Developer',
            'date_of_joining': '2021-03-15',
            'date_of_birth': '1990-05-20',
            'gender': 'Male',
            'marital_status': 'Married',
            'tax_code': '1234567890',
            'social_insurance_number': 'SI-001-2021',
            'bank_account': '1234567890123',
            'bank_name': 'Vietcombank',
            'status': 'Active',
        },
        {
            'employee_id': 'EMP002',
            'first_name': 'Tran', 'last_name': 'Thi Bich',
            'full_name': 'Tran Thi Bich',
            'email': 'bich.tran@demo-company.vn',
            'phone': '0912345678',
            'department': 'HR',
            'position': 'HR Manager',
            'date_of_joining': '2019-08-01',
            'date_of_birth': '1988-11-12',
            'gender': 'Female',
            'marital_status': 'Single',
            'tax_code': '2345678901',
            'social_insurance_number': 'SI-002-2019',
            'bank_account': '2345678901234',
            'bank_name': 'Techcombank',
            'status': 'Active',
        },
        {
            'employee_id': 'EMP003',
            'first_name': 'Le', 'last_name': 'Hoang Cuong',
            'full_name': 'Le Hoang Cuong',
            'email': 'cuong.le@demo-company.vn',
            'phone': '0923456789',
            'department': 'Finance',
            'position': 'Accountant',
            'date_of_joining': '2022-01-10',
            'date_of_birth': '1995-07-30',
            'gender': 'Male',
            'marital_status': 'Married',
            'tax_code': '3456789012',
            'social_insurance_number': 'SI-003-2022',
            'bank_account': '3456789012345',
            'bank_name': 'ACB',
            'status': 'Active',
        },
        {
            'employee_id': 'EMP004',
            'first_name': 'Pham', 'last_name': 'Minh Duc',
            'full_name': 'Pham Minh Duc',
            'email': 'duc.pham@demo-company.vn',
            'phone': '0934567890',
            'department': 'Sales',
            'position': 'Sales Executive',
            'date_of_joining': '2023-06-20',
            'date_of_birth': '1997-02-14',
            'gender': 'Male',
            'marital_status': 'Single',
            'tax_code': '4567890123',
            'social_insurance_number': 'SI-004-2023',
            'bank_account': '4567890123456',
            'bank_name': 'MB Bank',
            'status': 'Active',
        },
        {
            'employee_id': 'EMP005',
            'first_name': 'Vo', 'last_name': 'Ngoc Huong',
            'full_name': 'Vo Ngoc Huong',
            'email': 'huong.vo@demo-company.vn',
            'phone': '0945678901',
            'department': 'Engineering',
            'position': 'QA Engineer',
            'date_of_joining': '2020-09-01',
            'date_of_birth': '1992-12-05',
            'gender': 'Female',
            'marital_status': 'Married',
            'tax_code': '5678901234',
            'social_insurance_number': 'SI-005-2020',
            'bank_account': '5678901234567',
            'bank_name': 'Vietinbank',
            'status': 'Active',
        },
    ]

    # =====================================================
    # DEMO SALARY DATA  (amounts in VND)
    # =====================================================
    DEMO_SALARY = {
        'EMP001': {
            'employee_id': 'EMP001',
            'basic_salary': 25000000,
            'position_allowance': 3000000,
            'lunch_allowance': 730000,
            'transport_allowance': 500000,
            'phone_allowance': 200000,
            'overtime_hours': 12,
            'overtime_amount': 2076923,
            'kpi_bonus': 5000000,
            'social_insurance_employee': 2000000,
            'health_insurance_employee': 375000,
            'unemployment_insurance_employee': 250000,
            'personal_income_tax': 1850000,
            'advance_deduction': 0,
            'working_days': 22,
            'actual_working_days': 21,
        },
        'EMP002': {
            'employee_id': 'EMP002',
            'basic_salary': 30000000,
            'position_allowance': 5000000,
            'lunch_allowance': 730000,
            'transport_allowance': 500000,
            'phone_allowance': 300000,
            'overtime_hours': 0,
            'overtime_amount': 0,
            'kpi_bonus': 3000000,
            'social_insurance_employee': 2400000,
            'health_insurance_employee': 450000,
            'unemployment_insurance_employee': 300000,
            'personal_income_tax': 3200000,
            'advance_deduction': 5000000,
            'working_days': 22,
            'actual_working_days': 22,
        },
        'EMP003': {
            'employee_id': 'EMP003',
            'basic_salary': 18000000,
            'position_allowance': 2000000,
            'lunch_allowance': 730000,
            'transport_allowance': 500000,
            'phone_allowance': 0,
            'overtime_hours': 8,
            'overtime_amount': 1107692,
            'kpi_bonus': 2000000,
            'social_insurance_employee': 1440000,
            'health_insurance_employee': 270000,
            'unemployment_insurance_employee': 180000,
            'personal_income_tax': 850000,
            'advance_deduction': 0,
            'working_days': 22,
            'actual_working_days': 20,
        },
        'EMP004': {
            'employee_id': 'EMP004',
            'basic_salary': 15000000,
            'position_allowance': 1000000,
            'lunch_allowance': 730000,
            'transport_allowance': 500000,
            'phone_allowance': 200000,
            'overtime_hours': 0,
            'overtime_amount': 0,
            'kpi_bonus': 8000000,
            'social_insurance_employee': 1200000,
            'health_insurance_employee': 225000,
            'unemployment_insurance_employee': 150000,
            'personal_income_tax': 1100000,
            'advance_deduction': 2000000,
            'working_days': 22,
            'actual_working_days': 22,
        },
        'EMP005': {
            'employee_id': 'EMP005',
            'basic_salary': 22000000,
            'position_allowance': 3000000,
            'lunch_allowance': 730000,
            'transport_allowance': 500000,
            'phone_allowance': 200000,
            'overtime_hours': 4,
            'overtime_amount': 605128,
            'kpi_bonus': 4000000,
            'social_insurance_employee': 1760000,
            'health_insurance_employee': 330000,
            'unemployment_insurance_employee': 220000,
            'personal_income_tax': 1500000,
            'advance_deduction': 0,
            'working_days': 22,
            'actual_working_days': 19,
        },
    }

    # =====================================================
    # DEMO DEPENDENT DATA
    # =====================================================
    DEMO_DEPENDENTS = {
        'EMP001': [
            {
                'employee_id': 'EMP001',
                'dependent_name': 'Nguyen Thi Mai',
                'relationship': 'Spouse',
                'date_of_birth': '1991-08-15',
                'age': 34,
                'gender': 'Female',
                'status': 'Active',
                'is_tax_dependent': True,
            },
            {
                'employee_id': 'EMP001',
                'dependent_name': 'Nguyen Minh Tuan',
                'relationship': 'Child',
                'date_of_birth': '2019-03-22',
                'age': 6,
                'gender': 'Male',
                'status': 'Active',
                'is_tax_dependent': True,
            },
            {
                'employee_id': 'EMP001',
                'dependent_name': 'Nguyen Ngoc Linh',
                'relationship': 'Child',
                'date_of_birth': '2022-11-10',
                'age': 3,
                'gender': 'Female',
                'status': 'Active',
                'is_tax_dependent': True,
            },
        ],
        'EMP003': [
            {
                'employee_id': 'EMP003',
                'dependent_name': 'Le Thi Thanh',
                'relationship': 'Spouse',
                'date_of_birth': '1996-04-18',
                'age': 29,
                'gender': 'Female',
                'status': 'Active',
                'is_tax_dependent': False,
            },
            {
                'employee_id': 'EMP003',
                'dependent_name': 'Le Hoang Nam',
                'relationship': 'Child',
                'date_of_birth': '2024-01-05',
                'age': 2,
                'gender': 'Male',
                'status': 'Active',
                'is_tax_dependent': True,
            },
        ],
        'EMP005': [
            {
                'employee_id': 'EMP005',
                'dependent_name': 'Vo Van Hung',
                'relationship': 'Spouse',
                'date_of_birth': '1991-06-25',
                'age': 34,
                'gender': 'Male',
                'status': 'Active',
                'is_tax_dependent': False,
            },
            {
                'employee_id': 'EMP005',
                'dependent_name': 'Vo Minh Khoa',
                'relationship': 'Child',
                'date_of_birth': '2020-09-14',
                'age': 5,
                'gender': 'Male',
                'status': 'Active',
                'is_tax_dependent': True,
            },
        ],
    }

    # =====================================================
    # DEMO ATTENDANCE DATA
    # =====================================================
    DEMO_ATTENDANCE = {
        'EMP001': {
            'employee_id': 'EMP001',
            'total_working_days': 22,
            'days_present': 21,
            'days_absent': 1,
            'late_count': 2,
            'early_leave_count': 0,
            'overtime_hours': 12,
        },
        'EMP002': {
            'employee_id': 'EMP002',
            'total_working_days': 22,
            'days_present': 22,
            'days_absent': 0,
            'late_count': 0,
            'early_leave_count': 1,
            'overtime_hours': 0,
        },
        'EMP003': {
            'employee_id': 'EMP003',
            'total_working_days': 22,
            'days_present': 20,
            'days_absent': 2,
            'late_count': 1,
            'early_leave_count': 0,
            'overtime_hours': 8,
        },
        'EMP004': {
            'employee_id': 'EMP004',
            'total_working_days': 22,
            'days_present': 22,
            'days_absent': 0,
            'late_count': 0,
            'early_leave_count': 0,
            'overtime_hours': 0,
        },
        'EMP005': {
            'employee_id': 'EMP005',
            'total_working_days': 22,
            'days_present': 19,
            'days_absent': 3,
            'late_count': 3,
            'early_leave_count': 2,
            'overtime_hours': 4,
        },
    }

    # =====================================================
    # DEMO LEAVE DATA
    # =====================================================
    DEMO_LEAVES = {
        'EMP001': [
            {
                'employee_id': 'EMP001',
                'leave_type': 'Annual Leave',
                'days': 1,
                'status': 'Approved',
                'start_date': '2026-02-10',
                'end_date': '2026-02-10',
            },
        ],
        'EMP003': [
            {
                'employee_id': 'EMP003',
                'leave_type': 'Annual Leave',
                'days': 1,
                'status': 'Approved',
                'start_date': '2026-02-05',
                'end_date': '2026-02-05',
            },
            {
                'employee_id': 'EMP003',
                'leave_type': 'Sick Leave',
                'days': 1,
                'status': 'Approved',
                'start_date': '2026-02-18',
                'end_date': '2026-02-18',
            },
        ],
        'EMP005': [
            {
                'employee_id': 'EMP005',
                'leave_type': 'Annual Leave',
                'days': 2,
                'status': 'Approved',
                'start_date': '2026-02-12',
                'end_date': '2026-02-13',
            },
            {
                'employee_id': 'EMP005',
                'leave_type': 'Sick Leave',
                'days': 1,
                'status': 'Approved',
                'start_date': '2026-02-20',
                'end_date': '2026-02-20',
            },
        ],
    }

    # =====================================================
    # REQUIRED INTERFACE METHODS
    # =====================================================
    def authenticate(self) -> bool:
        """Demo connector always authenticates successfully."""
        _logger.info("Demo connector: authentication successful (always passes)")
        return True

    def test_connection(self) -> Tuple[bool, str]:
        """Demo connector always connects successfully."""
        return True, "Demo connector is always connected. 5 employees ready."

    def get_available_fields(self) -> List[Dict[str, Any]]:
        """Return the list of all available fields from the demo data."""
        fields_list = []

        # Employee fields
        sample_emp = self.DEMO_EMPLOYEES[0]
        for key, val in sample_emp.items():
            dtype = 'string'
            if isinstance(val, (int, float)):
                dtype = 'number'
            elif 'date' in key:
                dtype = 'date'
            fields_list.append({
                'name': key,
                'label': key.replace('_', ' ').title(),
                'data_type': dtype,
                'path': key,
                'sample_value': str(val),
                'category': 'employee',
            })

        # Salary fields
        sample_sal = self.DEMO_SALARY['EMP001']
        for key, val in sample_sal.items():
            if key == 'employee_id':
                continue
            dtype = 'number' if isinstance(val, (int, float)) else 'string'
            fields_list.append({
                'name': key,
                'label': key.replace('_', ' ').title(),
                'data_type': dtype,
                'path': key,
                'sample_value': str(val),
                'category': 'salary',
            })

        # Dependent fields
        sample_dep = self.DEMO_DEPENDENTS['EMP001'][0]
        for key, val in sample_dep.items():
            if key == 'employee_id':
                continue
            dtype = 'string'
            if isinstance(val, (int, float)):
                dtype = 'number'
            elif isinstance(val, bool):
                dtype = 'boolean'
            elif 'date' in key:
                dtype = 'date'
            fields_list.append({
                'name': key,
                'label': key.replace('_', ' ').title(),
                'data_type': dtype,
                'path': key,
                'sample_value': str(val),
                'category': 'dependent',
            })

        return fields_list

    def fetch_employees(self, filters: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Return all demo employees."""
        _logger.info("Demo connector: fetching %d employees", len(self.DEMO_EMPLOYEES))
        return list(self.DEMO_EMPLOYEES)

    def fetch_payroll_data(
        self,
        employee_ids: List[str],
        date_from: str,
        date_to: str
    ) -> Dict[str, Dict[str, Any]]:
        """Return salary data for requested employees."""
        result = {}
        for emp_id in employee_ids:
            if emp_id in self.DEMO_SALARY:
                result[emp_id] = dict(self.DEMO_SALARY[emp_id])
        _logger.info(
            "Demo connector: fetched salary data for %d/%d employees",
            len(result), len(employee_ids)
        )
        return result

    # =====================================================
    # ADDITIONAL DATA TYPES (used by action_pull_data)
    # =====================================================
    def fetch_dependents(self, employee_ids: List[str]) -> Dict[str, List[Dict]]:
        """Return dependent data for requested employees."""
        result = {}
        for emp_id in employee_ids:
            if emp_id in self.DEMO_DEPENDENTS:
                result[emp_id] = list(self.DEMO_DEPENDENTS[emp_id])
        return result

    def fetch_attendance(
        self,
        employee_ids: List[str],
        date_from: str,
        date_to: str
    ) -> Dict[str, Dict]:
        """Return attendance data for requested employees."""
        result = {}
        for emp_id in employee_ids:
            if emp_id in self.DEMO_ATTENDANCE:
                result[emp_id] = dict(self.DEMO_ATTENDANCE[emp_id])
        return result

    def fetch_leaves(
        self,
        employee_ids: List[str],
        date_from: str,
        date_to: str
    ) -> Dict[str, List[Dict]]:
        """Return leave data for requested employees."""
        result = {}
        for emp_id in employee_ids:
            if emp_id in self.DEMO_LEAVES:
                result[emp_id] = list(self.DEMO_LEAVES[emp_id])
        return result
