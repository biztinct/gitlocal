# Workforce Futures — research and design recommendation

Audience: Payobook leadership and product team. Research date: 5 September 2026.
Decision: choose an interaction model for a new workforce planning product; three working HTML proofs of concept, before production implementation.

## Recommendation
Make the What-if Cockpit the default home. Offer the Guided Path as an optional starting point for novice users. Open the Coverage Studio when leaders need to resolve shift-specific constraints. These are complementary interaction models over one explainable calculation engine. This is a design recommendation, not evidence that competing systems lack these capabilities.

The product promise: **Change a decision. Understand the consequence. Find a better plan.** A new user should see a useful starting scenario immediately, without constructing a model or knowing planning jargon.

## Evidence and implications

Workday markets unlimited scenarios, financial and HR impact assessment, and drag-and-drop organizational modeling. These are established capabilities, not defensible novelty by themselves. The proposed product differentiator is a shorter journey from a question to an understood decision. [Workday organizational design and scenario modeling](https://www.workday.com/en-us/products/adaptive-planning/scenario-modeling-software.html). Workday also describes links between strategic goals, capacity and talent supply. [Workday strategic workforce planning](https://www.workday.com/en-us/products/adaptive-planning/workforce-planning/strategic-workforce-planning.html).

Pigment describes real-time HR, recruiting and finance integrations, forecasting models, scenario analysis, and approval workflows. This supports one connected scenario model, with a clear separation between exploring an idea and approving execution. [Pigment headcount planning](https://www.pigment.com/use-case/headcount-planning).

Anaplan describes connections among HR, finance and operations, with a real-time view of jobs, positions and costs. Planning should account for role mix and hiring timing rather than treating every employee as equivalent. [Anaplan operational workforce planning](https://www.anaplan.com/solutions/operational-workforce-planning/).

UKG’s documented labor forecast converts demand into required employees by job and 15-minute intervals and distinguishes paid time from productive time. Aggregate headcount can conceal shortages by shift or skill. The prototype therefore models three shift pools and specialist/lead capacity; production would need interval-level demand and roster rules. [UKG labor forecast documentation](https://communityfiles.ukg.com/support/KOL/onlinehelp81/Subsystems/Help-WFF/Content/WFF_OLH/configuring_labor_forecast.htm).

Nielsen Norman Group recommends progressive disclosure to defer secondary choices, keeping the primary interface focused. Its usability heuristics emphasize recognition, feedback and user control. The proposed interfaces use starting questions, labeled controls, baseline comparisons, reversible edits, plain-language feedback, and expandable assumptions. These are evidence-informed design choices; a usability test is still needed to prove novice success. [NN/g progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/), [NN/g usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/).

## Three options

| Concept | First action | Primary delight | Strength | Trade-off |
|---|---|---|---|---|
| What-if Cockpit | Adjust one labeled slider or apply an example | Charts, money breakdown and a causal explanation update together | Fast executive exploration | Too many exposed controls could overwhelm; advanced inputs are folded away |
| Guided Path | Choose a business goal | Compare calculated paths and see whether the goal is achievable | Easiest first-time experience | Recommendations must disclose the search space and assumptions |
| Coverage Studio | Add or move capacity among day, evening and night | A visible shortage shrinks while financial impact updates | Operational clarity | A monthly capacity sketch is not a compliant employee roster |

## Deliberate product decisions

1. One shared model and comparable baseline in all three concepts.
2. Demand and capacity determine realized revenue. More hires alone do not guarantee more sales.
3. Show forecast operating profit, margin, fully loaded workforce cost, headcount, fulfilled demand and employee take-home separately.
4. Distinguish employee withholding from additional employer cost. The prototype uses explicitly fictional rates, with no claim of jurisdictional payroll compliance.
5. Hiring takes effect in the selected month, with a two-month capacity ramp and one-off recruiting costs.
6. Skills are bottlenecks: operators need enough specialists and team leads. Office roles incur cost; this small prototype does not invent a direct revenue productivity effect for them.
7. Explain uncertain demand through a stress test, labeled as an assumption rather than a statistical confidence interval.
8. Keep a baseline, support undo and reset, save named scenarios locally, compare scenarios, and export a readable decision brief with assumptions.
9. Goal seeking searches a bounded candidate set and says when a target is unattainable within that set. It must never disguise a preset as an optimized answer.
10. Use a monthly plan cursor so users can see the effect of hiring timing and ramp-up.

## Beyond these prototypes

After concept approval, start with validated imports of workforce, compensation, demand and ledger actuals; a visible data-quality check; legal-entity and currency isolation; versioned local employer/employee payroll rules; permissions; durable scenario branches; auditable approvals and a plan-to-requisition handoff. Add attrition and backfill, absence patterns, internal mobility, contractor choices, recruitment capacity, skills development and multi-site transfers as genuine decision drivers. Show the source and freshness of every material assumption.

For advanced operations, enforce contract hours, breaks, rest, skill eligibility, availability, overtime caps and employee preferences. Surface unfilled work rather than hiding infeasibility. For strategic planning, incorporate hiring lead time, ramp curves, seasonal demand and uncertainty with transparent ranges. The prototypes demonstrate the core experience without pretending to implement those full capabilities.

## Proposed usability acceptance gate

Test with at least five first-time users spanning CEO/finance, HR and operations. Ask each to find the cost of ten additional operators, explain a revenue plateau, compare two approaches to 15% growth, resolve an evening coverage gap, and undo a mistake. Proposed targets: first meaningful change within 30 seconds, an accurate explanation of the business impact within two minutes, and completion without facilitator help for at least four of five participants. These are proposed product targets, not measured results.

## Scope and limitations

The user confirmed a mixed office-and-shift workforce and wants all major planning outcomes. All company data, rates, salaries, seasonality and operational coefficients are invented demonstration assumptions in USD. Figures are simplified operating estimates, excluding financing, income tax, working capital, severance and legal compliance. No live HR/payroll data is read or modified. Employer costs and employee deductions are illustrative, not legal or financial guidance.

Research is a bounded review of first-party product descriptions/documentation and published usability guidance. Vendor claims show marketed capabilities, not independently verified usability or comparative superiority. No licensed product trials or novice-user studies were performed. We cannot substantiate that an interaction is unique across the entire market. Sources sufficiently support the decision slots; further broad searches would be unlikely to change this prototype direction.

## Claim-to-source ledger and evidence gaps

| Claim family | Source / publisher | Publication date | Confidence / access | Gap / resolution |
|---|---|---|---|---|
| Scenario and org modeling | Workday, two product pages linked above | Not stated | High for marketed capabilities; opened official page | Actual novice usability unknown; validate our own design with users |
| Connected headcount planning | Pigment, headcount planning | Not stated | High for marketed capabilities; opened official page | No independent performance claims made |
| HR/finance/operations planning | Anaplan, operational workforce planning | Not stated | High for marketed capabilities; official search evidence | Capability claim only; no ranking |
| Productive time, job and interval demand | UKG, labor forecast documentation | Version 8.1 documentation; date not stated | High for documented mechanics; opened official documentation | Older documentation supports stable concepts, not latest UI claims |
| Progressive disclosure | NN/g, Progressive Disclosure | Page date not captured | High for published guidance; opened | Applied as design principle, not proof of usability |
| Feedback, recognition and reversibility | NN/g, 10 Usability Heuristics | Page date not captured | High for published guidance; opened | Proposed acceptance test above |

Discovery covered Workday, Pigment, Anaplan and UKG. Follow-up read official product pages, detailed UKG mechanics, and NN/g guidance. No material contradictions were found within these scoped claims. Planning tool was not exposed in this session; scope, discovery, synthesis and verification are recorded here instead.
