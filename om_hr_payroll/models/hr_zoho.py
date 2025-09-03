import requests
import base64
import tempfile
from odoo import http
from odoo.http import request
import json
import datetime
from dateutil.relativedelta import relativedelta 
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from pudb import set_trace
_logger = logging.getLogger(__name__) 
from openpyxl import Workbook, load_workbook
from odoo.exceptions import ValidationError


# 1. Define a new model to store Zoho employee data
class ZohoEmployeeData(models.Model):
    _name = 'zoho.employee.data'
    _description = 'Stores raw employee data from Zoho People'
    _rec_name = 'first_name'  # Use first_name as the display name

    # Add all the fields from the Zoho API response
    first_name = fields.Char(string="First Name")
    last_name = fields.Char(string="Last Name")
    email = fields.Char(string="Email")
    employee_id = fields.Char(string="Employee ID")
    department = fields.Char(string="Department")
    employee_status = fields.Char(string="Employee Status")
    location_name = fields.Char(string="Location Name")
    designation = fields.Char(string="Designation")
    pan_number = fields.Char(string="Pan Number")
    bank_name = fields.Char(string="Bank Name")
    pit_number = fields.Char(string="PIT Number")
    bank_account_number_vnd = fields.Char(string="Bank Account Number VND")
    uan_number = fields.Char(string="UAN Number")
    aadhaar_number = fields.Char(string="Aadhaar Number")
    zoho_id = fields.Char(string="Zoho ID")
    full_name_en = fields.Char(string="Full Name EN")
    full_name_vn = fields.Char(string="Full Name VN")
    insurance_book_number = fields.Char(string="Insurance Book Number")
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], string="Gender")
    employee_type = fields.Char(string="Employee Type")
    date_of_birth = fields.Date(string="Date of Birth")
    mobile = fields.Char(string="Mobile")
    date_of_joining = fields.Date(string="Date of Joining")
    number_of_dependents = fields.Integer(string="Number of Dependents")
    standard_whr = fields.Float(string="Standard Working Hours")
    actual_working_hours_incl_paid_leave = fields.Float(string="Actual Working Hours (incl. Paid Leave)")
    actual_working_hours_excl_paid_leave = fields.Float(string="Actual Working Hours (excl. Paid Leave)")
    overtime_normal_150_hour = fields.Float(string="Overtime Normal (150%) Hours")
    overtime_weekend_200_hour = fields.Float(string="Overtime Weekend (200%) Hours")
    overtime_holiday_300_hour = fields.Float(string="Overtime Weekend (300%) Hours")
    overtime_nightshift_200_hour = fields.Float(string="Overtime Nightshift Normal(200%) Hours")
    overtime_nightshift_210_hour = fields.Float(string="Overtime Nightshift Normal (210%) Hours")
    overtime_nightshift_270_hour = fields.Float(string="Overtime Nightshift Weeekend (270%) Hours")
    overtime_nightshift_390_hour = fields.Float(string="Overtime Nightshift Holiday (390%) Hours")
    start_date = fields.Date(string="Pay Start Date")
    end_date = fields.Date(string="Pay End Date")
    last_workday = fields.Date(string="Last Working Day")
    costcenter = fields.Char(string="Cost Center")
    base_salary = fields.Float(string="Base Salary")
    gas_allowance = fields.Float(string="Gas Allowance")
    phone_allowance = fields.Float(string="Phone Allowance")
    meal_allowance = fields.Float(string="Meal Allowance")
    resp_allowance = fields.Float(string="Responsibility Allowance")
    park_allowance = fields.Float(string="Parking Allowance")
    taxi_allowance = fields.Float(string="Taxi Allowance")
    recog_bonus = fields.Float(string="Recognition Bonus")
    other_income = fields.Float(string="Other Income")
    paidleave_unused = fields.Float(string="Paid leave Unused")
    other_bonus = fields.Float(string="Other bonus")     
    bonus_stip = fields.Float(string="Bonus - STIP")    
    marsh_ins = fields.Float(string="Marsh Insurance refund( non Tax)")
    adjustment = fields.Float(string="Adjustment")
    shui_part = fields.Char(string="SHUI Participation")
    tu_part = fields.Char(string="TU Participation")
    sales_incentive = fields.Float(string="Sales Incentive")
    thirteenth_month = fields.Float(string="Thirteenth month salary")
    sever_allow = fields.Float(string="Severance Allowance")
    reimb_payment = fields.Float(string="Reimbursement Payment")
    nightshift_hour = fields.Float(string="Night shift hour")
    etu = fields.Float(string="Employee Trade Union")
    # Biztinct - To confirm need to delete dependent field as it is is duplicate of above
    dependent = fields.Integer(string="Dependent No")
    other_notcounted = fields.Float(string="Other deduction/addition not counted")
    spreadsheet_data = fields.Many2one('spreadsheet.core', string="Spreadsheet Data")
    res_status = fields.Char(string="Residency status")
    idcard_num = fields.Char(string="ID card num")
    contract_from = fields.Date(string="Contract from")
    contract_to = fields.Date(string="Contract to")
    enroll_tax = fields.Char(string="Enroll for tax")
    enroll_ins = fields.Char(string="Enroll for insurance")
    emp_bank_accntname = fields.Char(string="Employee bank account name")
    bank_branch = fields.Char(string="Bank branch")
    bank_code = fields.Char(string="Bank code")
    paidleave_unused = fields.Char(string="Paid leave unused")
    longterm_incent = fields.Char(string="Longterm incentive")

    #Calculated fields from spreadsheet
    actual_basicsalary =  fields.Float(string="Actual basic salary")
    actual_gas =  fields.Float(string="Actual gas allowance")
    actual_phone =  fields.Float(string="Actual phone")
    actual_meal =  fields.Float(string="Actual meal")
    actual_resp =  fields.Float(string="Actual responsibility")
    actual_parking =  fields.Float(string="Actual parking")
    actual_taxi =  fields.Float(string="Actual taxi")
    ot_15amount =  fields.Float(string="OT 1.5 amount")
    ot_2amount =  fields.Float(string="OT 2 amount")
    ot_3amount =  fields.Float(string="OT 3 amount")
    ns_amount =  fields.Float(string="Night shift amount")
    otns_weekamount =  fields.Float(string="OT night shift weekday amount")
    otns_offamount =  fields.Float(string="OT night shift offday amount")
    otns_holamount =  fields.Float(string="OT night shift holiday amount")
    total_otamount =  fields.Float(string="Total overtime amount")
    ot_nontax =  fields.Float(string="OT nontaxable")
    ot_tax =  fields.Float(string="OT taxable")
    actual_totalincome =  fields.Float(string="Actual total income")
    salary_si =  fields.Float(string="Salary for SI")
    salary_ui =  fields.Float(string="Salary for UI")
    social_ins8 =  fields.Float(string="Social insurance 8%")
    med_ins15 =  fields.Float(string="Medical insurance 1.5%")
    unemp_ins1 =  fields.Float(string="Unemployment insurance 1%")
    sihiui_total105 =  fields.Float(string="SI-HI-UI total 10.5%")
    dep_amount =  fields.Float(string="Dependent amount")
    tax_income =  fields.Float(string="Taxable income")
    taxincome_afterded =  fields.Float(string="Taxable income after deduction")
    monthly_pit =  fields.Float(string="Monthly PIT")
    total_ded =  fields.Float(string="Total deductions")
    net_pay =  fields.Float(string="Net pay")
    social_ins175 =  fields.Float(string="Social insurance 17.5%")
    med_ins3 =  fields.Float(string="Medical insurance 3%")
    sihiui_total215 =  fields.Float(string="SI-HI-UI total 21.5%")
    trade_er2 =  fields.Float(string="Trade union ER 2%")
    total_cte =  fields.Float(string="Total cost to employer")

    '''
    Commenting as these write and create methods are calling create_or_updfate which is a loop

    @api.model_create_multi
    def create(self, vals_list):
        """Override the create method."""
        records = super(ZohoEmployeeData, self).create(vals_list)
        self.env['zoho.timesheet.importer']._create_or_update_employee()  # Call the method from zoho.timesheet.importer
        return records



    def write(self, vals):
        """Override the write method."""
        res = super(ZohoEmployeeData, self).write(vals)
        self.env['zoho.timesheet.importer']._create_or_update_employee()  # Call the method from zoho.timesheet.importer
        return res

'''
    # This was originaly writeen to bypass the trigger for create. That trigger i snow commeted/deleted  above. So this can be refactored.
    
    @api.model
    def bypass_create(self, vals):
        # Call the original 'create' method directly
        original_create = models.Model.create
        record = original_create(self, vals)
        return record

        



class ZohoTimesheetImporter(models.TransientModel):
    _name = 'zoho.timesheet.importer'
    _description = 'Import Timesheets from Zoho People'

######################################################################################################
#   Biztinct - following code is kept for future use cases
#####################################################################################################
    '''
    def _get_total_working_hours(self, access_token):
        """
        Gets the total working hours from Zoho People timesheets.
        """
        #url = "https://people.zoho.com/people/api/timetracker/gettimesheet"
        url = "https://people.zoho.com/people/api/attendance/getSummaryReport"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }
        params = {
            #"dateFormat": "dd-MM-yyyy",
            "startDate": self.from_date.strftime('%d/%m/%Y'),
            "endDate": self.to_date.strftime('%d/%m/%Y')
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            #set_trace()
            timesheets = response.json()['result']
            for timesheet in timesheets:
                # Access relevant data (adjust based on Zoho API response)
                employee_name = timesheet.get('employeeName')
                total_hours = timesheet.get('totalHours')
                date = timesheet.get('date')

                # TODO: Process the data as needed (e.g., create records in Odoo)
                print(f"Employee: {employee_name}, Date: {date}, Total Hours: {total_hours}")
            return

        except requests.exceptions.RequestException as e:
            raise UserError(f"Error fetching working hours from Zoho API: {e}")




    def _get_leave_hours(self, access_token):
        """
        Fetches leave hours from Zoho People for all employees.
        """
        try:
            url = "https://people.zoho.com/api/v2/leavetracker/leaves/records"
            headers = {
                "Authorization": f"Zoho-oauthtoken {access_token}"
            }
            params = {
                "from": self.from_date.strftime('%d/%m/%Y'),
                "to": self.to_date.strftime('%d/%m/%Y'),
            }
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()

            leaves_data = response.json()['records']

            for leave in leaves_data:
                # Access relevant data (adjust based on Zoho API response)
                employee_name = leave.get('Employee')  # Assuming the API returns employeeName
                leave_duration = leave.get('Days')  # Assuming leave duration in hours
                leave_type = leave.get('Type', '')  # Get leave type if available
                
                # TODO: Process the data as needed (e.g., create records in Odoo)
                print(f"Employee: {employee_name}, Leave Type: {leave_type}, Leave Duration: {leave_duration} hours")

            return 

        except requests.exceptions.RequestException as e:
            raise UserError(f"Error fetching leave hours from Zoho People: {e}")


    def _get_overtime_hours(self, access_token):
        """
        Fetches overtime hours from Zoho People for all employees.
        """
        try:
            url = "https://people.zoho.com/people/api/forms/getOvertimeRequests"  # Use the correct endpoint
            headers = {
                "Authorization": f"Zoho-oauthtoken {access_token}"
            }
            params = {
                "user": "all",
                "dateFormat": "yyyy-MM-dd",
                "fromDate": self.from_date.strftime('%Y-%m-%d'),
                "toDate": self.to_date.strftime('%Y-%m-%d'),
                "status": "approved"  # Consider only approved overtime requests
            }
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            overtime_requests = response.json()['forms']  # Assuming API response structure

            total_overtime_hours = 0
            for request in overtime_requests:
                # Access relevant data (adjust based on Zoho API response)
                employee_name = request.get('employeeName')
                overtime_hours = request.get('totalHours', 0)  # Get overtime hours
                date = request.get('date')

                # TODO: Process the data as needed (e.g., create records in Odoo)
                print(f"Employee: {employee_name}, Date: {date}, Overtime Hours: {overtime_hours}")

                total_overtime_hours += overtime_hours

            return total_overtime_hours

        except requests.exceptions.RequestException as e:
            raise UserError(f"Error fetching overtime hours from Zoho People: {e}")
    '''

########################################################################################################


    def _create_or_update_employee(self):
        """
        Gets all records from zoho.employee.data and creates/updates 
        corresponding records in hr.employee.
        """
        """Modified to handle country-specific salary structures"""
        # Get payroll country from context
        payroll_country = self.env.context.get('payroll_country', 'VN')

        # Fetch all records from zoho.employee.data
        zoho_employees = self.env['zoho.employee.data'].search([])

        for zoho_employee in zoho_employees:
            employee = self.env['hr.employee'].search([('employee_id', '=', zoho_employee.employee_id)], limit=1)

            # Validate the presence of the department
            if not zoho_employee.department:
                raise ValidationError(f'Department is not specified for the employee with ID {zoho_employee.employee_id} and name {zoho_employee.full_name_vn}. Please update Employee Details worksheet with details and import again')

            # --- Department ---
            department = self.env['hr.department'].search([('name', '=', zoho_employee.department)], limit=1)
       
            if not department:
                department = self.env['hr.department'].create({'name': zoho_employee.department})


            # --- Job ---

            # Validate the presence of job
            if not zoho_employee.designation:
                raise ValidationError(f'Designation is not specified for the employee with ID {zoho_employee.employee_id} and name {zoho_employee.full_name_vn}. Please update Employee Details worksheet with details and import again')

            job = self.env['hr.job'].search([('name', '=', zoho_employee.designation)], limit=1)
            if not job:
                job = self.env['hr.job'].create({'name': zoho_employee.designation})


            bank_account_number = zoho_employee.bank_account_number_vnd
            if bank_account_number:
                bank_account = self.env['res.partner.bank'].search([
                    ('acc_number', '=', bank_account_number)
                ], limit=1)
                if not bank_account:
                    # If no bank account found, create a new one
                    # --- Bank ---
                    bank = self.env['res.bank'].search([('name', '=', zoho_employee.bank_name)], limit=1)
                    if not bank:
                        # If no bank found, create a new bank
                        bank = self.env['res.bank'].create({'name': zoho_employee.bank_name})
                    emp = self.env['hr.employee'].search([('employee_id', '=', zoho_employee.employee_id)], limit=1)
                    #partner = self.env['res.partner'].search([('id', '=', emp.work_contact_id.id)], limit=1)
                    if emp :
                        bank_account = self.env['res.partner.bank'].create({
                            'acc_number': bank_account_number,
                            'bank_id': self.env['res.bank'].search([('name', '=', zoho_employee.bank_name)], limit=1).id,
                            'partner_id': emp.work_contact_id.id,
                            # Add other bank account details if available (e.g., partner_id)
                        })


            employee_data = {
                'name': zoho_employee.full_name_vn or zoho_employee.first_name or "Unknown Employee", 
                'work_email': zoho_employee.email,
                'department_id': self.env['hr.department'].search([('name', '=', zoho_employee.department)], limit=1).id,
                'bank_account_id': self.env['res.partner.bank'].search([('acc_number', '=', zoho_employee.bank_account_number_vnd)], limit=1).id,
                'location': zoho_employee.location_name,
                'job_id': self.env['hr.job'].search([('name', '=', zoho_employee.designation)], limit=1).id,
                #'identification_id': zoho_employee.pan_number,
                'gender': zoho_employee.gender,
                'org_employee_type': zoho_employee.employee_type,
                'birthday': zoho_employee.date_of_birth,
                'mobile_phone': zoho_employee.mobile,
                'marital': 'single' if zoho_employee.employee_status == 'Single' else 'married',
                'employee_id': zoho_employee.employee_id,
                #'full_name_en': zoho_employee.full_name_en,
                'full_name_vn': zoho_employee.full_name_vn,
                #'insurance_book_number': zoho_employee.insurance_book_number,
                #'pit_number': zoho_employee.pit_number,
                #'uan_number': zoho_employee.uan_number,
                #'aadhaar_number': zoho_employee.aadhaar_number,
                # ... map other fields to hr.employee (e.g., bank account, address, etc.) ...
            }

            if employee:
                employee.write(employee_data)
            else:
                new_employee = employee.create(employee_data)

                # --- Contract Creation ---

                # Validate the presence of the contract date_from
                '''
                if not zoho_employee.contract_from:
                    raise ValidationError(f'Contract Date From is not specified for the employee with ID {zoho_employee.employee_id} and name {zoho_employee.full_name_vn}. Please update Employee Details worksheet with details and import again')
                # Validate the presence of the contract date_to
                if not zoho_employee.contract_to:
                    raise ValidationError(f'Contract Date To is not specified for the employee with ID {zoho_employee.employee_id} and name {zoho_employee.full_name_vn}. Please update Employee Details worksheet with details and import again')
                '''

                # Use flexible salary structure search with fallbacks
                country_structure_names = {
                    'VN': ['Vietnam Salary Structure', 'Vietnam Payroll Structure', 'VN Salary Structure'],
                    'ID': ['Indonesia Salary Structure', 'Indonesia Payroll Structure', 'ID Salary Structure'],
                    'IN': ['India Salary Structure', 'India Payroll Structure', 'IN Salary Structure'],
                    'SG': ['Singapore Salary Structure', 'Singapore Payroll Structure', 'SG Salary Structure'],
                    'TH': ['Thailand Salary Structure', 'Thailand Payroll Structure', 'TH Salary Structure'],
                    'KH': ['Cambodia Salary Structure', 'Cambodia Payroll Structure', 'KH Salary Structure'],
                    'MY': ['Malaysia Salary Structure', 'Malaysia Payroll Structure', 'MY Salary Structure'],
                }
                
                salary_structure = None
                structure_names = country_structure_names.get(payroll_country, [])
                
                # Try to find country-specific structure first
                for structure_name in structure_names:
                    salary_structure = self.env['hr.payroll.structure'].search([('name', '=', structure_name)], limit=1)
                    if salary_structure:
                        break
                
                # If no country-specific structure found, use any available structure as fallback
                if not salary_structure:
                    salary_structure = self.env['hr.payroll.structure'].search([], limit=1)
                
                if not salary_structure:
                    raise UserError(f"No salary structure found in the system! Please create at least one salary structure.")


                # Find or create general journal for payroll accounting
                gen_journal = self.env['account.journal'].search([('type', '=', 'general')], limit=1)
                if not gen_journal:
                    # Create a default general journal if none exists
                    try:
                        gen_journal = self.env['account.journal'].create({
                            'name': 'General Journal',
                            'code': 'GEN',
                            'type': 'general',
                        })
                    except Exception as e:
                        # If journal creation fails, make it optional for payroll import
                        _logger.warning(f"Could not create general journal: {e}. Payroll import will continue without journal reference.")
                        gen_journal = None

                # Determine contract type
                contract_type = zoho_employee.employee_type or 'Permanent' 
                # Search for existing contract type
                existing_contract_type = self.env['hr.contract.type'].search([('name', '=', contract_type)], limit=1)
                if not existing_contract_type:
                    # Create a new contract type if it doesn't exist
                    existing_contract_type = self.env['hr.contract.type'].create({'name': contract_type})

                # Create the contract with conditional journal
                contract_data = {
                    'name': f"{new_employee.name} Contract",
                    'employee_id': new_employee.id,
                    'date_start': zoho_employee.contract_from or datetime.date(2000, 1, 1),
                    'date_end': zoho_employee.contract_to or datetime.date(2100, 1, 1),
                    #'date_start': datetime.date(2000, 1, 1),
                    #'date_end': datetime.date(2100, 1, 1),
                    'state': 'open',  # 'open' is typically the state for running contracts
                    'struct_id': salary_structure.id,
                    'wage': zoho_employee.base_salary,
                    'type_id': existing_contract_type.id,  # Assign the contract type
                    # ... add other contract details if needed ...
                }
                
                # Add journal only if it exists
                if gen_journal:
                    contract_data['journal_id'] = gen_journal.id
                
                self.env['hr.contract'].create(contract_data)


            #Update contract values as per latest from zoho_employee_data
            if employee.contract_ids:
            #else:

                # Determine contract type
                contract_type = zoho_employee.employee_type or 'Permanent' 
                # Search for existing contract type
                existing_contract_type = self.env['hr.contract.type'].search([('name', '=', contract_type)], limit=1)
                if not existing_contract_type:
                    # Create a new contract type if it doesn't exist
                    existing_contract_type = self.env['hr.contract.type'].create({'name': contract_type})

                # --- Contract Update ---
                contract_data = {
                    'date_start': zoho_employee.contract_from or datetime.date(2000, 1, 1),
                    'date_end': zoho_employee.contract_to or datetime.date(2100, 1, 1),
                    'state': 'open',
                    'wage': zoho_employee.base_salary,
                    'type_id': existing_contract_type.id,
                    'tupart' : zoho_employee.tu_part,
                    'shuipart' : zoho_employee.shui_part,
                    'costcenter' : zoho_employee.costcenter,
                    'location' : zoho_employee.location_name,
                    #'hirestatus' : zoho_employee.employee_status,
                    'dependents' : zoho_employee.number_of_dependents,
                }

                # Update the latest contract
                latest_contract = employee.contract_ids.sorted(lambda c: c.date_start, reverse=True)[0]
                latest_contract.write(contract_data)

                # Update or Create contract advantages
                advantage_mapping = {
                    'GAZ': zoho_employee.gas_allowance,
                    'PHONE': zoho_employee.phone_allowance,
                    'MEAL': zoho_employee.meal_allowance,
                    'RESP': zoho_employee.resp_allowance,
                    'PARK': zoho_employee.park_allowance,
                    'TAXI': zoho_employee.taxi_allowance,
                    'RECO': zoho_employee.recog_bonus,
                    'OTHERINC': zoho_employee.other_income,
                    'OTHERBON': zoho_employee.other_bonus,
                    'BONSTIP': zoho_employee.bonus_stip,
                    'MARSH': zoho_employee.marsh_ins,
                    'ADJ': zoho_employee.adjustment,
                    'SALESINC': zoho_employee.sales_incentive,
                    'THMON': zoho_employee.thirteenth_month,
                    'SEVER': zoho_employee.sever_allow,
                    'REIMB': zoho_employee.reimb_payment,
                    'OTDEDU': zoho_employee.other_notcounted,
                    'PAIDUNUSED': zoho_employee.paidleave_unused,
                }
                for code, amount in advantage_mapping.items():
                    advantage_line = latest_contract.advantages_ids.filtered(lambda l: l.advantage_template_code == code)
                    if advantage_line:
                        advantage_line.write({'amount': amount})
                    else:
                        latest_contract.write({
                            'advantage_ids': [(0, 0, {'advantage_template_code': code, 'amount': amount})]
                        })

