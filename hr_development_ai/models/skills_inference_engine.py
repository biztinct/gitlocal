# -*- coding: utf-8 -*-

from odoo import models, api, _
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class SkillsInferenceEngine(models.AbstractModel):
    _name = 'hr.skills.inference.engine'
    _description = 'AI-Powered Skills Inference Engine'

    @api.model
    def infer_skills_for_employee(self, employee_id, sources='all'):
        """
        Comprehensive skills inference from multiple sources

        Args:
            employee_id: Employee record ID
            sources: 'all' or list of ['tasks', 'courses', 'assessments']

        Returns:
            dict: Inferred skills with sources and confidence scores
        """
        employee = self.env['hr.employee'].browse(employee_id)

        if sources == 'all':
            sources = ['tasks', 'courses', 'assessments']

        inferred_skills = {}

        if 'tasks' in sources:
            task_skills = self._infer_from_project_tasks(employee)
            self._merge_skills(inferred_skills, task_skills, 'ai_inferred')

        if 'courses' in sources:
            course_skills = self._infer_from_courses(employee)
            self._merge_skills(inferred_skills, course_skills, 'course')

        if 'assessments' in sources:
            assessment_skills = self._get_self_assessments(employee)
            self._merge_skills(inferred_skills, assessment_skills, 'self')

        # Update employee skills
        self._update_employee_skills(employee, inferred_skills)

        return inferred_skills

    def _infer_from_project_tasks(self, employee):
        """
        AI-powered inference from project tasks

        Analyzes task descriptions, tags, and completion data to detect demonstrated skills
        """
        _logger.info(f"Inferring skills from project tasks for {employee.name}")

        skills = {}

        # Get tasks from last 12 months
        one_year_ago = datetime.now() - timedelta(days=365)
        tasks = self.env['project.task'].search([
            ('user_ids', 'in', [employee.id]),
            ('create_date', '>=', one_year_ago.strftime('%Y-%m-%d'))
        ])

        if not tasks:
            return skills

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Get all known skills for better matching
            all_skills = self.env['hr.skill'].search([])
            skill_taxonomy = all_skills.mapped('name')

            # Batch process tasks for efficiency
            for task in tasks:
                task_text = f"""
Title: {task.name}
Description: {task.description or ''}
Tags: {', '.join(task.tag_ids.mapped('name'))}
Project: {task.project_id.name if task.project_id else ''}
Stage: {task.stage_id.name if task.stage_id else ''}
                """.strip()

                # Extract skills using AI
                extracted_skills = ai_provider.extract_skills(task_text, skill_taxonomy)

                for skill_data in extracted_skills:
                    skill_name = skill_data.get('skill')
                    confidence = skill_data.get('confidence', 0.7)

                    # Find or create skill
                    skill = all_skills.filtered(lambda s: s.name.lower() == skill_name.lower())

                    if skill:
                        skill_id = skill[0].id

                        if skill_id not in skills:
                            skills[skill_id] = {
                                'score': 0,
                                'confidence': 0,
                                'evidence': []
                            }

                        # Increase score based on task complexity
                        task_score = 10 if task.stage_id.fold else 5  # Higher if completed
                        skills[skill_id]['score'] += task_score
                        skills[skill_id]['confidence'] = max(skills[skill_id]['confidence'], confidence)
                        skills[skill_id]['evidence'].append(task.name)

        except Exception as e:
            _logger.warning(f"AI skills inference failed, using fallback: {e}")
            # Fallback: Simple keyword matching
            skills = self._fallback_task_inference(employee, tasks)

        # Normalize scores to 0-100
        if skills:
            max_score = max(s['score'] for s in skills.values())
            for skill_id in skills:
                skills[skill_id]['score'] = min(100, (skills[skill_id]['score'] / max_score) * 100)

        return skills

    def _fallback_task_inference(self, employee, tasks):
        """Fallback keyword-based inference when AI unavailable"""
        skills = {}
        all_skills = self.env['hr.skill'].search([])

        for task in tasks:
            task_text = f"{task.name} {task.description or ''} {' '.join(task.tag_ids.mapped('name'))}".lower()

            for skill in all_skills:
                if skill.name.lower() in task_text:
                    if skill.id not in skills:
                        skills[skill.id] = {
                            'score': 0,
                            'confidence': 0.6,
                            'evidence': []
                        }
                    skills[skill.id]['score'] += 10
                    skills[skill.id]['evidence'].append(task.name)

        return skills

    def _infer_from_courses(self, employee):
        """Infer skills from completed courses"""
        _logger.info(f"Inferring skills from courses for {employee.name}")

        skills = {}

        # Get completed courses
        completed_courses = self.env['slide.channel.partner'].search([
            ('partner_id', '=', employee.user_id.partner_id.id),
            ('completed', '=', True)
        ])

        for course_partner in completed_courses:
            course = course_partner.channel_id

            # Get skills associated with course
            for skill in course.skill_ids:
                if skill.id not in skills:
                    skills[skill.id] = {
                        'score': 0,
                        'confidence': 0.9,  # High confidence from formal learning
                        'evidence': []
                    }

                # Score based on completion percentage and quiz results
                completion_score = 50  # Base score for completion
                if course_partner.completion >= 100:
                    completion_score = 70

                skills[skill.id]['score'] += completion_score
                skills[skill.id]['evidence'].append(f"Completed: {course.name}")

        return skills

    def _get_self_assessments(self, employee):
        """Get self-assessment scores"""
        skills = {}

        for employee_skill in employee.skill_ids:
            if employee_skill.self_assessment_score > 0:
                skills[employee_skill.skill_id.id] = {
                    'score': employee_skill.self_assessment_score,
                    'confidence': 0.7,
                    'evidence': ['Self-assessed']
                }

        return skills

    def _merge_skills(self, target, source, source_type):
        """Merge skills from different sources"""
        for skill_id, data in source.items():
            if skill_id not in target:
                target[skill_id] = {
                    'sources': {},
                    'max_score': 0,
                    'max_confidence': 0,
                    'all_evidence': []
                }

            target[skill_id]['sources'][source_type] = data['score']
            target[skill_id]['max_score'] = max(target[skill_id]['max_score'], data['score'])
            target[skill_id]['max_confidence'] = max(target[skill_id]['max_confidence'], data.get('confidence', 0.7))
            target[skill_id]['all_evidence'].extend(data.get('evidence', []))

    def _update_employee_skills(self, employee, inferred_skills):
        """Update employee skill records with inferred data"""
        for skill_id, data in inferred_skills.items():
            employee_skill = self.env['hr.employee.skill'].search([
                ('employee_id', '=', employee.id),
                ('skill_id', '=', skill_id)
            ], limit=1)

            sources = data.get('sources', {})

            vals = {
                'employee_id': employee.id,
                'skill_id': skill_id,
                'confidence': data.get('max_confidence', 0.7),
                'evidence_text': '\n'.join(data.get('all_evidence', [])[:10]),  # Top 10 evidence items
            }

            # Update source-specific scores
            if 'ai_inferred' in sources:
                vals['ai_inference_score'] = sources['ai_inferred']

            if 'course' in sources:
                vals['course_completion_score'] = sources['course']

            if 'self' in sources:
                vals['self_assessment_score'] = sources['self']

            if employee_skill:
                employee_skill.write(vals)
                employee_skill.aggregate_proficiency_score()
            else:
                new_skill = self.env['hr.employee.skill'].create(vals)
                new_skill.aggregate_proficiency_score()

        _logger.info(f"Updated {len(inferred_skills)} skills for {employee.name}")

    @api.model
    def scheduled_inference_all_employees(self):
        """
        Cron job: Run skills inference for all active employees
        """
        employees = self.env['hr.employee'].search([('active', '=', True)])

        _logger.info(f"Running scheduled skills inference for {len(employees)} employees")

        for employee in employees:
            try:
                self.infer_skills_for_employee(employee.id)
            except Exception as e:
                _logger.error(f"Skills inference failed for {employee.name}: {e}")

        return True
