"""Read-only import provenance for people the current scheme map cannot reach."""
from odoo import api, models


class SchemeImportEvidence(models.AbstractModel):
    _inherit = 'pb.scheme.board'

    def _people_import_evidence(self, people, company_id):
        """A linked import is evidence, never a permanent assignment.

        The caller has already authorised the company and limited the roster.
        Repeat both company constraints before reading staging data with sudo.
        Keep archived schemes as history, with an explicit availability flag.
        """
        ids = [person['employee_id'] for person in people]
        if not ids or 'hr.payroll.import.line' not in self.env:
            return people
        Line = self.env['hr.payroll.import.line'].sudo()
        latest = Line._read_group([
            ('employee_id', 'in', ids),
            ('employee_id.company_id', '=', company_id),
            ('batch_id.company_id', '=', company_id),
            ('batch_id.source_type', '=', 'excel'),
            ('batch_id.formula_config_id.company_id', 'in', [False, company_id]),
            ('batch_id.state', 'not in', ['draft', 'cancelled', 'error']),
            ('state', 'in', ['matched', 'validated', 'processed']),
        ], ['employee_id'], ['id:max'])
        lines = Line.browse([line_id for _employee, line_id in latest])
        evidence = {}
        for line in lines:
            if line.employee_id.id in evidence:
                continue
            batch = line.batch_id
            config = batch.formula_config_id
            if not config or config.company_id.id not in (False, company_id):
                continue
            evidence[line.employee_id.id] = {
                'config_id': config.id,
                'config': config.name or '',
                'available': bool(config.active and config.state == 'active'),
                'filename': batch.import_filename or '',
                'batch': batch.name or '',
                'processed': line.state == 'processed',
                'cycle': self.env['pb.scheme.map'].cycle_words(config.cycle_type),
            }
        return [dict(person, import_evidence=evidence.get(person['employee_id']) or False)
                for person in people]

    @api.model
    def get_board(self, company_id=None, cycle_type='any'):
        board = super().get_board(company_id, cycle_type)
        if board.get('allowed'):
            board['exceptions']['people'] = self._people_import_evidence(
                board['exceptions']['people'], board['company_id'])
        return board

    @api.model
    def exceptions(self, company_id=None, cycle_type='any'):
        result = super().exceptions(company_id, cycle_type)
        result['people'] = self._people_import_evidence(
            result['people'], result['company_id'])
        return result
