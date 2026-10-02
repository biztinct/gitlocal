# Copyright 2022 CreuBlanca
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import json
import zipfile
from io import BytesIO

from odoo import _, api, fields, models
#Biztinct
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError
from datetime import datetime

from odoo import models, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class SpreadsheetSpreadsheet(models.Model):
    _name = "spreadsheet.spreadsheet"
    _inherit = "spreadsheet.abstract"
    _description = "Spreadsheet"

    data = fields.Binary()
    filename = fields.Char(compute="_compute_filename")
    spreadsheet_raw = fields.Serialized(
        compute="_compute_spreadsheet_raw", inverse="_inverse_spreadsheet_raw"
    )
    owner_id = fields.Many2one(
        "res.users", required=True, default=lambda r: r.env.user.id
    )
    contributor_ids = fields.Many2many(
        "res.users",
        relation="spreadsheet_contributor",
        column1="spreadsheet_id",
        column2="user_id",
        string="Contributors",
    )
    reader_ids = fields.Many2many(
        "res.users",
        relation="spreadsheet_reader",
        column1="spreadsheet_id",
        column2="user_id",
        string="Readers",
    )


    @api.depends("name")
    def _compute_filename(self):
        for record in self:
            record.filename = "%s.json" % (self.name or _("Unnamed"))

    @api.depends("data")
    def _compute_spreadsheet_raw(self):
        for dashboard in self:
            if dashboard.data:
                dashboard.spreadsheet_raw = json.loads(
                    base64.decodebytes(dashboard.data).decode("UTF-8")
                )
            else:
                dashboard.spreadsheet_raw = {}

    def _inverse_spreadsheet_raw(self):
        for record in self:
            record.data = base64.encodebytes(
                json.dumps(record.spreadsheet_raw).encode("UTF-8")
            )

    def create_document_from_attachment(self, attachment_ids):
        attachments = self.env["ir.attachment"].browse(attachment_ids)
        spreadsheets = self.env["spreadsheet.spreadsheet"]
        for attachment in attachments:
            extracted = {}
            with zipfile.ZipFile(
                BytesIO(base64.b64decode(attachment.datas)), "r"
            ) as xlsx:
                # List and filter for XML and REL files
                xml_files = [
                    f
                    for f in xlsx.namelist()
                    if f.endswith(".xml") or f.endswith(".rels")
                ]
                # Extract each file
                for xml_file in xml_files:
                    # Read the XML file into memory
                    with xlsx.open(xml_file) as file:
                        extracted[xml_file] = file.read().decode("UTF8")
                spreadsheets |= self.create(
                    {
                        "spreadsheet_raw": extracted,
                        "name": attachment.name,
                    }
                )
        attachments.unlink()
        if len(spreadsheets) == 1:
            return spreadsheets.get_formview_action()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "spreadsheet_oca.spreadsheet_spreadsheet_act_window"
        )
        action["domain"] = [("id", "in", spreadsheets.ids)]
        return action


    #Biztinct
    '''   
    def write(self, vals):
        set_trace()
        if 'data' in vals:
            for record in self:
                header_row = record.data[0] if record.data else None
                if not header_row:
                    raise ValidationError("The header row cannot be deleted.")
        return super(SpreadsheetSpreadsheet, self).write(vals)
    '''

    '''
    def write(self, vals):
        # Decoding the data from base64
        data = json.loads(base64.b64decode(self.data).decode("UTF-8"))
        set_trace()
        # Check for changes in the "Staging" worksheet
        for sheet in data.get('sheets', []):
            if sheet['name'] == "Staging":
                for cell, content in sheet.get('cells', {}).items():
                    row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                    if row <= 2:  # Check if row is 1 or 2
                        if cell in vals:  # Check if cell is being modified
                            raise ValidationError("You are not allowed to modify the top 2 rows in the 'Staging' worksheet.")

        return super().write(vals)
    '''



    '''
    def write(self, vals):
        # Check if 'data' field is being modified
        if 'data' in vals:
            # Decode the base64 encoded original data
            original_data = json.loads(base64.b64decode(self.data).decode("UTF-8"))

            # Decode the base64 encoded new data
            new_data = json.loads(base64.b64decode(vals['data']).decode("UTF-8"))

            # Check for changes in the "Staging" worksheet
            for new_sheet in new_data.get('sheets', []):
                if new_sheet['name'] == "Staging":
                    original_sheet = next((sheet for sheet in original_data.get('sheets', []) if sheet['name'] == "Staging"), None)
                    if not original_sheet:
                        raise ValidationError("Original 'Staging' worksheet not found.")

                    for cell, new_content in new_sheet.get('cells', {}).items():
                        row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                        if row <= 2:  # Check if row is 1 or 2
                            original_content = original_sheet.get('cells', {}).get(cell, {}).get('content', '')
                            if new_content.get('content', '') != original_content:  # Check if content has changed
                                raise ValidationError("You are not allowed to modify the top 2 rows in the 'Staging' worksheet.")

        return super().write(vals)
    '''



    '''
    def write(self, vals):
        # Check if 'data' field is being modified
        if 'data' in vals:
            # Ensure the data is a string and not boolean
            if isinstance(vals['data'], (str, bytes)):
                try:
                    # Decode the base64 encoded original data
                    original_data = json.loads(base64.b64decode(self.data).decode("UTF-8"))

                    # Decode the base64 encoded new data
                    new_data = json.loads(base64.b64decode(vals['data']).decode("UTF-8"))

                    changes = []
                                        
                    # Check for changes in the "Staging" worksheet
                    for new_sheet in new_data.get('sheets', []):
                        if new_sheet['name'] == "Staging":
                            original_sheet = next((sheet for sheet in original_data.get('sheets', []) if sheet['name'] == "Staging"), None)
                            if not original_sheet:
                                raise ValidationError("Original 'Staging' worksheet not found.")

                            for cell, new_content in new_sheet.get('cells', {}).items():
                                row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                                if row <= 2:  # Check if row is 1 or 2
                                    original_content = original_sheet.get('cells', {}).get(cell, {}).get('content', '')
                                    if new_content.get('content', '') != original_content:  # Check if content has changed
                                        changes.append({
                                            'cell': cell,
                                            'original': original_content,
                                            'new': new_content.get('content', '')
                                        })
                                        
                    if changes:
                        # Format the changes into a message
                        change_messages = [f"Cell {change['cell']}: Original Content = '{change['original']}', New Content = '{change['new']}'" for change in changes]
                        #super().write({'data': self.data})
                        #raise ValidationError("The following changes were detected in the top 2 rows of the 'Staging' worksheet:\n" + "\n".join(change_messages))
                        return
                except (TypeError, json.JSONDecodeError, base64.binascii.Error) as e:
                    self.env.user.notify_info(message=f"Error decoding base64 data: {e}", title='INFO', sticky=False)
                    return super().write(vals)
            else:
                self.env.user.notify_info(message="Invalid data format: Expected a base64-encoded string.", title='INFO', sticky=False)
                return super().write(vals)

        return super().write(vals)
    '''

    ###################################################################################
    # Following method is used by Import Spreadsheet menuitem to import data 
    ####################################################################################

    def import_manual_json_data(self):

        # Need to delete zoho.employee.data as it gets deleted only when you run import_timesheets
        self.env['zoho.employee.data'].search([]).unlink()
        data = json.loads(base64.b64decode(self.data).decode("UTF-8"))
        headers_emp_details = {}
        rows_emp_details = {}

        for sheet in data.get('sheets', []):
            if sheet['name'] == "TEMPLATE Employee Details":
                for cell, content in sheet.get('cells', {}).items():
                    col = ''.join(filter(str.isalpha, cell))  # Extract column letters
                    row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                    if row == 1 and 'HEADER' in content['content']:
                        field_name = content['content'].split('\"')[1]
                        headers_emp_details[col] = field_name
                break

        for sheet in data.get('sheets', []):
            if sheet['name'] == "Employee Details":
                for cell, content in sheet.get('cells', {}).items():
                    col = ''.join(filter(str.isalpha, cell))  # Extract column letters
                    row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                    if row > 1:  # Skip headers
                        if row not in rows_emp_details:
                            rows_emp_details[row] = {}
                        cell_value = content.get('content', '')
                        # Modify cell_value if column is 'A' and it starts with 'E' . 
                        # This has been done because E has been deliberately appended in spreadsheet to make it text and not number
                        
                        if col == 'A' and cell_value.startswith('E'):
                            cell_value = cell_value[1:]  # Strip the first letter
                        
                        rows_emp_details[row][col] = cell_value
                break

        for row, cells in rows_emp_details.items():
            field_value_dict = {}
            for col, field_name in headers_emp_details.items():
                cell_value = cells.get(col, '')
                if cell_value.strip() == '-':  # Check if cell_value is only a hyphen after stripping blanks
                    cell_value = ''  # Change cell value to empty string
                if cell_value:  # Check if cell_value is not empty or null
                    if field_name in ['contract_from', 'contract_to', 'start_date', 'end_date']:  # Date fields
                        cell_value = self.parse_date(cell_value)  # Parse date values
                    field_value_dict[field_name] = cell_value
                else:
                    field_value_dict[field_name] = None  # Handle empty data fields
            #set_trace()
            self.env['zoho.employee.data'].create(field_value_dict)
          
        #self.env.user.notify_success(message='Manual payroll data has been process successfully! Now you can import data', title='SUCCESS', sticky=False)
        self.import_json_data()
        
        return {
            'type': 'ir.actions.act_window_close',
        }     
           

    ###################################################################################
    # Following method is used by Import Integrated Spreadsheet menuitem to import data 
    ####################################################################################

    def import_json_data(self):
        #self.env.user.notify_info(message='Payroll data is being imported from FINAL worksheet. Ensure FINAL worksheet has latest data otherwise copy and import again.', title='INFORMATION', sticky=False )
        # Get payroll country from context
        payroll_country = self.env.context.get('payroll_country', 'VN')
        
        # Select appropriate spreadsheet based on country with updated external IDs
        spreadsheet_refs = {
            'VN': 'pb_hr_payroll_vietnam.payrollstaging_vietnam',
            'ID': 'pb_hr_payroll_indonesia.payrollstaging_indonesia', 
            'IN': '__custom__.payrollstaging_india',
            'SG': '__custom__.payrollstaging_singapore',
            'TH': '__custom__.payrollstaging_thailand',
            'KH': '__custom__.payrollstaging_cambodia',
            'MY': '__custom__.payrollstaging_malaysia',
        }
        
        spreadsheet_ref = spreadsheet_refs.get(payroll_country)
        if spreadsheet_ref:
            spreadsheet = self.env.ref(spreadsheet_ref, raise_if_not_found=False)
        else:
            spreadsheet = None
            
        if not spreadsheet:
            # If country-specific spreadsheet not found, try to use the current spreadsheet (self)
            spreadsheet = self
            if not spreadsheet.data:
                raise UserError(f"{payroll_country} payroll spreadsheet not found! Expected reference: {spreadsheet_ref or 'Unknown country'}")
        
        # Continue with existing logic but use selected spreadsheet
        # ... rest of the existing import_json_data code ...
        
        # Make sure to pass payroll_country in context when calling _create_or_update_employee
        self.env['zoho.timesheet.importer'].with_context(payroll_country=payroll_country)._create_or_update_employee()

        data = json.loads(base64.b64decode(spreadsheet.data).decode("UTF-8"))

        # Delete all existing data from zoho.employee.data
        #self.env['zoho.employee.data'].search([]).unlink()

        # Process the "Employee details" sheet
        headers_emp_details = {}
        rows_emp_details = {}

        for sheet in data.get('sheets', []):
            if sheet['name'] == "TEMPLATE Employee Details":
                for cell, content in sheet.get('cells', {}).items():
                    col = ''.join(filter(str.isalpha, cell))  # Extract column letters
                    row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                    if row == 1 and 'HEADER' in content['content']:
                        field_name = content['content'].split('\"')[1]
                        headers_emp_details[col] = field_name
                break

        for sheet in data.get('sheets', []):
            if sheet['name'] == "Employee Details":
                for cell, content in sheet.get('cells', {}).items():
                    col = ''.join(filter(str.isalpha, cell))  # Extract column letters
                    row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                    if row > 1:  # Skip headers
                        if row not in rows_emp_details:
                            rows_emp_details[row] = {}
                        cell_value = content.get('content', '')
                        # Modify cell_value if column is 'A' and it starts with 'E' . 
                        # This has been done because E has been deliberately appended in spreadsheet to make it text and not number
                        
                        if col == 'A' and cell_value.startswith('E'):
                            cell_value = cell_value[1:]  # Strip the first letter
                        
                        rows_emp_details[row][col] = cell_value
                break

        field_value_dicts = {}  # Dictionary to hold all field_value_dicts based on employee_id
        for row, cells in rows_emp_details.items():
            field_value_dict = {}
            for col, field_name in headers_emp_details.items():
                cell_value = cells.get(col, '')
                if cell_value.strip() == '-':  # Check if cell_value is only a hyphen after stripping blanks
                    cell_value = ''  # Change cell value to empty string
                if cell_value:  # Check if cell_value is not empty or null
                    if field_name in ['contract_from', 'contract_to', 'start_date', 'end_date']:  # Date fields
                        cell_value = self.parse_date(cell_value)  # Parse date values
                    field_value_dict[field_name] = cell_value
                else:
                    field_value_dict[field_name] = None  # Handle empty data fields

            employee_id_cell = cells.get('A', '')  # Assuming employee_id is in column A. Also note that it is already stripped of E as above
            if employee_id_cell:
                employee_id = employee_id_cell
                field_value_dicts[employee_id] = field_value_dict  # Store field_value_dict by employee_id

        headers = {}
        rows = {}
        # Extract headers from the "Staging" sheet
        for sheet in data.get('sheets', []):
            if sheet['name'] == "Staging":
                for cell, content in sheet.get('cells', {}).items():
                    col = ''.join(filter(str.isalpha, cell))  # Extract column letters
                    row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                    if row == 1 and 'HEADER' in content['content']:
                        field_name = content['content'].split('\"')[1]
                        headers[col] = field_name
                break
        # Extract values from the "Final" sheet
        for sheet in data.get('sheets', []):
            if sheet['name'] == "Final":
                for cell, content in sheet.get('cells', {}).items():
                    col = ''.join(filter(str.isalpha, cell))  # Extract column letters
                    row = int(''.join(filter(str.isdigit, cell)))  # Extract row numbers
                    if row > 1:  # Skip headers
                        if row not in rows:
                            rows[row] = {}
                        cell_value = content.get('content', '').strip()

                        # Modify cell_value if column is 'A' and it starts with 'E' as it was delberately added to make spreadhseet column as Text and not number
                        if col == 'A' and cell_value.startswith('E'):
                            cell_value = cell_value[1:]  # Strip the first letter

                        rows[row][col] = cell_value  # Update the rows dictionary with the modified value
                break

        # Update field_value_dict with values from "Final" sheet
        for row, cells in rows.items():
            employee_id_cell = cells.get('A', '')  # Assuming employee_id is in column A
            if employee_id_cell:
                employee_id = employee_id_cell
                field_value_dict = field_value_dicts.get(employee_id, {})  # Get the existing dictionary or create a new one
                for col, field_name in headers.items():
                    cell_value = cells.get(col, '')
                    if cell_value.strip() == '-':  # Check if cell_value is only a hyphen after stripping blanks
                        cell_value = ''  # Change cell value to empty string
                    if cell_value:  # Check if cell_value is not empty or null
                        if field_name in ['date_of_birth', 'date_of_joining', 'start_date', 'end_date', 'last_workday', 'contract_from', 'contract_to']:  # Date fields
                            cell_value = self.parse_date(cell_value)  # Parse date values
                        field_value_dict[field_name] = cell_value
                    else:
                        field_value_dict[field_name] = None  # Handle empty date fields
                field_value_dicts[employee_id] = field_value_dict  # Update the dictionary for this employee_id

        # Now update or create the record in zoho_employee_data with the combined field_value_dict
        for employee_id, field_value_dict in field_value_dicts.items():
            record = self.env['zoho.employee.data'].search([('employee_id', '=', employee_id)])
            if record:
                record.write(field_value_dict)
            else:
                self.env['zoho.employee.data'].create(field_value_dict)

        # Update various models like employee , contract, bank etc and also pay amount
        #self.env['zoho.timesheet.importer']._create_or_update_employee()
        self.env['zoho.timesheet.importer'].with_context(payroll_country=payroll_country)._create_or_update_employee()
        self.env.user.notify_success(message='Import of payroll data completed successfully! Now you can do payroll processing', title='SUCCESS', sticky=True)
        return {
            'type': 'ir.actions.act_window_close',
        }
  

    @staticmethod
    def parse_date(date_str):
        # Check if the date_str is a number
        if date_str.isdigit():
            # Convert the number to an integer
            date_num = int(date_str)
            # Calculate the date from the base date (e.g., 1-Jan-1900)
            base_date = datetime(1900, 1, 1)
            date = base_date + timedelta(days=date_num - 2)  # Adjust for Excel's date system
            return date.date()

        # Try parsing the date in various formats
        for fmt in ('%Y-%m-%d', '%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%d/%m/%y', '%m/%d/%Y'):
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        #return None
        return datetime(2000, 1, 1).date()
        #raise ValueError(f"Date format not supported: {date_str}")



