# -*- coding: utf-8 -*-
"""The chat session — its messages, and the redaction table that rides with it.

TWO THINGS LEARNOS PHASE 6 PUT HERE
-----------------------------------
1. **The per-conversation redaction mapping.** Until Phase 6 the placeholder
   table was built from scratch for every question, so a name restored into
   turn 2's answer was unrecognisable in turn 3's history and went back out to
   the provider in full. The mapping now lives on the conversation row, which
   is the only place with exactly the right lifetime.
2. **The voice seam.** `rpc_transcribe_voice` replaces `rpc_send_voice_message`
   and does strictly less: it transcribes and RETURNS THE TEXT. It cannot send
   anything, and that is a property of the method rather than a promise about
   it — see the comment on the method and `tests/test_egress.py::test_04b`.

RETENTION OF THE MAPPING, stated where the mechanism is (the ledger's standing
rule) rather than only in a report:

  * it is a JSON object of `{"[person-N]": "<name as stored>"}` on the
    conversation row, and it contains no salary, no id and no contact detail —
    only the association "this conversation talked about this person";
  * it is deleted with the conversation (an ordinary column, so `unlink`
    takes it) and by `action_clear`, which is the "clear chat" button the
    drawer already has: clearing the messages that the placeholders refer to
    and keeping the table that decodes them would be keeping the worse half;
  * it is capped at `MAP_CAP` people. Past that the LOWEST-numbered (the
    earliest, whose turns have long scrolled away) are dropped. A placeholder
    whose entry is gone restores to itself — `restore_names` leaves an unknown
    number exactly as the model wrote it — so the reader's failure mode is a
    visible `[person-3]`, never somebody else's name.
    **THE EGRESS SIDE OF THE CAP, stated because it is a real residual:** a
    dropped person is no longer matchable, so if their name is still sitting in
    a history turn that scrolls into the next prompt, it goes out in full — the
    same state the whole conversation was in before Phase 6. It needs a
    four-hundred-person conversation to happen, and the alternative (an
    unbounded column) is worse, but it is not nothing;
  * a PayAI MANAGER can read it. `rule_conversation_manager` gives that group
    every conversation, and the mapping is a column on the conversation, so it
    rides along — a list of who a colleague discussed with PayAI. That rule
    predates this phase and widening or narrowing it is a product decision, not
    a redaction one; it is raised as a ticket rather than changed here;
  * there is no cron. A mapping with no conversation cannot exist, so a
    sweeper would have nothing to sweep; conversations themselves have never
    had a retention policy in this module and giving one to their side-table
    alone would be theatre.
"""

from odoo import models, fields, api, _
import json
import logging

from .ai_redaction import _PERSON_RE
from .payroll_ai_consent import VOICE_FLAG, flag_on

_logger = logging.getLogger(__name__)

# How many people one conversation may carry placeholders for. Four hundred is
# far past any real chat and small enough that the column stays a few KB.
MAP_CAP = 400

# THE CEILING ON ONE RECORDING, IN BASE64 CHARACTERS, CHECKED BEFORE A BYTE IS
# DECODED. The browser stops at sixty seconds, and the browser is not the
# control: this endpoint is reachable by RPC from anything holding a session,
# so a caller can post a gigabyte of "audio" and make this worker decode it
# into memory before any of our own code looks at it. Eight megabytes of base64
# is about six of audio — several minutes of speech in Opus, and far past what
# a held button produces.
MAX_AUDIO_B64 = 8 * 1024 * 1024


class PayrollAIConversation(models.Model):
    """Chat conversation model for PayAI — persists chat sessions with chart history."""

    _name = 'payroll.ai.conversation'
    _description = 'PayAI Conversation'
    _order = 'create_date desc'

    name = fields.Char(
        string='Session Name',
        default=lambda self: _('PayAI Chat'),
        required=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        required=True,
    )

    message_ids = fields.One2many(
        'payroll.ai.message',
        'conversation_id',
        string='Messages',
    )

    state = fields.Selection([
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], default='active', string='Status')

    message_count = fields.Integer(
        compute='_compute_message_count',
        string='Messages',
    )

    # ADDITIVE COLUMN, and that is the whole migration story: a new nullable
    # Text field on an existing model plus one new model
    # (`payroll.ai.consent`). Odoo's own schema update creates both on `-u`;
    # there is nothing to carry, nothing to rename and nothing to back-fill —
    # an existing conversation simply starts with an empty mapping, which is
    # exactly the Phase-5 behaviour it already had. No pre-migrate script.
    redaction_map = fields.Text(
        string='Redaction map',
        help="JSON: which placeholder stands for which person in this "
             "conversation. Never leaves the server; see the retention note "
             "at the top of this file.",
    )

    @api.depends('message_ids')
    def _compute_message_count(self):
        for rec in self:
            rec.message_count = len(rec.message_ids)

    @api.model
    def get_or_create_session(self, user_id=None):
        """Get active session for user or create new one."""
        user_id = user_id or self.env.user.id
        session = self.search([
            ('user_id', '=', user_id),
            ('state', '=', 'active'),
        ], limit=1, order='create_date desc')

        if not session:
            session = self.create({
                'name': _('PayAI Chat'),
                'user_id': user_id,
            })

        return session

    def add_message(self, role, content, chart_config=None, insights=None, intent=None):
        """Add a message to the conversation."""
        self.ensure_one()
        return self.env['payroll.ai.message'].create({
            'conversation_id': self.id,
            'role': role,
            'content': content,
            'chart_config': json.dumps(chart_config) if chart_config else False,
            'insights': json.dumps(insights) if insights else False,
            'intent': intent or False,
        })

    def get_history(self, limit=20):
        """Get conversation history as list of dicts."""
        self.ensure_one()
        messages = self.message_ids.sorted('create_date')[-limit:]
        return [
            {
                'role': msg.role,
                'content': msg.content,
                'chart': json.loads(msg.chart_config) if msg.chart_config else None,
                'insights': json.loads(msg.insights) if msg.insights else [],
                'timestamp': msg.create_date.isoformat() if msg.create_date else '',
                'intent': msg.intent or '',
            }
            for msg in messages
        ]

    def action_clear(self):
        """Clear all messages in conversation — and the table that decodes them.

        Keeping the mapping across a clear would leave the one part of the
        conversation that names real people standing after the part that
        mentioned them is gone.
        """
        self.ensure_one()
        self.message_ids.unlink()
        self.write({'redaction_map': False})
        return True

    # ------------------------------------------------ the redaction mapping
    def load_redaction_map(self):
        """`{placeholder: name}` for this conversation, or `{}`.

        Total on every shape. The column is written by `store_redaction_map`
        alone, but a hand edit or a half-finished migration must degrade to
        "no mapping yet" — which is Phase 5's behaviour — rather than to a
        traceback in the middle of somebody's question.
        """
        self.ensure_one()
        try:
            data = json.loads(self.redaction_map or '{}')
        except (TypeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items()
                if isinstance(k, str) and isinstance(v, str)
                and _PERSON_RE.fullmatch(k)}

    def store_redaction_map(self, mapping):
        """Persist the extended mapping, capped, without a write when nothing
        changed (a knowledge question extends nothing, and a write per turn
        would touch `write_date` on every conversation for no reason)."""
        self.ensure_one()
        mapping = {k: v for k, v in (mapping or {}).items()
                   if isinstance(k, str) and isinstance(v, str)
                   and _PERSON_RE.fullmatch(k)}
        if len(mapping) > MAP_CAP:
            keep = sorted(mapping,
                          key=lambda k: int(_PERSON_RE.fullmatch(k).group(1)),
                          reverse=True)[:MAP_CAP]
            mapping = {k: mapping[k] for k in keep}
        blob = json.dumps(mapping, ensure_ascii=False) if mapping else False
        if (self.redaction_map or False) != blob:
            self.write({'redaction_map': blob})
        return True

    # --- RPC methods called from frontend ---

    @api.model
    def rpc_send_message(self, message, session_id=None, screen=None):
        """
        RPC endpoint for the chat widget.

        Args:
            message (str): User's message
            session_id (int): Optional session ID to continue conversation

        Returns:
            dict: AI response with chart config
        """
        # Get or create session
        if session_id:
            session = self.browse(session_id).exists()
            if not session:
                session = self.get_or_create_session()
        else:
            session = self.get_or_create_session()

        # Save user message
        session.add_message('user', message)

        # Get conversation history
        history = session.get_history(limit=10)

        # Process through AI engine.
        #
        # `conversation_id` is what lets the engine load, extend and save this
        # conversation's redaction mapping — the Phase 6 closure of the
        # prior-turn-names residual. It is an id and not a recordset because
        # `process_message` is an `@api.model` entry point that other callers
        # reach with no session at all.
        engine = self.env['payroll.ai.engine']
        result = engine.process_message(
            message,
            conversation_history=history[:-1],  # Exclude the message we just added
            context={'user_id': self.env.user.id, 'screen': screen,
                     'conversation_id': session.id},
        )

        # Save assistant response
        session.add_message(
            'assistant',
            result.get('response', ''),
            chart_config=result.get('chart'),
            insights=result.get('insights'),
            intent=result.get('intent'),
        )

        return {
            'session_id': session.id,
            'response': result.get('response', ''),
            'chart': result.get('chart'),
            'insights': result.get('insights', []),
            'follow_up_questions': result.get('follow_up_questions', []),
            'intent': result.get('intent', ''),
            'drilldown_model': result.get('drilldown_model', ''),
            'action': result.get('action'),
        }

    @api.model
    def rpc_get_history(self, session_id=None):
        """RPC endpoint to get chat history."""
        if session_id:
            session = self.browse(session_id).exists()
        else:
            session = self.get_or_create_session()

        if not session:
            return {'session_id': None, 'messages': []}

        return {
            'session_id': session.id,
            'messages': session.get_history(limit=50),
        }

    @api.model
    def rpc_clear_history(self, session_id=None):
        """RPC endpoint to clear chat history."""
        if session_id:
            session = self.browse(session_id).exists()
            if session:
                session.action_clear()
        return True

    # ------------------------------------------------------------------
    # VOICE
    #
    # THE SHAPE OF THIS SEAM IS THE CONTROL. `rpc_send_voice_message` used to
    # decode the audio, transcribe it, and CALL `rpc_send_message` with
    # whatever came back — so a mis-heard sentence went to a language model
    # before the person who said it had seen it, and a person who mumbled a
    # colleague's salary into a hot microphone found out afterwards.
    #
    # It is replaced, not patched, by a method that transcribes and returns.
    # There is no branch in it that sends, no flag that makes it send, and
    # nothing for a future edit to re-enable: sending is a second, separate
    # press by the learner on the ordinary send button, over the ordinary
    # `rpc_send_message` path, with the ordinary redaction. `test_egress`
    # asserts the absence structurally, and the negative control (calling
    # `rpc_send_message` from inside it) fails that test.
    # ------------------------------------------------------------------
    @api.model
    def rpc_voice_status(self):
        """What the drawer needs to decide whether to draw a microphone.

        THE BUTTON IS ABSENT, NOT DISABLED, when voice is unavailable. A
        disabled control with a tooltip is a promise the tenant never made and
        an explanation nobody asked for; on a database with no speech provider
        the honest interface has no microphone in it.

        `ask` is the one state where the button IS drawn and pressing it opens
        the consent card instead of the recorder.
        """
        Consent = self.env['payroll.ai.consent']
        enabled = flag_on(self.env, VOICE_FLAG)
        state = Consent.voice_state()
        available = bool(enabled and self._speech_provider() is not None)
        return {
            'available': available and state != 'declined',
            'ask': available and state == 'unset',
            'consent': state,
            # Server-rendered so it follows the READER's language through the
            # ordinary `_()` path — this module's copy contract since D1.
            'copy': {
                'consent_title': _('Send recordings for transcription?'),
                # THE CARD NAMES WHAT LEAVES, WHO GETS IT AND WHEN.
                #
                # The first draft said "nothing is sent until you press send",
                # which is true of the TEXT and false of the RECORDING — the
                # audio goes the moment the button is released, which is the
                # whole reason this consent exists. A notice that is reassuring
                # about the wrong half is worse than none.
                'consent_body': _(
                    "Hold the microphone and speak. When you let go, the "
                    "recording goes to an outside company's speech service, "
                    "which turns it into text. The recording is audio: unlike "
                    "text, we cannot take names out of it first. The text then "
                    "waits in the box — nothing is asked or answered until you "
                    "read it and press send. Say no and the microphone stays "
                    "off. Everything else works the same."),
                'consent_yes': _('Yes, send my recordings'),
                'consent_no': _('No, keep the microphone off'),
                'hold_hint': _('Hold to speak'),
                'check_hint': _('This is what I heard. Edit it, then press send.'),
                'listen_label': _('Read answers aloud'),
                'failed': _('I could not turn that into text. Please try typing.'),
            },
        }

    @api.model
    def rpc_set_voice_consent(self, granted):
        """Record this user's answer to the card above. Asked once, either way."""
        return self.env['payroll.ai.consent'].set_voice(bool(granted))

    @api.model
    def _speech_provider(self):
        """The configured provider IF it can transcribe, else None.

        `get_provider` — the method `payroll.ai.config` actually has. What
        the voice path used to call was a factory name that never existed (not
        written out here: `tests/test_egress.py` greps this file for it), and
        the bare `except` around it turned that into a feature which answered
        "voice requires Whisper support" on every database forever. Repairing the lookup is switching
        an egress path ON, so it happens in the same change as the gate above
        and the audio residual written into ai_redaction.py.
        """
        try:
            config = self.env['payroll.ai.config'].get_active_config()
            if not config:
                return None
            provider = config.get_provider()
        except Exception as exc:                                # noqa: BLE001
            _logger.warning("PayAI voice: no usable provider (%s)", exc)
            return None
        return provider if hasattr(provider, 'transcribe_audio') else None

    @api.model
    def rpc_transcribe_voice(self, audio_base64):
        """Audio in, TEXT OUT. This method never sends a message.

        Both gates are re-asked here and not only in the browser: this is
        reachable over RPC from anything holding a session, so the tenant flag
        and the user's consent are checked on the server, in that order, before
        a single byte is decoded.
        """
        Consent = self.env['payroll.ai.consent']
        if not flag_on(self.env, VOICE_FLAG):
            return {'error': _('Voice input is switched off for this database.')}
        if not Consent.voice_granted():
            return {'error': _('Voice input needs your agreement first.')}

        provider = self._speech_provider()
        if provider is None:
            return {'error': _('No speech service is set up here.')}

        # THE CEILING FIRST. Measuring the string we were handed costs
        # nothing; decoding it is what allocates.
        if not isinstance(audio_base64, str):
            return {'error': _('That recording did not arrive in one piece.')}
        if len(audio_base64) > MAX_AUDIO_B64:
            _logger.warning(
                "PayAI voice: refused a %d-character payload (ceiling %d)",
                len(audio_base64), MAX_AUDIO_B64)
            return {'error': _('That recording is too long. Try a shorter one.')}

        import base64
        try:
            audio_bytes = base64.b64decode(audio_base64 or '')
        except Exception as exc:                                # noqa: BLE001
            _logger.error("PayAI voice: failed to decode audio: %s", exc)
            return {'error': _('That recording did not arrive in one piece.')}
        if not audio_bytes:
            return {'error': _('That recording was empty.')}

        try:
            text = provider.transcribe_audio(audio_bytes)
        except Exception as exc:                                # noqa: BLE001
            # The provider's own words are not shown to the reader: an API
            # error string is not copy, and it can carry the request back.
            _logger.error("PayAI voice transcription failed: %s", exc)
            return {'error': _('I could not turn that into text. Please try typing.')}

        text = (text or '').strip()
        if not text:
            return {'error': _('I did not catch anything in that recording.')}
        # The transcript goes back to the person who spoke it. Nothing here
        # stores it, and nothing here sends it.
        return {'text': text[:2000]}


class PayrollAIMessage(models.Model):
    """Individual message in a PayAI conversation."""

    _name = 'payroll.ai.message'
    _description = 'PayAI Message'
    _order = 'create_date asc'

    conversation_id = fields.Many2one(
        'payroll.ai.conversation',
        string='Conversation',
        required=True,
        ondelete='cascade',
    )

    role = fields.Selection([
        ('user', 'User'),
        ('assistant', 'PayAI'),
        ('system', 'System'),
    ], string='Role', required=True)

    content = fields.Text(string='Content', required=True)

    chart_config = fields.Text(
        string='Chart Configuration',
        help='JSON Chart.js configuration for inline chart rendering',
    )

    insights = fields.Text(
        string='Insights',
        help='JSON list of insight strings',
    )

    intent = fields.Char(
        string='Intent',
        help='Classified intent: payroll_data, payroll_knowledge, general',
    )
