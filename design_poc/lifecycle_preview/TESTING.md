# Preview validation

## Build

- `npm run build`: passed.
- `npx tsc --noEmit`: passed.
- Source reconciliation: extracted Indonesia 18, Vietnam 13, Singapore 11, India 13 dates; source conflicts represented explicitly.

## Chrome UI checks on local preview

- Existing live Payobook Lifecycle screen inspected for theme and workflow context.
- Desktop visual inspection: hierarchy, indigo palette, sidebar, journey, overview and modal layouts checked.
- Hiring request: populated role definition and all three interview rounds, reviewed budget and approver, submitted demo request and navigated to roles.
- Candidate: opened Maya, moved from Panel Review to Recruiter Phone Call with required reason, confirmed updated stage and reset stage age.
- Probation: completed manager 1:1, strengths and development fields; submitted to HR; simulated approval; outcome action became available.
- Holiday: publish disabled before reconciliation; chose country sheet for Indonesia and combined sheet for Vietnam; publishing enabled and success state displayed.
- Email: edited subject with tokens; preview rendered “Hello Maya from Rize”; switched to on-hold template and verified resolved context.
- Generic branding: switched workspace to Acme; referral entity choices became Acme Singapore/Vietnam/Indonesia/India.

## Limits

No production backend, email, uploads, calendar or signature integration tested; those are intentionally simulated in this design preview. The social preview PNG is a product asset. Browser screenshots were emitted directly for inspection without saving testing screenshot files.

Additional Chrome checks passed: referral consent set to No disables submission; two peer selections disable confirmation; mobile breakpoint at 390 × 844 has no page-level horizontal overflow, and navigation/steps scroll within their containers. Temporary viewport restored.
