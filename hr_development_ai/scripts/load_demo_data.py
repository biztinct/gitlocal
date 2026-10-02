# -*- coding: utf-8 -*-
"""
AI Performance Coaching - Comprehensive Demo Data Loader
=========================================================
Run: cat addons/hr_development_ai/scripts/load_demo_data.py | python3 odoo-bin shell -d <dbname>
  OR: python3 odoo-bin shell -d <dbname> < addons/hr_development_ai/scripts/load_demo_data.py

This script creates realistic demo data for a full client demo covering:
1. Regions, Branches, Employees (Bankers + Managers)
2. Users linked to employees with proper security groups
3. KPI Targets per banker type
4. 3 months of historical Performance KPI records (for trends & ranking movement)
5. Coaching Strategies (AI-generated, multiple states)
6. Coaching Sessions (scheduled, in-progress, completed)
7. Action Plans with items (various states and progress)
8. AI Provider configuration
"""

import json
from datetime import date, datetime, timedelta
import random

print("=" * 60)
print("AI Performance Coaching - Demo Data Loader")
print("=" * 60)

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def get_or_create(model, domain, vals):
    """Find existing record or create new one."""
    rec = env[model].search(domain, limit=1)
    if not rec:
        rec = env[model].create(vals)
        print(f"  Created {model}: {vals.get('name', vals.get('login', ''))}")
    else:
        print(f"  Found existing {model}: {rec.name if hasattr(rec, 'name') else rec.id}")
    return rec

def ensure_group(user_rec, group_xmlid):
    """Add user to group if not already member."""
    try:
        group = env.ref(group_xmlid)
        # Odoo 19 with access_roles: try SQL insert directly
        env.cr.execute("""
            INSERT INTO res_groups_users_rel (gid, uid)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (group.id, user_rec.id))
    except Exception as e:
        print(f"  Warning: Could not add group {group_xmlid}: {e}")

today = date.today()

# ============================================================
# 1. REGIONS
# ============================================================
print("\n--- Creating Regions ---")
region_north = get_or_create('bfsi.region', [('code', '=', 'HCM')], {
    'name': 'Ho Chi Minh Region', 'code': 'HCM', 'sequence': 1
})
region_south = get_or_create('bfsi.region', [('code', '=', 'HN')], {
    'name': 'Ha Noi Region', 'code': 'HN', 'sequence': 2
})

# ============================================================
# 2. BRANCHES
# ============================================================
print("\n--- Creating Branches ---")
branch_1 = get_or_create('bfsi.branch', [('code', '=', 'D1-001')], {
    'name': 'District 1 Branch', 'code': 'D1-001',
    'region_id': region_north.id,
    'street': '88 Dong Khoi Street, District 1',
    'city': 'Ho Chi Minh City', 'phone': '+84 28 3821 0000', 'sequence': 1
})
branch_2 = get_or_create('bfsi.branch', [('code', '=', 'D7-002')], {
    'name': 'District 7 Branch', 'code': 'D7-002',
    'region_id': region_north.id,
    'street': '123 Nguyen Luong Bang, District 7',
    'city': 'Ho Chi Minh City', 'phone': '+84 28 3773 0000', 'sequence': 2
})

# ============================================================
# 3. EMPLOYEES + LINKED USERS
# ============================================================
print("\n--- Creating Employees & Users ---")

def create_employee_with_user(name, login, job_title, banker_type, branch, groups):
    """Create employee with linked user and security groups."""
    user_rec = env['res.users'].search([('login', '=', login)], limit=1)
    if not user_rec:
        user_rec = env['res.users'].with_context(no_reset_password=True).create({
            'name': name, 'login': login, 'password': 'demo123',
        })
        print(f"  Created user: {login}")
    else:
        print(f"  Found existing user: {login}")
    ensure_group(user_rec, 'base.group_user')
    for g in groups:
        ensure_group(user_rec, g)

    emp = env['hr.employee'].search([('user_id', '=', user_rec.id)], limit=1)
    if not emp:
        emp = env['hr.employee'].search([('name', '=', name)], limit=1)
    if not emp:
        emp = env['hr.employee'].create({
            'name': name, 'user_id': user_rec.id,
            'job_title': job_title, 'banker_type': banker_type,
            'branch_id': branch.id if branch else False,
            'work_email': f'{login}@mbbank.com.vn',
            'ai_coaching_enabled': True,
        })
        print(f"  Created employee: {name}")
    else:
        emp.write({
            'user_id': user_rec.id, 'job_title': job_title,
            'banker_type': banker_type,
            'branch_id': branch.id if branch else False,
            'ai_coaching_enabled': True,
        })
        print(f"  Updated employee: {name}")
    return emp, user_rec

BM_GROUPS = [
    'hr_development_ai.group_bfsi_branch_manager',
    'hr_development_ai.group_hr_development_manager',
]
BANKER_GROUPS = [
    'hr_development_ai.group_bfsi_banker',
    'hr_development_ai.group_hr_development_user',
]

# Branch 1 - District 1
mgr1, mgr1_user = create_employee_with_user(
    'Nguyen Van Minh', 'minh.nv', 'Branch Manager', 'branch_manager', branch_1, BM_GROUPS)
branch_1.write({'manager_id': mgr1.id})

banker_a, _ = create_employee_with_user(
    'Tran Thi Lan', 'lan.tt', 'Relationship Manager', 'rm', branch_1, BANKER_GROUPS)
banker_b, _ = create_employee_with_user(
    'Le Hoang Nam', 'nam.lh', 'Relationship Manager', 'rm', branch_1, BANKER_GROUPS)
banker_c, _ = create_employee_with_user(
    'Pham Duc Anh', 'anh.pd', 'Wealth Manager', 'wealth_manager', branch_1, BANKER_GROUPS)
banker_d, _ = create_employee_with_user(
    'Vo Thi Mai', 'mai.vt', 'Loan Officer', 'loan_officer', branch_1, BANKER_GROUPS)
banker_e, _ = create_employee_with_user(
    'Hoang Minh Tuan', 'tuan.hm', 'Telesales Agent', 'telesales', branch_1, BANKER_GROUPS)

# Branch 2 - District 7
mgr2, mgr2_user = create_employee_with_user(
    'Do Thanh Ha', 'ha.dt', 'Branch Manager', 'branch_manager', branch_2, BM_GROUPS)
branch_2.write({'manager_id': mgr2.id})

banker_f, _ = create_employee_with_user(
    'Bui Van Khoa', 'khoa.bv', 'Relationship Manager', 'rm', branch_2, BANKER_GROUPS)
banker_g, _ = create_employee_with_user(
    'Nguyen Thi Huong', 'huong.nt', 'Insurance Advisor', 'insurance_advisor', branch_2, BANKER_GROUPS)

# Regional Manager
reg_mgr, _ = create_employee_with_user(
    'Tran Quoc Bao', 'bao.tq', 'Regional Manager', 'regional_manager', None,
    ['hr_development_ai.group_bfsi_regional_manager', 'hr_development_ai.group_hr_development_admin'])

region_north.write({'regional_manager_id': reg_mgr.id})

# ============================================================
# 4. KPI TARGETS
# ============================================================
print("\n--- Creating KPI Targets ---")
for bt, bt_name, targets in [
    ('rm', 'RM Monthly', {'target_dials_per_hour': 15, 'target_meetings_scheduled': 20,
        'target_calls_made': 200, 'target_script_adherence': 85,
        'target_objection_handling': 80, 'target_need_analysis': 75,
        'target_conversions': 10, 'target_products_sold': 15,
        'target_appointments_set': 25, 'target_revenue': 500000000}),
    ('telesales', 'Telesales Monthly', {'target_dials_per_hour': 25,
        'target_meetings_scheduled': 30, 'target_calls_made': 500,
        'target_script_adherence': 90, 'target_objection_handling': 85,
        'target_conversions': 15, 'target_products_sold': 20,
        'target_revenue': 300000000}),
    ('wealth_manager', 'Wealth Mgr Monthly', {'target_dials_per_hour': 10,
        'target_meetings_scheduled': 15, 'target_calls_made': 100,
        'target_script_adherence': 80, 'target_need_analysis': 85,
        'target_conversions': 8, 'target_revenue': 800000000,
        'target_aum': 5000000000}),
    ('loan_officer', 'Loan Officer Monthly', {'target_dials_per_hour': 12,
        'target_meetings_scheduled': 18, 'target_calls_made': 150,
        'target_conversions': 8, 'target_revenue': 400000000}),
]:
    # Note: removed 'active' field - doesn't exist on bfsi.kpi.target
    existing = env['bfsi.kpi.target'].search([
        ('banker_type', '=', bt), ('period_type', '=', 'monthly')], limit=1)
    if not existing:
        vals = {'name': bt_name, 'banker_type': bt, 'period_type': 'monthly'}
        vals.update(targets)
        env['bfsi.kpi.target'].create(vals)
        print(f"  Created KPI target: {bt_name}")
    else:
        print(f"  Found existing KPI target for {bt}")

# ============================================================
# 5. HISTORICAL PERFORMANCE KPIs (3 months of daily data)
# ============================================================
print("\n--- Creating Historical Performance KPIs ---")

# Performance profiles: (base_score_range, trend_direction, volatility)
PROFILES = {
    banker_a.id: {'label': 'High Performer (Lan)', 'base': 85, 'trend': 2, 'vol': 3},
    banker_b.id: {'label': 'Mid Performer - Improving (Nam)', 'base': 65, 'trend': 5, 'vol': 5},
    banker_c.id: {'label': 'High Performer (Anh)', 'base': 88, 'trend': 1, 'vol': 2},
    banker_d.id: {'label': 'Low Performer - Needs Coaching (Mai)', 'base': 45, 'trend': -2, 'vol': 6},
    banker_e.id: {'label': 'Critical - Urgent Coaching (Tuan)', 'base': 35, 'trend': -3, 'vol': 4},
    banker_f.id: {'label': 'Mid Performer (Khoa)', 'base': 70, 'trend': 3, 'vol': 4},
    banker_g.id: {'label': 'Mid Performer (Huong)', 'base': 72, 'trend': 1, 'vol': 3},
}

# Delete existing demo KPI records to avoid duplicates
existing_kpis = env['bfsi.performance.kpi'].search([
    ('employee_id', 'in', list(PROFILES.keys()))
])
if existing_kpis:
    print(f"  Removing {len(existing_kpis)} existing KPI records...")
    existing_kpis.unlink()

random.seed(42)  # Reproducible

# Create monthly KPIs for last 3 months + current
for month_offset in [3, 2, 1, 0]:
    period_date = today - timedelta(days=month_offset * 30)
    for emp_id, profile in PROFILES.items():
        # Score improves/degrades over time based on trend
        progress = (3 - month_offset) / 3.0  # 0 to 1
        base = profile['base'] + profile['trend'] * progress * 10
        noise = random.uniform(-profile['vol'], profile['vol'])
        score_factor = max(0.2, min(1.0, (base + noise) / 100.0))

        vals = {
            'employee_id': emp_id,
            'period_date': period_date,
            'period_type': 'monthly',
            'dials_per_hour': round(random.uniform(8, 25) * score_factor, 1),
            'total_dials': int(random.uniform(60, 200) * score_factor),
            'connects': int(random.uniform(20, 80) * score_factor),
            'meetings_scheduled': int(random.uniform(8, 30) * score_factor),
            'meetings_conducted': int(random.uniform(5, 25) * score_factor),
            'calls_made': int(random.uniform(100, 300) * score_factor),
            'script_adherence': round(min(100, max(30, base + noise)), 1),
            'objection_handling_score': round(min(100, max(25, base + noise - 5)), 1),
            'need_analysis_quality': round(min(100, max(20, base + noise - 3)), 1),
            'product_knowledge_score': round(min(100, max(30, base + noise + 2)), 1),
            'compliance_score': round(min(100, max(40, base + noise + 5)), 1),
            'customer_satisfaction': round(min(100, max(30, base + noise)), 1),
            'conversions': int(max(1, random.uniform(3, 15) * score_factor)),
            'products_sold': int(max(1, random.uniform(4, 20) * score_factor)),
            'appointments_set': int(max(2, random.uniform(8, 30) * score_factor)),
            'leads_generated': int(max(1, random.uniform(5, 20) * score_factor)),
            'revenue': round(random.uniform(100000000, 800000000) * score_factor, 0),
            'aum': round(random.uniform(500000000, 5000000000) * score_factor, 0),
        }
        env['bfsi.performance.kpi'].create(vals)

    print(f"  Created KPIs for month offset -{month_offset} ({period_date})")

env.cr.commit()
print("  KPI data committed.")

# ============================================================
# 6. COACHING STRATEGIES
# ============================================================
print("\n--- Creating Coaching Strategies ---")

# Strategy for Nam (mid performer, improving) - generated state
strat_nam = get_or_create('bfsi.coaching.strategy', [
    ('banker_id', '=', banker_b.id), ('state', '=', 'generated')
], {
    'banker_id': banker_b.id,
    'manager_id': mgr1.id,
    'branch_id': branch_1.id,
    'state': 'generated',
    'ai_confidence': 85,
    'performance_summary': '<p>Nam is a mid-level performer showing positive improvement trends. Current overall score: 68%. Main areas for development:</p><ul><li>Script adherence: 72% (target: 85%)</li><li>Objection handling: 67% (target: 80%)</li><li>Conversion rate: Below target by 15%</li></ul>',
    'root_cause_analysis': '<p>Analysis indicates:</p><ul><li>Tends to deviate from script when customers raise unexpected questions</li><li>Lacks confidence handling price-related objections</li><li>Good rapport building but struggles with closing techniques</li></ul>',
    'strengths': 'Strong customer rapport\nGood product knowledge\nConsistent attendance and positive attitude\nShowing upward trend in performance',
    'improvement_areas': 'Script adherence needs improvement\nObjection handling confidence\nClosing techniques\nTime management during calls',
    'coaching_themes': 'Sales Fundamentals Reinforcement\nObjection Handling Mastery\nClosing Technique Practice',
    'ai_strategy': '<p><strong>Recommended Coaching Approach:</strong></p><p>Use a supportive coaching style. Nam responds well to positive reinforcement and is showing improvement. Focus on building confidence through role-play practice.</p><p><strong>Key Focus Areas:</strong></p><ol><li>Script practice with scenario variations</li><li>Top 5 objection response techniques</li><li>Assumptive close and trial close methods</li></ol>',
    'session_guide': '1. Start with wins - acknowledge recent rank improvement\n2. Review specific call recordings showing script deviation\n3. Practice the LAER objection handling method\n4. Role-play 3 common customer scenarios\n5. Set specific, measurable weekly goals\n6. Schedule follow-up check-in for next week',
    'opening_questions': 'What do you feel went well in your sales calls this week?\nWhen you think about your most successful sale recently, what made it work?',
    'probing_questions': 'What typically happens when a customer raises a price objection?\nWalk me through your thought process when you deviate from the script.\nWhat would help you feel more confident in closing?',
    'closing_questions': 'What specific actions will you commit to this week?\nHow can I best support you in reaching your targets?',
    'coaching_tips': 'Use call recordings as teaching moments\nCelebrate small wins to build momentum\nSchedule regular role-play practice sessions',
    'roleplay_scenarios': 'Customer says: "I need to think about it" - Practice the Feel, Felt, Found technique\nCustomer says: "Your competitor offers lower rates" - Practice value-based response\nCustomer is ready but hesitant - Practice the assumptive close',
    'learning_recommendations': 'Complete Objection Handling Masterclass (online module)\nReview top performer call recordings from Lan\nPractice script variations with peer buddy',
})

# Strategy for Mai (low performer) - in_use state
strat_mai = get_or_create('bfsi.coaching.strategy', [
    ('banker_id', '=', banker_d.id), ('state', '=', 'in_use')
], {
    'banker_id': banker_d.id,
    'manager_id': mgr1.id,
    'branch_id': branch_1.id,
    'state': 'in_use',
    'ai_confidence': 78,
    'performance_summary': '<p>Mai is underperforming significantly. Current overall score: 45%. Critical areas:</p><ul><li>Script adherence: 55% (target: 85%)</li><li>Conversions: 3 vs target 8</li><li>Revenue: 40% below target</li></ul>',
    'root_cause_analysis': '<p>Root causes identified:</p><ul><li>Inconsistent daily call activity levels</li><li>Weak product knowledge on new loan products</li><li>Poor time management leading to missed follow-ups</li></ul>',
    'strengths': 'Good interpersonal skills\nWilling to learn\nPunctual and reliable',
    'improvement_areas': 'Daily activity consistency\nProduct knowledge gaps\nFollow-up discipline\nScript adherence',
    'coaching_themes': 'Activity Management\nProduct Knowledge Enhancement\nFollow-up Discipline',
    'ai_strategy': '<p><strong>Recommended Approach: Structured Improvement Plan</strong></p><p>Mai needs a highly structured approach with daily check-ins. Focus on building habits around activity levels first, then layer in skill development.</p>',
    'session_guide': '1. Review daily activity log\n2. Identify 3 specific product knowledge gaps\n3. Practice one product pitch\n4. Set daily minimum activity targets\n5. Establish end-of-day reporting habit',
    'opening_questions': 'How has your week been? What challenges have you faced?\nTell me about your best customer interaction this week.',
    'probing_questions': 'What stops you from making more calls?\nWhen a customer asks about loan terms, how confident do you feel?',
    'closing_questions': 'What daily targets feel achievable for you this week?\nWhat support do you need from me?',
})

# Strategy for Tuan (critical) - generated state
strat_tuan = get_or_create('bfsi.coaching.strategy', [
    ('banker_id', '=', banker_e.id), ('state', '=', 'generated')
], {
    'banker_id': banker_e.id,
    'manager_id': mgr1.id,
    'branch_id': branch_1.id,
    'state': 'generated',
    'ai_confidence': 72,
    'performance_summary': '<p>Tuan requires urgent coaching intervention. Current score: 35%. All major KPIs significantly below target.</p>',
    'root_cause_analysis': '<p>Critical gaps in fundamental sales skills. May need re-training on basics before advanced coaching.</p>',
    'strengths': 'Enthusiasm and energy\nGood attendance record',
    'improvement_areas': 'All core sales skills\nCall handling basics\nProduct knowledge\nScript adherence',
    'coaching_themes': 'Back to Basics Sales Training\nCall Handling Fundamentals\nDaily Activity Structure',
    'ai_strategy': '<p><strong>Urgent Intervention Required</strong></p><p>Start with fundamentals. Pair with top performer Lan for shadowing. Daily 15-minute check-ins.</p>',
    'session_guide': '1. Assess baseline understanding of products\n2. Review and practice basic call script\n3. Set up shadowing schedule with top performer\n4. Establish daily minimum of 100 dials\n5. Daily 15-min debrief for first 2 weeks',
})

env.cr.commit()

# ============================================================
# 7. COACHING SESSIONS
# ============================================================
print("\n--- Creating Coaching Sessions ---")

# Delete existing demo sessions
env['hr.coaching.session'].search([
    ('employee_id', 'in', [banker_b.id, banker_d.id, banker_e.id, banker_a.id]),
    ('is_bfsi_session', '=', True)
]).unlink()

# Completed session - Nam (2 weeks ago)
session_nam_1 = env['hr.coaching.session'].create({
    'name': 'Performance Review - Le Hoang Nam',
    'employee_id': banker_b.id, 'coach_id': mgr1.id,
    'session_type': 'hybrid', 'topic': 'performance',
    'session_date': datetime.now() - timedelta(days=14),
    'state': 'completed', 'coaching_strategy_id': strat_nam.id,
    'coached_by_type': 'ai_assisted', 'is_bfsi_session': True,
    'duration': 45, 'outcome': 'good', 'employee_satisfaction': '4',
    'discussion_notes': '<p>Productive session. Nam showed strong engagement and commitment to improving script adherence. Practiced LAER objection handling method with 3 scenarios.</p><p><strong>Key outcomes:</strong></p><ul><li>Committed to 85% script adherence target</li><li>Will practice 3 objection scenarios daily</li><li>Paired with Lan for weekly call review sessions</li></ul>',
    'ai_transcript': json.dumps({
        'messages': [
            {'role': 'user', 'content': 'How can I improve my objection handling when customers say our rates are too high?', 'timestamp': (datetime.now() - timedelta(days=14)).isoformat()},
            {'role': 'assistant', 'content': "Great question, Nam! When customers raise price objections, use the LAER method: Listen fully, Acknowledge their concern, Explore the real need behind it, and Respond with value. For example: 'I understand that cost is important. Many of our most satisfied clients initially had similar concerns. What they found was that our comprehensive service package actually saved them money in the long run. Can I show you how?'", 'timestamp': (datetime.now() - timedelta(days=14)).isoformat()},
            {'role': 'user', 'content': 'That makes sense. What about when they say they need to think about it?', 'timestamp': (datetime.now() - timedelta(days=14)).isoformat()},
            {'role': 'assistant', 'content': "The 'I need to think about it' objection often means they have an unresolved concern. Try the Feel-Felt-Found technique: 'I completely understand - this is an important decision. Many of my clients felt the same way initially. What they found after reviewing the details was that starting sooner actually benefited them because of [specific benefit]. What specific aspects would you like to think about? I can provide more information to help your decision.'", 'timestamp': (datetime.now() - timedelta(days=14)).isoformat()},
        ],
        'updated_at': (datetime.now() - timedelta(days=14)).isoformat()
    })
})
print(f"  Created completed session: {session_nam_1.name}")

# In-progress session - Mai (today)
session_mai = env['hr.coaching.session'].create({
    'name': 'Improvement Plan Review - Vo Thi Mai',
    'employee_id': banker_d.id, 'coach_id': mgr1.id,
    'session_type': 'hybrid', 'topic': 'performance',
    'session_date': datetime.now(),
    'state': 'in_progress', 'coaching_strategy_id': strat_mai.id,
    'coached_by_type': 'ai_assisted', 'is_bfsi_session': True, 'duration': 30,
})
print(f"  Created in-progress session: {session_mai.name}")

# Scheduled session - Tuan (next week)
session_tuan = env['hr.coaching.session'].create({
    'name': 'Urgent Coaching - Hoang Minh Tuan',
    'employee_id': banker_e.id, 'coach_id': mgr1.id,
    'session_type': 'hybrid', 'topic': 'performance',
    'session_date': datetime.now() + timedelta(days=3),
    'state': 'scheduled', 'coaching_strategy_id': strat_tuan.id,
    'coached_by_type': 'ai_assisted', 'is_bfsi_session': True, 'duration': 60,
})
print(f"  Created scheduled session: {session_tuan.name}")

# AI Direct session for Lan (banker self-service)
session_lan_ai = env['hr.coaching.session'].create({
    'name': 'AI Self-Coaching - Tran Thi Lan',
    'employee_id': banker_a.id, 'coach_id': False,
    'session_type': 'ai', 'topic': 'skill_development',
    'session_date': datetime.now() - timedelta(days=3),
    'state': 'completed', 'coached_by_type': 'ai_direct',
    'is_bfsi_session': True, 'duration': 15,
    'outcome': 'excellent', 'employee_satisfaction': '5',
    'ai_transcript': json.dumps({
        'messages': [
            {'role': 'user', 'content': 'I want to improve my cross-selling techniques. Any advice?'},
            {'role': 'assistant', 'content': "Excellent initiative, Lan! Given your strong performance (score 88%), here are advanced cross-selling strategies:\n\n1. **Need-Based Cross-Sell**: During your needs analysis (where you score 85%), identify secondary needs. For example, if a customer opens a savings account, explore their insurance or investment needs.\n\n2. **Timing**: The best time to cross-sell is right after solving a customer problem - they trust you most at that moment.\n\n3. **Bundle Approach**: Present complementary products as a package with combined benefits rather than individual add-ons.\n\nWould you like to practice a specific cross-selling scenario?"},
        ]
    })
})
print(f"  Created AI self-coaching session: {session_lan_ai.name}")

env.cr.commit()

# ============================================================
# 8. ACTION PLANS
# ============================================================
print("\n--- Creating Action Plans ---")

# Delete existing demo action plans
env['bfsi.action.plan'].search([
    ('employee_id', 'in', [banker_b.id, banker_d.id, banker_e.id])
]).unlink()

# Nam - In Progress (35% done)
plan_nam = env['bfsi.action.plan'].create({
    'employee_id': banker_b.id, 'manager_id': mgr1.id,
    'state': 'in_progress',
    'target_date': (today + timedelta(days=14)).strftime('%Y-%m-%d'),
    'employee_notes': 'Focus on script adherence and objection handling to reach 85% target.',
    'coaching_session_id': session_nam_1.id,
})
for seq, item_vals in enumerate([
    {'name': 'Review and practice sales script daily', 'kpi_category': 'behavior',
     'success_criteria': 'Score 85%+ on script adherence for 5 consecutive days',
     'state': 'in_progress', 'progress': 60,
     'target_date': (today + timedelta(days=7)).strftime('%Y-%m-%d')},
    {'name': 'Complete Objection Handling Training Module', 'kpi_category': 'behavior',
     'success_criteria': 'Complete all modules and pass quiz with 80%+',
     'state': 'in_progress', 'progress': 30,
     'target_date': (today + timedelta(days=10)).strftime('%Y-%m-%d')},
    {'name': 'Increase daily call volume to 200+', 'kpi_category': 'input',
     'success_criteria': 'Maintain 200+ calls/day for 2 weeks',
     'state': 'pending', 'progress': 0,
     'target_date': (today + timedelta(days=14)).strftime('%Y-%m-%d')},
    {'name': 'Role-play 3 scenarios with peer buddy Lan', 'kpi_category': 'behavior',
     'success_criteria': 'Complete 3 role-play sessions per week',
     'state': 'pending', 'progress': 0,
     'target_date': (today + timedelta(days=14)).strftime('%Y-%m-%d')},
], 1):
    item_vals['action_plan_id'] = plan_nam.id
    item_vals['sequence'] = seq * 10
    env['bfsi.action.plan.item'].create(item_vals)
print(f"  Created action plan: {plan_nam.name}")

# Mai - Committed (10% done)
plan_mai = env['bfsi.action.plan'].create({
    'employee_id': banker_d.id, 'manager_id': mgr1.id,
    'state': 'committed',
    'target_date': (today + timedelta(days=30)).strftime('%Y-%m-%d'),
    'employee_notes': 'Comprehensive improvement plan. Daily check-ins required.',
})
for seq, item_vals in enumerate([
    {'name': 'Achieve minimum 120 dials per day', 'kpi_category': 'input',
     'success_criteria': '120+ dials/day for 5 consecutive days',
     'state': 'pending', 'progress': 10,
     'target_date': (today + timedelta(days=7)).strftime('%Y-%m-%d')},
    {'name': 'Complete product knowledge quiz on all loan products', 'kpi_category': 'behavior',
     'success_criteria': 'Pass quiz with 90%+ score',
     'state': 'pending', 'progress': 0,
     'target_date': (today + timedelta(days=14)).strftime('%Y-%m-%d')},
    {'name': 'Follow up with all pending leads within 24 hours', 'kpi_category': 'behavior',
     'success_criteria': '100% follow-up rate for 2 weeks',
     'state': 'pending', 'progress': 0,
     'target_date': (today + timedelta(days=21)).strftime('%Y-%m-%d')},
], 1):
    item_vals['action_plan_id'] = plan_mai.id
    item_vals['sequence'] = seq * 10
    env['bfsi.action.plan.item'].create(item_vals)
print(f"  Created action plan: {plan_mai.name}")

# Tuan - Committed (5% done)
plan_tuan = env['bfsi.action.plan'].create({
    'employee_id': banker_e.id, 'manager_id': mgr1.id,
    'state': 'committed',
    'target_date': (today + timedelta(days=21)).strftime('%Y-%m-%d'),
    'employee_notes': 'Urgent intervention required. Back-to-basics approach.',
})
for seq, item_vals in enumerate([
    {'name': 'Shadow top performer Lan for 3 full days', 'kpi_category': 'behavior',
     'success_criteria': 'Complete 3 shadowing days and submit observation notes',
     'state': 'pending', 'progress': 0,
     'target_date': (today + timedelta(days=7)).strftime('%Y-%m-%d')},
    {'name': 'Memorize and practice basic call script', 'kpi_category': 'behavior',
     'success_criteria': 'Deliver script from memory with 80%+ accuracy',
     'state': 'pending', 'progress': 5,
     'target_date': (today + timedelta(days=10)).strftime('%Y-%m-%d')},
], 1):
    item_vals['action_plan_id'] = plan_tuan.id
    item_vals['sequence'] = seq * 10
    env['bfsi.action.plan.item'].create(item_vals)
print(f"  Created action plan: {plan_tuan.name}")

env.cr.commit()

# ============================================================
# 9. AI PROVIDER CONFIGURATION
# ============================================================
print("\n--- Checking AI Provider Config ---")
ai_config = env['hr.ai.provider.config'].search([
    ('company_id', '=', env.company.id)], limit=1)
if ai_config:
    print(f"  AI Provider already configured: {ai_config.provider}")
else:
    ai_config = env['hr.ai.provider.config'].create({
        'company_id': env.company.id,
        'provider': 'openai',
        'model_name': 'gpt-4o-mini',
        'timeout': 60,
        'is_active': True,
    })
    print("  Created AI Provider config (OpenAI gpt-4o-mini)")

env.cr.commit()

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("DEMO DATA LOADED SUCCESSFULLY!")
print("=" * 60)
print(f"""
DATA CREATED:
  Regions:     {env['bfsi.region'].search_count([])}
  Branches:    {env['bfsi.branch'].search_count([])}
  Employees:   {env['hr.employee'].search_count([('banker_type', '!=', False)])} bankers
  KPI Records: {env['bfsi.performance.kpi'].search_count([])} records
  Strategies:  {env['bfsi.coaching.strategy'].search_count([])}
  Sessions:    {env['hr.coaching.session'].search_count([('is_bfsi_session', '=', True)])}
  Action Plans:{env['bfsi.action.plan'].search_count([])}

DEMO USERS (password: demo123):
  Branch Manager:  minh.nv (District 1 Branch)
  Branch Manager:  ha.dt   (District 7 Branch)
  RM (Top):        lan.tt  (High performer)
  RM (Mid):        nam.lh  (Improving - good coaching demo)
  Wealth Mgr:      anh.pd  (High performer)
  Loan Officer:    mai.vt  (Low performer - needs coaching)
  Telesales:       tuan.hm (Critical - urgent coaching)
  RM:              khoa.bv (District 7)
  Insurance:       huong.nt(District 7)
  Regional Mgr:    bao.tq  (Full oversight)
""")
print("Script completed. You can now exit the shell.")
