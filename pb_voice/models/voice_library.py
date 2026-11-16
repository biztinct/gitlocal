# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.voice.library`` — ready-made questions in English, Vietnamese and
Indonesian. OFFERED, never started: installing the module creates no round
and asks nobody anything; HR picks questions into a round of their own."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from .voice_common import KINDS, THEMES


class PbVoiceLibrary(models.Model):
    _name = 'pb.voice.library'
    _description = 'Survey question library'
    _order = 'sequence, id'
    _rec_name = 'text'

    sequence = fields.Integer(default=10)
    kind = fields.Selection(KINDS, string='Answered as', required=True,
                            default='scale')
    theme = fields.Selection(THEMES, string='Theme', required=True,
                             default='engagement')
    text = fields.Char(string='Question', required=True, translate=True)
    options = fields.Text(string='Options', translate=True,
                          help='For "Pick one option": one option per line.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        help='Leave empty for a question every company can use.')

    def _round_vals(self, round_id, sequence):
        """Question values for a round, carrying EVERY language's words."""
        self.ensure_one()
        return {'round_id': round_id, 'sequence': sequence, 'kind': self.kind,
                'theme': self.theme, 'library_id': self.id}

    def _copy_into(self, rnd):
        """Add these library questions to a draft round, in all languages."""
        if rnd.state != 'draft':
            raise UserError(self.env._(
                "This round has been sent out, so no question can be added."))
        Q = self.env['pb.voice.question']
        langs = [code for code, _n in self.env['res.lang'].get_installed()]
        seq = max(rnd.question_ids.mapped('sequence') or [0])
        made = Q
        for lib in self:
            seq += 10
            q = Q.create(dict(lib._round_vals(rnd.id, seq),
                              text=lib.text, options=lib.options or False))
            for lang in langs:
                src = lib.with_context(lang=lang)
                q.with_context(lang=lang).write(
                    {'text': src.text, 'options': src.options or False})
            made |= q
        return made


class PbVoiceLibraryPick(models.TransientModel):
    """"Add from the library": tick questions, press Add."""
    _name = 'pb.voice.library.pick'
    _description = 'Add questions from the library'

    round_id = fields.Many2one('pb.voice.round', required=True)
    library_ids = fields.Many2many(
        'pb.voice.library', string='Questions',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    company_id = fields.Many2one(related='round_id.company_id')
    has_values = fields.Boolean(compute='_compute_has_values')

    def _compute_has_values(self):
        on = 'pb.company.value' in self.env
        for rec in self:
            rec.has_values = on

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        rid = self.env.context.get('default_round_id') or (
            self.env.context.get('active_model') == 'pb.voice.round'
            and self.env.context.get('active_id'))
        if rid:
            res['round_id'] = rid
        return res

    def action_add(self):
        self.ensure_one()
        self.round_id._voice_require_hr()
        already = set(self.round_id.question_ids.mapped('library_id').ids)
        self.library_ids.filtered(lambda l: l.id not in already)._copy_into(
            self.round_id)
        return {'type': 'ir.actions.act_window_close'}

    def action_add_values(self):
        """Praise's company values as rating questions (when Praise is here)."""
        self.ensure_one()
        rnd = self.round_id
        rnd._voice_require_hr()
        if 'pb.company.value' not in self.env:
            raise UserError(self.env._("No company values are set up."))
        values = self.env['pb.company.value'].sudo().search(
            ['|', ('company_id', '=', False),
             ('company_id', '=', rnd.company_id.id)])
        if not values:
            raise UserError(self.env._(
                "No company values are set up. Add them under Praise first."))
        langs = [code for code, _n in self.env['res.lang'].get_installed()]
        Q = self.env['pb.voice.question']
        seq = max(rnd.question_ids.mapped('sequence') or [0])
        for val in values:
            seq += 10
            q = Q.create({'round_id': rnd.id, 'sequence': seq, 'kind': 'scale',
                          'theme': 'values',
                          'text': self.env._('People here live our value: %(v)s',
                                             v=val.name)})
            for lang in langs:
                me = self.with_context(lang=lang)
                q.with_context(lang=lang).write({'text': me.env._(
                    'People here live our value: %(v)s',
                    v=val.with_context(lang=lang).name)})
        return {'type': 'ir.actions.act_window_close'}
