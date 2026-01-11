# -*- coding: utf-8 -*-

from odoo import api, models


class ReportFullAndFinal(models.AbstractModel):
    _name = 'report.pb_hr_fullandfinal.report_full_and_final_document'
    _description = 'Full and Final Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        settlements = self.env['hr.full.final.settlement'].browse(docids)
        settlement_data = {}
        for settlement in settlements:
            components = settlement.get_component_summary()
            if not components:
                components = settlement._build_component_summary()
            settlement_data[settlement.id] = {
                'components': components,
                'currency': settlement.currency_id or settlement.company_id.currency_id,
                'settlement_month': settlement.settlement_month or '',
            }
        return {
            'doc_ids': settlements.ids,
            'doc_model': 'hr.full.final.settlement',
            'docs': settlements,
            'settlement_data': settlement_data,
        }
