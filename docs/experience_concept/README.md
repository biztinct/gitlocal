# Paybook experience concept

Design-only proposal requested on 23 September 2026. Open `index.html` directly in a browser; it has no external dependencies. Local preview: http://127.0.0.1:8767/ while the preview server is running.

## Recommendation

Connect the existing features through one journey: Learn → Watch → Practise → contextual help. Replace the stacked Stuck?/lightning launchers with one labelled Ask Paybook entry. Keep Guide me and Analyse data visibly distinct within that surface and retain their separate permission and data boundaries.

The concept includes:

- A task-based learning home with a recommended next step, resume point, searchable task cards and demonstrated practice skills.
- A three-step manual walkthrough and a fictional payroll exception mission, including source inspection, incorrect-answer feedback, retry, reset and completion feedback.
- A payroll review concept with a docked assistant, sample evidence-backed explanation and a path into practice.
- Design rationale covering prioritisation, accessibility, localisation, unknown-screen recovery, content compatibility as screens evolve and later feature opportunities.

## Basis and limits

Reviewed the supplied screenshots and local source in `pb_learn/static/src/coach/coach.xml`, `pb_learn/static/src/hub/learn_hub.xml`, `pb_learn/models/learn_intent.py`, learning content and PayAI design documents. Existing source already supports coaching, scenario Watch/Try links, explain-screen support and answer source handling. These should be connected and refined, not unnecessarily rebuilt. Older handover feature-status statements were not taken as evidence of current production availability.

No deployed application audit was performed. This file is a design artifact, not an Odoo implementation. All employee data, amounts, readiness and responses are illustrative. The overtime rate is training arithmetic, not a statutory formula. No application files, database schema, real records or AI integrations were changed. English only; complete English/Vietnamese parity is a recommendation for implementation.

## Validation

Chrome checks against the locally served artifact passed:

- Learning screen renders; desktop and 390px layouts visually inspected.
- Three walkthrough steps lead into the practice mission.
- Incorrect choice explains the issue; source record expands; correct choice updates readiness from 1/3 to 2/3.
- Task search shows a useful no-results state.
- Payroll variance opens its explanation and supporting fictional evidence.
- Unknown free-text question gives an explicit scripted-preview fallback.
- Escape closes the assistant and updates its expanded state.

Screenshots were inspected in memory; no PNG or screenshot files were written to the repository. Local preview is the only deployment target for this design-only phase. Production and databases are outside scope under the explicit “Do not code yet” instruction. Existing unrelated workbook deletion was preserved and excluded from the commit.
