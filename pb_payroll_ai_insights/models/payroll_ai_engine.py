# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

from .ai_redaction import (
    generic_scrub, redact_names, redact_text, restore_deep, restore_names,
)

_logger = logging.getLogger(__name__)


# System prompt for PayAI
PAYAI_SYSTEM_PROMPT = """You are PayAI, an intelligent payroll analytics assistant for Payobook.
You help HR managers and payroll administrators with:

1. PAYROLL DATA QUERIES: When users ask about payroll data (salaries, costs, headcount, overtime, deductions, etc.), you analyze the provided data and generate insights with chart configurations.

2. PAYROLL KNOWLEDGE: When users ask conceptual payroll/HR questions (tax rates, CTC meaning, compliance rules, etc.), you answer from your knowledge.

3. GENERAL QUESTIONS: You can also answer any general question — writing emails, explaining concepts, providing advice, etc.

CRITICAL RULES FOR DATA QUERIES:
- When you receive payroll data, you MUST respond with a JSON object containing:
  - "response": Your natural language explanation/narrative
  - "chart": A Chart.js configuration object (if a chart is appropriate)
  - "insights": A list of key insight strings
  - "follow_up_questions": Suggested follow-up questions

- For chart configurations, use this EXACT Chart.js v4 format:
  {
    "type": "bar|line|pie|doughnut|radar|scatter|bubble",
    "data": {
      "labels": ["Label1", "Label2"],
      "datasets": [{
        "label": "Dataset Name",
        "data": [100, 200],
        "backgroundColor": ["#6366f1", "#22c55e"]
      }]
    },
    "options": {
      "responsive": true,
      "plugins": {
        "title": {"display": true, "text": "Chart Title"},
        "legend": {"position": "bottom"}
      }
    }
  }

- Use this color palette for charts:
  Primary: #6366f1 (indigo), #8b5cf6 (violet), #a78bfa (light violet)
  Success: #22c55e (green), #4ade80 (light green)
  Warning: #f59e0b (amber), #fbbf24 (yellow)
  Danger: #ef4444 (red), #f87171 (light red)
  Info: #06b6d4 (cyan), #22d3ee (light cyan)
  Neutral: #64748b (slate), #94a3b8 (light slate)

- Choose chart type intelligently:
  - Comparisons between categories → bar chart
  - Trends over time → line chart
  - Proportions of a whole → pie or doughnut
  - Multi-dimension comparison → radar
  - Correlation between two variables → scatter

FOR NON-DATA QUESTIONS:
- Respond with a JSON object containing only:
  - "response": Your text answer
  - "chart": null
  - "insights": []
  - "follow_up_questions": []

ALWAYS respond with valid JSON. Never include markdown code fences around the JSON.
"""

INTENT_CLASSIFICATION_PROMPT = """Classify the following user message into one of these categories:

1. "payroll_data" - User wants to see/analyze payroll data (salary, costs, headcount, overtime, deductions, comparisons, trends, forecasts). This requires querying the database.
2. "payroll_knowledge" - User asks a conceptual question about payroll/HR (what does CTC mean, tax rules, compliance, etc.)
3. "onboarding" - User asks HOW to USE the Payobook app or wants to be shown/guided (how do I run payroll, how to add an employee, where is X, how does the formula engine work, show me around, give me a tour, get started).
4. "general" - Any other question (write an email, explain something, general help)

User message: "{message}"

Respond with ONLY the category name, nothing else. Just one word from: payroll_data, payroll_knowledge, onboarding, general"""


# Onboarding copilot — grounded in the real Payobook demo product so answers are
# accurate, and able to open a pb_learn LESSON via an optional "action".
ONBOARDING_SYSTEM_PROMPT = """You are PayAI, the in-app onboarding copilot for Payobook, an Odoo-based multi-country payroll platform. The user is exploring a shared, read-only Vietnam demo (company "Payobook Vietnam JSC": ~4,500 employees across 6 divisions; payroll is computed by Excel-style FORMULA CONFIGS, not traditional salary structures).

Answer "how do I…" / "where is…" / "show me" questions about USING Payobook with clear, correct, numbered steps grounded ONLY in the real product facts below. Keep answers short and skimmable.

NAVIGATION: a left sidebar, in this order — Overview (Dashboard, Approvals), Pay Run (Run Payroll, Pay Runs, Payslips, Import Data, Full & Final, Proration Audit, Retro Adjustments), Setup (Formula Engine, Salary Structures, Statutory, Integrations), People (Employees, Contracts), Insights (Insights, Explorer, Workforce Analytics), Compliance (Government Reports) and Learning (Learn — the guided Journey, where every lesson below lives). Admin is not available to demo accounts, and Setup is read-only there.

HOW TO RUN PAYROLL (the core flow):
1. On the Dashboard, click "Run Payroll" (top-right) to open the pay-run wizard.
2. "Select period": pick a Division (e.g. Retail). Payobook auto-loads that division's formula config and eligible employees; the period is the demo month (June 2026).
3. Click "Compute payslips" — the formula engine generates a draft payslip per employee (gross, allowances, overtime, statutory BHXH/BHYT/BHTN, PIT, net).
4. "Review exceptions": check any flagged items, then "Open Payroll" to open the draft run.
5. Approve through the states: Draft -> Submit -> HR review -> GM approval -> Done. Each transition is role-gated.

FORMULA CONFIGS: payroll logic lives in Excel-like grids of components (inputs, constants, formulas) that reference each other by code (BASIC, GROSS, PIT…). The demo has 12 configs (6 divisions x mid/end cycle), viewable read-only in the Formula Engine.

PAY RUNS & PAYSLIPS: Pay Runs lists every run (April/May are Done, June is live/Draft). Open any payslip to see its formula-driven components.

DEMO NOTE: this is a shared, read-only demo — payslips you generate are temporary and may be reset by another demo user.

You can OFFER TO SHOW the user by opening a guided LESSON via an optional "action". Available lessons:
- "LW": Welcome to your command centre — the Dashboard, the monthly loop, where everything lives
- "L1": Run Payroll — your first pay run (division -> compute -> review -> submit)
- "L5": The formula is the payslip — read a division's formula configuration end to end
- "L3": Read a payslip like an auditor — gross to net, line by line
- "L4": Import with confidence — the confidence score, and fixing rows before they commit
- "LA": Approve like it is your signature — the approval queue, sampling, variance, rejecting well
- "L2": The board and the gates — the Pay Runs board and the approval chain
- "L6": Statutory — the insurance rates, the tax table, and applying a rate change

ALWAYS respond with a SINGLE valid JSON object (no markdown fences):
{
  "response": "<concise step-by-step answer; newlines and numbered steps are fine>",
  "insights": [],
  "follow_up_questions": ["<2-3 helpful next questions>"],
  "action": { "type": "open_lesson", "lesson": "<one lesson key above>", "label": "Show me" }
}
Include "action" ONLY when a listed lesson clearly matches the request; otherwise omit it or set it to null. Never invent menus, buttons or lesson keys that are not listed above."""


def data_query_prompt(message, payload_json):
    """The exact string the data-query path sends, as a pure function.

    Factored out of ``_process_data_query`` in LEARNOS Phase 4 for one reason:
    "no employee name is in the prompt" is a claim about a STRING, and a claim
    about a string should be asserted against the string. With this here, the
    redaction suite builds a payload full of names, emails and phone numbers,
    calls this, and asserts on the whole result — with no provider, no network
    and no database.

    Both arguments must already be redacted. This function deliberately does
    not redact anything itself: a builder that quietly cleans its inputs is a
    builder whose caller stops thinking about them.
    """
    return f"""The user asked: "{message}"

Here is the actual payroll data from the system:

{payload_json}

Based on this data, provide:
1. A clear, insightful narrative response
2. An appropriate Chart.js chart configuration to visualize the data
3. Key insights and observations
4. Suggested follow-up questions

Names have been replaced with placeholders of the form [person-1]. Use those
placeholders exactly as they appear, including in chart labels. Do not invent
real names for them and do not guess who they are.

Remember to use the PayAI color palette and choose the best chart type for this data."""


class PayrollAIEngine(models.Model):
    """Core AI engine for PayAI — handles intent classification, data retrieval, and response generation."""

    _name = 'payroll.ai.engine'
    _description = 'PayAI Engine'

    @api.model
    def _get_provider(self):
        """Get the configured AI provider."""
        config = self.env['payroll.ai.config'].get_active_config()
        if not config:
            raise UserError(_(
                'PayAI is not configured. Please go to PayAI > Configuration '
                'and set up your AI provider.'
            ))
        return config.get_provider()

    @api.model
    def process_message(self, message, conversation_history=None, context=None):
        """
        Main entry point for processing a user message.

        Args:
            message (str): User's message
            conversation_history (list): Previous messages [{role, content}, ...]
            context (dict): Additional context (employee_id, etc.)

        Returns:
            dict: {
                'response': str,
                'chart': dict or None,
                'insights': list,
                'follow_up_questions': list,
                'intent': str,
            }
        """
        context = context or {}
        conversation_history = conversation_history or []

        try:
            provider = self._get_provider()

            # Step 1: Classify intent
            intent = self._classify_intent(provider, message)
            # Scrubbed in the LOG too. The server log is inside the trust
            # boundary, so this is not an egress fix — it is a retention one:
            # this line was writing "why is <a colleague>'s net only 4.200.000"
            # into a file with no retention policy, once per question.
            _logger.info("PayAI intent: %s for message: %s",
                         intent, generic_scrub(message)[:80])

            # Step 2: Process based on intent
            if intent == 'payroll_data':
                return self._process_data_query(provider, message, conversation_history, context)
            elif intent == 'payroll_knowledge':
                return self._process_knowledge_query(provider, message, conversation_history)
            elif intent == 'onboarding':
                return self._process_onboarding_query(provider, message, conversation_history, context)
            else:
                return self._process_general_query(provider, message, conversation_history)

        except UserError:
            raise
        except Exception as e:
            _logger.exception("PayAI processing error: %s", str(e))
            return {
                'response': f'I apologize, but I encountered an error: {str(e)}. Please try again.',
                'chart': None,
                'insights': [],
                'follow_up_questions': [],
                'intent': 'error',
            }

    def _classify_intent(self, provider, message):
        """Classify the user's message intent.

        THE FIRST THING THAT LEAVES, AND IT USED TO LEAVE RAW.

        This runs before any query, so nothing has been read and there is no
        name mapping to build one from — which is exactly why it was missed:
        the redaction work all sits in `_process_data_query`, and by the time
        that runs, the whole message has already been on the wire once, in
        this prompt, to decide which of four paths to take.

        `generic_scrub` is what is available here and it is not nothing: an
        email, a phone number, a record id and a money amount all go. A NAME
        does not, because there is nothing yet to match it against, and that
        residual is written down in ai_redaction's list rather than left to be
        found. Classification does not need the name — it needs the shape of
        the question, and "[person-1]" and "Mai" route identically.
        """
        safe_message = generic_scrub(message)
        try:
            prompt = INTENT_CLASSIFICATION_PROMPT.format(message=safe_message)
            response = provider.generate_text(prompt, max_tokens=20, temperature=0.1)
            intent = response.strip().lower().replace('"', '').replace("'", '')

            # Normalize
            if 'payroll_data' in intent or 'data' in intent:
                return 'payroll_data'
            elif 'payroll_knowledge' in intent or 'knowledge' in intent:
                return 'payroll_knowledge'
            elif 'onboard' in intent or 'guide' in intent or 'tour' in intent:
                return 'onboarding'
            else:
                return 'general'
        except Exception as e:
            _logger.warning("Intent classification failed: %s, defaulting to general", e)
            return 'general'

    def _process_data_query(self, provider, message, conversation_history, context):
        """Process a payroll data query — fetch real data from Odoo and generate chart."""
        # Step 1: Get the data query engine to fetch relevant data
        data_engine = self.env['payroll.data.query']
        payroll_data = data_engine.query_for_message(message, context)

        # Step 1b: a refusal is an ANSWER, and it stops here.
        #
        # The query layer runs with the asker's access rights (Phase D1), so
        # "you may not read this" is a normal outcome. Passing it on to the
        # provider would spend a token asking a model to paraphrase our own
        # refusal, and would let it soften or contradict the sentence — the one
        # sentence in this flow that has to be exact. It also keeps the fact
        # that a refusal happened off the wire entirely.
        if payroll_data.get('access_refused'):
            return {
                'response': payroll_data.get('message', ''),
                'chart': None,
                'insights': [],
                'follow_up_questions': [],
                'intent': 'payroll_data',
                'access_refused': True,
            }

        # A partial gate (individual salaries withheld, aggregate returned) is
        # NOT a refusal: the question was answered one level up. The note is
        # appended deterministically below rather than left to the model.
        access_note = payroll_data.get('access_note') or ''

        # Step 1c: THE NAMES COME OUT BEFORE THIS PROMPT IS BUILT.
        #
        # The asking user has already passed the access gate above, so they are
        # entitled to these names. The provider is not, and never was — this
        # path posted employee names, job titles and wages verbatim from the
        # day it was written. `mapping` stays on this server and is what puts
        # them back at the end.
        #
        # EXACTLY WHAT IS PROTECTED, AND WHERE. An earlier draft of this
        # comment said "three things are redacted" and was FALSE AS BUILT,
        # because it described this method and the message had already been
        # sent once, unredacted, by `_classify_intent`. The honest version:
        #
        #   payload          names by key then everywhere, plus emails, phones,
        #                    record ids. Figures survive — they are the answer.
        #   this message     the same mapping, plus the free-text scrub. A name
        #                    IS caught here, because by now there is a mapping.
        #   history turns    the same treatment, with the SAME mapping — so a
        #                    person named in an earlier answer and absent from
        #                    THIS query's result is only reached by the generic
        #                    patterns. Named residual; see ai_redaction.
        #   the classifier   ran BEFORE all of this and had no mapping to use.
        #                    It gets `generic_scrub` only: contact details and
        #                    money go, a name does not.
        redacted_data, mapping = redact_names(payroll_data)
        safe_message = redact_text(message, mapping)

        # Step 2: Build the prompt with the redacted data
        data_prompt = data_query_prompt(
            safe_message, json.dumps(redacted_data, indent=2, default=str))

        messages = [
            {"role": "system", "content": PAYAI_SYSTEM_PROMPT},
        ]
        # Add recent conversation history for context
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": redact_text(msg.get('content', ''), mapping),
            })
        messages.append({"role": "user", "content": data_prompt})

        # Step 3: Generate response with chart
        try:
            raw_response = provider.generate_chat(messages, max_tokens=2500, temperature=0.5)
            result = provider._parse_json_response(raw_response)
            # THE PLACEHOLDERS GO BACK, EVERYWHERE. Not only in the narrative:
            # a chart's labels are the names the model was handed, and an axis
            # reading "[person-1]" is a worse outcome than no redaction at all,
            # because it reads as a rendering fault rather than as a control.
            result = restore_deep(result, mapping)

            return {
                'response': self._with_access_note(
                    result.get('response', 'Here is the data analysis.'), access_note),
                'chart': result.get('chart', None),
                'insights': result.get('insights', []),
                'follow_up_questions': result.get('follow_up_questions', []),
                'intent': 'payroll_data',
                'drilldown_model': payroll_data.get('drilldown_model', ''),
            }
        except Exception as e:
            _logger.warning("Failed to parse chart response: %s", e)
            # Fallback: return raw text response. It is the model's own words
            # with nothing parsed out of them, so it carries placeholders too.
            fallback = (restore_names(raw_response, mapping)
                        if 'raw_response' in dir() else str(e))
            return {
                'response': self._with_access_note(fallback, access_note),
                'chart': None,
                'insights': [],
                'follow_up_questions': [],
                'intent': 'payroll_data',
                'drilldown_model': payroll_data.get('drilldown_model', ''),
            }

    @api.model
    def _with_access_note(self, response, access_note):
        """Append the gate note to a narrative the model wrote.

        Both return paths of `_process_data_query` go through here, including
        the parse-failure fallback — a user whose individual detail was
        withheld must be told so even when the chart JSON did not parse.
        """
        if not access_note:
            return response
        return '%s\n\n%s' % (response or '', access_note)

    def _process_knowledge_query(self, provider, message, conversation_history):
        """Process a payroll knowledge question."""
        messages = [
            {"role": "system", "content": PAYAI_SYSTEM_PROMPT},
        ]
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                # HISTORY IS AN EARLIER ANSWER WITH THE NAMES PUT BACK IN.
                # No mapping exists on this path, so this is the generic
                # scrub: contact details and money go, a prior-turn name does
                # not. Named residual — see ai_redaction's list.
                "content": generic_scrub(msg.get('content', '')),
            })
        messages.append({"role": "user", "content": message})

        try:
            raw_response = provider.generate_chat(messages, max_tokens=1500, temperature=0.7)
            try:
                result = provider._parse_json_response(raw_response)
                return {
                    'response': result.get('response', raw_response),
                    'chart': result.get('chart', None),
                    'insights': result.get('insights', []),
                    'follow_up_questions': result.get('follow_up_questions', []),
                    'intent': 'payroll_knowledge',
                }
            except Exception:
                return {
                    'response': raw_response,
                    'chart': None,
                    'insights': [],
                    'follow_up_questions': [],
                    'intent': 'payroll_knowledge',
                }
        except Exception as e:
            _logger.error("Knowledge query error: %s", e)
            raise

    # ------------------------------------------------------------------
    # THE ACTION ENVELOPE
    #
    # PayAI may offer to SHOW the user something. Until Phase C2 that meant
    # starting a pb_coach tour; it now means opening a pb_learn lesson, and the
    # difference is not cosmetic. A tour was a spotlight walk over the live
    # product in English with nothing recorded at the end. A lesson runs over
    # the practice replica, ships in both languages, ends on a judgement check
    # and stores completion per learner — and, unlike a tour, it exists as a
    # DATABASE RECORD this whitelist can be validated against.
    #
    # `_KNOWN_LESSONS` is a whitelist and nothing else: the LLM chooses from it,
    # it never authors a key. An unknown key is dropped rather than passed
    # through, because a button that opens nothing is worse than no button.
    _KNOWN_LESSONS = ('LW', 'L1', 'L5', 'L3', 'L4', 'LA', 'L2', 'L6')

    # The old tour ids, and the lesson each became. Kept because the SYSTEM
    # PROMPT and the model behind it may lag a deploy — a cached conversation,
    # a slow provider rollout, a fine-tune that learned the old vocabulary — and
    # an envelope that only understood the new form would silently drop every
    # "Show me" for as long as that lasted.
    #
    # LEARNOS PHASE 1b: THE TOURS NOW HAVE TWO SUCCESSORS EACH, AND THIS MAP
    # STILL POINTS AT THE LESSON. The tour module was deleted and its six tours
    # were ported into pb_learn SCENARIOS — `hero_path` is `sc_welcome`,
    # `tour_payrun` is `sc_payrun`, `tour_payslips` is `sc_payslips`,
    # `tour_formula` is `sc_formula`, `tour_import` is `sc_import` and
    # `tour_mapping` is `sc_mapping` — so for every entry below there is now a
    # walkthrough that is a closer descendant of the tour than the lesson is.
    # Every entry still lands on the LESSON, decided per entry and for two
    # reasons that hold for all six:
    #
    #   · THE ENVELOPE CANNOT SAY IT. `_sanitize_action` emits exactly one
    #     shape, `open_lesson`, and the browser opens the Journey with
    #     `context.lesson`. Re-pointing an entry at `sc_payrun` would put a
    #     scenario key in a field named `lesson`, fail the whitelist below, and
    #     be dropped — a button that opens nothing. A scenario envelope is a
    #     change to the sanitizer and to `ai_insight_chat.js`, which is a
    #     separate piece of work with its own trust boundary to re-argue.
    #   · A LESSON IS THE BETTER LANDING FOR A QUESTION. Somebody arrives here
    #     by ASKING, and a lesson answers: it is bilingual, it runs where
    #     nothing can matter, it ends on a judgement check and it records
    #     completion. A Watch of the real product answers "where is that", which
    #     is what the Coach's own "Show me how" section now offers on the screen
    #     the person is already standing on — reached in one press, without a
    #     language model in the path.
    #
    #   hero_path      -> LW   the Dashboard welcome; LW is its direct successor
    #                          (sc_welcome is the Watch of the same ground)
    #   tour_payrun    -> L1   run a pay run, division to submit (sc_payrun)
    #   tour_formula   -> L5   read a division's formula configuration (sc_formula)
    #   tour_payslips  -> L3   read a payslip line by line (sc_payslips)
    #   tour_import    -> L4   the import confidence score and fixing rows
    #                          (sc_import)
    #   tour_mapping   -> L5   NOT L4: the mid/end mapping wizard pairs COMPONENTS
    #                          across two formula configurations, which is L5's
    #                          subject. L4 is about attendance files and would
    #                          send the asker to the wrong desk. (sc_mapping)
    _TOUR_TO_LESSON = {
        'hero_path': 'LW',
        'tour_payrun': 'L1',
        'tour_formula': 'L5',
        'tour_payslips': 'L3',
        'tour_import': 'L4',
        'tour_mapping': 'L5',
    }

    def _sanitize_action(self, action):
        """Accept both envelope forms; ALWAYS emit `open_lesson`.

        Two inputs, one output. `start_tour` with an old tour id is converted
        through `_TOUR_TO_LESSON`; `open_lesson` is validated against the
        whitelist. Anything else — a type nobody ships, a lesson key nobody
        wrote, a non-dict — returns None, and the chat renders no button at all.
        """
        if not isinstance(action, dict):
            return None
        kind = action.get('type')
        if kind == 'open_lesson':
            lesson = action.get('lesson')
        elif kind == 'start_tour':
            # isinstance FIRST. `dict.get` on an unhashable key raises TypeError,
            # and everything reaching this method came out of a language model's
            # JSON — a list or a dict where a string was asked for is not a
            # remote possibility, it is Tuesday. A sanitizer that can be made to
            # raise is not a sanitizer.
            tour = action.get('tour')
            lesson = self._TOUR_TO_LESSON.get(tour) if isinstance(tour, str) else None
        else:
            return None
        if lesson not in self._KNOWN_LESSONS:
            return None
        # Same rule for the label, one type further: `or` lets a non-empty int
        # through and `[:40]` then raises, while a list would slice happily and
        # reach the DOM as a caption nobody wrote.
        label = action.get('label')
        return {
            'type': 'open_lesson',
            'lesson': lesson,
            'label': label[:40] if isinstance(label, str) and label else 'Show me',
        }

    # Friendly names for the cockpits the user may be standing on.
    _SCREEN_NAMES = {
        'pb_dashboard': 'the Dashboard (command centre)',
        'pb_payrun_wizard': 'the Run Payroll wizard',
        'pb_payruns': 'the Pay Runs board',
        'pb_payslip': 'the Payslips screen',
        'pb_formula_studio': 'the Formula Studio',
    }

    def _describe_screen(self, screen):
        if not isinstance(screen, dict):
            return None
        tag = screen.get('tag') or ''
        xid = screen.get('xml_id') or ''
        model = screen.get('model') or ''
        if tag in self._SCREEN_NAMES:
            return self._SCREEN_NAMES[tag]
        if 'formula' in tag or 'formula' in xid:
            return 'the Formula Engine'
        if model in ('hr.payslip.run', 'hr.payslip') or 'payslip_run' in xid:
            return 'the Pay Runs / Payslips area'
        return screen.get('name') or None

    def _process_onboarding_query(self, provider, message, conversation_history, context=None):
        """Answer a 'how do I use Payobook' question, optionally launching a tour."""
        messages = [{"role": "system", "content": ONBOARDING_SYSTEM_PROMPT}]
        screen_desc = self._describe_screen((context or {}).get('screen'))
        if screen_desc:
            messages.append({
                "role": "system",
                "content": "The user is currently on %s. If they say 'this', 'here' or "
                           "'this screen', interpret it relative to that." % screen_desc,
            })
        for msg in conversation_history[-6:]:
            # Same rule as the other three paths — see _process_knowledge_query.
            messages.append({"role": msg.get('role', 'user'),
                             "content": generic_scrub(msg.get('content', ''))})
        messages.append({"role": "user", "content": message})

        raw_response = provider.generate_chat(messages, max_tokens=1200, temperature=0.4)
        try:
            result = provider._parse_json_response(raw_response)
        except Exception:
            result = {'response': raw_response}
        return {
            'response': result.get('response', raw_response),
            'chart': None,
            'insights': result.get('insights', []),
            'follow_up_questions': result.get('follow_up_questions', []),
            'intent': 'onboarding',
            'action': self._sanitize_action(result.get('action')),
        }

    def _process_general_query(self, provider, message, conversation_history):
        """Process a general (non-payroll) question."""
        messages = [
            {"role": "system", "content": PAYAI_SYSTEM_PROMPT},
        ]
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                # HISTORY IS AN EARLIER ANSWER WITH THE NAMES PUT BACK IN.
                # No mapping exists on this path, so this is the generic
                # scrub: contact details and money go, a prior-turn name does
                # not. Named residual — see ai_redaction's list.
                "content": generic_scrub(msg.get('content', '')),
            })
        messages.append({"role": "user", "content": message})

        try:
            raw_response = provider.generate_chat(messages, max_tokens=1500, temperature=0.7)
            try:
                result = provider._parse_json_response(raw_response)
                return {
                    'response': result.get('response', raw_response),
                    'chart': None,
                    'insights': [],
                    'follow_up_questions': result.get('follow_up_questions', []),
                    'intent': 'general',
                }
            except Exception:
                return {
                    'response': raw_response,
                    'chart': None,
                    'insights': [],
                    'follow_up_questions': [],
                    'intent': 'general',
                }
        except Exception as e:
            _logger.error("General query error: %s", e)
            raise
