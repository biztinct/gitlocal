# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
import json
import logging

_logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """
    Abstract base class for AI providers.
    All AI providers (Llama, OpenAI, Odoo Native, etc.) must implement this interface.
    """

    def __init__(self, config=None):
        """
        Initialize provider with configuration

        Args:
            config: Configuration dict or record with provider-specific settings
        """
        self.config = config or {}
        self.logger = _logger

    @abstractmethod
    def generate_text(self, prompt, max_tokens=500, temperature=0.7, **kwargs):
        """
        Generate text completion from prompt

        Args:
            prompt (str): Input prompt text
            max_tokens (int): Maximum tokens to generate
            temperature (float): Sampling temperature (0-1)
            **kwargs: Provider-specific parameters

        Returns:
            str: Generated text
        """
        pass

    @abstractmethod
    def analyze_sentiment(self, text):
        """
        Analyze sentiment of text

        Args:
            text (str): Text to analyze

        Returns:
            dict: {'sentiment': 'positive'|'negative'|'neutral', 'score': float}
        """
        pass

    @abstractmethod
    def extract_skills(self, text, skill_taxonomy=None):
        """
        Extract skills mentioned in text

        Args:
            text (str): Text to analyze (job description, task, etc.)
            skill_taxonomy (list): Optional list of known skills to match against

        Returns:
            list: [{'skill': 'Python', 'confidence': 0.95}, ...]
        """
        pass

    @abstractmethod
    def generate_coaching_nudge(self, context):
        """
        Generate personalized coaching suggestion

        Args:
            context (dict): Context data including:
                - employee_name
                - situation (missed_deadline, upcoming_meeting, skill_gap_detected, etc.)
                - relevant_data (KPIs, tasks, goals, etc.)
                - tone (supportive, motivational, direct)

        Returns:
            dict: {
                'message': 'Coaching suggestion text',
                'action_items': ['Action 1', 'Action 2'],
                'priority': 'high'|'medium'|'low'
            }
        """
        pass

    @abstractmethod
    def recommend_learning(self, employee_skills, job_requirements, available_courses):
        """
        Recommend learning paths based on skills gap

        Args:
            employee_skills (list): [{'skill': 'Python', 'level': 3}, ...]
            job_requirements (list): [{'skill': 'Python', 'level': 5}, ...]
            available_courses (list): [{'id': 1, 'name': 'Advanced Python', 'skills': [...]}, ...]

        Returns:
            list: Ranked list of recommended course IDs with reasoning
        """
        pass

    @abstractmethod
    def match_mentor(self, mentee_profile, potential_mentors):
        """
        AI-powered mentor matching

        Args:
            mentee_profile (dict): Mentee skills, goals, preferences
            potential_mentors (list): List of mentor profiles

        Returns:
            list: Ranked list of mentor IDs with match scores
        """
        pass

    @abstractmethod
    def summarize_meeting(self, transcript):
        """
        Summarize meeting transcript

        Args:
            transcript (str): Meeting transcript text

        Returns:
            dict: {
                'summary': 'Brief summary',
                'key_points': ['Point 1', 'Point 2'],
                'action_items': ['Action 1', 'Action 2'],
                'decisions': ['Decision 1']
            }
        """
        pass

    @abstractmethod
    def extract_knowledge(self, project_data):
        """
        Extract knowledge nodes from project/task data

        Args:
            project_data (dict): Project information including tasks, outcomes

        Returns:
            list: [
                {
                    'title': 'Knowledge title',
                    'description': 'Description',
                    'type': 'concept'|'decision'|'best_practice'|'lesson_learned',
                    'confidence': 0.85,
                    'related_skills': ['skill1', 'skill2']
                },
                ...
            ]
        """
        pass

    def is_available(self):
        """
        Check if provider is available and configured

        Returns:
            bool: True if provider can be used
        """
        return True

    def test_connection(self):
        """
        Test connection to AI service

        Returns:
            dict: {'success': bool, 'message': str, 'latency_ms': float}
        """
        try:
            start_time = self._get_current_time_ms()
            response = self.generate_text("Test connection", max_tokens=10)
            latency = self._get_current_time_ms() - start_time

            return {
                'success': True,
                'message': 'Connection successful',
                'latency_ms': latency,
                'response': response
            }
        except Exception as e:
            return {
                'success': False,
                'message': str(e),
                'latency_ms': 0
            }

    def _get_current_time_ms(self):
        """Helper to get current time in milliseconds"""
        import time
        return int(time.time() * 1000)

    def _parse_json_response(self, text):
        """
        Parse JSON from AI response, handling markdown code blocks

        Args:
            text (str): AI response that may contain JSON

        Returns:
            dict: Parsed JSON data
        """
        try:
            # Try direct JSON parse
            return json.loads(text)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

            # Try finding first { to last }
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])

            raise ValueError(f"Could not parse JSON from response: {text[:100]}...")

    # =====================================================
    # BFSI-SPECIFIC METHODS FOR PERFORMANCE COACHING
    # =====================================================

    def analyze_kpi_deviation(self, kpi_data, targets):
        """
        Analyze KPI deviation and identify root causes

        Args:
            kpi_data (dict): Current KPI values
            targets (dict): Target KPI values

        Returns:
            dict: {
                'deviation_summary': 'Brief summary of deviations',
                'root_causes': ['Root cause 1', 'Root cause 2'],
                'coaching_priority': 'low'|'medium'|'high'|'critical',
                'focus_areas': ['Area 1', 'Area 2']
            }
        """
        # Default implementation - subclasses can override
        deviations = {}
        for key in kpi_data:
            if key in targets and targets[key]:
                target = targets[key]
                actual = kpi_data.get(key, 0) or 0
                if target > 0:
                    deviation_pct = ((actual - target) / target) * 100
                    deviations[key] = {
                        'actual': actual,
                        'target': target,
                        'deviation_pct': round(deviation_pct, 1)
                    }

        # Determine priority based on deviations
        negative_count = sum(1 for d in deviations.values() if d['deviation_pct'] < -20)
        if negative_count >= 3:
            priority = 'critical'
        elif negative_count >= 2:
            priority = 'high'
        elif negative_count >= 1:
            priority = 'medium'
        else:
            priority = 'low'

        return {
            'deviation_summary': f"Found {len(deviations)} KPI deviations",
            'root_causes': ['Insufficient lead generation', 'Need for skill development'],
            'coaching_priority': priority,
            'focus_areas': list(deviations.keys())[:3]
        }

    def generate_coaching_strategy(self, banker_profile, kpi_data, historical_coaching=None):
        """
        Generate comprehensive coaching strategy for a banker

        Args:
            banker_profile (dict): Banker information (name, role, experience, etc.)
            kpi_data (dict): Current and historical KPI data
            historical_coaching (list): Previous coaching sessions and outcomes

        Returns:
            dict: {
                'strategy_summary': 'Overview of coaching strategy',
                'coaching_themes': ['Theme 1', 'Theme 2'],
                'session_guide': 'Step-by-step session guide',
                'opening_questions': ['Question 1', 'Question 2'],
                'probing_questions': ['Question 1', 'Question 2'],
                'roleplay_scenarios': ['Scenario 1', 'Scenario 2'],
                'learning_recommendations': ['Recommendation 1']
            }
        """
        # Default implementation - subclasses should override with AI
        prompt = self._build_coaching_strategy_prompt(banker_profile, kpi_data, historical_coaching)

        try:
            response = self.generate_text(prompt, max_tokens=2000, temperature=0.7)
            return self._parse_json_response(response)
        except Exception as e:
            self.logger.error(f"Error generating coaching strategy: {e}")
            return self._get_default_coaching_strategy(banker_profile)

    def generate_contextual_coaching(self, context, message, session_type='general', is_manager=False):
        """
        Generate contextual coaching response for chat interface

        Args:
            context (dict): Full context including KPIs, action plans, etc.
            message (str): User's chat message
            session_type (str): Type of coaching session
            is_manager (bool): Whether user is a manager

        Returns:
            dict: {
                'response': 'AI coaching response',
                'suggested_actions': [{'type': 'action_type', 'label': 'Action Label'}],
                'learning_content': {'title': 'Content title', 'url': '/path'},
                'follow_up_questions': ['Question 1']
            }
        """
        prompt = self._build_contextual_coaching_prompt(context, message, session_type, is_manager)

        try:
            response = self.generate_text(prompt, max_tokens=1000, temperature=0.7)

            # Try to parse as JSON, otherwise return as plain text
            try:
                return self._parse_json_response(response)
            except:
                return {
                    'response': response,
                    'suggested_actions': [],
                    'learning_content': None,
                    'follow_up_questions': []
                }
        except Exception as e:
            self.logger.error(f"Error in contextual coaching: {e}")
            return {
                'response': 'I apologize, but I encountered an issue. Please try again.',
                'suggested_actions': [],
                'learning_content': None,
                'follow_up_questions': []
            }

    def generate_action_plan(self, coaching_session_summary, kpi_gaps):
        """
        Generate action plan from coaching session

        Args:
            coaching_session_summary (str): Summary of coaching session
            kpi_gaps (dict): Identified KPI gaps

        Returns:
            dict: {
                'actions': [{'action': 'Action', 'kpi_category': 'input', 'success_criteria': 'Criteria'}],
                'commitments': ['Commitment 1'],
                'check_in_schedule': 'Weekly check-ins recommended'
            }
        """
        prompt = f"""Based on this coaching session summary and KPI gaps, generate an action plan.

Session Summary:
{coaching_session_summary}

KPI Gaps:
{json.dumps(kpi_gaps, indent=2)}

Return a JSON object with:
- actions: list of specific actions with kpi_category and success_criteria
- commitments: list of commitments the banker should make
- check_in_schedule: recommended check-in schedule

Response in JSON:"""

        try:
            response = self.generate_text(prompt, max_tokens=1000, temperature=0.5)
            return self._parse_json_response(response)
        except Exception as e:
            self.logger.error(f"Error generating action plan: {e}")
            return {
                'actions': [
                    {'action': 'Increase daily call volume', 'kpi_category': 'input', 'success_criteria': '+20% calls'},
                    {'action': 'Improve script adherence', 'kpi_category': 'behavior', 'success_criteria': '90% score'}
                ],
                'commitments': ['Complete daily activity log', 'Attend weekly coaching session'],
                'check_in_schedule': 'Weekly check-ins with manager'
            }

    def simulate_coaching_roleplay(self, scenario, manager_message, conversation_history=None):
        """
        Simulate banker response in roleplay practice

        Args:
            scenario (str): The roleplay scenario context
            manager_message (str): Manager's coaching message
            conversation_history (list): Previous messages in roleplay

        Returns:
            dict: {
                'banker_response': 'Simulated banker response',
                'coaching_feedback': 'Feedback on manager approach',
                'suggested_follow_up': 'Suggested next step'
            }
        """
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-5:]:  # Last 5 messages
                role = "Manager" if msg.get('role') == 'manager' else "Banker"
                history_text += f"{role}: {msg.get('content', '')}\n"

        prompt = f"""You are simulating a banker in a coaching roleplay session.

Scenario:
{scenario}

Conversation History:
{history_text}

Manager's Message:
{manager_message}

Respond as the banker would respond in this scenario. Be realistic - the banker may show resistance, confusion, or acceptance depending on the scenario.

Also provide coaching feedback on the manager's approach.

Return JSON:
{{
    "banker_response": "Your response as the banker",
    "coaching_feedback": "Feedback on manager's coaching approach",
    "suggested_follow_up": "What the manager might say next"
}}

Response:"""

        try:
            response = self.generate_text(prompt, max_tokens=800, temperature=0.8)
            return self._parse_json_response(response)
        except Exception as e:
            self.logger.error(f"Error in roleplay simulation: {e}")
            return {
                'banker_response': "I understand what you're saying. Can you give me a specific example?",
                'coaching_feedback': "Good approach. Consider asking more open-ended questions.",
                'suggested_follow_up': "Ask about specific challenges they've faced."
            }

    def _build_coaching_strategy_prompt(self, banker_profile, kpi_data, historical_coaching):
        """Build prompt for coaching strategy generation"""
        return f"""You are an expert banking performance coach. Generate a comprehensive coaching strategy.

Banker Profile:
{json.dumps(banker_profile, indent=2, default=str)}

Current KPI Data:
{json.dumps(kpi_data, indent=2, default=str)}

Historical Coaching Sessions:
{json.dumps(historical_coaching or [], indent=2, default=str)}

Generate a detailed coaching strategy as JSON:
{{
    "strategy_summary": "Brief overview of coaching approach",
    "coaching_themes": ["Theme 1", "Theme 2", "Theme 3"],
    "session_guide": "Step-by-step guide for coaching session",
    "opening_questions": ["Question 1", "Question 2"],
    "probing_questions": ["Question 1", "Question 2"],
    "closing_questions": ["Question 1", "Question 2"],
    "roleplay_scenarios": ["Scenario 1", "Scenario 2"],
    "learning_recommendations": ["Recommendation 1", "Recommendation 2"],
    "coaching_tips": "Tips for the manager conducting this session"
}}

Response:"""

    def _build_contextual_coaching_prompt(self, context, message, session_type, is_manager):
        """Build prompt for contextual coaching response"""
        role_context = "a Branch Manager coaching your team" if is_manager else "a Banker seeking coaching"

        return f"""You are an AI Performance Coach for banking professionals. You are helping {role_context}.

User Context:
- Name: {context.get('employee_name', 'User')}
- Role: {context.get('role', 'Banking Professional')}
- Branch: {context.get('branch', 'N/A')}
- Current Score: {context.get('latest_score', 'N/A')}%
- Coaching Priority: {context.get('coaching_priority', 'N/A')}

Session Type: {session_type}

User Message: {message}

Provide helpful, specific coaching advice. Be conversational but professional.
If relevant, suggest specific actions or learning content.

Return JSON:
{{
    "response": "Your coaching response",
    "suggested_actions": [{{"type": "action_type", "label": "Action Label"}}],
    "learning_content": {{"title": "Content Title"}} or null,
    "follow_up_questions": ["Follow-up question"]
}}

Response:"""

    def _get_default_coaching_strategy(self, banker_profile):
        """Return default coaching strategy when AI fails"""
        return {
            'strategy_summary': f"Coaching strategy for {banker_profile.get('name', 'banker')}",
            'coaching_themes': ['Performance improvement', 'Skill development', 'Goal setting'],
            'session_guide': '1. Review current KPIs\n2. Discuss challenges\n3. Set goals\n4. Create action plan',
            'opening_questions': [
                'How do you feel about your current performance?',
                'What challenges have you faced this month?'
            ],
            'probing_questions': [
                'What strategies have you tried?',
                'Where do you think you could improve?'
            ],
            'closing_questions': [
                'What specific actions will you commit to?',
                'How can I support you?'
            ],
            'roleplay_scenarios': [
                'Handle objection: Customer says they need to think about it',
                'Cross-sell: Customer just opened a savings account'
            ],
            'learning_recommendations': [
                'Sales techniques workshop',
                'Objection handling masterclass'
            ],
            'coaching_tips': 'Focus on specific behaviors, use positive reinforcement, set clear expectations'
        }
