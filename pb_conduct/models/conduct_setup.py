# -*- coding: utf-8 -*-
"""The three set-up tables: reasons, letter wording, country notes.

None of them names a person, but they are still read only by the people
named for conduct cases (their ACL), and changed only by the head of HR for
conduct cases.

COUNTRY NOTES ARE EMPTY ON PURPOSE. The legal steps for a hearing or a
warning differ by country (Vietnam, Indonesia, ...) and checking them is an
owner/adviser item, not something this module may invent. HR writes what their
adviser tells them; every case shows "Check each step with your adviser".
"""

import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .conduct_common import LETTER_KINDS, NOTE_STEPS

#: The words a letter template may use. Anything else stays as typed.
PLACEHOLDERS = (
    'employee', 'job', 'department', 'company', 'date', 'reason',
    'incident_date', 'hearing_date', 'hearing_place', 'decision',
    'valid_until', 'signed_by',
)


class PbConductReason(models.Model):
    _name = 'pb.conduct.reason'
    _description = 'Conduct case reason'
    _order = 'sequence, id'

    name = fields.Char(string='Reason', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave empty to offer it in every company.')


class PbConductCountryNote(models.Model):
    _name = 'pb.conduct.country.note'
    _description = 'Conduct case country note'
    _order = 'country_id, step'

    country_id = fields.Many2one('res.country', string='Country', required=True)
    step = fields.Selection(NOTE_STEPS, string='Step', required=True)
    note = fields.Text(
        string='What to do in this country', required=True,
        help='Write what your adviser tells you for this step in this country '
             '(time limits, who must attend, what the letter must say). It '
             'shows on every case at this step.')

    _country_step_uniq = models.Constraint(
        'unique(country_id, step)',
        'There is already a note for this country and step. Edit that one.')


class PbConductLetterTemplate(models.Model):
    _name = 'pb.conduct.letter.template'
    _description = 'Conduct letter wording'
    _order = 'kind, sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    kind = fields.Selection(LETTER_KINDS, string='Letter', required=True)
    sequence = fields.Integer(default=10)
    title = fields.Char(string='Letter title', required=True, translate=True)
    body = fields.Text(
        string='Wording', required=True, translate=True,
        help='The letter text. Words in ${...} are filled in from the case: '
             '${employee}, ${job}, ${department}, ${company}, ${date}, '
             '${reason}, ${incident_date}, ${hearing_date}, ${hearing_place}, '
             '${decision}, ${valid_until}, ${signed_by}.')
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave empty to use it in every company.')
    active = fields.Boolean(default=True)

    @api.constrains('body')
    def _check_placeholders(self):
        for rec in self:
            for word in re.findall(r'\$\{([^}]*)\}', rec.body or ''):
                if word.strip() not in PLACEHOLDERS:
                    raise ValidationError(_(
                        '"${%(word)s}" is not a word the letter can fill in. '
                        'Use one of: %(words)s.', word=word,
                        words=', '.join('${%s}' % p for p in PLACEHOLDERS)))

    @api.model
    def pick(self, kind, company):
        """The wording for a kind: the company's own first, then the shared one."""
        dom = [('kind', '=', kind),
               '|', ('company_id', '=', False),
               ('company_id', '=', company.id if company else False)]
        rows = self.sudo().search(dom, order='company_id desc, sequence, id', limit=1)
        return rows

    @staticmethod
    def render(text, values):
        """Fill ${word} from `values`. Plain replacement: nothing is evaluated."""
        out = text or ''
        for key in PLACEHOLDERS:
            out = out.replace('${%s}' % key, values.get(key) or '')
        return out
