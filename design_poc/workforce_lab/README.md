# Workforce Futures — review prototypes

Four distinct HTML concepts for a new Payobook workforce planning experience:

- `public/cockpit.html` — CEO what-if cockpit, live sliders, annual metrics, monthly chart, money breakdown, scenario comparison.
- `public/guide.html` — goal-first planning, bounded candidate search, hiring/development/blended paths, explicit infeasibility.
- `public/studio.html` — monthly shift coverage, operator allocation, hiring, overtime, productive time and support-skill bottlenecks.
- `public/living.html` — The Living Plan: the three concepts joined on one connected canvas. Hero stage with profit / people cost / coverage views, ±10% demand band and a month scrubber; people → coverage → profit ripple; shift balance, profit bridge and take-home tabs; compare against the baseline, a pinned plan or any saved scenario. Logic in `public/living-model.js` (pure) and `public/living.js` (page).
- `public/living.html` — recommended connected canvas: before/after forecast, demand stress envelope, profit bridge, monthly exploration, goal paths, marginal hiring preview and pinned comparisons.
- `public/option5.html` — The Decision Room: Option 04 with the option_e violet palette, six simultaneous executive goals, cumulative outlook, reversible path trials, demand/capacity chart and exact feasible hiring ranges.
- `public/option5-standalone.html` — self-contained portable version; no external assets or runtime dependencies.
- `public/index.html` — offline concept gallery.
- `public/research.html` — research, comparison, recommendation and proposed production roadmap.

Open `public/index.html` directly, keeping the public folder together. All five concepts work without a server, external libraries or live business data. Named scenarios are stored only in this browser. Export creates a portable HTML decision brief.

Hosted preview: https://payobook-workforce-futures.groovy-pixie-4012.chatgpt.site

## Scope

This phase creates reviewable standalone prototypes only. The existing workforce modules and earlier `design_poc/wfplan` concepts are preserved. The deployment target is the owner-private Sites project in `.openai/hosting.json`; no Odoo server, tenant or database is in scope for this design-only phase. Production implementation follows concept approval.

## Reproduce

- `npm install`
- `python3 scripts/export-html.py` regenerates offline gallery and research HTML.
- `node --test tests/*.test.mjs tests/living.test.mjs` validates reconciliations, timing, capacity constraints, role effects and goal seeking.
- `python3 scripts/export-option5.py` regenerates the standalone Option 05 HTML.
- `npm run dev` serves the local gallery and prototypes.
- `npm run build` creates the Sites deployment output.

## Model contract

Fictional 240-person mixed workforce in USD. Operator, specialist, team lead and office monthly salaries are $3,200 / $5,200 / $6,200 / $4,800. Baseline headcounts are 140 / 40 / 16 / 44. Ordinary paid hours are 160/month. Overtime is paid at 1.5×. Evening/night premiums are 10%/25%. Availability loss and productivity improvements affect capacity. Training costs $35 per productivity percentage point per operator per month.

Revenue = $150 × fulfilled delivery hours. Fulfilled hours are capped by shift demand, available operator capacity, and specialist/team lead support (650/1,700 hours per FTE per month). Demand uses visible year-end growth plus an invented seasonal profile. Additional employees receive full salary from the start month; first-month productive capacity is 50%, then 100%. One-off recruiting cost is 75% of monthly base salary per new hire.

Workforce cost = gross salaries + overtime + shift premiums + employer contributions + recruiting + development. Employee deductions come from gross pay and are not added a second time to employer expense. Other operating cost = $420,000/month + 25% realized revenue. Profit excludes financing and income tax. Salary changes start in the selected start month; shift, overtime, productivity and availability assumptions affect the whole modeled year.

All rates are invented demonstration assumptions, not statutory rules. The monthly shift board is not a legal roster. No live payroll, hiring, staffing or approval action is executed. Search evaluates 2,496 candidates, reports lowest-cost feasible paths in each lane, and explicitly labels unattained targets. For infeasible cost targets, the fallback is lowest cost (coverage may fail); for other targets it is highest coverage.

## Browser review paths

Cockpit: edit operators → observe metrics and chart → undo → save a named scenario → reset → reload saved plan → export brief. Guided Path: calculate a 15% growth goal → compare three paths → inspect selected plan; also test a 50% cost reduction target for explicit infeasibility. Studio: balance shift shares → transfer operators → hire into a shift → compare months before/after start. Living Plan: load “Grow thoughtfully” → move the operators lever → watch the ripple → open “Why profit changed” → pin the plan as comparison → try “Help me reach a goal” → save and export. Check all five at desktop and mobile widths.

Testing screenshots must not be retained. `public/og.png` is the generated social preview product asset, not a testing screenshot.

Option 05 decisions and production mapping: `research/option5-design.md`. Its named scenarios include goals and use a separate browser-local storage key, preserving Option 04 scenarios. Browser check: set all six goals → find paths → try/cancel/keep → Room to hire → trial a feasible addition → save → change goals → restore → export. Validate impossible goals explicitly.
