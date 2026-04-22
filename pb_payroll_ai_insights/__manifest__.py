# -*- coding: utf-8 -*-
{
    'name': 'PayAI — Intelligent Payroll Analytics',
    'version': '19.0.2.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'AI-powered payroll analytics with conversational charts, dashboards, and insights',
    'description': """
PayAI — Intelligent Payroll Analytics
======================================

AI-powered module that brings conversational intelligence to payroll data.

Features
--------
* **Conversational AI Chat**: Ask any question in natural language — get charts, tables, and insights
* **In-Chat Chart Rendering**: Interactive Chart.js visualizations rendered directly in the chat window
* **AI Dashboard Builder**: AI-configurable dashboard with drag-and-drop chart widgets
* **Dual-Mode AI**: Answers payroll data queries (with charts) AND general questions
* **Individual + Aggregate Data**: Access to employee-level and department-level payroll data
* **Multiple Chart Types**: Bar, line, pie, doughnut, radar, scatter, bubble charts
* **Floating Pill + Full Page**: Quick-access pill for fast queries, full-page view for deep analysis
* **Narrative Insights**: AI-generated text explanations accompanying every chart
* **Voice-to-Chart**: Microphone input with Whisper STT + TTS audio response
* **Predictive Forecasting**: AI-powered payroll cost predictions with confidence bands
* **Proactive Pulse Engine**: Anomaly detection with daily alerts and AI narratives
* **Executive PDF Reports**: AI-narrated payroll reports with data tables

AI Provider Support
-------------------
* OpenAI GPT-4o / GPT-4o-mini (primary)
* OpenAI Whisper (voice transcription)
* OpenAI TTS (text-to-speech)
* Ollama / Llama / Mistral (planned)

Inspired by: Power BI Copilot, ThoughtSpot, Julius AI, Tableau Pulse, Zoho Zia
    """,
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'hr_contract',
        'mail',
        'web',
        'om_hr_payroll',
        'pb_hr_payroll_base',
    ],
    'data': [
        # Security
        'security/payroll_ai_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/payroll_ai_config_data.xml',
        'data/payroll_ai_pulse_cron.xml',

        # Reports
        'report/payroll_ai_report_templates.xml',

        # Views
        'views/payroll_ai_config_views.xml',
        'views/payroll_ai_chat_views.xml',
        'views/payroll_ai_dashboard_views.xml',
        'views/payroll_ai_pulse_views.xml',
        'views/payroll_ai_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Gridstack.js library (drag & resize grid)
            'pb_payroll_ai_insights/static/src/lib/gridstack.min.css',
            'pb_payroll_ai_insights/static/src/lib/gridstack-all.min.js',

            # Chart.js library
            'pb_payroll_ai_insights/static/src/lib/chart.umd.min.js',

            # Global CSS
            'pb_payroll_ai_insights/static/src/css/payroll_ai_global.scss',

            # Chart Renderer Component
            'pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.js',
            'pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.xml',
            'pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.scss',

            # AI Insight Chat Component
            'pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.js',
            'pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.xml',
            'pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.scss',

            # AI Insight Chat Full Page
            'pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat_full.js',
            'pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat_full.xml',

            # AI Dashboard Component
            'pb_payroll_ai_insights/static/src/components/ai_dashboard/ai_dashboard.js',
            'pb_payroll_ai_insights/static/src/components/ai_dashboard/ai_dashboard.xml',
            'pb_payroll_ai_insights/static/src/components/ai_dashboard/ai_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
