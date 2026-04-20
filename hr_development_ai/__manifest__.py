# -*- coding: utf-8 -*-
{
    'name': 'AI-Enabled Employee Development System',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Employee Development',
    'summary': 'AI-native employee development with skills intelligence, coaching, learning paths, and knowledge management',
    'description': """
AI-Enabled Employee Development System
=======================================

A comprehensive, AI-native employee development platform built on Odoo 19 CE that integrates:

Core Features
-------------
* **AI-Driven Talent Intelligence**: Skills inference from actual work, AI-powered recommendations
* **Learning Experience Platform**: Personalized learning paths, course recommendations
* **Continuous Performance & Coaching**: Real-time AI coaching nudges based on KPIs
* **Mentoring & Career Development**: AI mentorship matching, career path planning
* **Skills & Capability Framework**: Comprehensive skills taxonomy with proficiency tracking
* **Knowledge & Organizational Memory**: Knowledge graphs linked to projects and expertise
* **Employee Experience**: Self-service dashboards, gamification, mobile-first design
* **Analytics & Governance**: Development ROI, skills coverage, compliance tracking

AI Provider Support
------------------
* Llama/Ollama (open source, default)
* Mistral (open source)
* OpenAI ChatGPT (optional, for demos)
* Odoo 19 Native AI (built-in features)

Inspired by world-class platforms: SAP SuccessFactors, Workday Skills Cloud, BetterUp, Degreed, Microsoft Viva
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'website_slides',
        'gamification',
        'project',
        'mail',
        'portal',
        'web',
        'web_timeline',
    ],
    'data': [
        # Security
        'security/hr_development_security.xml',
        'security/hr_development_groups.xml',
        'security/ir.model.access.csv',

        # Data
        'data/hr_skill_category_data.xml',
        'data/hr_skill_level_data.xml',
        # 'data/hr_skill_data.xml',  # Commented out - base Odoo requires skill_type_id
        'data/ai_provider_data.xml',
        'data/gamification_data.xml',

        # Views - Configuration
        'views/ai_provider_config_views.xml',

        # Views - Skills & Capabilities
        'views/hr_skill_views.xml',
        'views/hr_employee_skill_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_skill_gap_views.xml',

        # Views - Learning & Development
        'views/hr_learning_path_views.xml',
        'views/hr_certification_views.xml',
        'views/hr_development_plan_views.xml',

        # Views - Coaching & Mentoring
        'views/hr_coaching_views.xml',
        'views/hr_mentorship_views.xml',

        # Views - Career & Knowledge
        'views/hr_career_path_views.xml',
        'views/hr_knowledge_views.xml',

        # Wizards
        'wizards/skill_assessment_wizard_views.xml',
        'wizards/ai_coaching_wizard_views.xml',
        'wizards/mentorship_matching_wizard_views.xml',

        # Dashboard
        'views/hr_development_dashboard_views.xml',

        # BFSI Performance Coaching Views
        'views/bfsi_branch_views.xml',
        'views/bfsi_kpi_views.xml',
        'views/bfsi_action_plan_views.xml',
        'views/bfsi_coaching_strategy_views.xml',
        'views/bfsi_kpi_integration_views.xml',
        'views/bfsi_progress_wizard_views.xml',

        # Menus (must be loaded AFTER all views that define actions)
        'views/hr_development_menus.xml',
        'views/bfsi_menus.xml',

        # AI Dashboard
        'views/bfsi_ai_dashboard_views.xml',
    ],
    'demo': [
        'data/demo_data.xml',
        'data/bfsi_demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Global CSS
            'hr_development_ai/static/src/css/hr_development.css',

            # Dashboard
            'hr_development_ai/static/src/components/dashboard/hr_development_dashboard.js',
            'hr_development_ai/static/src/components/dashboard/hr_development_dashboard.xml',
            'hr_development_ai/static/src/components/dashboard/hr_development_dashboard.css',

            # AI Coaching Chat Widget
            'hr_development_ai/static/src/components/ai_coaching_chat/ai_coaching_chat_widget.js',
            'hr_development_ai/static/src/components/ai_coaching_chat/ai_coaching_chat_widget.xml',
            'hr_development_ai/static/src/components/ai_coaching_chat/ai_coaching_chat_widget.css',
            'hr_development_ai/static/src/components/ai_coaching_chat/ai_coaching_form_widget.js',
            'hr_development_ai/static/src/components/ai_coaching_chat/ai_coaching_form_widget.xml',

            # Skills Matrix Widget
            'hr_development_ai/static/src/components/skills_matrix/skills_matrix_widget.js',
            'hr_development_ai/static/src/components/skills_matrix/skills_matrix_widget.xml',
            'hr_development_ai/static/src/components/skills_matrix/skills_matrix_widget.css',

            # Knowledge Graph Widget
            'hr_development_ai/static/src/components/knowledge_graph/knowledge_graph_widget.js',
            'hr_development_ai/static/src/components/knowledge_graph/knowledge_graph_widget.xml',
            'hr_development_ai/static/src/components/knowledge_graph/knowledge_graph_widget.css',

            # BFSI AI Coach Panel (Persistent Sidebar)
            'hr_development_ai/static/src/components/bfsi_ai_coach_panel/bfsi_ai_coach_panel.js',
            'hr_development_ai/static/src/components/bfsi_ai_coach_panel/bfsi_ai_coach_panel.xml',
            'hr_development_ai/static/src/components/bfsi_ai_coach_panel/bfsi_ai_coach_panel.scss',

            # BFSI Dashboard Premium CSS
            'hr_development_ai/static/src/css/bfsi_dashboard.css',

            # BFSI Manager Dashboard
            'hr_development_ai/static/src/components/bfsi_manager_dashboard/bfsi_manager_dashboard.js',
            'hr_development_ai/static/src/components/bfsi_manager_dashboard/bfsi_manager_dashboard.xml',
            'hr_development_ai/static/src/components/bfsi_manager_dashboard/bfsi_manager_dashboard.scss',

            # BFSI AI Performance Dashboard (PerformX-inspired)
            'hr_development_ai/static/src/components/bfsi_ai_dashboard/bfsi_ai_dashboard.js',
            'hr_development_ai/static/src/components/bfsi_ai_dashboard/bfsi_ai_dashboard.xml',
            'hr_development_ai/static/src/components/bfsi_ai_dashboard/bfsi_ai_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
