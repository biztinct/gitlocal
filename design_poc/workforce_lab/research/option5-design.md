# Option 05 — The Decision Room

A review-only HTML evolution of Option 04, informed by `design_poc/wfplan/option_e.html` and the supplied goal-finder screenshot. Uses the reference's violet #5A4BB0, deep purple #241F52, lavender #EDEAF8 and canvas #F4F5FB, with teal for capacity and rose for demand/gaps. Uses the existing fictional 240-person USD model, not private Payobook payroll records.

## What changed, and why

- **Goals visible while planning.** Margin floor, annual profit floor, workforce budget ceiling and annual demand coverage are enabled initially. Team size and overtime ceilings are optional. Each displays actual, target and a precise gap, so a better result is not confused with a goal being met. Percentage differences use percentage points.
- **Goals work together.** The path search evaluates all selected goals simultaneously. Unlike Option 04's preset search, it preserves the user's demand, stress, timing, office hiring, pay, shift and payroll assumptions. It searches planned operator/support hires, overtime and productivity. Existing jobs remain protected. Infeasible results explicitly list the missed goals.
- **Try before keeping.** A suggested plan enters a clearly marked trial. Keep accepts it into undo history; Back restores the previous state and goals. Saving and export are available after a direction is kept. This is more deliberate than making a hover silently change the plan.
- **Annual outcome and timing.** The headline is annual. The main money chart is cumulative, so December exactly equals that headline. Profit and budget goal lines show an even monthly pace, not a forecast or a monthly approval limit. Coverage stays a percentage rather than being summed. A separate month ribbon shows individual monthly profits and months below the annual coverage benchmark.
- **Work and shifts.** One chart, one unit: arriving work, potential capacity and delivered work in hours. This reveals skill and shift constraints without mixing currency, people and percentages. The shift cards provide the operational detail.
- **Room to hire.** Tests every additional whole-person hire for the selected role, holding everything else fixed. Teal points satisfy all selected goals; rose points do not. Exact feasible intervals are shown, including disconnected intervals. A point can be tried as a reversible plan.
- **Retained from Option 04.** Live levers, comparison overlays, difference mode, accounting profit bridge, employee deductions and take-home, demand stress, named browser-local scenarios and portable briefs.

## Deliberately deferred

A draggable money-flow diagram, a separate window full of charts, arbitrary panel docking, and overlapping multi-plan line charts add learning and interaction costs for executives. The accounting bridge and pay split answer the money questions more directly. Role/division cost charts can be added inside People & pay when actual division data is available. Month-by-month hiring events, departures/backfill and local bonus/tax rules require a richer production model; this POC keeps its existing single start month and fictional rates explicit.

## Implementation in Payobook

No new runtime library is needed for this prototype. It uses plain HTML, CSS, native controls and canvas with accessible text equivalents. No external font, icon, chart or animation CDN is used. The social asset belongs to the existing gallery and is preserved.

For production, implement state and components in OWL and load Chart.js through the existing `web.chartjs_lib` bundle. The local repository already uses that approach in `pb_explorer/static/src/js/pbex_charts.js` and `pb_workforce_insights/static/src/js/workforce_insights.js`. Keep CSS tokens in module-scoped SCSS, reuse Odoo dialogs/inputs/icons, and use Chart.js line/bar charts for the outlook, demand, hiring room and waterfall. Native CSS is sufficient for goal cards, month ribbons and transitions. Do not introduce React, D3, ECharts, or a second chart bundle solely for this design.

Keep the pure model behind a service boundary, with OWL components consuming a normalized scenario/result contract. The production calculation service must use authorized company/currency data, real planning rates, effective-dated role costs, validated demand assumptions, jurisdiction-specific payroll rules, tenant access checks, server-persisted scenarios and a separate approval workflow. Bounded search is transparent arithmetic, not an AI forecast or proof of global optimality. Use a worker or server-side job if real-company candidate calculations outgrow an interactive response time.

This phase publishes only the private review site. No Odoo deployment or database migration is part of the design POC.
