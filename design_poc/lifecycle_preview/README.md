# Payobook People Journeys — design review

This is the requested interactive HTML design preview before production implementation. It covers Hiring, Probation and Holiday Calendar in the existing Payobook indigo theme. The Odoo application and tenant databases are not changed by this design phase.

## Run

- `npm install`
- `npm run dev`
- `npm run build`
- `npx tsc --noEmit`

Private preview: https://payobook-people-journeys.groovy-pixie-4012.chatgpt.site

The Sites project is identified by `.openai/hosting.json`. Deploy the combined current state of this preview project. No database or external services are connected. UI state is in memory and resets on reload. Application/referral files remain in the browser. Emails, approvals, scheduling, signatures and production side effects are simulated.

## Review paths

1. Hiring → New hiring request → role details → interview plan → budget → review → submit demo request.
2. Candidates → Maya Chen → Move candidate → select stage and enter reason → inspect updated row and activity history.
3. Templates → JD studio / email studio → edit content → review rendered output. Switch workspace to Acme to review generic branding.
4. Overview → application / referral preview. Check 150–250 word constraint and referral consent gate.
5. Probation → Linh → peer summary → manager ratings, 1:1 and recommendation → HR review → outcome preview. Dewi → nominate 3–4 peers.
6. Holiday Calendar → entity filters, month navigation, country comparison → Import review → resolve both discrepancies → publish demo.

`REQUIREMENTS.md` records source coverage, assumptions and production implementation mapping. `TESTING.md` records checks. `public/og.png` is a generated product social card, not a testing screenshot; preserve it.
