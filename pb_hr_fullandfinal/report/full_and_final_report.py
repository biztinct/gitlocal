# -*- coding: utf-8 -*-

from odoo import api, models


class ReportFullAndFinal(models.AbstractModel):
    _name = 'report.pb_hr_fullandfinal.report_full_and_final_document'
    _description = 'Full and Final Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        employees = self.env['hr.employee'].browse(docids)
        payslip_data = {}
        for employee in employees:
            payslip = self.env['hr.payslip'].search(
                [('employee_id', '=', employee.id)],
                order='date_to desc',
                limit=1,
            )
            net_amount = 0.0
            net_code = False
            if payslip:
                net_line = payslip.line_ids.filtered(lambda line: line.code in ('NETPAY', 'NET_PAY', 'NET'))
                if net_line:
                    net_line = net_line[0]
                    net_amount = net_line.total
                    net_code = net_line.code
            payslip_data[employee.id] = {
                'payslip': payslip,
                'net_amount': net_amount,
                'net_code': net_code,
            }
        return {
            'doc_ids': employees.ids,
            'doc_model': 'hr.employee',
            'docs': employees,
            'payslip_data': payslip_data,
        }
