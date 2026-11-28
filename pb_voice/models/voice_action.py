# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.voice.action`` — what the company will do about what it heard.

A small list of our own (owner default, FACTS §7): a title, the theme it came
from, an owner, a due date and a state. Not workflow tasks (those belong to
the Workflow programme) and not the approvals inbox. The owner is told by a
standard to-do and, on My Payobook, by a "Needs you" row while it is open.
"""

from odoo import api, fields, models
from odoo.tools import format_date
from odoo.exceptions import AccessError, UserError

from .voice_common import ACTION_STATES, THEMES

#: what the owner (not HR) may change on their own plan
_OWNER_FIELDS = frozenset({'state', 'progress'})


class PbVoiceAction(models.Model):
    _name = 'pb.voice.action'
    _description = 'Survey action plan'
    _inherit = ['mail.activity.mixin']
    _order = 'state, date_due, id'

    round_id = fields.Many2one('pb.voice.round', string='Survey', required=True,
                               index=True, ondelete='cascade',
                               groups='hr.group_hr_user,base.group_system')
    round_name = fields.Char(related='round_id.name', string='Survey name')
    company_id = fields.Many2one(related='round_id.company_id', store=True)
    theme = fields.Selection(THEMES, string='Theme', required=True,
                             default='engagement')
    name = fields.Char(string='What we will do', required=True)
    owner_id = fields.Many2one(
        'res.users', string='Owner', required=True,
        domain=[('share', '=', False)], default=lambda self: self.env.user)
    date_due = fields.Date(string='Due')
    state = fields.Selection(ACTION_STATES, string='Status', default='open',
                             required=True)
    progress = fields.Text(string='Progress note')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env['pb.voice.round']._voice_is_hr():
            raise AccessError(self.env._("Action plans are set up by HR."))
        recs = super().create(vals_list)
        for rec in recs:
            rec._voice_todo()
        return recs

    def write(self, vals):
        if not self.env.su and not self.env['pb.voice.round']._voice_is_hr():
            if set(vals) - _OWNER_FIELDS or any(
                    r.owner_id != self.env.user for r in self):
                raise AccessError(self.env._(
                    "You can update the progress of your own action plans "
                    "only."))
        if 'owner_id' in vals and vals.get('owner_id'):
            owner = self.env['res.users'].browse(vals['owner_id'])
            if owner.share:
                raise UserError(self.env._(
                    "The owner needs a staff login to follow it up."))
        res = super().write(vals)
        if 'owner_id' in vals or 'date_due' in vals:
            for rec in self:
                rec.activity_unlink(['mail.mail_activity_data_todo'])
                rec._voice_todo()
        if vals.get('state') == 'done':
            self.activity_unlink(['mail.mail_activity_data_todo'])
        return res

    def _voice_todo(self):
        """A standard to-do for the owner (no email of its own is sent from
        here; the to-do follows the owner's own notification settings)."""
        self.ensure_one()
        if self.state == 'done' or not self.owner_id or self.owner_id.share:
            return
        try:
            self.sudo().activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=self.date_due or fields.Date.context_today(self),
                summary=self.name[:100],
                note=self.env._('From the survey "%(name)s".',
                                name=self.sudo().round_id.name),
                user_id=self.owner_id.id)
        except Exception:                   # noqa: BLE001 — the plan stands
            pass

    def _voice_dict(self):
        self.ensure_one()
        rec = self.sudo()
        themes = dict(self._fields['theme']._description_selection(self.env))
        states = dict(self._fields['state']._description_selection(self.env))
        return {
            'id': rec.id, 'name': rec.name, 'theme': rec.theme,
            'theme_label': themes.get(rec.theme, ''),
            'owner': rec.owner_id.name or '', 'owner_id': rec.owner_id.id,
            'date_due': fields.Date.to_string(rec.date_due) if rec.date_due else '',
            'date_due_label': format_date(self.env, rec.date_due) if rec.date_due else '',
            'state': rec.state, 'state_label': states.get(rec.state, ''),
            'progress': rec.progress or '',
            'round': rec.round_id.name or '',
            'overdue': bool(rec.date_due and rec.state != 'done'
                            and rec.date_due < fields.Date.context_today(self)),
        }
