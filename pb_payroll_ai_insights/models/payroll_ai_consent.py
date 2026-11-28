# -*- coding: utf-8 -*-
"""What a user has agreed to let PayAI send out, one row per user.

WHY A ROW AND NOT A BROWSER FLAG
--------------------------------
The only consent worth having is one the SERVER can refuse against. A
preference kept in localStorage is a preference the RPC endpoint cannot see,
and `rpc_transcribe_voice` is reachable from anything holding a session — so
the browser's own check saves a round trip and is not the control.

MODELLED ON `learn.consent` (pb_learn/models/learn_question.py), deliberately
and shape for shape: own-rows record rule, one row per user, a three-valued
selection where 'unset' means "has not been asked" rather than "said no", a
`should_ask_*` predicate that is False when there is nothing to ask ABOUT, and
an idempotent setter. Not IMPORTED from there: this module already depends on
pb_learn, but a consent about PayAI's audio egress belongs to PayAI — a row in
another module's table would make uninstalling either one a data question, and
the two consents are about different things.

WHAT VOICE CONSENT IS ABOUT, and the copy says it in both languages: the
RECORDING ITSELF leaves this server. Everything else PayAI sends can be
redacted; a person's voice saying a colleague's name cannot be. See the
raw-audio residual in ai_redaction.py.
"""
from odoo import api, fields, models

# The tenant's half of the gate. Absent or falsey means off — a feature that
# posts audio to a third party does not get to default to on.
VOICE_FLAG = 'payai.voice_enabled'


def flag_on(env, name):
    raw = env['ir.config_parameter'].sudo().get_param(name)
    return str(raw or '').strip().lower() in ('1', 'true', 'yes', 'on')


class PayrollAIConsent(models.Model):
    _name = 'payroll.ai.consent'
    _description = 'PayAI user consent'
    _order = 'write_date desc'

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user,
                              ondelete='cascade')
    voice = fields.Selection(
        selection=lambda self: self._selection_voice(),
        required=True, default='unset',
        help="Whether this user agreed to their microphone recording being "
             "sent to the configured speech-to-text provider.")
    decided_at = fields.Datetime()

    _sql_constraints = [
        ('user_uniq', 'unique(user_id)', 'One PayAI consent row per user.'),
    ]

    @api.model
    def _selection_voice(self):
        return [('unset', self.env._('Not asked yet')),
                ('granted', self.env._('Recordings may be sent for transcription')),
                ('declined', self.env._('Recordings must not be sent'))]

    @api.model
    def _my_row(self):
        return self.search([('user_id', '=', self.env.uid)], limit=1)

    @api.model
    def voice_state(self):
        """'unset' | 'granted' | 'declined'. Asked once, remembered either way."""
        row = self._my_row()
        return row.voice if row else 'unset'

    @api.model
    def voice_granted(self):
        return self.voice_state() == 'granted'

    @api.model
    def should_ask_voice(self):
        """True only when there is something to consent TO.

        A consent card for a switched-off feature costs the reader attention,
        buys nothing, and implies the thing is already happening.
        """
        return flag_on(self.env, VOICE_FLAG) and self.voice_state() == 'unset'

    @api.model
    def set_voice(self, granted):
        """Record this user's answer. Idempotent; only ever their own row."""
        value = 'granted' if granted else 'declined'
        row = self._my_row()
        vals = {'voice': value, 'decided_at': fields.Datetime.now()}
        if row:
            row.write(vals)
        else:
            self.create(dict(vals, user_id=self.env.uid))
        return value
