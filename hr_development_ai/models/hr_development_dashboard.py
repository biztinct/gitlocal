# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json


class HRDevelopmentDashboard(models.Model):
    _name = 'hr.development.dashboard'
    _description = 'HR Development Dashboard'
    _auto = False  # This is a virtual model for dashboard

    name = fields.Char('Dashboard')

    @api.model
    def get_dashboard_stats(self, employee_id=None):
        """Get comprehensive dashboard statistics"""
        user = self.env.user
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

        if employee_id:
            employee = self.env['hr.employee'].browse(employee_id)

        # Get date ranges
        today = fields.Date.today()
        month_start = today.replace(day=1)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)

        stats = {
            'employee': self._get_employee_info(employee),
            'skills': self._get_skills_stats(employee),
            'learning': self._get_learning_stats(employee),
            'certifications': self._get_certification_stats(employee),
            'coaching': self._get_coaching_stats(employee),
            'mentorship': self._get_mentorship_stats(employee),
            'development_plans': self._get_development_plan_stats(employee),
            'recent_activities': self._get_recent_activities(employee),
            'skill_gaps': self._get_skill_gaps(employee),
            'charts': self._get_chart_data(employee),
            'team_stats': self._get_team_stats(employee) if employee.subordinate_ids else {},
        }

        return stats

    def _get_employee_info(self, employee):
        """Get basic employee information"""
        if not employee:
            return {}
        return {
            'id': employee.id,
            'name': employee.name,
            'job_title': employee.job_id.name if employee.job_id else '',
            'department': employee.department_id.name if employee.department_id else '',
            'image_url': f'/web/image/hr.employee/{employee.id}/image_128' if employee.image_128 else '',
            'manager': employee.parent_id.name if employee.parent_id else '',
        }

    def _get_skills_stats(self, employee):
        """Get skills statistics"""
        if not employee:
            return {'total': 0, 'by_level': [], 'recent': []}

        skills = self.env['hr.employee.skill'].search([
            ('employee_id', '=', employee.id)
        ])

        # Group by level
        level_counts = {}
        for skill in skills:
            level_name = skill.level_id.name if skill.level_id else 'Unknown'
            level_counts[level_name] = level_counts.get(level_name, 0) + 1

        # Recent skills (added in last 30 days)
        thirty_days_ago = fields.Date.today() - timedelta(days=30)
        recent_skills = skills.filtered(lambda s: s.create_date and s.create_date.date() >= thirty_days_ago)

        return {
            'total': len(skills),
            'by_level': [{'level': k, 'count': v} for k, v in level_counts.items()],
            'recent_count': len(recent_skills),
            'recent': [{'name': s.skill_id.name, 'level': s.level_id.name if s.level_id else ''} for s in recent_skills[:5]],
        }

    def _get_learning_stats(self, employee):
        """Get learning and enrollment statistics"""
        if not employee:
            return {'enrolled': 0, 'completed': 0, 'in_progress': 0}

        enrollments = self.env['hr.learning.enrollment'].search([
            ('employee_id', '=', employee.id)
        ])

        completed = enrollments.filtered(lambda e: e.state == 'completed')
        in_progress = enrollments.filtered(lambda e: e.state == 'in_progress')

        return {
            'enrolled': len(enrollments),
            'completed': len(completed),
            'in_progress': len(in_progress),
            'completion_rate': round(len(completed) / len(enrollments) * 100, 1) if enrollments else 0,
            'recent': [
                {
                    'name': e.learning_path_id.name,
                    'progress': e.progress_percentage,
                    'state': e.state
                } for e in enrollments[:5]
            ]
        }

    def _get_certification_stats(self, employee):
        """Get certification statistics"""
        if not employee:
            return {'total': 0, 'active': 0, 'expiring_soon': 0}

        certs = self.env['hr.certification'].search([
            ('employee_id', '=', employee.id)
        ])

        today = fields.Date.today()
        thirty_days = today + timedelta(days=30)

        active = certs.filtered(lambda c: c.active and not c.is_expired)
        expiring = certs.filtered(
            lambda c: c.active and not c.is_expired and c.expiry_date and c.expiry_date <= thirty_days
        )

        return {
            'total': len(certs),
            'active': len(active),
            'expiring_soon': len(expiring),
            'recent': [
                {
                    'name': c.name,
                    'issuer': c.issuing_organization,
                    'expiry': str(c.expiry_date) if c.expiry_date else '',
                    'state': c.state
                } for c in certs[:5]
            ]
        }

    def _get_coaching_stats(self, employee):
        """Get coaching statistics"""
        if not employee:
            return {'sessions': 0, 'nudges': 0}

        sessions = self.env['hr.coaching.session'].search([
            ('employee_id', '=', employee.id)
        ])

        nudges = self.env['hr.coaching.nudge'].search([
            ('employee_id', '=', employee.id)
        ])

        pending_nudges = nudges.filtered(lambda n: n.state == 'pending')

        return {
            'total_sessions': len(sessions),
            'total_nudges': len(nudges),
            'pending_nudges': len(pending_nudges),
            'recent_sessions': [
                {
                    'name': s.name,
                    'date': str(s.session_date) if s.session_date else '',
                    'type': s.session_type
                } for s in sessions[:5]
            ]
        }

    def _get_mentorship_stats(self, employee):
        """Get mentorship statistics"""
        if not employee:
            return {'as_mentor': 0, 'as_mentee': 0}

        as_mentor = self.env['hr.mentorship'].search([
            ('mentor_id', '=', employee.id),
            ('state', '=', 'active')
        ])

        as_mentee = self.env['hr.mentorship'].search([
            ('mentee_id', '=', employee.id),
            ('state', '=', 'active')
        ])

        return {
            'as_mentor': len(as_mentor),
            'as_mentee': len(as_mentee),
            'mentees': [{'name': m.mentee_id.name, 'focus': m.focus_area} for m in as_mentor[:5]],
            'mentors': [{'name': m.mentor_id.name, 'focus': m.focus_area} for m in as_mentee[:5]],
        }

    def _get_development_plan_stats(self, employee):
        """Get development plan statistics"""
        if not employee:
            return {'total': 0, 'active': 0}

        plans = self.env['hr.development.plan'].search([
            ('employee_id', '=', employee.id)
        ])

        active = plans.filtered(lambda p: p.state in ['draft', 'in_progress'])

        # Calculate overall progress
        total_progress = 0
        for plan in active:
            if plan.objective_ids:
                completed = len(plan.objective_ids.filtered(lambda o: o.state == 'completed'))
                total_progress += (completed / len(plan.objective_ids)) * 100

        avg_progress = total_progress / len(active) if active else 0

        return {
            'total': len(plans),
            'active': len(active),
            'avg_progress': round(avg_progress, 1),
            'recent': [
                {
                    'name': p.name,
                    'state': p.state,
                    'objectives_count': len(p.objective_ids)
                } for p in plans[:5]
            ]
        }

    def _get_recent_activities(self, employee):
        """Get recent activities across all development areas"""
        activities = []

        if not employee:
            return activities

        # Recent skills
        recent_skills = self.env['hr.employee.skill'].search([
            ('employee_id', '=', employee.id)
        ], order='create_date desc', limit=3)

        for skill in recent_skills:
            activities.append({
                'type': 'skill',
                'icon': 'fa-cogs',
                'color': 'primary',
                'title': f'Added skill: {skill.skill_id.name}',
                'date': str(skill.create_date.date()) if skill.create_date else '',
                'description': f'Level: {skill.level_id.name}' if skill.level_id else ''
            })

        # Recent coaching sessions
        recent_sessions = self.env['hr.coaching.session'].search([
            ('employee_id', '=', employee.id)
        ], order='create_date desc', limit=3)

        for session in recent_sessions:
            activities.append({
                'type': 'coaching',
                'icon': 'fa-comments',
                'color': 'success',
                'title': f'Coaching: {session.name}',
                'date': str(session.session_date) if session.session_date else '',
                'description': f'Topic: {session.topic}' if session.topic else ''
            })

        # Recent certifications
        recent_certs = self.env['hr.certification'].search([
            ('employee_id', '=', employee.id)
        ], order='create_date desc', limit=3)

        for cert in recent_certs:
            activities.append({
                'type': 'certification',
                'icon': 'fa-certificate',
                'color': 'warning',
                'title': f'Certification: {cert.name}',
                'date': str(cert.issue_date) if cert.issue_date else '',
                'description': f'Issuer: {cert.issuing_organization}' if cert.issuing_organization else ''
            })

        # Sort by date
        activities.sort(key=lambda x: x.get('date', ''), reverse=True)
        return activities[:10]

    def _get_skill_gaps(self, employee):
        """Get skill gaps for the employee"""
        if not employee:
            return []

        gaps = self.env['hr.skill.gap'].search([
            ('employee_id', '=', employee.id),
            ('gap_score', '>', 0)
        ], limit=10)

        return [
            {
                'skill': g.skill_id.name,
                'current_level': f"{round(g.current_score or 0)} / 100",
                'required_level': f"{round(g.required_score or 0)} / 100",
                'priority': g.priority,
                'gap_score': g.gap_score
            } for g in gaps
        ]

    def _get_chart_data(self, employee):
        """Get data for dashboard charts"""
        if not employee:
            return {}

        # Skills by category
        skills = self.env['hr.employee.skill'].search([
            ('employee_id', '=', employee.id)
        ])

        category_counts = {}
        for skill in skills:
            category = skill.skill_id.category_id.name if skill.skill_id.category_id else 'Other'
            category_counts[category] = category_counts.get(category, 0) + 1

        # Learning progress over time (last 6 months)
        enrollments = self.env['hr.learning.enrollment'].search([
            ('employee_id', '=', employee.id)
        ])

        # Skills by level distribution
        level_counts = {}
        for skill in skills:
            level = skill.level_id.name if skill.level_id else 'Unknown'
            level_counts[level] = level_counts.get(level, 0) + 1

        return {
            'skills_by_category': {
                'labels': list(category_counts.keys()),
                'data': list(category_counts.values()),
                'colors': ['#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#9b59b6', '#1abc9c']
            },
            'skills_by_level': {
                'labels': list(level_counts.keys()),
                'data': list(level_counts.values()),
                'colors': ['#e74c3c', '#f39c12', '#f1c40f', '#2ecc71', '#27ae60']
            },
            'learning_completion': {
                'completed': len(enrollments.filtered(lambda e: e.state == 'completed')),
                'in_progress': len(enrollments.filtered(lambda e: e.state == 'in_progress')),
                'not_started': len(enrollments.filtered(lambda e: e.state == 'enrolled'))
            }
        }

    def _get_team_stats(self, employee):
        """Get team statistics for managers"""
        if not employee or not employee.subordinate_ids:
            return {}

        team = employee.subordinate_ids
        team_ids = team.ids

        # Team skills
        team_skills = self.env['hr.employee.skill'].search([
            ('employee_id', 'in', team_ids)
        ])

        # Team learning
        team_enrollments = self.env['hr.learning.enrollment'].search([
            ('employee_id', 'in', team_ids)
        ])

        # Team certifications
        team_certs = self.env['hr.certification'].search([
            ('employee_id', 'in', team_ids),
            ('active', '=', True),
            ('is_expired', '=', False),
        ])

        return {
            'team_size': len(team),
            'total_skills': len(team_skills),
            'avg_skills_per_member': round(len(team_skills) / len(team), 1) if team else 0,
            'learning_enrollments': len(team_enrollments),
            'active_certifications': len(team_certs),
            'members': [
                {
                    'id': m.id,
                    'name': m.name,
                    'job': m.job_id.name if m.job_id else '',
                    'skills_count': len(m.skill_ids)
                } for m in team[:10]
            ]
        }

    @api.model
    def get_organization_stats(self):
        """Get organization-wide statistics for administrators"""
        # Total employees
        total_employees = self.env['hr.employee'].search_count([('active', '=', True)])

        # Total skills tracked
        total_skills = self.env['hr.employee.skill'].search_count([])

        # Total learning enrollments
        total_enrollments = self.env['hr.learning.enrollment'].search_count([])

        # Active certifications
        active_certs = self.env['hr.certification'].search_count([
            ('active', '=', True),
            ('is_expired', '=', False),
        ])

        # Active mentorships
        active_mentorships = self.env['hr.mentorship'].search_count([('state', '=', 'active')])

        # Coaching sessions this month
        month_start = fields.Date.today().replace(day=1)
        monthly_sessions = self.env['hr.coaching.session'].search_count([
            ('session_date', '>=', month_start)
        ])

        # Skills distribution
        skill_categories = self.env['hr.skill.category'].search([])
        skills_by_category = {}
        for cat in skill_categories:
            count = self.env['hr.employee.skill'].search_count([
                ('skill_id.category_id', '=', cat.id)
            ])
            skills_by_category[cat.name] = count

        return {
            'total_employees': total_employees,
            'total_skills_tracked': total_skills,
            'avg_skills_per_employee': round(total_skills / total_employees, 1) if total_employees else 0,
            'total_learning_enrollments': total_enrollments,
            'active_certifications': active_certs,
            'active_mentorships': active_mentorships,
            'monthly_coaching_sessions': monthly_sessions,
            'skills_by_category': {
                'labels': list(skills_by_category.keys()),
                'data': list(skills_by_category.values())
            }
        }
