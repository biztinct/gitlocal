# AI Performance Coaching - Demo Guide

## 🔧 Pre-Demo Setup

### 1. Load Demo Data
```bash
cat addons/hr_development_ai/scripts/load_demo_data.py | python3 odoo-bin shell -d <your_database>
```

### 2. Configure AI Provider
- Go to **AI Performance Coaching → Configuration → AI Provider**
- Set provider to **OpenAI** and enter API key (or use **Ollama** if local LLM available)
- Click **Test Connection** to verify

### 3. Demo Login Accounts
| Login | Password | Role | Branch | Demo Scenario |
|-------|----------|------|--------|---------------|
| `minh.nv` | demo123 | Branch Manager | District 1 | Main demo persona |
| `lan.tt` | demo123 | RM (Banker) | District 1 | Top performer |
| `nam.lh` | demo123 | RM (Banker) | District 1 | Mid performer, improving |
| `mai.vt` | demo123 | Loan Officer | District 1 | Low performer |
| `tuan.hm` | demo123 | Telesales | District 1 | Critical, needs coaching |
| `ha.dt` | demo123 | Branch Manager | District 7 | Second branch |
| `bao.tq` | demo123 | Regional Manager | All | Full oversight |

---

## 📋 Demo Flow (Recommended: ~45 minutes)

### PHASE 1: Analytics & Identification (10 min)
_Login as **minh.nv** (Branch Manager)_

1. **Manager Dashboard** → AI Performance Coaching → Dashboard → Manager Dashboard
   - Show team ranking table with rank movement indicators (↑ ↓)
   - Highlight the "Needs Coaching" badge count (Mai & Tuan are flagged)
   - Point out Avg Team Score, Total Sessions, Action Plan Completion metrics
   - Demo sorting/filtering by priority (Critical, High, Medium, Low)

2. **Performance KPIs** → Performance → Performance KPIs
   - Open any banker's KPI record to show Input/Behavior/Output/Outcome metrics
   - Show **Overall Score** computation and **Coaching Priority** auto-classification
   - Show **Rank Movement** (↑3 means improved 3 positions)
   - Click **Generate AI Analysis** button on a low performer's KPI

3. **Branch View** → Organization → Branches
   - Open District 1 Branch form → shows aggregate metrics
   - Show computed fields: Avg Score, Needs Coaching Count, Bankers Coached

### PHASE 2: Pre-Coaching Preparation (10 min)
_Still logged as **minh.nv**_

4. **AI Strategy Generation** → Coaching → Coaching Strategies
   - Open Nam's strategy (state: Generated) → walk through all tabs:
     - **Performance Analysis**: AI-generated summary, root causes, strengths, gaps
     - **Coaching Strategy**: Themes, AI strategy, proposed plan
     - **Session Guide**: Step-by-step guide, opening/probing/closing questions
     - **Roleplay Scenarios**: Practice scenarios for the manager
     - **Learning Recommendations**: Suggested learning content
   - **LIVE DEMO**: Create a NEW strategy for Tuan:
     - Go to Coaching Strategies → CreateAlso the coaching sessions do not appear here although I started the coaching session by clicking on the button below
     - Select banker "Hoang Minh Tuan"
     - Click **"Generate AI Strategy"** → watch AI populate all fields

5. **Coaching Roleplay Practice**
   - On Nam's strategy, click **"Practice Roleplay"** button
   - Type a coaching message → AI responds as the banker would
   - Show how the manager can practice before the real session

### PHASE 3: Execution & Support (10 min)

6. **Guided Coaching Session**
   - From Nam's strategy, click **"Start Coaching Session"**
   - Session form opens with strategy pre-linked
   - Click **"Open AI Chat"** or use the chat widget on the form
   - Type coaching questions → AI provides contextual responses with KPI data
   - Show AI suggesting powerful questions and next steps
   - In the header buttons:
     - Click **"Capture KPI Context"** → snapshots current performance data for AI context
     - Click **"Generate Action Items (AI)"** → AI analyzes the conversation and creates action plan items automatically
     - Click **"Create Action Plan"** → creates or opens an action plan linked to this session

7. **AI Coach Panel (Persistent Sidebar)**
   - Notice the AI Coach panel on the right side (visible to BFSI Banker/Manager users)
   - Shows contextual greeting with KPI summary (score, rank, conversions, meetings)
   - Quick Actions are always visible:
     - **Banker view**: Check KPIs, Action Plan, Get Coaching, Help Me Handle
     - **Manager view**: Team Overview, Needs Coaching, AI Strategy, Practice
   - Type a message for contextual coaching based on actual performance data

### PHASE 4: Banker Self-Service (10 min)
_Login as **nam.lh** (Banker)_

8. **My Performance** → Dashboard → My Performance
   - Banker sees own KPI records and trends

9. **AI Coach Panel (Banker View)**
   - Sidebar shows personalized greeting with score
   - Quick actions available: Check KPIs, Action Plan Review, Get Coaching, Difficult Scenario
   - Type: "I need help handling a difficult customer who wants a lower interest rate"
   - AI provides contextual coaching based on Nam's actual performance data

10. **Action Plan Management** → Coaching → My Action Plans
    - Show Nam's action plan with progress bars
    - Click **"Report Progress"** → update completion percentage
    - Show how items can be marked as Complete/Blocked

### PHASE 5: Monitoring & Optimization (5 min)
_Login back as **minh.nv**_

11. **Action Plan Tracking**
    - Go to Coaching → Action Plans
    - Show all plans across team with status/progress
    - Open Mai's plan → show committed items, deadlines

12. **Coaching Session History**
    - Show completed sessions with AI transcripts
    - Show different states: Completed, In Progress, Scheduled

---

## 🎯 Key Talking Points

### For the CEO/C-Level
- "AI reduces coaching preparation time by 80%"
- "Every coaching session is data-driven, not gut-feel"
- "Continuous feedback loop: Analytics → Coaching → Action → Results"
- "24/7 AI support for bankers when manager is unavailable"

### For Branch Managers
- "AI identifies WHO needs coaching and WHY automatically"
- "Strategy generator gives you a complete coaching playbook"
- "Roleplay lets you practice before the real conversation"
- "Track action plan completion to measure coaching ROI"

### For IT/Technical
- "Supports multiple AI providers: OpenAI, Ollama (local), Mistral"
- "Built on Odoo 19 CE - no additional infrastructure needed"
- "Data stays private - can run entirely on-premise with Ollama"
- "Role-based access: Banker vs Branch Manager vs Regional Manager"

---

## ⚠️ Demo Tips

1. **AI Response Time**: If using OpenAI, responses take 2-3 seconds. Mention "AI is analyzing the data..." while waiting
2. **Fallback**: If AI is unavailable, the system shows intelligent fallback responses with KPI data
3. **Data Freshness**: KPI dates are relative to today. Every re-run of the script creates fresh data
4. **Show Both Personas**: Always demo BOTH the Branch Manager AND the Banker view
5. **The WOW Moment**: The "Generate AI Strategy" button filling all tabs automatically is the biggest wow factor
6. **Session State**: Coaching session buttons (Capture KPI, Generate Action Items, Create Action Plan) only appear when session is In Progress or Completed
7. **AI Coach Panel**: Quick Actions are always visible. Panel requires BFSI Banker or Branch Manager group access
