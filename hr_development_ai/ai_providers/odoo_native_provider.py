# -*- coding: utf-8 -*-

import json
import logging
import re
from .base_provider import BaseAIProvider

_logger = logging.getLogger(__name__)


class OdooNativeAIProvider(BaseAIProvider):
    """
    Odoo 19 Native AI provider
    Uses built-in Odoo AI features (AI Server Actions, AI Text Fields)
    Fallback to rule-based approaches when AI not available
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.odoo_env = config.get('env') if config else None

    def generate_text(self, prompt, max_tokens=500, temperature=0.7, **kwargs):
        """
        Generate text using Odoo 19 AI features
        Falls back to template-based generation if AI unavailable
        """
        # TODO: When Odoo 19 AI Server Actions are available, use them here
        # For now, use rule-based templates

        _logger.info("Using Odoo Native AI (template-based fallback)")

        if "coaching" in prompt.lower():
            return self._generate_coaching_template(prompt)
        elif "skill" in prompt.lower():
            return self._generate_skills_template(prompt)
        elif "summary" in prompt.lower() or "meeting" in prompt.lower():
            return self._generate_summary_template(prompt)
        else:
            return "Generated response (Odoo Native AI)"

    def analyze_sentiment(self, text):
        """Analyze sentiment using rule-based approach"""
        text_lower = text.lower()

        # Simple keyword-based sentiment
        positive_keywords = ['good', 'great', 'excellent', 'happy', 'satisfied', 'love', 'amazing', 'wonderful']
        negative_keywords = ['bad', 'poor', 'terrible', 'unhappy', 'disappointed', 'hate', 'awful', 'horrible']

        positive_count = sum(1 for word in positive_keywords if word in text_lower)
        negative_count = sum(1 for word in negative_keywords if word in text_lower)

        if positive_count > negative_count:
            sentiment = "positive"
            score = min(0.5 + (positive_count * 0.1), 0.95)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = max(0.5 - (negative_count * 0.1), 0.05)
        else:
            sentiment = "neutral"
            score = 0.5

        return {"sentiment": sentiment, "score": score}

    def extract_skills(self, text, skill_taxonomy=None):
        """Extract skills using keyword matching"""
        extracted_skills = []

        if not skill_taxonomy:
            # Default common skills
            skill_taxonomy = [
                'Python', 'JavaScript', 'Leadership', 'Communication',
                'Project Management', 'Data Analysis', 'SQL', 'Machine Learning'
            ]

        text_lower = text.lower()

        for skill in skill_taxonomy:
            if skill.lower() in text_lower:
                # Calculate confidence based on context
                confidence = 0.8 if f"{skill.lower()} " in text_lower else 0.6
                extracted_skills.append({
                    "skill": skill,
                    "confidence": confidence
                })

        return extracted_skills

    def generate_coaching_nudge(self, context):
        """Generate coaching nudge using intelligent template matching"""
        situation = context.get('situation', 'general')
        employee_name = context.get('employee_name', 'Employee')
        relevant_data = context.get('relevant_data', {})
        question = relevant_data.get('question', '')

        # If there's a specific question, generate contextual response
        if question:
            response_message = self._generate_coaching_template(question)
            # Extract action items from the response
            action_items = self._extract_action_items(question, response_message)

            return {
                "message": response_message,
                "action_items": action_items,
                "priority": self._determine_priority(question)
            }

        # Fallback to situation-based templates
        templates = {
            'missed_deadline': {
                "message": f"Hi {employee_name}, it looks like a deadline was missed. Let's review what happened and create a plan to prevent this in the future.",
                "action_items": [
                    "Review task priorities and time estimates",
                    "Schedule a brief check-in to discuss blockers"
                ],
                "priority": "high"
            },
            'upcoming_meeting': {
                "message": f"Hi {employee_name}, you have an important meeting coming up. Take a few minutes to prepare key discussion points.",
                "action_items": [
                    "Review meeting agenda and objectives",
                    "Prepare questions and talking points"
                ],
                "priority": "medium"
            },
            'skill_gap_detected': {
                "message": f"Hi {employee_name}, we've identified an opportunity to develop new skills that align with your career goals.",
                "action_items": [
                    "Review recommended learning paths",
                    "Set aside time for skill development"
                ],
                "priority": "medium"
            },
            'skill_development': {
                "message": f"Hi {employee_name}, let's focus on developing your skills strategically.",
                "action_items": [
                    "Identify your top 3 skill development priorities",
                    "Create a learning plan with specific milestones",
                    "Set aside dedicated time for learning each week"
                ],
                "priority": "medium"
            },
            'career_planning': {
                "message": f"Hi {employee_name}, let's map out your career development path.",
                "action_items": [
                    "Define your 3-5 year career vision",
                    "Identify skills needed for your target role",
                    "Find a mentor who can guide your journey"
                ],
                "priority": "medium"
            },
            'performance': {
                "message": f"Hi {employee_name}, let's work on optimizing your performance.",
                "action_items": [
                    "Set clear priorities for your key deliverables",
                    "Identify and eliminate productivity blockers",
                    "Schedule regular progress reviews"
                ],
                "priority": "medium"
            },
            'goal_setting': {
                "message": f"Hi {employee_name}, let's ensure your goals are well-defined and achievable.",
                "action_items": [
                    "Review your goals using SMART criteria",
                    "Break large goals into smaller milestones",
                    "Share goals with someone for accountability"
                ],
                "priority": "medium"
            },
            'general': {
                "message": f"Hi {employee_name}, I'm here to help with your professional development. What would you like to work on today?",
                "action_items": [
                    "Reflect on your recent accomplishments",
                    "Identify one area you'd like to improve",
                    "Consider what support or resources you need"
                ],
                "priority": "low"
            }
        }

        return templates.get(situation, templates['general'])

    def _extract_action_items(self, question, response):
        """Extract relevant action items based on question type"""
        question_lower = question.lower()

        if any(kw in question_lower for kw in ['skill', 'learn', 'develop', 'training']):
            return [
                "Identify specific skills to develop",
                "Create a learning plan with milestones",
                "Allocate dedicated time for skill practice",
                "Find courses or resources to support learning"
            ]
        elif any(kw in question_lower for kw in ['career', 'promotion', 'advance', 'grow']):
            return [
                "Define your career vision and target role",
                "Identify required skills and experience",
                "Find a mentor in your target area",
                "Document your achievements and impact"
            ]
        elif any(kw in question_lower for kw in ['performance', 'productivity', 'efficient']):
            return [
                "Set clear priorities for the week",
                "Block time for focused deep work",
                "Identify and eliminate distractions",
                "Track progress on key metrics"
            ]
        elif any(kw in question_lower for kw in ['goal', 'objective', 'target']):
            return [
                "Write SMART goals with clear metrics",
                "Break goals into weekly milestones",
                "Set up accountability check-ins",
                "Celebrate progress along the way"
            ]
        elif any(kw in question_lower for kw in ['price', 'objection', 'customer', 'sales']):
            return [
                "Prepare value-focused responses",
                "Practice objection handling scenarios",
                "Gather customer success stories",
                "Understand your competitive positioning"
            ]
        else:
            return [
                "Reflect on your current situation",
                "Identify one specific action to take today",
                "Seek feedback or guidance from others",
                "Track your progress over time"
            ]

    def _determine_priority(self, question):
        """Determine priority based on question urgency"""
        question_lower = question.lower()

        high_priority_keywords = ['urgent', 'deadline', 'immediately', 'asap', 'crisis', 'problem', 'issue']
        low_priority_keywords = ['when i have time', 'eventually', 'future', 'someday']

        if any(kw in question_lower for kw in high_priority_keywords):
            return "high"
        elif any(kw in question_lower for kw in low_priority_keywords):
            return "low"
        else:
            return "medium"

    def recommend_learning(self, employee_skills, job_requirements, available_courses):
        """Recommend learning using rule-based matching"""
        recommendations = []

        # Build skills gap dictionary
        employee_skill_dict = {s['skill']: s.get('level', 0) for s in employee_skills}
        required_skill_dict = {s['skill']: s.get('level', 5) for s in job_requirements}

        gaps = {}
        for skill, required_level in required_skill_dict.items():
            current_level = employee_skill_dict.get(skill, 0)
            if current_level < required_level:
                gaps[skill] = required_level - current_level

        # Match courses to gaps
        for course in available_courses:
            course_skills = course.get('skills', [])
            relevance_score = 0

            for skill in course_skills:
                if skill in gaps:
                    relevance_score += gaps[skill] * 0.3

            if relevance_score > 0:
                recommendations.append({
                    "course_id": course.get('id'),
                    "relevance_score": min(relevance_score, 0.99),
                    "reason": f"Helps close skill gaps in: {', '.join([s for s in course_skills if s in gaps])}"
                })

        # Sort by relevance
        recommendations.sort(key=lambda x: x['relevance_score'], reverse=True)
        return recommendations[:5]

    def match_mentor(self, mentee_profile, potential_mentors):
        """Match mentor using rule-based scoring"""
        matches = []

        mentee_skills = set(s['skill'] for s in mentee_profile.get('skills', []))
        mentee_goals = set(mentee_profile.get('career_goals', []))

        for mentor in potential_mentors:
            score = 0
            reasons = []

            mentor_skills = set(s['skill'] for s in mentor.get('skills', []))
            skill_overlap = mentee_skills & mentor_skills

            if skill_overlap:
                score += len(skill_overlap) * 0.2
                reasons.append(f"Expertise in {', '.join(list(skill_overlap)[:3])}")

            mentor_career = set(mentor.get('career_path', []))
            career_overlap = mentee_goals & mentor_career

            if career_overlap:
                score += 0.3
                reasons.append("Similar career trajectory")

            if mentor.get('mentoring_capacity', 0) > 0:
                score += 0.1
                reasons.append("Available for mentoring")

            if score > 0:
                matches.append({
                    "mentor_id": mentor.get('id'),
                    "match_score": min(score, 0.99),
                    "reason": "; ".join(reasons)
                })

        matches.sort(key=lambda x: x['match_score'], reverse=True)
        return matches[:5]

    def summarize_meeting(self, transcript):
        """Summarize meeting using text extraction"""
        lines = transcript.split('\n')

        # Extract key points (lines with certain keywords)
        key_point_keywords = ['decided', 'agreed', 'conclusion', 'important', 'key', 'critical']
        action_keywords = ['action', 'todo', 'will', 'should', 'must', 'need to']
        decision_keywords = ['decided', 'agreed', 'approved', 'rejected']

        key_points = []
        action_items = []
        decisions = []

        for line in lines:
            line_lower = line.lower()

            if any(kw in line_lower for kw in key_point_keywords):
                key_points.append(line.strip())

            if any(kw in line_lower for kw in action_keywords):
                action_items.append(line.strip())

            if any(kw in line_lower for kw in decision_keywords):
                decisions.append(line.strip())

        return {
            "summary": f"Meeting covered {len(lines)} discussion points with {len(action_items)} action items identified.",
            "key_points": key_points[:5],
            "action_items": action_items[:5],
            "decisions": decisions[:5]
        }

    def extract_knowledge(self, project_data):
        """Extract knowledge using pattern matching"""
        knowledge = []

        project_name = project_data.get('name', 'Project')
        description = project_data.get('description', '')
        tasks = project_data.get('tasks', [])

        # Extract lessons from description
        if 'lesson' in description.lower() or 'learned' in description.lower():
            knowledge.append({
                "title": f"Lessons from {project_name}",
                "description": description[:500],
                "type": "lesson_learned",
                "confidence": 0.7,
                "related_skills": []
            })

        # Extract decisions
        if 'decided' in description.lower() or 'decision' in description.lower():
            knowledge.append({
                "title": f"Key decisions in {project_name}",
                "description": description[:500],
                "type": "decision",
                "confidence": 0.7,
                "related_skills": []
            })

        # Extract best practices from completed tasks
        completed_tasks = [t for t in tasks if t.get('stage') == 'done']
        if len(completed_tasks) > 5:
            knowledge.append({
                "title": f"Best practices from {project_name}",
                "description": f"Successfully completed {len(completed_tasks)} tasks using established methodologies.",
                "type": "best_practice",
                "confidence": 0.6,
                "related_skills": []
            })

        return knowledge

    def is_available(self):
        """Odoo Native AI is always available (uses fallbacks)"""
        return True

    def _generate_coaching_template(self, prompt):
        """Generate contextual coaching response based on the prompt"""
        question = self._extract_question_from_prompt(prompt) or prompt
        prompt_lower = question.lower()

        # Skill development questions
        if any(kw in prompt_lower for kw in ['skill', 'learn', 'develop', 'improve', 'training']):
            if 'technical' in prompt_lower or 'programming' in prompt_lower or 'coding' in prompt_lower:
                return """To develop your technical skills effectively:

1. **Set Clear Learning Goals**: Identify specific technologies or programming languages you want to master.

2. **Practice Consistently**: Dedicate at least 1-2 hours daily to hands-on coding practice. Build real projects.

3. **Take Structured Courses**: Enroll in online courses on platforms like Coursera, Udemy, or internal training programs.

4. **Join Communities**: Participate in tech forums, code reviews, and pair programming sessions with colleagues.

5. **Work on Challenging Projects**: Volunteer for projects that push you outside your comfort zone.

6. **Document Your Learning**: Keep a learning journal to track progress and reinforce concepts.

Remember, consistent practice over time yields the best results. What specific technical skill would you like to focus on first?"""

            elif 'leadership' in prompt_lower or 'management' in prompt_lower:
                return """Developing leadership skills requires intentional practice:

1. **Seek Feedback**: Regularly ask your team and peers for honest feedback on your leadership style.

2. **Find a Mentor**: Connect with experienced leaders who can guide your development.

3. **Read Widely**: Study leadership books, case studies, and biographies of successful leaders.

4. **Practice Active Listening**: Focus on truly understanding others before responding.

5. **Take Initiative**: Lead small projects or initiatives to build your confidence.

6. **Develop Emotional Intelligence**: Work on self-awareness, empathy, and relationship management.

7. **Learn to Delegate**: Trust your team with responsibilities while providing support.

What aspect of leadership would you like to develop most?"""

            elif 'communication' in prompt_lower or 'presentation' in prompt_lower:
                return """Improving communication skills is essential for career growth:

1. **Practice Public Speaking**: Join groups like Toastmasters or volunteer to present in meetings.

2. **Write Regularly**: Start a blog or write internal documentation to improve written communication.

3. **Active Listening**: Focus on understanding before responding. Ask clarifying questions.

4. **Seek Feedback**: Record yourself presenting and review, or ask colleagues for input.

5. **Adapt Your Style**: Learn to adjust your communication based on your audience.

6. **Non-Verbal Communication**: Pay attention to body language, eye contact, and tone.

7. **Handle Difficult Conversations**: Practice having challenging discussions with empathy and clarity.

What specific communication challenge are you facing?"""

            else:
                return """Here's a structured approach to skill development:

1. **Assess Current State**: Identify your current proficiency level and gaps.

2. **Set SMART Goals**: Make your learning objectives Specific, Measurable, Achievable, Relevant, and Time-bound.

3. **Create a Learning Plan**: Map out resources, courses, and practice opportunities.

4. **Dedicate Time**: Block regular time in your calendar for learning.

5. **Apply Immediately**: Use new skills in real work projects as soon as possible.

6. **Track Progress**: Monitor your advancement and celebrate milestones.

7. **Seek Feedback**: Get input from mentors and colleagues on your progress.

Which skills are you most interested in developing?"""

        # Career planning questions
        elif any(kw in prompt_lower for kw in ['career', 'promotion', 'advance', 'grow', 'future', 'path']):
            return """Career planning requires strategic thinking and action:

1. **Define Your Vision**: Where do you want to be in 3-5 years? What role excites you?

2. **Understand Requirements**: Research what skills, experience, and qualifications your target role requires.

3. **Gap Analysis**: Compare your current capabilities with the requirements and identify gaps.

4. **Build Relationships**: Network with people in roles you aspire to. Seek mentors who can guide you.

5. **Take Visible Initiative**: Volunteer for high-impact projects that showcase your abilities.

6. **Document Achievements**: Keep track of your accomplishments and quantify your impact.

7. **Have Career Conversations**: Regularly discuss your aspirations with your manager.

8. **Be Patient but Persistent**: Career growth takes time, but consistent effort pays off.

What specific career goal would you like to work toward?"""

        # Performance questions
        elif any(kw in prompt_lower for kw in ['performance', 'productivity', 'efficient', 'better', 'improve work']):
            return """To improve your performance at work:

1. **Set Clear Priorities**: Use techniques like Eisenhower Matrix to focus on what matters most.

2. **Time Management**: Block time for deep work, minimize distractions, use techniques like Pomodoro.

3. **Regular Review**: Weekly review your accomplishments and plan for the upcoming week.

4. **Seek Feedback**: Proactively ask for feedback and act on it promptly.

5. **Health Matters**: Ensure adequate sleep, exercise, and breaks to maintain peak performance.

6. **Automate & Delegate**: Identify tasks that can be automated or delegated.

7. **Continuous Learning**: Stay updated with industry trends and best practices.

8. **Build Strong Relationships**: Collaborate effectively with colleagues for better outcomes.

What specific aspect of your performance would you like to improve?"""

        # Goal setting questions
        elif any(kw in prompt_lower for kw in ['goal', 'objective', 'target', 'plan', 'achieve']):
            return """Effective goal setting follows the SMART framework:

**S - Specific**: Clearly define what you want to achieve. Avoid vague goals.

**M - Measurable**: Include metrics to track progress. How will you know you've succeeded?

**A - Achievable**: Set challenging but realistic goals based on your resources and constraints.

**R - Relevant**: Ensure goals align with your broader career objectives and organizational needs.

**T - Time-bound**: Set deadlines to create urgency and accountability.

**Action Steps**:
1. Write down your goals and review them regularly
2. Break large goals into smaller milestones
3. Share goals with a mentor or colleague for accountability
4. Celebrate progress along the way
5. Adjust goals if circumstances change

What goal would you like to set or refine?"""

        # Price/objection handling (from the screenshot)
        elif any(kw in prompt_lower for kw in ['price', 'objection', 'customer', 'sales', 'client', 'expensive']):
            return """Handling price objections effectively:

1. **Listen First**: Understand the real concern behind the objection. Is it budget, value perception, or timing?

2. **Acknowledge**: Validate their concern. "I understand budget is important..."

3. **Reframe Value**: Focus on ROI and benefits rather than cost. Calculate the value your solution provides.

4. **Compare Alternatives**: Show how your solution compares to alternatives in terms of total cost of ownership.

5. **Break It Down**: Present pricing in smaller units (per day, per user) to make it more digestible.

6. **Offer Options**: Provide different packages or payment terms that might fit their budget.

7. **Use Social Proof**: Share success stories from similar customers.

8. **Ask Questions**: "What would make this investment feel right for you?"

What specific objection are you dealing with?"""

        # Training questions
        elif any(kw in prompt_lower for kw in ['training', 'next', 'course', 'certif']):
            return """For identifying your next training focus:

1. **Review Your Role Requirements**: What skills does your current or target role require?

2. **Check Performance Feedback**: What areas for improvement have been highlighted?

3. **Analyze Industry Trends**: What skills are becoming more valuable in your field?

4. **Consult Your Manager**: Discuss development priorities in your 1-on-1 meetings.

5. **Consider Certifications**: Industry certifications can validate and enhance your expertise.

**Recommended Approach**:
- Start with skills that have immediate application in your current role
- Balance technical skills with soft skills development
- Look for training that includes hands-on practice
- Set aside dedicated time for learning each week

Would you like recommendations for specific courses or certifications?"""

        # Default contextual response
        else:
            summary = question.strip().replace('\n', ' ')
            if len(summary) > 140:
                summary = summary[:137].rstrip() + "..."

            return f"""Thank you for your question about "{summary}".

Here are some coaching insights to consider:

1. **Reflect on Your Goals**: What do you ultimately want to achieve in this area?

2. **Identify Obstacles**: What's currently preventing you from making progress?

3. **Seek Resources**: What tools, training, or support could help you move forward?

4. **Take Small Steps**: Break your challenge into manageable actions you can start today.

5. **Build Accountability**: Share your goals with someone who can support and check in on your progress.

6. **Learn from Others**: Find people who have successfully addressed similar challenges.

I'm here to provide more specific guidance. Could you share more details about:
- What specific outcome you're hoping for?
- What approaches you've already tried?
- What resources you have available?"""

    def _extract_question_from_prompt(self, prompt):
        """Extract the user question from a structured coaching prompt"""
        match = re.search(r'the employee asks:\\s*(.+)', prompt, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return None

        question = match.group(1).strip()
        question = re.split(r'\\n\\s*(provide|response):', question, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        return question or None

    def _generate_skills_template(self, prompt):
        """Generate skills list based on context"""
        prompt_lower = prompt.lower()

        if 'technical' in prompt_lower or 'developer' in prompt_lower:
            return '["Python", "JavaScript", "SQL", "Git", "API Development", "Data Analysis"]'
        elif 'leadership' in prompt_lower or 'manager' in prompt_lower:
            return '["Leadership", "Team Management", "Strategic Planning", "Decision Making", "Conflict Resolution"]'
        elif 'communication' in prompt_lower:
            return '["Public Speaking", "Written Communication", "Active Listening", "Presentation Skills", "Negotiation"]'
        else:
            return '["Problem Solving", "Critical Thinking", "Collaboration", "Time Management", "Adaptability"]'

    def _generate_summary_template(self, prompt):
        """Generate meeting summary based on content"""
        return '{"summary": "Meeting covered key discussion topics with actionable outcomes identified.", "key_points": ["Review of progress on current initiatives", "Discussion of upcoming priorities", "Resource allocation decisions"], "action_items": ["Follow up on pending items", "Schedule next review meeting"], "decisions": ["Approved proposed timeline", "Allocated additional resources"]}'
