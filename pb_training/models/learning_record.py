# -*- coding: utf-8 -*-
"""LEARNING L1 — the learning record, a PDF that reads like a transcript.

Every finished course (when, and the score) and every certificate and
licence (who issued it, when, and where it stands today) for one person, on
the company's own letterhead. The values are built HERE, not in the template,
so the template only lays out words that are already right.
"""

import logging

from odoo import api, fields, models

from .training_common import tr

_logger = logging.getLogger(__name__)


class ReportLearningRecord(models.AbstractModel):
    _name = 'report.pb_training.report_learning_record'
    _description = 'Payobook Training — the learning record'

    @api.model
    def _get_report_values(self, docids, data=None):
        employees = self.env['hr.employee'].sudo().browse(docids).exists()
        return {
            'doc_ids': employees.ids,
            'doc_model': 'hr.employee',
            'docs': employees,
            'records': {emp.id: self._record(emp) for emp in employees},
        }

    @api.model
    def _record(self, emp):
        today = fields.Date.today()
        Doc = self.env['pb.employee.document']
        date_words = Doc._pb_date_words
        done = self.env['pb.training.assignment'].sudo().search(
            [('employee_id', '=', emp.id), ('state', '=', 'done')],
            order='completed_on desc, id desc')
        courses = [{
            'course': row.channel_id.sudo().name or '',
            'finished': date_words(row.completed_on) if row.completed_on
            else '',
            'score': ('%s%%' % int(round(row.score))) if row.score else '',
            # LEARNING L2: the hours the course counted for when finished.
            'hours': _hours_words(row.hours),
        } for row in done]
        total_hours = sum(done.mapped('hours'))
        certs = []
        if 'pb.employee.document' in self.env:
            docs = self.env['pb.employee.document'].sudo().search(
                [('employee_id', '=', emp.id),
                 ('training_source', '!=', False)],
                order='issue_date desc, id desc')
            for doc in docs:
                certs.append({
                    'name': doc.name or '',
                    'issuer': doc.issuer or '',
                    'issued': date_words(doc.issue_date),
                    'valid': doc.valid_words or '',
                    'state': doc.training_state,
                    'checked': tr(self.env, 'Yes') if doc.verified else '',
                })
        live = [c for c in certs if c['state'] != 'renewed']
        return {
            'name': emp.name or '',
            'job': emp.job_id.name or emp.job_title or '',
            'department': emp.department_id.name or '',
            'company': emp.company_id.name or '',
            'as_at': date_words(today),
            'courses': courses,
            'certificates': certs,
            'summary': self._summary(len(courses), live),
            'hours_total': _hours_words(total_hours),
        }

    @api.model
    def _summary(self, finished, live):
        env = self.env
        bits = [tr(env, '1 course finished') if finished == 1
                else tr(env, '%s courses finished', finished)]
        valid = len([c for c in live if c['state'] in ('valid', 'soon',
                                                         'none')])
        bits.append(tr(env, '1 certificate in date') if valid == 1
                    else tr(env, '%s certificates in date', valid))
        soon = len([c for c in live if c['state'] == 'soon'])
        if soon:
            bits.append(tr(env, '1 due for renewal') if soon == 1
                        else tr(env, '%s due for renewal', soon))
        gone = len([c for c in live if c['state'] == 'expired'])
        if gone:
            bits.append(tr(env, '1 expired') if gone == 1
                        else tr(env, '%s expired', gone))
        return ' · '.join(bits)


def _hours_words(hours):
    hours = float(hours or 0.0)
    if not hours:
        return ''
    return ('%d' % hours) if hours == int(hours) else ('%.1f' % hours)
