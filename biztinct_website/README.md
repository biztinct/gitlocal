# Biztinct public website (Odoo 14)

This module serves Biztinct's public home, solutions, approach, contact and
privacy and account sign-in pages. Authentication is delegated to the original
Odoo controller; its login form uses the new brand layout and preserves return
destinations. Its activation is restricted to the website whose domain
contains `biztinct.com`; the selected website ID is saved in
`biztinct_website.website_id`. The other website and the business application
remain on their existing routes. Legacy service URLs redirect to relevant
sections of the new solutions page.

## Runtime and deployment scope

Target: SSH `Biztinct`, 54.206.115.180, Odoo **14.0**, database **biztinctprod**.
Deploy this whole module to `/odoo/odoo-server/addons/biztinct_website`.
The other custom modules in the shared checkout target Odoo 19 and are not
installed in this environment. Never replace this server's standard addons
with the vendored snapshots in the shared repository. Preserve its existing
theme modules, source modifications and the concurrent Payobook work.

Take a database and server-configuration backup, install and test on a
mail-disabled restored database, then install/upgrade this module on
`biztinctprod` with the service stopped and restart it. Recheck HEAD and
working-tree status immediately before packaging the latest combined module
state. Verify source hashes, installed version and both the HTTPS hostname
and direct IP endpoint. Run Chrome checks against production after deployment.
The publish script uses install only for a new module and update for an installed
module, preserving noupdate SMTP settings entered by the administrator.

## Contact delivery

Enquiries are stored first as `biztinct.contact`, with administrator-only ACLs.
They use CSRF protection, server validation, a honeypot and a transactional
five-enquiries-per-ten-minutes network limit. User content is escaped for mail.
The visitor cannot choose the sender, recipient or SMTP server.

The dedicated mail server is preconfigured for `smtp.gmail.com`, port 587,
STARTTLS, username `ash@biztinct.com`. No password is stored in source or logs.
It starts inactive. `biztinct_contact_only` excludes it from default SMTP
selection, so enabling it cannot release the existing unrelated mail backlog.
A minute-based cron queues and delivers saved enquiries once this server is
active and has a password, selecting only this site's dedicated mail server.
It does not release the general mail backlog. Queued mail is
retained for delivery-state inspection. The visitor's email is the Reply-To.
Test Connection probes ash@biztinct.com as both sender and recipient, without
sending a message, so it is independent of the administrator's old placeholder
profile address. Other outgoing servers retain their standard connection test.
The dedicated Gmail connection uses one AUTH LOGIN exchange over verified TLS.
This preserves Gmail's credential rejection instead of Python's automatic
authentication fallback masking it as an unexpected disconnect. Rejections
show the SMTP code and instructions to create an App Password in the correct
Google account; passwords and SMTP authentication exchanges are never logged.
Correcting credentials or reactivating the configured server retries failed
notifications linked to saved website enquiries. Unrelated mail is not retried.

Administrator screens (HTTPS):

- `https://biztinct.com/biztinct/mail-setup` redirects to the dedicated outgoing
  server form. Sign in as a system administrator (existing login: `adminbiz`).
  Enter a Google **App Password**, Save, Test Connection, switch Active on,
  then Save. Use the Google account for **ash@biztinct.com**, rather than one
  of the other signed-in Gmail accounts. Normal Gmail passwords are not
  supported for this connection. App Password creation requires two-step
  verification and may be controlled by the Workspace administrator.
- `https://biztinct.com/biztinct/enquiries` opens the saved enquiries.
- Standard Settings → Technical → Email → Emails shows delivery states.

Google instructions: https://support.google.com/a/answer/176600 and
https://support.google.com/mail/answer/185833.

Use nginx's loopback upstream and correct forwarded headers, with Odoo proxy
mode, so HTTPS URLs and the real client address are retained. Credential entry
must use the HTTPS hostname.
The service is pinned to `biztinctprod` through `db_name` and `dbfilter`, so
temporary restored QA databases cannot change public routing.

## Design and assets

The lightweight public pages use self-hosted Manrope and Instrument Serif
fonts (OFL licenses in `static/src/fonts`). The homepage uses a typography-led layout with interactive canvas particles spelling
Biztinct and a soft mist/glow behind the text, inspired by the supplied 21st.dev
particle-text-canvas example. Its former abstract artwork and floating messages
have been removed from the homepage and shared call to action. The existing
illustrations on other pages remain available. The effect renders at 30 fps,
sleeps when hidden or offscreen, uses local pointer coordinates, and resamples
after fonts load or its container changes size. Reduced-motion and data-saving
preferences show the readable gradient text fallback.

This is an Odoo QWeb site, not a React/shadcn/TypeScript application. Components
are QWeb templates in `views/templates.xml`; styles are in `static/src/css`.
The native component lives in `static/src/js/particle-text-canvas.js`, so no
React, Tailwind, shadcn CLI or build pipeline is required. In a separate React
project the reusable TSX component would belong in `components/ui` (or
`src/components/ui` with the corresponding `@/` alias); that convention does
not apply to this server-rendered Odoo module.

Service cards have
pointer tilt and lighting; sections reveal on scroll, with a moving capability
strip and animated workflow states. Reduced-motion and data-saving
preferences disable unnecessary effects. No animation is required to use the
site. The original Biztinct logo and favicon are preserved; explanatory workflow diagrams use SVG/CSS.
Workflow illustrations are labelled as examples, not live
customer data. No invented testimonials, client logos or performance claims.
Links, native forms and FAQ disclosures work without JavaScript. Animations
respect reduced-motion preferences. Fonts and scripts load from this server;
the public pages have no third-party trackers.

## Tests

Run the module's Odoo tests on a restored, mail-disabled database with
`--test-enable --test-tags /biztinct_website --stop-after-init`.
They cover credential gating, fixed recipients, HTML escaping, duplicate
notification prevention, SMTP isolation and public access restrictions.
HTTP checks cover CSRF, validation, abuse limiting, legacy redirects and the
production contact-to-database flow. Inspect desktop and mobile Chrome views,
navigation, FAQ and submission confirmation. Test screenshots must stay in
memory or be removed before completion.

The original Biztinct logo and favicon are byte-for-byte copies of the existing website assets. The logo is displayed without recolouring, filters or altered proportions; a white backing preserves its legibility on the dark theme.
