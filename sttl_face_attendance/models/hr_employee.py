# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class Employee(models.Model):
    _inherit = 'hr.employee'

    def new_employee_image(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'new_employee_image',
            'params': {
                'employee_id': self.id,
            }
        }

    def register_face(self, image_data):
        try:
            if image_data.startswith('data:image/png;base64,'):
                image_data = image_data.split('base64,')[1]

            if image_data:
                self.image_1920 = image_data
                _logger.info("Image saved successfully.")
            else:
                _logger.warning("No image data provided.")
        except Exception as e:
            _logger.error("Error registering face: %s", str(e))

    def get_employee_images(self):
        for rec in self:
            _logger.info(f"self : {rec}")
            employee_data = [{"employee_id": rec.id, "image": rec.image_1920}]
            return employee_data
        employees = self.env['hr.employee'].search([])
        employee_data = []
        for employee in employees:
            employee_data.append({"employee_id": employee.id, "image":employee.image_1920})
        return employee_data
