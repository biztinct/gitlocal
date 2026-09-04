# -*- coding: utf-8 -*-

import json
import logging
from .base_provider import BaseAIProvider

_logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI provider supporting ChatGPT models
    Requires OpenAI API key
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.api_key = config.get('openai_api_key', '') if config else ''
        self.model = config.get('model_name', 'gpt-4o-mini') if config else 'gpt-4o-mini'
        self.timeout = config.get('timeout', 60) if config else 60

        if not self.api_key:
            _logger.warning("OpenAI API key not configured")

    def _get_client(self):
        """Get OpenAI client instance"""
        try:
            from openai import OpenAI
            return OpenAI(api_key=self.api_key, timeout=self.timeout)
        except ImportError:
            raise ImportError("OpenAI library not installed. Install with: pip install openai")

    def generate_text(self, prompt, max_tokens=500, temperature=0.7, **kwargs):
        """Generate text using OpenAI API"""
        try:
            client = self._get_client()

            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )

            return response.choices[0].message.content

        except Exception as e:
            _logger.error(f"OpenAI generation error: {e}")
            return f"Error: {str(e)}"

    def analyze_sentiment(self, text):
        """Analyze sentiment using OpenAI"""
        prompt = f"""Analyze the sentiment of the following text.
Return ONLY a JSON object with this exact format:
{{"sentiment": "positive/negative/neutral", "score": 0.0-1.0}}

Text: {text}

JSON:"""

        response = self.generate_text(prompt, max_tokens=100, temperature=0.3)

        try:
            return self._parse_json_response(response)
        except Exception as e:
            _logger.warning(f"Sentiment parsing error: {e}, response: {response}")
            return {"sentiment": "neutral", "score": 0.5}

    def extract_skills(self, text, skill_taxonomy=None):
        """Extract skills from text using OpenAI"""
        taxonomy_hint = ""
        if skill_taxonomy:
            taxonomy_hint = f"\n\nKnown skills in our taxonomy: {', '.join(skill_taxonomy[:50])}"

        prompt = f"""Extract technical and soft skills from this text.
Return ONLY a JSON array with this exact format:
[{{"skill": "Skill Name", "confidence": 0.0-1.0}}]

Text: {text}{taxonomy_hint}

JSON array:"""

        response = self.generate_text(prompt, max_tokens=300, temperature=0.3)

        try:
            skills = self._parse_json_response(response)
            return skills if isinstance(skills, list) else []
        except Exception as e:
            _logger.warning(f"Skills extraction error: {e}, response: {response}")
            return []

    def generate_coaching_nudge(self, context):
        """Generate coaching nudge using OpenAI"""
        employee_name = context.get('employee_name', 'Employee')
        situation = context.get('situation', 'general')
        relevant_data = context.get('relevant_data', {})
        tone = context.get('tone', 'supportive')

        prompt = f"""You are an AI executive coach. Generate a brief, actionable coaching message.

Employee: {employee_name}
Situation: {situation}
Context: {json.dumps(relevant_data, indent=2)}
Tone: {tone}

Return ONLY a JSON object with this exact format:
{{
    "message": "Brief coaching message (2-3 sentences)",
    "action_items": ["Specific action 1", "Specific action 2"],
    "priority": "high/medium/low"
}}

JSON:"""

        response = self.generate_text(prompt, max_tokens=400, temperature=0.8)

        try:
            return self._parse_json_response(response)
        except Exception as e:
            _logger.warning(f"Coaching nudge parsing error: {e}")
            return {
                "message": f"Focus on improving {situation}. Review your recent performance and identify areas for growth.",
                "action_items": ["Reflect on recent activities", "Set improvement goals"],
                "priority": "medium"
            }

    def recommend_learning(self, employee_skills, job_requirements, available_courses):
        """Recommend learning paths using OpenAI"""
        prompt = f"""Analyze skills gap and recommend learning courses.

Current Employee Skills: {json.dumps(employee_skills, indent=2)}
Job Requirements: {json.dumps(job_requirements, indent=2)}
Available Courses: {json.dumps(available_courses, indent=2)}

Return ONLY a JSON array of recommended course IDs with reasoning:
[
    {{"course_id": 1, "relevance_score": 0.95, "reason": "Closes Python skill gap from level 3 to 5"}},
    {{"course_id": 5, "relevance_score": 0.80, "reason": "..."}}
]

JSON array:"""

        response = self.generate_text(prompt, max_tokens=500, temperature=0.4)

        try:
            recommendations = self._parse_json_response(response)
            return recommendations if isinstance(recommendations, list) else []
        except Exception as e:
            _logger.warning(f"Learning recommendation error: {e}")
            return []

    def match_mentor(self, mentee_profile, potential_mentors):
        """Match mentor using OpenAI"""
        prompt = f"""Match a mentee with the best mentor candidates.

Mentee Profile: {json.dumps(mentee_profile, indent=2)}
Potential Mentors: {json.dumps(potential_mentors, indent=2)}

Consider: skill alignment, experience level, career goals compatibility, availability.

Return ONLY a JSON array of mentor IDs ranked by match quality:
[
    {{"mentor_id": 1, "match_score": 0.92, "reason": "Strong Python expertise, similar career path"}},
    {{"mentor_id": 3, "match_score": 0.85, "reason": "..."}}
]

JSON array:"""

        response = self.generate_text(prompt, max_tokens=400, temperature=0.4)

        try:
            matches = self._parse_json_response(response)
            return matches if isinstance(matches, list) else []
        except Exception as e:
            _logger.warning(f"Mentor matching error: {e}")
            return []

    def summarize_meeting(self, transcript):
        """Summarize meeting using OpenAI"""
        prompt = f"""Summarize this meeting transcript.

Transcript:
{transcript}

Return ONLY a JSON object with this exact format:
{{
    "summary": "Brief 2-3 sentence summary",
    "key_points": ["Point 1", "Point 2", "Point 3"],
    "action_items": ["Action 1", "Action 2"],
    "decisions": ["Decision 1", "Decision 2"]
}}

JSON:"""

        response = self.generate_text(prompt, max_tokens=600, temperature=0.5)

        try:
            return self._parse_json_response(response)
        except Exception as e:
            _logger.warning(f"Meeting summary error: {e}")
            return {
                "summary": "Meeting summary unavailable",
                "key_points": [],
                "action_items": [],
                "decisions": []
            }

    def extract_knowledge(self, project_data):
        """Extract knowledge from project data using OpenAI"""
        prompt = f"""Extract key knowledge from this project.

Project Data: {json.dumps(project_data, indent=2)}

Identify:
1. Key decisions made and rationale
2. Best practices discovered
3. Lessons learned
4. Technical expertise demonstrated

Return ONLY a JSON array:
[
    {{
        "title": "Knowledge item title",
        "description": "Detailed description",
        "type": "concept/decision/best_practice/lesson_learned",
        "confidence": 0.0-1.0,
        "related_skills": ["skill1", "skill2"]
    }}
]

JSON array:"""

        response = self.generate_text(prompt, max_tokens=800, temperature=0.5)

        try:
            knowledge = self._parse_json_response(response)
            return knowledge if isinstance(knowledge, list) else []
        except Exception as e:
            _logger.warning(f"Knowledge extraction error: {e}")
            return []

    def is_available(self):
        """Check if OpenAI is available"""
        if not self.api_key:
            return False

        try:
            # Test with minimal request
            client = self._get_client()
            client.models.list()
            return True
        except Exception as e:
            _logger.warning(f"OpenAI provider not available: {e}")
            return False
