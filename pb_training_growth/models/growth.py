# -*- coding: utf-8 -*-
"""Growth-plan objective → learning path (LEARNING L3, handover §3.5).

THE BRIDGE IS THE ONLY PLACE `pb_pip` IS TOUCHED (safety rail 4), and only by
inheritance: one column on the objective, one on the enrolment, and the
growth-plan facade's `get_case` gains a `path` dict per objective plus two
verbs. Every write keeps the growth-plan gate (`pb.pip._require_read` and the
plan's own `_require_hr`); the learning-path side is done as the system, the
same way the joining checklist enrols a joiner (the HR person running a plan
holds no training group by definition).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Enrolment states that count as "on it" for the chip.
_LIVE = ('not_started', 'in_progress', 'overdue', 'done')


class PbPipObjectivePath(models.Model):
    _inherit = 'pb.pip.objective'

    path_id = fields.Many2one(
        'pb.training.path', string='Learning path', ondelete='set null',
        index=True,
        help='The learning path that builds what this objective asks for.')
    path_enrolment_id = fields.Many2one(
        'pb.training.path.enrolment', string='On the path',
        compute='_compute_path')
    path_percent = fields.Integer(string='Path done (%)',
                                  compute='_compute_path')
    path_words = fields.Char(string='Path in words', compute='_compute_path')

    @api.depends('path_id', 'employee_id')
    def _compute_path(self):
        Enrol = self.env['pb.training.path.enrolment'].sudo()
        for rec in self:
            enr = Enrol.browse()
            if rec.path_id and rec.employee_id:
                enr = Enrol.search([
                    ('path_id', '=', rec.path_id.id),
                    ('employee_id', '=', rec.employee_id.id),
                    ('state', 'in', _LIVE)], order='id desc', limit=1)
            rec.path_enrolment_id = enr.id
            rec.path_percent = enr.percent if enr else 0
            rec.path_words = rec._path_sentence(enr)

    def _path_sentence(self, enr):
        """"Leading a line · 40%" — or "not on it yet", or "finished"."""
        self.ensure_one()
        if not self.path_id:
            return ''
        name = self.path_id.sudo().name or ''
        if not enr:
            return self.env._('%s · not on it yet', name)
        if enr.state == 'done':
            return self.env._('%s · finished', name)
        return self.env._('%(path)s · %(pct)s%%', path=name, pct=enr.percent)


class PbTrainingPathEnrolmentObjective(models.Model):
    _inherit = 'pb.training.path.enrolment'

    objective_id = fields.Many2one(
        'pb.pip.objective', string='For the growth-plan objective',
        ondelete='set null', index=True, readonly=True)


class PbPipPaths(models.AbstractModel):
    _inherit = 'pb.pip'

    # ------------------------------------------------------------ reading
    @api.model
    def _objective_path(self, objective):
        if not objective or not objective.path_id:
            return {}
        enr = objective.path_enrolment_id
        return {
            'id': objective.path_id.id,
            'name': objective.path_id.sudo().name or '',
            'percent': objective.path_percent,
            'words': objective.path_words,
            'enrolment_id': enr.id or 0,
            'state': enr.state or '',
            'late': enr.state == 'overdue',
        }

    @api.model
    def _path_options(self, case):
        paths = self.env['pb.training.path'].sudo().search([
            ('active', '=', True),
            ('company_id', '=', case.company_id.id or self.env.company.id)])
        return [{'id': p.id, 'name': p.name or ''} for p in paths]

    @api.model
    def get_case(self, case_id):
        data = super().get_case(case_id)
        try:
            ids = [o['id'] for o in data.get('objectives') or []]
            rows = {o.id: o for o in self.env['pb.pip.objective'].sudo()
                    .browse(ids).exists()}
            for line in data.get('objectives') or []:
                line['path'] = self._objective_path(rows.get(line['id']))
            case = self.env['pb.pip.case'].sudo().browse(int(case_id))
            data['path_options'] = self._path_options(case)
        except Exception:               # noqa: BLE001 — the plan still opens
            _logger.warning('pb_training_growth: the learning paths could not '
                            'be read for plan %s', case_id, exc_info=True)
            for line in data.get('objectives') or []:
                line.setdefault('path', {})
            data.setdefault('path_options', [])
        return data

    # ------------------------------------------------------------ writing
    @api.model
    def _objective(self, objective_id):
        self._require_read()
        row = self.env['pb.pip.objective'].browse(int(objective_id or 0)) \
            .exists()
        if not row:
            raise UserError(_("That objective could not be found."))
        row.case_id._require_hr()
        return row

    @api.model
    def set_objective_path(self, objective_id, path_id):
        """Point an objective at a learning path (or at none)."""
        row = self._objective(objective_id)
        path = self.env['pb.training.path'].sudo().browse(
            int(path_id or 0)).exists()
        if path and path.company_id != row.case_id.company_id:
            raise UserError(_("That learning path belongs to another "
                              "company."))
        row.sudo().write({'path_id': path.id or False})
        if path:
            row.case_id.message_post(body=_(
                "%(what)s now points at the learning path %(path)s.",
                what=row.name or _('An objective'), path=path.name))
        else:
            row.case_id.message_post(body=_(
                "%s no longer points at a learning path.",
                row.name or _('An objective')))
        return {'path': self._objective_path(row)}

    @api.model
    def enrol_objective_path(self, objective_id):
        """Put the plan's person on the objective's path, once."""
        row = self._objective(objective_id)
        if not row.path_id:
            raise UserError(_("Pick a learning path for this objective "
                              "first."))
        emp = row.employee_id.sudo()
        Enrol = self.env['pb.training.path.enrolment'].sudo()
        open_row = Enrol.search([
            ('path_id', '=', row.path_id.id), ('employee_id', '=', emp.id),
            ('state', 'in', ('not_started', 'in_progress', 'overdue'))],
            limit=1)
        if open_row:
            if not open_row.objective_id:
                open_row.write({'objective_id': row.id})
            return {'message': _("%(who)s is already on %(path)s.",
                                 who=emp.name, path=row.path_id.name),
                    'path': self._objective_path(row)}
        res = Enrol._enrol_people(row.path_id.id, [emp.id],
                                  reason='leadership', by_user=self.env.user)
        if res.get('no_login'):
            raise UserError(_(
                "%s has no login yet, so there is nowhere for the courses to "
                "appear.", emp.name))
        if not res.get('made'):
            raise UserError(res.get('message') or _("That did not work."))
        Enrol.browse(res['made'][0]).write({'objective_id': row.id})
        row.case_id.message_post(body=_(
            "%(who)s is put on the learning path %(path)s for %(what)s.",
            who=emp.name, path=row.path_id.name, what=row.name or ''))
        row.invalidate_recordset(['path_enrolment_id', 'path_percent',
                                  'path_words'])
        return {'message': _("%(who)s is on %(path)s. The first course is on "
                             "their list.", who=emp.name,
                             path=row.path_id.name),
                'path': self._objective_path(row)}
