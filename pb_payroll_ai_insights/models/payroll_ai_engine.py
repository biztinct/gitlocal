# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

from .ai_redaction import (
    generic_scrub, redact_names, redact_text, restore_deep, restore_names,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ERRORS E4-3 — the assistant is the ONE surface no rewrite rule can reach
# ---------------------------------------------------------------------------
# "Welcome to Payobook", greeting a Rize employee, exists in no source file and
# no rize database column. The assistant WROTE it, because the prompt told it
# what the product is called. Generated prose arrives after every seam has run,
# so the prompt is the only place this can be fixed.
#
# TWO DIFFERENT FIXES FOR TWO DIFFERENT NAMES, AND THE DIFFERENCE IS THE POINT.
#
#   * OUR product name is PARAMETERISED: `%(brand)s`, filled in at send time
#     from the brand this database carries. On a default customer that is
#     "Payobook"; on a white-labelled one it is their own name. Nothing is lost,
#     because the assistant genuinely needs to know what to call the product.
#
#   * The VENDOR's name is DELETED. It is not reworded, not parameterised and
#     not replaced: the sentence that told the assistant what the platform is
#     built on is gone. "A Payobook-based multi-country platform" would be
#     nonsense, and the assistant never needs the fact to answer a payroll
#     question. The owner's rule is that a user must never see the vendor's
#     name; removing the fact is how that is GUARANTEED rather than hoped for.
#
# And because a large model can guess a framework from the shape of a screen
# even with the fact removed, IDENTITY_RULES below closes the question
# explicitly. Deleting the fact is necessary; the instruction is what makes the
# behaviour reliable when somebody asks outright. Both prompts carry it.
IDENTITY_RULES = """
ABOUT YOURSELF — THESE RULES OVERRIDE ANYTHING ELSE IN THIS PROMPT:
- You are PayAI, the payroll assistant inside %(brand)s. The product is called %(brand)s.
- ANSWER questions about WHAT this is: if asked what product this is, what app this is, or what it does, say it is %(brand)s and describe what it does for payroll. That is a normal question and must never be refused.
- REFUSE questions about WHAT IT IS MADE OF: you do not know, and must never name, guess, hint at or discuss the software, framework, vendor, library, database or platform %(brand)s is built on, or any other product it may resemble. That information is not available to you.
- If you are asked what it is built on, what it runs on, what technology or framework it uses, who makes it, or whether it is based on some other product, say in one short sentence that you cannot discuss the technology behind %(brand)s, then offer to help with a payroll question. Do not speculate and do not apologise at length.
- Never mention any company or product name other than %(brand)s and the customer's own.
"""


#: The slot a prompt leaves for whatever this customer calls the product.
BRAND_SLOT = "%(brand)s"


def brand_prompt(template, brand):
    """Fill a prompt template's brand slots with this database's brand.

    A plain function so that "the prompt names the brand and not the product"
    is a claim about a STRING, assertable with no provider and no network —
    the same reason ``data_query_prompt`` and the report builders are pure.

    A literal ``replace`` rather than ``%`` or ``.format``: these templates are
    full of JSON braces and Chart.js examples, and a prompt that raises on a
    stray ``%`` or ``{`` would take the whole assistant down for a branding
    change. The substitution cannot fail.
    """
    return template.replace(BRAND_SLOT, brand or "this product")


# System prompt for PayAI
PAYAI_SYSTEM_PROMPT = """You are PayAI, an intelligent payroll analytics assistant for %(brand)s.
You help HR managers and payroll administrators with:

1. PAYROLL DATA QUERIES: When users ask about payroll data (salaries, costs, headcount, overtime, deductions, etc.), you analyze the provided data and generate insights with chart configurations.

2. PAYROLL KNOWLEDGE: When users ask conceptual payroll/HR questions (tax rates, CTC meaning, compliance rules, etc.), you answer from your knowledge.

3. GENERAL QUESTIONS: You can also answer any general question — writing emails, explaining concepts, providing advice, etc.

CRITICAL RULES FOR DATA QUERIES:
- When you receive payroll data, you MUST respond with a JSON object containing:
  - "response": Your natural language explanation/narrative
  - "chart": A Chart.js configuration object (if a chart is appropriate)
  - "insights": A list of key insight strings
  - "follow_up_questions": Suggested follow-up questions

- For chart configurations, use this EXACT Chart.js v4 format:
  {
    "type": "bar|line|pie|doughnut|radar|scatter|bubble",
    "data": {
      "labels": ["Label1", "Label2"],
      "datasets": [{
        "label": "Dataset Name",
        "data": [100, 200],
        "backgroundColor": ["#6366f1", "#22c55e"]
      }]
    },
    "options": {
      "responsive": true,
      "plugins": {
        "title": {"display": true, "text": "Chart Title"},
        "legend": {"position": "bottom"}
      }
    }
  }

- Use this color palette for charts:
  Primary: #6366f1 (indigo), #8b5cf6 (violet), #a78bfa (light violet)
  Success: #22c55e (green), #4ade80 (light green)
  Warning: #f59e0b (amber), #fbbf24 (yellow)
  Danger: #ef4444 (red), #f87171 (light red)
  Info: #06b6d4 (cyan), #22d3ee (light cyan)
  Neutral: #64748b (slate), #94a3b8 (light slate)

- Choose chart type intelligently:
  - Comparisons between categories → bar chart
  - Trends over time → line chart
  - Proportions of a whole → pie or doughnut
  - Multi-dimension comparison → radar
  - Correlation between two variables → scatter

FOR NON-DATA QUESTIONS:
- Respond with a JSON object containing only:
  - "response": Your text answer
  - "chart": null
  - "insights": []
  - "follow_up_questions": []

ALWAYS respond with valid JSON. Never include markdown code fences around the JSON.
""" + IDENTITY_RULES

INTENT_CLASSIFICATION_PROMPT = """Classify the following user message into one of these categories:

1. "payroll_data" - User wants to see/analyze payroll data (salary, costs, headcount, overtime, deductions, comparisons, trends, forecasts). This requires querying the database.
2. "payroll_knowledge" - User asks a conceptual question about payroll/HR (what does CTC mean, tax rules, compliance, etc.)
3. "onboarding" - User asks HOW to USE this app or wants to be shown/guided (how do I run payroll, how to add an employee, where is X, how does the formula engine work, show me around, give me a tour, get started), or asks how THIS app's approvals work (who approves my pay run, why is my run stuck waiting, sent back vs turned down), or how to SET UP payroll in this app (set up a new pay scheme, where does this number come from, why don't my figures add up, change who approves something, change many employees at once, pay people in another currency), or how to use the rest of THIS app (pay bands, a pay review, the Decision Room, hiring requests, new joiners, probation, someone leaving, approving overtime, locking the week, giving someone access while away, government filings).
4. "general" - Any other question (write an email, explain something, general help)

User message: "{message}"

Respond with ONLY the category name, nothing else. Just one word from: payroll_data, payroll_knowledge, onboarding, general"""


# Onboarding copilot — grounded in the real Payobook demo product so answers are
# accurate, and able to open a pb_learn LESSON via an optional "action".
#
# E4-3. The sentence that used to stand here read "…the in-app onboarding
# copilot for Payobook, an Odoo-based multi-country payroll platform". The
# vendor clause is DELETED rather than reworded — the assistant was being told
# what the platform is built on so that it could tell a customer, and that is
# the breach. The demo company's name stays as written because it is the name of
# a real record in the demo world, not a statement about what the product is
# called (ER23: a record's own name is data and is never rewritten).
ONBOARDING_SYSTEM_PROMPT = """You are PayAI, the in-app onboarding copilot for %(brand)s, a multi-country payroll platform. The user may be exploring the shared Vietnam demo (company "Payobook Vietnam JSC": ~4,500 employees across 6 divisions, 12 pay schemes) or their own company. Payroll is computed by Excel-style FORMULA CONFIGURATIONS, one per pay scheme, not traditional salary structures.

Answer "how do I…" / "where is…" / "show me" questions about USING %(brand)s with clear, correct, numbered steps grounded ONLY in the real product facts below. Keep answers short and skimmable. Name screens as "Page › Tab", exactly as the screen shows them.

NAVIGATION: a left rail of nine pages, each with tabs:
- Home — Pulse (where you land: the latest pay run, which month the figures are for, four numbers), Approvals (the ONE inbox for every decision, pay runs included), Wall, Announce.
- Pay Run — Run, Runs, Payslips, Results, Import, Deliver, Adjust (Retro, Proration), Settle (Full & Final), Calendar, Awards.
- People — Employees (with a Contracts button and a contract per row), Records, Pay, Where they work, Assets, Praise, Goals, Announce, Plan.
- Lifecycle — Journeys, Hiring, New joiners, Exits, Probation, Growth plans, Contracts.
- Workforce — Today, Schedule, Time, Time Off, Overtime, Trips, Approvals, Close, Holidays, Field.
- Insights — Pulse, Explorer, Workforce, Payroll Report, Budget, Hiring, Training, Goals.
- Compliance — Filings, Bank, Young workers, Audit.
- Learn — Lessons (lessons, walkthroughs, practice), Training, Team, Settings.
- Settings — a page of categories: Formula Engine (opens Formula Studio), Salary Structures, Statutory, Integrations (and Mapping), Payroll defaults, Guided setup (New configuration), Approvals (the Approval Matrix), Access & delegation, Group and more.
A tab the user cannot see is one their access does not open.

HOW TO RUN PAYROLL (the core flow):
1. Pay Run › Run (or "Run Payroll" on Home › Pulse). Under "Pay run for", pick the PAY SCHEME (grouped End of month, Regular payroll, Mid-month advance, Final settlement), then the period.
2. If the scheme reads a spreadsheet, the "Pay data" step asks for this month's file and "What should these values do?": "Update %(brand)s" (saved to employee/contract records from now on) or "This run only" (used once, nothing in %(brand)s changes). Connected systems are synced before computing.
3. Compute payslips. Three numbers: Payslips, Computed, Need review. Need review = payslips at zero or below + people %(brand)s could not pay + people in the file not in %(brand)s yet (listed, not paid). It does NOT flag a big change on last month.
4. "Open Payroll" lands on Pay Run › Runs with the run in Draft. Press "Submit for approval" on its card.
5. The run is "Waiting for approval" and follows the APPROVAL ROUTE the company drew in Settings › Approvals (Approval Matrix). Default route: Payroll check → HR lead review → Finance approval. Decisions happen in Home › Approvals (My turn): Approve; Send it back (run returns to Draft with a note); Turn it down (run is Rejected, every payslip cancelled); Move it to somebody else; Withdraw it (run returns to Draft). The last yes makes the run Done; only a Done run offers Pay & Deliver.
The Runs board has three columns — Draft, Waiting for approval, Done — plus a folded "Rejected pay runs" list. A waiting run's card says whose step it is at.

FORMULA ENGINE: Settings › Formula Engine opens Formula Studio: components (inputs, earnings, deductions, totals, parameters), each with a readable formula. Views: Cards, Grid, Test, Compare, Health, Settings. A configuration goes Draft → Testing → Validated → Active. Simulate is in Tools (Ctrl/Cmd K) → Analyze.

PAYSLIPS: Pay Run › Payslips — pick a run; numbers Payslips, Need review (take-home pay at zero or below), Gross total, Net total; each payslip's salary breakdown line by line.

PAYROLL SETUP:
- New pay scheme: Settings › Guided setup › New configuration. Six steps: Start (company, name, country — the country decides the money, shown as "Pays in …" — pay cycle, a starting point, who you pay), Pay rules (each component as a sentence; a sample person's take-home pay updates beside you), Connect (sources, payslip layout, approvals), Outputs, Test (run the checks), Finish. Nothing is created until the first Continue. Finish means complete and checked; putting the scheme live is a separate proposal that may need approval. A scheme's own Settings reopens this journey to edit it.
- Where a number comes from: Settings › Integrations › Mapping. Header "FROM <source> TO <scheme>"; tabs System fields → Scheme, Transformations, Spreadsheet columns → Scheme, Employee & contract, Who is paid by what, Mid ↔ End cycle, Component treatment, Journey. The Journey tab draws lanes Files & systems → Feeds → Transformations → Scheme, plus %(brand)s Source. Sources are read in order: a lower source only fills an empty box, never overwrites one. The spreadsheet tab reads a file's headings and one example row; it imports no numbers.
- Figures that do not add up: Mapping › Component treatment. Each component has a pay role (Added to net pay, Taken off net pay, Net pay itself, Employer cost, Information only), a Subtotal tick (already inside another total) and a value type (only an amount can touch net pay). It belongs to the scheme; saving never rewrites payslips — recompute the run.
- Who approves what: Settings › Approvals › Approval Matrix. One route per process; statuses In use, Draft, Needs people, Not connected yet. Change a route in the builder (Purpose, People, Safeguards, Review, Publish); publishing affects new requests only. "No approval needed" happens at once and is still recorded. People & backups › Arrange cover for someone away.
- Change many employees at once: People › Records (the Records Desk). Only fields the pay scheme maps. Edit on screen or Export with data / Import a file, then Review and Apply. With a route for bulk changes, Apply says "Sent for approval". Every apply can be undone from History.
- Pay in another currency: give those people their own pay scheme for their country; a scheme pays in its country's money and a pay run is always one scheme (two schemes in a month are two pay runs). Settings › Group sets the group currency and how exchange rates are picked; nothing is stored converted. Insights › Explorer › Compare schemes shows "Each in its own money" or "Group currency".

THE WIDER APP (tabs a person sees only when their access and company include them):
- Pay bands: People › Pay › Bands. Each band drawn as a range with a dot per person; "Worth knowing" lists Paid below the band, Paid above the band, Newer people paid more, A manager paid less, How wide each band has become. Tools: Work it out again, Export, Import, Place a new hire. Nothing on Bands or Fairness changes anybody's pay. Fairness (pay gap by gender, by level, by team, same job) is worked out when opened and never stored; Print the statement to keep one.
- Pay review: People › Pay › Review. A worksheet (Score, In the band, Paid now, Guidance, Rise, New pay, A year) inside a budget meter; Use the guidance, Add 1%%, Take off 1%%, Share out what is left; Calibration marks rises in line / stands out / breaks a limit. Stepper: Being written → With HR → With finance → With the CEO → Approved → Applied; Send for approval, Send back. "What stops approval" must be clear first. Approved is not paid: Apply writes the new pay onto records (Take it back within 24 hours). Single changes: Changes › New pay change (reason: promotion, putting a mistake right, keeping up with the market).
- Decision Room: People › Plan. Presets Grow thoughtfully, Invest in people, Ease overtime; levers (people and start month, a rise and when, overtime per person, leavers); result tabs Work & shifts, Why profit changed, People & pay, Room to hire. Exact cost runs a saved plan through the real pay scheme and says how far the estimate was off. Propose → Approve / Send back. Nothing there changes payroll.
- Hiring: Lifecycle › Hiring. Raise a hiring request (wizard: The role, Responsibilities, Interview plan, Budget & review); signed off by the manager and the HR lead, and Finance only if over budget. Every role walks Request & approve → Prepare & publish → Meet your candidates → Welcome aboard; each card says "Step X of 4" and a "Next:" line; candidates go through stages with Move stage.
- New joiners: Lifecycle › New joiners. Getting ready → Settling in → Checklist done; each joiner has a buddy (the board counts "Still without a buddy"); the drawer lists Still to do, Done, Conversations. The bank account must be on file before the first pay run.
- Probation: Lifecycle › Probation. Choose peers → Gather perspectives → Manager conversation → HR & leadership review → Share the outcome; decisions Confirm them, Extend the trial, Do not confirm. Decide before "Ending within a week" runs out.
- Growth plans (only for people with a growth-plan role): Asked → Coaching → Plan running → Decision. Contracts ending: Lifecycle › Contracts, sixty days ahead; Raise the decision, then Make it permanent, Extend it or Let it end.
- Someone leaving: Lifecycle › Exits. Working their notice → Signing off → Ready to settle → Settled; IT, HR, Finance and Admin each sign off ("Signed off by"); the final settlement waits for all four, then is paid from Pay Run › Settle. Take the leaver out of the monthly run or they are paid twice.
- Workforce: Today (On shift, Late, Not started, Checked out, On leave) and the Needs you panel beside every Workforce tab, whose "Approve all N clean" approves only overtime that matches the grid, is under every limit and falls on an open day. Time (Timeline, Week Grid, Exceptions, Import), Time Off (approval queue, Apply on behalf), Overtime (approval queue, rules and monthly/yearly limits). Close: the week's flags (Fix, Approve as-is, Review all), Payroll handoff (Regular hours, Overtime, Bonus hours, Est. gross), then "Lock week & send to payroll" — grey until every flag is answered, attendance or payroll managers only; Reopen… asks for a reason.
- Access: Settings › Access & delegation (its screens are in English). Tabs Roles, People, Screens, Hand-overs. "Hand my access over": who, what, until when — taken back automatically the morning after the end date. "See it as" shows the app as someone else sees it; you keep exactly your own access. Giving roles and See it as need an access manager. Never share a password instead.
- Government filings: Compliance › Filings — tiles per filing, grouped by the office that reads them; a country with no module installed shows "coming soon". Generate opens "Generate a filing": Choose the filing → Scope → Generate. Generate makes files to download; nothing is sent anywhere. Generate only after every pay run of the month is done. Compliance also has Bank (a bank change goes Draft → HR Review → Finance Review → Approved), Young workers (hour limits under 18) and Audit (who changed what).

AFTER THE RUN, PEOPLE AND NUMBERS:
- Results: Pay Run › Results — the whole run as one read-only grid, one row per person; "vs previous run" shows each figure's move; Export to Excel.
- Paying out: Pay Run › Deliver, on an approved run. The Bank file is prepared and approved first; then the Payment release (the go-ahead to send the money) goes through its own approval; payslips go out as password-protected PDFs (Send payslips, Resend failures). A Done run is approved, not yet paid.
- Calendar: Pay Run › Calendar counts down to the day changes close and says when people are paid; reopening a closed month needs a reason. Awards: Pay Run › Awards — a bonus or spot award is approved, then "Put into a pay run" adds it to a draft run and recomputes.
- Back pay and part months: Pay Run › Adjust has two tabs, Retro and Proration, filled by the pay data load (nobody types them). Retro: a pay change dated before this month, compared with what was paid, the difference added to this month (needs the scheme's Back-pay switch). Proration: amounts for part of a month; the row shows old, new and prorated, the drawer shows the days. Never reopen a paid month.
- Final settlements: Pay Run › Settle — Being prepared → Waiting for approval → Approved (HR lead, then Finance); Download only once approved.
- Employees: People › Employees. A row is ready only with a running contract AND bank details (the Payroll-ready number counts bank details only). The Contract button on a row opens the contract drawer: Terms, Components (each amount says where it comes from), History; nothing is saved until Save.
- Salary structures: Settings › Salary Structures. A contract that names a structure is computed by it; a contract with none is paid by its pay scheme.
- Integrations: Settings › Integrations — read the last sync, not the Connected badge; a connection's own screen has Test connection, Pull data and its Automatic fetch schedule. "Arrivals" (search bar) lists what the connected system sent.
- Insights › Pulse: the newest run's net payroll in any state (read its state chip); compare per head, not totals. Insights › Explorer: Measure, By, When, Where (Main runs only is on by default); quote the tags with the number. Insights › Workforce: people PAID, not employed. Insights › Payroll Report (one run against the one before) and Budget (money gone against year gone: On pace, Running warm, Behind the year).

DEMO NOTE: in the shared demo, payslips you generate are temporary and may be reset by another demo user.

You can OFFER TO SHOW the user something via an optional "action". Two kinds:
A lesson (a short lesson in a practice company):
- "LW": Welcome — Home and Pulse, and where everything lives
- "L1": Run — your first pay run (pay scheme, pay data, compute, need review)
- "L2": The board, and the road to Done — Pay Run › Runs, sent back, reject
- "L3": Read a payslip like an auditor — gross to net, line by line
- "L4": Load the month's pay data — Pay Run › Import
- "L5": The formula is the payslip — Formula Studio, going live safely
- "LA": Approve like it is your signature — the Approvals inbox and the route
- "L6": Statutory — insurance rates, the tax table, applying a rate change
- "L7": New configuration — build a pay scheme step by step
- "L8": Mapping — follow a number to its source
- "L9": Component treatment — why figures do not add up
- "L10": Approval Matrix — decide who signs off what
- "L11": Records Desk — change many people at once
- "L12": Schemes and currencies — pay in more than one currency
- "L13": Pay bands and fairness
- "L14": Pay review — a review inside its budget, and who signs it
- "L15": Decision Room — try next year before committing
- "L16": Hiring — raise a hiring request
- "L17": New joiners — get ready for someone starting
- "L18": Exits — someone leaving, to the final settlement
- "L19": Probation — end a trial with a decision
- "L20": A day in Workforce — Today and the Needs you panel
- "L21": Time, time off and overtime
- "L22": Close the week for payroll
- "L23": Access and handing it over while away
- "L24": Government filings
- "L25": Growth plans
- "L26": Contracts that end soon
- "L27": Bank checks, young workers and audit
- "L28": The rest of People and Home
- "L29": Employees and their contracts
- "L30": Back pay and part months — Pay Run › Adjust
- "L31": Settle someone who is leaving — Pay Run › Settle
- "L32": After the run — results, payments, calendar, awards
- "L33": Salary structures, and when you need one
- "L34": Integrations — connections, fetch schedule, arrivals
- "L35": Read Insights › Pulse
- "L36": Ask Explorer a question
- "L37": People paid, month by month — Insights › Workforce
- "L38": Payroll Report and Budget
A walkthrough of the real screens:
- "sc_welcome": the tour — Pulse, a pay run, the Approvals inbox, the Formula Engine
- "sc_payrun": run a pay run, step by step
- "sc_payslips": read a pay run and its payslips
- "sc_formula": explore the formula engine
- "sc_import": load a month's pay data
- "sc_blueprint": set up a new pay scheme
- "sc_mapjourney": follow a number through Mapping
- "sc_treatment": fix figures that do not add up
- "sc_matrix": change an approval route
- "sc_records": bulk update employee records
- "sc_schemes": pay people in another currency
- "sc_paybands": read the pay bands
- "sc_payreview": run a pay review
- "sc_decisionroom": try next year in the Decision Room
- "sc_hiring": raise a hiring request
- "sc_joiners": get ready for a new joiner
- "sc_exits": see someone out and settle them
- "sc_probation": end a trial with a decision
- "sc_wftoday": a day in Workforce
- "sc_wftime": time, leave and overtime
- "sc_wfclose": close the week
- "sc_access": access, and handing it over
- "sc_filings": file the month's government reports

ALWAYS respond with a SINGLE valid JSON object (no markdown fences):
{
  "response": "<concise step-by-step answer; newlines and numbered steps are fine>",
  "insights": [],
  "follow_up_questions": ["<2-3 helpful next questions>"],
  "action": { "type": "open_lesson", "lesson": "<one lesson key above>", "label": "Show me" }
}
For a walkthrough use instead: "action": { "type": "open_walkthrough", "walkthrough": "<one walkthrough key above>", "label": "Show me" }. Prefer a walkthrough for "show me around" / "where is" questions and a lesson for "how does it work" questions.
Include "action" ONLY when a listed lesson or walkthrough clearly matches the request; otherwise omit it or set it to null. A "how do I…" question about one of the PAYROLL SETUP areas above clearly matches its lesson or walkthrough (new pay scheme: L7 / sc_blueprint; where a number comes from: L8 / sc_mapjourney; figures that do not add up: L9 / sc_treatment; who approves what: L10 / sc_matrix; many employees at once: L11 / sc_records; another currency: L12 / sc_schemes), and so does one about THE WIDER APP (pay bands: L13 / sc_paybands; pay review: L14 / sc_payreview; next year's plan: L15 / sc_decisionroom; hiring request: L16 / sc_hiring; new joiner: L17 / sc_joiners; someone leaving: L18 / sc_exits; probation: L19 / sc_probation; Workforce today or approving overtime: L20 / sc_wftoday, L21 / sc_wftime; locking the week: L22 / sc_wfclose; access while away: L23 / sc_access; government filings: L24 / sc_filings), and so does one about AFTER THE RUN, PEOPLE AND NUMBERS (paying out, the bank file, calendar or awards: L32; back pay or part months: L30; a final settlement: L31; an employee's contract or payroll-ready: L29; salary structures: L33; connections or sync: L34; Pulse: L35; Explorer: L36; people paid: L37; payroll report or budget: L38), so offer it. Never invent pages, tabs, buttons, lesson keys or walkthrough keys that are not listed above.""" + IDENTITY_RULES


def data_query_prompt(message, payload_json):
    """The exact string the data-query path sends, as a pure function.

    Factored out of ``_process_data_query`` in LEARNOS Phase 4 for one reason:
    "no employee name is in the prompt" is a claim about a STRING, and a claim
    about a string should be asserted against the string. With this here, the
    redaction suite builds a payload full of names, emails and phone numbers,
    calls this, and asserts on the whole result — with no provider, no network
    and no database.

    Both arguments must already be redacted. This function deliberately does
    not redact anything itself: a builder that quietly cleans its inputs is a
    builder whose caller stops thinking about them.
    """
    return f"""The user asked: "{message}"

Here is the actual payroll data from the system:

{payload_json}

Based on this data, provide:
1. A clear, insightful narrative response
2. An appropriate Chart.js chart configuration to visualize the data
3. Key insights and observations
4. Suggested follow-up questions

Names have been replaced with placeholders of the form [person-1]. Use those
placeholders exactly as they appear, including in chart labels. Do not invent
real names for them and do not guess who they are.

Remember to use the PayAI color palette and choose the best chart type for this data."""


class PayrollAIEngine(models.Model):
    """Core AI engine for PayAI — handles intent classification, data retrieval, and response generation."""

    _name = 'payroll.ai.engine'
    _description = 'PayAI Engine'

    @api.model
    def _get_provider(self):
        """Get the configured AI provider."""
        config = self.env['payroll.ai.config'].get_active_config()
        if not config:
            raise UserError(_(
                'PayAI is not configured. Please go to PayAI > Configuration '
                'and set up your AI provider.'
            ))
        return config.get_provider()

    @api.model
    def process_message(self, message, conversation_history=None, context=None):
        """
        Main entry point for processing a user message.

        Args:
            message (str): User's message
            conversation_history (list): Previous messages [{role, content}, ...]
            context (dict): Additional context (employee_id, etc.)

        Returns:
            dict: {
                'response': str,
                'chart': dict or None,
                'insights': list,
                'follow_up_questions': list,
                'intent': str,
            }
        """
        context = context or {}
        conversation_history = conversation_history or []
        # THE CONVERSATION'S OWN PLACEHOLDER TABLE (LEARNOS Phase 6).
        #
        # Loaded once per question and handed to whichever path runs, so that
        # every history turn is redacted against every person this
        # conversation has ever named — not only the ones this query happened
        # to return. Empty dict when there is no conversation (a caller with
        # no session, and the test harness), which degrades exactly to the
        # generic scrub the three non-data paths had before.
        mapping = self._conversation_mapping(context)

        try:
            provider = self._get_provider()

            # Step 1: Classify intent
            intent = self._classify_intent(provider, message)
            # Scrubbed in the LOG too. The server log is inside the trust
            # boundary, so this is not an egress fix — it is a retention one:
            # this line was writing "why is <a colleague>'s net only 4.200.000"
            # into a file with no retention policy, once per question.
            _logger.info("PayAI intent: %s for message: %s",
                         intent, generic_scrub(message)[:80])

            # Step 2: Process based on intent
            if intent == 'payroll_data':
                return self._process_data_query(
                    provider, message, conversation_history, context, mapping)
            elif intent == 'payroll_knowledge':
                return self._process_knowledge_query(
                    provider, message, conversation_history, mapping)
            elif intent == 'onboarding':
                return self._process_onboarding_query(
                    provider, message, conversation_history, context, mapping)
            else:
                return self._process_general_query(
                    provider, message, conversation_history, mapping,
                    context=context)

        except UserError:
            raise
        except Exception as e:
            _logger.exception("PayAI processing error: %s", str(e))
            return {
                'response': f'I apologize, but I encountered an error: {str(e)}. Please try again.',
                'chart': None,
                'insights': [],
                'follow_up_questions': [],
                'intent': 'error',
            }

    # ------------------------------------------------ the conversation table
    @api.model
    def _conversation(self, context):
        """The conversation this question belongs to, or an empty recordset.

        An id rather than a recordset crosses the RPC boundary, and an id that
        names nothing (a stale browser tab, a cleared session) must degrade to
        "no mapping" rather than raise inside somebody's question.
        """
        conv_id = (context or {}).get('conversation_id')
        if not conv_id:
            return self.env['payroll.ai.conversation'].browse()
        return self.env['payroll.ai.conversation'].browse(int(conv_id)).exists()

    @api.model
    def _conversation_mapping(self, context):
        """This conversation's table, or an empty one.

        `process_message` is an `@api.model` entry point, so the id in the
        context is whatever the caller sent. The record rule below it already
        refuses another user's conversation — what that refusal must not do is
        become a traceback in the middle of somebody's question, so it degrades
        to "no mapping", which is Phase 5's behaviour. Note the direction of
        the failure: a mapping that fails to load makes the redaction do LESS
        matching, never more, and a mapping belonging to somebody else could
        only ever remove names that are not there.
        """
        try:
            conversation = self._conversation(context)
            return conversation.load_redaction_map() if conversation else {}
        except Exception as exc:                                # noqa: BLE001
            _logger.warning("PayAI: could not load the redaction map: %s", exc)
            return {}

    @api.model
    def _persist_mapping(self, context, mapping):
        """Save the extended table back onto the conversation.

        Called on the DATA path only, because that is the only path that can
        learn a new name: the other three never read a record. A failure here
        must not lose the answer — the mapping is a privacy improvement across
        turns, and a database hiccup writing it is not a reason to hand the
        user an error instead of their chart.
        """
        conversation = self._conversation(context)
        if not conversation:
            return False
        try:
            return conversation.store_redaction_map(mapping)
        except Exception as exc:                                # noqa: BLE001
            _logger.warning("PayAI: could not store the redaction map: %s", exc)
            return False

    def _brand_name(self):
        """What THIS customer calls the product, read at send time.

        ERRORS E4-3. Read per request rather than cached on the class: one
        server process serves every customer's database on this platform, so a
        value remembered at import time would be whichever database happened to
        boot the registry first — and the assistant would introduce itself to
        one customer under another customer's brand.

        Falls back to the company's own name and then to a neutral phrase.
        Never to a hard-coded product name: a fallback is the path nobody
        watches, and getting this one wrong is exactly the bug E4 exists to fix.
        """
        try:
            icp = self.env["ir.config_parameter"].sudo()
            brand = (
                icp.get_param("biz_debrand.brand_name")
                or icp.get_param("web_debranding.new_name")
                or (self.env.company.name if self.env.company else "")
            )
            return (brand or "").strip() or "this product"
        except Exception:                                   # noqa: BLE001
            _logger.warning("PayAI: could not read the brand", exc_info=True)
            return "this product"

    def _system_prompt(self, template):
        """A prompt template, branded for this database."""
        return brand_prompt(template, self._brand_name())

    def _classify_intent(self, provider, message):
        """Classify the user's message intent.

        THE FIRST THING THAT LEAVES, AND IT USED TO LEAVE RAW.

        This runs before any query, so nothing has been read and there is no
        name mapping to build one from — which is exactly why it was missed:
        the redaction work all sits in `_process_data_query`, and by the time
        that runs, the whole message has already been on the wire once, in
        this prompt, to decide which of four paths to take.

        `generic_scrub` is what is available here and it is not nothing: an
        email, a phone number, a record id and a money amount all go. A NAME
        does not, because there is nothing yet to match it against, and that
        residual is written down in ai_redaction's list rather than left to be
        found. Classification does not need the name — it needs the shape of
        the question, and "[person-1]" and "Mai" route identically.
        """
        safe_message = generic_scrub(message)
        try:
            prompt = INTENT_CLASSIFICATION_PROMPT.format(message=safe_message)
            response = provider.generate_text(prompt, max_tokens=20, temperature=0.1)
            intent = response.strip().lower().replace('"', '').replace("'", '')

            # Normalize
            if 'payroll_data' in intent or 'data' in intent:
                return 'payroll_data'
            elif 'payroll_knowledge' in intent or 'knowledge' in intent:
                return 'payroll_knowledge'
            elif 'onboard' in intent or 'guide' in intent or 'tour' in intent:
                return 'onboarding'
            else:
                return 'general'
        except Exception as e:
            _logger.warning("Intent classification failed: %s, defaulting to general", e)
            return 'general'

    def _process_data_query(self, provider, message, conversation_history,
                            context, mapping=None):
        """Process a payroll data query — fetch real data from Odoo and generate chart.

        `mapping` is this conversation's accumulated placeholder table, or
        None for a caller with no conversation. It is EXTENDED here (this is
        the only path that reads records) and saved back.
        """
        # Step 1: Get the data query engine to fetch relevant data
        data_engine = self.env['payroll.data.query']
        payroll_data = data_engine.query_for_message(message, context)

        # Step 1b: a refusal is an ANSWER, and it stops here.
        #
        # The query layer runs with the asker's access rights (Phase D1), so
        # "you may not read this" is a normal outcome. Passing it on to the
        # provider would spend a token asking a model to paraphrase our own
        # refusal, and would let it soften or contradict the sentence — the one
        # sentence in this flow that has to be exact. It also keeps the fact
        # that a refusal happened off the wire entirely.
        if payroll_data.get('access_refused'):
            return {
                'response': payroll_data.get('message', ''),
                'chart': None,
                'insights': [],
                'follow_up_questions': [],
                'intent': 'payroll_data',
                'access_refused': True,
            }

        # A partial gate (individual salaries withheld, aggregate returned) is
        # NOT a refusal: the question was answered one level up. The note is
        # appended deterministically below rather than left to the model.
        access_note = payroll_data.get('access_note') or ''

        # Step 1c: THE NAMES COME OUT BEFORE THIS PROMPT IS BUILT.
        #
        # The asking user has already passed the access gate above, so they are
        # entitled to these names. The provider is not, and never was — this
        # path posted employee names, job titles and wages verbatim from the
        # day it was written. `mapping` stays on this server and is what puts
        # them back at the end.
        #
        # EXACTLY WHAT IS PROTECTED, AND WHERE. An earlier draft of this
        # comment said "three things are redacted" and was FALSE AS BUILT,
        # because it described this method and the message had already been
        # sent once, unredacted, by `_classify_intent`. The honest version:
        #
        #   payload          names by key then everywhere, plus emails, phones,
        #                    record ids. Figures survive — they are the answer.
        #   this message     the same mapping, plus the free-text scrub. A name
        #                    IS caught here, because by now there is a mapping.
        #   history turns    the same treatment, with the SAME mapping — and
        #                    since Phase 6 that mapping is the CONVERSATION's,
        #                    so a person named in an earlier answer is caught
        #                    here even when this query did not return them.
        #                    That is the Phase 4 residual, closed.
        #   the classifier   ran BEFORE all of this and had no mapping to use.
        #                    It gets `generic_scrub` only: contact details and
        #                    money go, a name does not.
        redacted_data, mapping = redact_names(payroll_data, mapping=mapping)
        # SAVED BEFORE THE PROMPT IS SENT, not after the answer comes back. A
        # provider timeout must not lose the association the reply's
        # placeholders will need.
        self._persist_mapping(context, mapping)
        safe_message = redact_text(message, mapping)

        # Step 2: Build the prompt with the redacted data
        data_prompt = data_query_prompt(
            safe_message, json.dumps(redacted_data, indent=2, default=str))

        messages = [
            {"role": "system", "content": self._system_prompt(PAYAI_SYSTEM_PROMPT)},
        ]
        # Add recent conversation history for context
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                "content": redact_text(msg.get('content', ''), mapping),
            })
        messages.append({"role": "user", "content": data_prompt})

        # Step 3: Generate response with chart
        try:
            raw_response = provider.generate_chat(messages, max_tokens=2500, temperature=0.5)
            result = provider._parse_json_response(raw_response)
            # THE PLACEHOLDERS GO BACK, EVERYWHERE. Not only in the narrative:
            # a chart's labels are the names the model was handed, and an axis
            # reading "[person-1]" is a worse outcome than no redaction at all,
            # because it reads as a rendering fault rather than as a control.
            result = restore_deep(result, mapping)

            return {
                'response': self._with_access_note(
                    result.get('response', 'Here is the data analysis.'), access_note),
                'chart': result.get('chart', None),
                'insights': result.get('insights', []),
                'follow_up_questions': result.get('follow_up_questions', []),
                'intent': 'payroll_data',
                'drilldown_model': payroll_data.get('drilldown_model', ''),
            }
        except Exception as e:
            _logger.warning("Failed to parse chart response: %s", e)
            # Fallback: return raw text response. It is the model's own words
            # with nothing parsed out of them, so it carries placeholders too.
            fallback = (restore_names(raw_response, mapping)
                        if 'raw_response' in dir() else str(e))
            return {
                'response': self._with_access_note(fallback, access_note),
                'chart': None,
                'insights': [],
                'follow_up_questions': [],
                'intent': 'payroll_data',
                'drilldown_model': payroll_data.get('drilldown_model', ''),
            }

    @api.model
    def _with_access_note(self, response, access_note):
        """Append the gate note to a narrative the model wrote.

        Both return paths of `_process_data_query` go through here, including
        the parse-failure fallback — a user whose individual detail was
        withheld must be told so even when the chart JSON did not parse.
        """
        if not access_note:
            return response
        return '%s\n\n%s' % (response or '', access_note)

    def _process_knowledge_query(self, provider, message, conversation_history,
                                 mapping=None):
        """Process a payroll knowledge question."""
        messages = [
            {"role": "system", "content": self._system_prompt(PAYAI_SYSTEM_PROMPT)},
        ]
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                # HISTORY IS AN EARLIER ANSWER WITH THE NAMES PUT BACK IN.
                # This path never READS a record, so it never extends the
                # mapping — but since Phase 6 it is handed the conversation's,
                # so a person an earlier data turn restored into an answer is
                # removed here too. With no conversation the mapping is empty
                # and `redact_text` degrades to exactly the generic scrub this
                # line used to call.
                "content": redact_text(msg.get('content', ''), mapping),
            })
        messages.append({"role": "user", "content": message})

        try:
            raw_response = provider.generate_chat(messages, max_tokens=1500, temperature=0.7)
            try:
                result = provider._parse_json_response(raw_response)
                return {
                    'response': result.get('response', raw_response),
                    'chart': result.get('chart', None),
                    'insights': result.get('insights', []),
                    'follow_up_questions': result.get('follow_up_questions', []),
                    'intent': 'payroll_knowledge',
                }
            except Exception:
                return {
                    'response': raw_response,
                    'chart': None,
                    'insights': [],
                    'follow_up_questions': [],
                    'intent': 'payroll_knowledge',
                }
        except Exception as e:
            _logger.error("Knowledge query error: %s", e)
            raise

    # ------------------------------------------------------------------
    # THE ACTION ENVELOPE
    #
    # PayAI may offer to SHOW the user something. Until Phase C2 that meant
    # starting a pb_coach tour; it now means opening a pb_learn lesson, and the
    # difference is not cosmetic. A tour was a spotlight walk over the live
    # product in English with nothing recorded at the end. A lesson runs over
    # the practice replica, ships in both languages, ends on a judgement check
    # and stores completion per learner — and, unlike a tour, it exists as a
    # DATABASE RECORD this whitelist can be validated against.
    #
    # `_KNOWN_LESSONS` is a whitelist and nothing else: the LLM chooses from it,
    # it never authors a key. An unknown key is dropped rather than passed
    # through, because a button that opens nothing is worse than no button.
    _KNOWN_LESSONS = ('LW', 'L1', 'L5', 'L3', 'L4', 'LA', 'L2', 'L6',
                      # LEARN REFRESH step 3 — payroll setup.
                      'L7', 'L8', 'L9', 'L10', 'L11', 'L12',
                      # LEARN REFRESH step 4 — the wider app.
                      'L13', 'L14', 'L15', 'L16', 'L17', 'L18', 'L19',
                      'L20', 'L21', 'L22', 'L23', 'L24',
                      # LEARN REFRESH step 5 — every remaining lesson.
                      'L25', 'L26', 'L27', 'L28', 'L29', 'L30', 'L31',
                      'L32', 'L33', 'L34', 'L35', 'L36', 'L37', 'L38')

    # LEARN REFRESH step 2: a WALKTHROUGH is the second thing "Show me" may
    # open — the real screens, narrated, in Watch mode. Same rule as lessons:
    # a whitelist the model chooses from and never authors. Only walkthroughs
    # that are on the lesson map and have a Watch mode are here.
    _KNOWN_WALKTHROUGHS = ('sc_welcome', 'sc_payrun', 'sc_payslips',
                           'sc_formula', 'sc_import',
                           # LEARN REFRESH step 3 — payroll setup.
                           'sc_blueprint', 'sc_mapjourney', 'sc_treatment',
                           'sc_matrix', 'sc_records', 'sc_schemes',
                           # LEARN REFRESH step 4 — the wider app.
                           'sc_paybands', 'sc_payreview', 'sc_decisionroom',
                           'sc_hiring', 'sc_joiners', 'sc_exits',
                           'sc_probation', 'sc_wftoday', 'sc_wftime',
                           'sc_wfclose', 'sc_access', 'sc_filings')

    # The old tour ids, and the lesson each became. Kept because the SYSTEM
    # PROMPT and the model behind it may lag a deploy — a cached conversation,
    # a slow provider rollout, a fine-tune that learned the old vocabulary — and
    # an envelope that only understood the new form would silently drop every
    # "Show me" for as long as that lasted.
    #
    # LEARNOS PHASE 1b: THE TOURS NOW HAVE TWO SUCCESSORS EACH, AND THIS MAP
    # STILL POINTS AT THE LESSON. The tour module was deleted and its six tours
    # were ported into pb_learn SCENARIOS — `hero_path` is `sc_welcome`,
    # `tour_payrun` is `sc_payrun`, `tour_payslips` is `sc_payslips`,
    # `tour_formula` is `sc_formula`, `tour_import` is `sc_import` and
    # `tour_mapping` is `sc_mapping` — so for every entry below there is now a
    # walkthrough that is a closer descendant of the tour than the lesson is.
    # Every entry still lands on the LESSON, decided per entry and for two
    # reasons that hold for all six:
    #
    #   · THE ENVELOPE CANNOT SAY IT. `_sanitize_action` emits exactly one
    #     shape, `open_lesson`, and the browser opens the Journey with
    #     `context.lesson`. Re-pointing an entry at `sc_payrun` would put a
    #     scenario key in a field named `lesson`, fail the whitelist below, and
    #     be dropped — a button that opens nothing. A scenario envelope is a
    #     change to the sanitizer and to `ai_insight_chat.js`, which is a
    #     separate piece of work with its own trust boundary to re-argue.
    #   · A LESSON IS THE BETTER LANDING FOR A QUESTION. Somebody arrives here
    #     by ASKING, and a lesson answers: it is bilingual, it runs where
    #     nothing can matter, it ends on a judgement check and it records
    #     completion. A Watch of the real product answers "where is that", which
    #     is what the Coach's own "Show me how" section now offers on the screen
    #     the person is already standing on — reached in one press, without a
    #     language model in the path.
    #
    #   hero_path      -> LW   the Dashboard welcome; LW is its direct successor
    #                          (sc_welcome is the Watch of the same ground)
    #   tour_payrun    -> L1   run a pay run, division to submit (sc_payrun)
    #   tour_formula   -> L5   read a division's formula configuration (sc_formula)
    #   tour_payslips  -> L3   read a payslip line by line (sc_payslips)
    #   tour_import    -> L4   the import confidence score and fixing rows
    #                          (sc_import)
    #   tour_mapping   -> L5   NOT L4: the mid/end mapping wizard pairs COMPONENTS
    #                          across two formula configurations, which is L5's
    #                          subject. L4 is about attendance files and would
    #                          send the asker to the wrong desk. (sc_mapping)
    _TOUR_TO_LESSON = {
        'hero_path': 'LW',
        'tour_payrun': 'L1',
        'tour_formula': 'L5',
        'tour_payslips': 'L3',
        'tour_import': 'L4',
        'tour_mapping': 'L5',
    }

    def _sanitize_action(self, action):
        """Accept both envelope forms; ALWAYS emit `open_lesson`.

        Two inputs, one output. `start_tour` with an old tour id is converted
        through `_TOUR_TO_LESSON`; `open_lesson` is validated against the
        whitelist. Anything else — a type nobody ships, a lesson key nobody
        wrote, a non-dict — returns None, and the chat renders no button at all.
        """
        if not isinstance(action, dict):
            return None
        kind = action.get('type')
        if kind == 'open_walkthrough':
            walk = action.get('walkthrough')
            if not isinstance(walk, str) or walk not in self._KNOWN_WALKTHROUGHS:
                return None
            label = action.get('label')
            return {
                'type': 'open_walkthrough',
                'walkthrough': walk,
                'label': label[:40] if isinstance(label, str) and label else 'Show me',
            }
        if kind == 'open_lesson':
            lesson = action.get('lesson')
        elif kind == 'start_tour':
            # isinstance FIRST. `dict.get` on an unhashable key raises TypeError,
            # and everything reaching this method came out of a language model's
            # JSON — a list or a dict where a string was asked for is not a
            # remote possibility, it is Tuesday. A sanitizer that can be made to
            # raise is not a sanitizer.
            tour = action.get('tour')
            lesson = self._TOUR_TO_LESSON.get(tour) if isinstance(tour, str) else None
        else:
            return None
        if not isinstance(lesson, str) or lesson not in self._KNOWN_LESSONS:
            return None
        # Same rule for the label, one type further: `or` lets a non-empty int
        # through and `[:40]` then raises, while a list would slice happily and
        # reach the DOM as a caption nobody wrote.
        label = action.get('label')
        return {
            'type': 'open_lesson',
            'lesson': lesson,
            'label': label[:40] if isinstance(label, str) and label else 'Show me',
        }

    # Friendly names for the cockpits the user may be standing on.
    _SCREEN_NAMES = {
        'pb_dashboard': 'Home › Pulse',
        'pb_payrun_wizard': 'Pay Run › Run',
        'pb_payruns': 'Pay Run › Runs',
        'pb_payslip': 'Pay Run › Payslips',
        'pb_formula_studio': 'Settings › Formula Engine (Formula Studio)',
    }

    @staticmethod
    def _plain_label(value):
        """A label from the browser, made safe to put in a prompt: a short
        single line of text, or ''. It arrives from the client, so it is
        treated as data — never longer than a rail label can be."""
        if not isinstance(value, str):
            return ''
        return ' '.join(value.split())[:40]

    def _describe_screen(self, screen):
        if not isinstance(screen, dict):
            return None
        tag = screen.get('tag') or ''
        xid = screen.get('xml_id') or ''
        model = screen.get('model') or ''
        # LEARN REFRESH step 1. Since the rail cutover almost every screen is
        # a TAB inside one of nine hub pages, and the action is the hub
        # whichever tab is showing; the client sends the hub and tab the hub
        # itself published. "the Payslips tab in Pay Run".
        hub = self._plain_label(screen.get('hub'))
        tab = self._plain_label(screen.get('tab'))
        if hub and tab:
            return 'the %s tab in %s' % (tab, hub)
        if hub:
            return 'the %s page' % hub
        if tag in self._SCREEN_NAMES:
            return self._SCREEN_NAMES[tag]
        if 'formula' in tag or 'formula' in xid:
            return 'the Formula Engine'
        if model in ('hr.payslip.run', 'hr.payslip') or 'payslip_run' in xid:
            return 'the Pay Runs / Payslips area'
        return screen.get('name') or None

    def _process_onboarding_query(self, provider, message, conversation_history,
                                  context=None, mapping=None):
        """Answer a 'how do I use Payobook' question, optionally launching a tour."""
        messages = [{"role": "system",
                     "content": self._system_prompt(ONBOARDING_SYSTEM_PROMPT)}]
        screen_note = self._screen_note(context)
        if screen_note:
            messages.append(screen_note)
        for msg in conversation_history[-6:]:
            # Same rule as the other three paths — see _process_knowledge_query.
            messages.append({"role": msg.get('role', 'user'),
                             "content": redact_text(msg.get('content', ''), mapping)})
        messages.append({"role": "user", "content": message})

        raw_response = provider.generate_chat(messages, max_tokens=1200, temperature=0.4)
        try:
            result = provider._parse_json_response(raw_response)
        except Exception:
            result = {'response': raw_response}
        return {
            'response': result.get('response', raw_response),
            'chart': None,
            'insights': result.get('insights', []),
            'follow_up_questions': result.get('follow_up_questions', []),
            'intent': 'onboarding',
            'action': (self._sanitize_action(result.get('action'))
                       or self._content_handoff(message)),
        }

    def _content_handoff(self, message):
        """LEARN REFRESH step 3 — the "Show me" the model left out.

        The model offers an action only when it is sure, and in practice it
        is rarely sure: "how do I change many employees at once?" came back
        with a correct answer and no button. The helper's own resolver
        (pb_learn `learn.intent.resolve`) already knows which questions a
        walkthrough answers — an intent's `watch` — so the same question is
        asked of it, and a walkthrough is offered only when that resolver
        names one AND the whitelist below knows it. Soft: without pb_learn,
        or on any error, there is simply no button.
        """
        if 'learn.intent' not in self.env or not isinstance(message, str):
            return None
        try:
            Intent = self.env['learn.intent'].sudo()
            key = Intent.resolve(message[:400])
            intent = key and self.env['learn.content'].sudo().intent(key)
            walk = (intent or {}).get('watch') or ''
        except Exception:       # noqa: BLE001 — a hint must never break an answer
            return None
        return self._sanitize_action(
            {'type': 'open_walkthrough', 'walkthrough': walk, 'label': 'Show me'})

    def _screen_note(self, context):
        """The one system line that says where the user is standing, or None.

        Shared by the onboarding and general paths: "what is this page?" is
        classified either way, and the answer has to name the tab the user
        is on in both (LEARN REFRESH step 1)."""
        screen_desc = self._describe_screen((context or {}).get('screen'))
        if not screen_desc:
            return None
        return {
            "role": "system",
            "content": "The user is currently on %s. If they say 'this', 'here', "
                       "'this page' or 'this screen', interpret it relative to that "
                       "and name it in your answer." % screen_desc,
        }

    def _process_general_query(self, provider, message, conversation_history,
                               mapping=None, context=None):
        """Process a general (non-payroll) question."""
        messages = [
            {"role": "system", "content": self._system_prompt(PAYAI_SYSTEM_PROMPT)},
        ]
        screen_note = self._screen_note(context)
        if screen_note:
            messages.append(screen_note)
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg.get('role', 'user'),
                # Same rule as the other three paths — see
                # _process_knowledge_query. The conversation's mapping, or an
                # empty one, which is the generic scrub.
                "content": redact_text(msg.get('content', ''), mapping),
            })
        messages.append({"role": "user", "content": message})

        try:
            raw_response = provider.generate_chat(messages, max_tokens=1500, temperature=0.7)
            try:
                result = provider._parse_json_response(raw_response)
                return {
                    'response': result.get('response', raw_response),
                    'chart': None,
                    'insights': [],
                    'follow_up_questions': result.get('follow_up_questions', []),
                    'intent': 'general',
                }
            except Exception:
                return {
                    'response': raw_response,
                    'chart': None,
                    'insights': [],
                    'follow_up_questions': [],
                    'intent': 'general',
                }
        except Exception as e:
            _logger.error("General query error: %s", e)
            raise
