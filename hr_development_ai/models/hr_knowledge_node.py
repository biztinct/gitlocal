# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HRKnowledgeNode(models.Model):
    _name = 'hr.knowledge.node'
    _description = 'Knowledge Graph Node'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Title', required=True, index=True, tracking=True)
    content = fields.Html(string='Content', tracking=True)

    node_type = fields.Selection([
        ('concept', 'Concept'),
        ('project', 'Project Outcome'),
        ('decision', 'Decision Rationale'),
        ('best_practice', 'Best Practice'),
        ('lesson_learned', 'Lesson Learned'),
        ('expertise', 'Expertise Area'),
        ('process', 'Process/Workflow')
    ], string='Type', required=True, default='concept', tracking=True)

    # Relationships
    expert_ids = fields.Many2many(
        'hr.employee',
        'knowledge_node_expert_rel',
        'node_id',
        'employee_id',
        string='Experts',
        help='Employees with expertise in this area'
    )

    skill_ids = fields.Many2many(
        'hr.skill',
        string='Related Skills'
    )

    # Source project/task
    project_id = fields.Many2one(
        'project.project',
        string='Source Project',
        ondelete='set null'
    )

    task_ids = fields.Many2many(
        'project.task',
        string='Related Tasks'
    )

    # Graph edges
    edge_from_ids = fields.One2many(
        'hr.knowledge.edge',
        'source_id',
        string='Outgoing Connections'
    )

    edge_to_ids = fields.One2many(
        'hr.knowledge.edge',
        'target_id',
        string='Incoming Connections'
    )

    related_node_ids = fields.Many2many(
        'hr.knowledge.node',
        compute='_compute_related_nodes',
        string='Related Nodes'
    )

    # Metadata
    confidence_score = fields.Float(
        string='AI Confidence',
        default=1.0,
        help='AI confidence in this knowledge extraction (0-1)'
    )

    view_count = fields.Integer(string='Views', default=0)
    last_accessed = fields.Datetime(string='Last Accessed')

    tags = fields.Char(string='Tags', help='Comma-separated tags')

    # Dummy field for knowledge graph widget attachment
    graph_data = fields.Text(string='Graph Data', help='Internal field for graph visualization widget')

    active = fields.Boolean(default=True)

    @api.depends('edge_from_ids.target_id', 'edge_to_ids.source_id')
    def _compute_related_nodes(self):
        for node in self:
            related = set()
            related.update(node.edge_from_ids.mapped('target_id').ids)
            related.update(node.edge_to_ids.mapped('source_id').ids)
            node.related_node_ids = [(6, 0, list(related))]

    def action_view(self):
        """Track view and update last accessed"""
        self.ensure_one()
        self.write({
            'view_count': self.view_count + 1,
            'last_accessed': fields.Datetime.now()
        })

    def action_add_connection(self):
        """Add connection to another node"""
        self.ensure_one()

        return {
            'name': 'Add Knowledge Connection',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.knowledge.edge',
            'view_mode': 'form',
            'context': {
                'default_source_id': self.id
            },
            'target': 'new'
        }

    @api.model
    def find_expert(self, topic_or_skill):
        """
        Find experts for a given topic or skill

        Args:
            topic_or_skill: Search term (skill name or topic)

        Returns:
            list: Ranked list of expert employees
        """
        # Search knowledge nodes matching topic
        nodes = self.search([
            '|', '|',
            ('name', 'ilike', topic_or_skill),
            ('content', 'ilike', topic_or_skill),
            ('tags', 'ilike', topic_or_skill)
        ])

        # Aggregate experts from matching nodes
        expert_scores = {}

        for node in nodes:
            for expert in node.expert_ids:
                if expert.id not in expert_scores:
                    expert_scores[expert.id] = {
                        'employee': expert,
                        'score': 0,
                        'nodes': []
                    }

                # Score based on node type and confidence
                type_weight = {
                    'expertise': 1.0,
                    'project': 0.8,
                    'best_practice': 0.7,
                    'decision': 0.6,
                    'concept': 0.5,
                    'lesson_learned': 0.4,
                    'process': 0.3
                }

                score = type_weight.get(node.node_type, 0.5) * node.confidence_score
                expert_scores[expert.id]['score'] += score
                expert_scores[expert.id]['nodes'].append(node.name)

        # Sort by score
        ranked_experts = sorted(
            expert_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )

        return ranked_experts

    @api.model
    def extract_knowledge_from_projects(self):
        """
        Cron job: Extract knowledge from completed projects using AI
        """
        # Get recently completed projects
        completed_projects = self.env['project.project'].search([
            ('date_last_stage_update', '>=', fields.Date.today().replace(day=1)),  # This month
        ], limit=10)

        for project in completed_projects:
            # Check if knowledge already extracted
            existing = self.search([('project_id', '=', project.id)], limit=1)
            if existing:
                continue

            try:
                from ..ai_providers.provider_factory import get_ai_provider
                ai_provider = get_ai_provider(self.env)

                # Prepare project data
                project_data = {
                    'name': project.name,
                    'description': project.description or '',
                    'tasks': [{
                        'name': t.name,
                        'description': t.description or '',
                        'stage': t.stage_id.name if t.stage_id else ''
                    } for t in project.task_ids[:20]]  # Limit to 20 tasks
                }

                # Extract knowledge using AI
                knowledge_items = ai_provider.extract_knowledge(project_data)

                # Create knowledge nodes
                for item in knowledge_items:
                    self.create({
                        'name': item.get('title', 'Untitled'),
                        'content': item.get('description', ''),
                        'node_type': item.get('type', 'concept'),
                        'project_id': project.id,
                        'confidence_score': item.get('confidence', 0.7),
                        'expert_ids': [(6, 0, [project.user_id.id])] if project.user_id else []
                    })

            except Exception as e:
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning(f"Knowledge extraction failed for {project.name}: {e}")

        return True

    @api.model
    def get_graph_data(self):
        """Get knowledge graph data for visualization

        Returns:
            dict: Nodes and edges for graph rendering
        """
        # Get all active knowledge nodes
        nodes = self.search([('active', '=', True)])

        # Format nodes for visualization
        nodes_data = []
        for node in nodes:
            nodes_data.append({
                'id': node.id,
                'name': node.name,
                'node_type': node.node_type,
                'description': node.content[:200] if node.content else '',  # Limit to 200 chars
                'view_count': node.view_count,
                'expert_count': len(node.expert_ids),
            })

        # Get all edges
        edges = self.env['hr.knowledge.edge'].search([
            ('source_id', 'in', nodes.ids),
            ('target_id', 'in', nodes.ids),
        ])

        # Format edges for visualization
        edges_data = []
        for edge in edges:
            edges_data.append({
                'source': edge.source_id.id,
                'target': edge.target_id.id,
                'relationship': edge.relationship_type,
                'strength': edge.strength,
            })

        return {
            'nodes': nodes_data,
            'edges': edges_data
        }


class HRKnowledgeEdge(models.Model):
    _name = 'hr.knowledge.edge'
    _description = 'Knowledge Graph Edge (Connection)'
    _rec_name = 'relationship_type'

    source_id = fields.Many2one(
        'hr.knowledge.node',
        string='From',
        required=True,
        ondelete='cascade',
        index=True
    )

    target_id = fields.Many2one(
        'hr.knowledge.node',
        string='To',
        required=True,
        ondelete='cascade',
        index=True
    )

    relationship_type = fields.Selection([
        ('related_to', 'Related To'),
        ('prerequisite_of', 'Prerequisite Of'),
        ('builds_on', 'Builds On'),
        ('contradicts', 'Contradicts'),
        ('example_of', 'Example Of'),
        ('part_of', 'Part Of'),
        ('leads_to', 'Leads To')
    ], string='Relationship', required=True, default='related_to')

    strength = fields.Float(
        string='Connection Strength',
        default=1.0,
        help='How strong is this relationship (0-1)'
    )

    description = fields.Text(string='Description')

    _sql_constraints = [
        ('source_target_unique', 'unique(source_id, target_id, relationship_type)',
         'This connection already exists!')
    ]
