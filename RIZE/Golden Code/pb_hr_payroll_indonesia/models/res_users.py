# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'
    
    def has_payroll_access(self, country_code):
        """Check if user has access to specific country payroll"""
        group_mapping = {
            'VN': 'pb_hr_payroll_indonesia.group_vietnam_payroll_user',
            'ID': 'pb_hr_payroll_indonesia.group_indonesia_payroll_user',
            'IN': 'pb_hr_payroll_indonesia.group_india_payroll_user',
        }
        
        group_xml_id = group_mapping.get(country_code)
        if group_xml_id:
            return self.has_group(group_xml_id)
        return False
        
        group_xml_id = group_mapping.get(country_code)
        if group_xml_id:
            return self.has_group(group_xml_id)
        return False