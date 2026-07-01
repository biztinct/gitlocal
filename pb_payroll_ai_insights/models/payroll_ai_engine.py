# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

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
# accurate, and able to launch a guided coach tour via an optional "action".
ONBOARDING_SYSTEM_PROMPT = """You are PayAI, the in-app onboarding copilot for Payobook, an Odoo-based multi-country payroll platform. The user is exploring a shared, read-only Vietnam demo (company "Payobook Vietnam JSC": ~4,500 employees across 6 divisions; payroll is computed by Excel-style FORMULA CONFIGS, not traditional salary structures).

Answer "how do I…" / "where is…" / "show me" questions about USING Payobook with clear, correct, numbered steps grounded ONLY in the real product facts below. Keep answers short and skimmable.

NAVIGATION: a left sidebar has Dashboard, Pay Runs, Payslips and Workforce Analytics. The Formula Engine is in the top bar. Import, Setup and Admin are locked in the demo.

HOW TO RUN PAYROLL (the core flow):
1. On the Dashboard, click "Run Payroll" (top-right) to open the pay-run wizard.
2. "Select period": pick a Division (e.g. Retail). Payobook auto-loads that division's formula config and eligible employees; the period is the demo month (June 2026).
3. Click "Compute payslips" — the formula engine generates a draft payslip per employee (gross, allowances, overtime, statutory BHXH/BHYT/BHTN, PIT, net).
4. "Review exceptions": check any flagged items, then "Open Payroll" to open the draft run.
5. Approve through the states: Draft -> Submit -> HR review -> GM approval -> Done. Each transition is role-gated.

FORMULA CONFIGS: payroll logic lives in Excel-like grids of components (inputs, constants, formulas) that reference each other by code (BASIC, GROSS, PIT…). The demo has 12 configs (6 divisions x mid/end cycle), viewable read-only in the Formula Engine.

PAY RUNS & PAYSLIPS: Pay Runs lists every run (April/May are Done, June is live/Draft). Open any payslip to see its formula-driven components.

DEMO NOTE: this is a shared, read-only demo — payslips you generate are temporary and may be reset by another demo user.

You can OFFER TO SHOW the user by launching a guided tour via an optional "action". Available tours:
- "hero_path"    : the full end-to-end product tour
- "tour_payrun"  : run a pay run (division -> compute -> review)
- "tour_formula" : explore the formula engine
- "tour_payslips": pay runs & payslips / approvals

ALWAYS respond with a SINGLE valid JSON object (no markdown fences):
{
  "response": "<concise step-by-step answer; newlines and numbered steps are fine>",
  "insights": [],
  "follow_up_questions": ["<2-3 helpful next questions>"],
  "action": { "type": "start_tour", "tour": "<one tour id above>", "label": "Show me" }
}
Include "action" ONLY when a listed tour clearly matches the request; otherwise omit it or set it to null. Never invent menus, buttons or tour ids that are not listed above."""


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
            _logger.info("PayAI intent: %s for message: %s", intent, message[:80])

            # Step 2: Process based on intent
            if intent == 'payroll_data':
                return self._process_data_query(provider, message, conversation_history, context)
            elif intent == 'payroll_knowledge':
                return self._process_knowledge_query(provider, message, conversation_history)
            elif intent == 'onboarding':
                return self._process_onboarding_query(provider, message, conversation_history)
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
        """Classify the user's message intent."""
        try:
            prompt = INTENT_CLASSIFICATION_PROMPT.format(message=message)
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

        # Step 2: Build the prompt with actual data
        data_prompt = f"""The user asked: "{message}"

Here is the actual payroll data from the system:

{json.dumps(payroll_data, indent=2, default=str)}

Based on this data, provide:
1. A clear, insightful narrative response
2. An appropriate Chart.js chart configuration to visualize the data
3. Key insights and observations
4. Suggested follow-up questions

Remember to use the PayAI color palette and choose the best chart type for this data."""

        messages = [
            {"role": "system", "content": PAYAI_SYSTEM_PROMPT},
        ]
        # Add recent conversation history for context
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": msg.get('content', ''),
            })
        messages.append({"role": "user", "content": data_prompt})

        # Step 3: Generate response with chart
        try:
            raw_response = provider.generate_chat(messages, max_tokens=2500, temperature=0.5)
            result = provider._parse_json_response(raw_response)

            return {
                'response': result.get('response', 'Here is the data analysis.'),
                'chart': result.get('chart', None),
                'insights': result.get('insights', []),
                'follow_up_questions': result.get('follow_up_questions', []),
                'intent': 'payroll_data',
                'drilldown_model': payroll_data.get('drilldown_model', ''),
            }
        except Exception as e:
            _logger.warning("Failed to parse chart response: %s", e)
            # Fallback: return raw text response
            return {
                'response': raw_response if 'raw_response' in dir() else str(e),
                'chart': None,
                'insights': [],
                'follow_up_questions': [],
                'intent': 'payroll_data',
                'drilldown_model': payroll_data.get('drilldown_model', ''),
            }

    def _process_knowledge_query(self, provider, message, conversation_history):
        """Process a payroll knowledge question."""
        messages = [
            {"role": "system", "content": PAYAI_SYSTEM_PROMPT},
        ]
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": msg.get('content', ''),
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

    # Tour ids the frontend coach knows about — used to validate the LLM's action.
    _KNOWN_TOURS = ('hero_path', 'tour_payrun', 'tour_formula', 'tour_payslips')

    def _sanitize_action(self, action):
        """Only allow well-formed start_tour actions for tours we actually ship."""
        if not isinstance(action, dict):
            return None
        if action.get('type') != 'start_tour':
            return None
        tour = action.get('tour')
        if tour not in self._KNOWN_TOURS:
            return None
        return {
            'type': 'start_tour',
            'tour': tour,
            'label': (action.get('label') or 'Show me')[:40],
        }

    def _process_onboarding_query(self, provider, message, conversation_history):
        """Answer a 'how do I use Payobook' question, optionally launching a tour."""
        messages = [{"role": "system", "content": ONBOARDING_SYSTEM_PROMPT}]
        for msg in conversation_history[-6:]:
            messages.append({"role": msg.get('role', 'user'), "content": msg.get('content', '')})
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
                "content": msg.get('content', ''),
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
