# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Skills demonstrated/required
    skill_ids = fields.Many2many(
        'hr.skill',
        string='Skills',
        help='Skills demonstrated or required for this task'
    )

    # Knowledge nodes
    knowledge_node_ids = fields.Many2many(
        'hr.knowledge.node',
        string='Related Knowledge',
        help='Knowledge captured from this task'
    )

    # Development objectives
    development_objective_ids = fields.One2many(
        'hr.development.objective',
        'task_id',
        string='Development Objectives',
        help='Development objectives linked to this task'
    )

    is_development_task = fields.Boolean(
        string='Development Task',
        default=False,
        help='This is a learning/development task'
    )

    def write(self, vals):
        """Track skills when task is completed"""
        res = super().write(vals)

        # If task stage changed to done, update employee skills
        if vals.get('stage_id'):
            for task in self:
                stage = self.env['project.task.type'].browse(vals['stage_id'])

                if stage.fold and task.user_ids and task.skill_ids:  # Task completed
                    for user in task.user_ids:
                        if user.employee_id:
                            employee = user.employee_id

                            for skill in task.skill_ids:
                                employee_skill = self.env['hr.employee.skill'].search([
                                    ('employee_id', '=', employee.id),
                                    ('skill_id', '=', skill.id)
                                ], limit=1)

                                if employee_skill:
                                    # Increment AI inference score
                                    employee_skill.ai_inference_score = min(100, employee_skill.ai_inference_score + 5)
                                    employee_skill.last_used_date = fields.Date.today()
                                    employee_skill.aggregate_proficiency_score()
                                else:
                                    # Create new skill entry
                                    new_skill = self.env['hr.employee.skill'].create({
                                        'employee_id': employee.id,
                                        'skill_id': skill.id,
                                        'ai_inference_score': 30,  # Initial score for task completion
                                        'source': 'ai_inferred',
                                        'last_used_date': fields.Date.today(),
                                        'evidence_text': f'Task: {task.name}'
                                    })
                                    new_skill.aggregate_proficiency_score()

        return res

    def action_add_to_knowledge_graph(self):
        """Extract knowledge from this task and add to graph"""
        self.ensure_one()

        try:
            from ..ai_providers.provider_factory import get_ai_provider
            ai_provider = get_ai_provider(self.env)

            # Prepare task data
            task_data = {
                'name': self.name,
                'description': self.description or '',
                'project': self.project_id.name if self.project_id else '',
                'stage': self.stage_id.name if self.stage_id else '',
                'tags': ','.join(self.tag_ids.mapped('name'))
            }

            # Extract knowledge
            knowledge_items = ai_provider.extract_knowledge({'tasks': [task_data]})

            # Create knowledge nodes
            for item in knowledge_items:
                node = self.env['hr.knowledge.node'].create({
                    'name': item.get('title', self.name),
                    'content': item.get('description', ''),
                    'node_type': item.get('type', 'concept'),
                    'task_ids': [(6, 0, [self.id])],
                    'project_id': self.project_id.id if self.project_id else False,
                    'confidence_score': item.get('confidence', 0.7),
                    'expert_ids': [(6, 0, self.user_ids.mapped('employee_id').ids)]
                })

                self.knowledge_node_ids = [(4, node.id)]

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Knowledge Extracted',
                    'message': f'Extracted {len(knowledge_items)} knowledge items',
                    'type': 'success',
                }
            }

        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Knowledge extraction failed: {e}")

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Extraction Failed',
                    'message': str(e),
                    'type': 'warning',
                }
            }
