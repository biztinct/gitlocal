# Builds "Rize Recruit - Traceability Matrix.xlsx" from RIZE/Zoho Recruit.xlsx.
# Client-facing: plain words, screen names, no internal codes, never the word "Odoo".
import copy
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

SRC = '/Users/adity/Documents/GitHub/gitlocal/RIZE/Zoho Recruit.xlsx'
OUT = '/Users/adity/Documents/GitHub/gitlocal/RIZE/Rize Recruit - Traceability Matrix.xlsx'

# ---------------------------------------------------------------- phrases
HIRING = ('Open Hiring: click the search bar at the top of the screen (or press Ctrl+K / ⌘K), '
          'type “hiring” and choose “Who we are hiring”.')
HIRING_REC = HIRING[:-1] + ' (Recruiters can also use the left menu: Operate › Lifecycle.)'
ROLE = 'On the “Roles” tab, find the role (for example DEMO Territory Manager) and press “Review candidates”.'
SETUP = 'Press “Set up hiring” at the top of the Hiring screen.'
CAND = 'Click a person\'s card on the board to open it.'
DETAILS = 'Open the “Details” tab of the role'

def steps(*xs):
    return '\n'.join(f'{i}. {x}' for i, x in enumerate(xs, 1))

YES, PART, NOTNOW, RIZE = 'Yes', 'Partly', 'Not now (agreed)', "Rize's side"
BUILT = 'Built for Rize in Payobook'
HAVE = 'Already in Payobook'
PARTB = 'Built; the rest follows later'
DEFER = 'Left out by agreement'

TL, REC, HM, AG, CA, EMP = ('Talent lead', 'Recruiter', 'Hiring manager', 'Agency',
                            'Candidate (no sign-in)', 'Any employee')

# ---------------------------------------------------------------- the REC lines
# ref: (supported, solution type, try it as, clicks, comments)
R = {
'REC-005': (YES, BUILT, TL, steps(
    'Sign in as the Talent lead.', HIRING, SETUP,
    'On the “Application forms” card press “Go”.',
    'Pick a form on the left (for example “Standard”).',
    'Use “Add a question”, drag a question to reorder it, click a question to rename it or make it required, or press “Remove”.',
    'The page the candidate will see is drawn live beside the editor. Press “Save”.',
    'For one role only: open the role, ' + DETAILS + ' › “Advert & publishing” › “Application form” › “Edit”.'),
    'Each role works on its own copy of a template, so changing one role never changes another. '
    'Ready-made templates: Standard, Field roles, Senior roles and Tech roles; you can save your own. '
    'No limit on the number of questions. Name, email and consent are always asked: they can be renamed, not removed.'),
'REC-036': (YES, BUILT, CA + ' / ' + TL, steps(
    'As a candidate: go to payobook.com/jobs, open a role (for example DEMO Territory Manager) and press “Apply Now!”.',
    'Use the language buttons at the top of the form: English, Tiếng Việt, Bahasa Indonesia.',
    'As the Talent lead: ' + SETUP + ' Then “Application forms” › “Go” › click a question: the Vietnamese and Bahasa Indonesia wording sits with the English.'),
    'The role\'s country chooses the first language (Vietnam → Vietnamese, Indonesia → Bahasa Indonesia); the candidate can switch. '
    'The confirmation email goes in the language they applied in.'),
'REC-006': (YES, BUILT, REC, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE,
    'The “Board” tab shows one column per stage and one card per person.',
    'Drag a card to another column, or press “Advance” on the card.',
    'To move several people: tick the box on each card (shift-click selects a range), then choose where they go.'),
    'Every move can be undone for 5 seconds. The count on each column updates as you move people.'),
'REC-007': (YES, BUILT, TL, steps(
    'Sign in as the Talent lead.', HIRING, SETUP,
    'In “Stages”: click a name to rename it everywhere; drag the handle to reorder.',
    'Below the list, presets decide which columns a new role shows for each department and country.',
    'On one role\'s board, “Show a hidden stage” brings back a column hidden for that role.'),
    "Rize's stage words are the default (Applications received, Shortlist, Hiring manager review, Recruiter review, Assignment, Discussion 1–3, Offer, Post-offer…). "
    'The Talent lead changes them without raising a ticket.'),
'REC-008': (YES, BUILT, REC + ' / ' + HM, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE, CAND,
    'Press “Share with…”, choose the person and tick what they may see: profile, CV, portfolio, answers, scorecards, expected pay.',
    'The default for a whole role: ' + DETAILS + ' › “Request & role” › “What the hiring manager sees by default”.',
    'Sign in as the Hiring manager to see the result: only their roles, a “Shared with you” list, and no Resume bank.'),
    'A candidate is private to the hiring team until a recruiter shares them. Expected pay is its own tick. '
    'Panel members see only their own interview; scorecards stay hidden from each other until all are in. Agencies see only their own portal.'),
'REC-035': (YES, BUILT, REC + ' / ' + TL, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE,
    'Drag any card to any column. Nothing stops the move or waits for a sign-off.',
    'Sign in as the Talent lead and press “Set up hiring”: stages, forms, scorecards, emails and automations are all changed here, without a ticket.'),
    'One rule only, agreed on the 28 Sep call: an offer cannot be sent until the role\'s hiring request is agreed; the message names who presses “Agree”. '
    'All other sign-offs are recorded and announced, never blocking. Only recruiters and the talent lead move people; hiring managers view and comment (a switch can widen this; it is off).'),
'REC-028': (YES, HAVE, REC, steps(
    'Sign in as the Recruiter.', HIRING_REC,
    'Press “Hiring tools” › “Cover for me”.',
    'Choose the colleague, the dates and the reason, then send it.',
    '“Hiring tools” › “Covers” shows who is covering for whom.'),
    'Agreed by the recruiter\'s own manager, logged, and ends by itself on the last date. Both people are emailed.'),
'REC-009': (YES, BUILT, HM, steps(
    'Sign in as the Hiring manager.', HIRING,
    'Press “Raise a hiring request”.',
    'Fill in each step: role, department, country, reason, how many, reporting manager, the interview rounds, budget, target date. Send it.',
    'The Confidential switch is on the role: ' + DETAILS + ' › “Request & role” › “Confidential”.'),
    'The request cannot be sent until the required fields are filled. Agreed on the call: a recruiter may open a role and start meeting candidates before the request exists; '
    'the request only has to be agreed before an offer is sent.'),
'REC-034': (YES, BUILT, REC + ' / ' + HM, steps(
    'Sign in as the Recruiter.', HIRING_REC,
    'Press “Ask a manager for a request”, fill in the role and choose the manager, then send it.',
    'The manager gets one page by email (no sign-in needed). It saves as they type; sending it in is their agreement.',
    'To nudge them yourself: press “Remind now” on the role\'s row.'),
    'Reminders go automatically until the manager sends it in. The talent lead is told after 3 working days.'),
'REC-010': (YES, BUILT, HM + ' / ' + REC, steps(
    HIRING_REC, ROLE, DETAILS + ' › “Request & role”.',
    'The top banner says “Within budget” or “Over budget”. Below: the manager\'s expected figure, “Confirmed with Finance”, the budget conversation (Not yet / Agreed / Declined) and who is told.',
    'The Hiring screen shows an “Over budget” number at the top; press it to see those roles.'),
    'Over budget never stops the role. The people named in “Set up hiring” › “Who does what” (for example CEO, Head of HR, Finance) get an email and a to-do.'),
'REC-011': (YES, HAVE, 'Head of hiring', steps(
    'The country-to-recruiter list: search bar › type “hiring rules” › open “Hiring rules” (Head of hiring).',
    'On the Hiring screen each role row shows who recruits it (for example “DEMO Recruiter recruits”).'),
    'The recruiter for the role\'s country is named the moment the role exists, and the recruiter and their manager are emailed. '
    'There is no Head of hiring demo sign-in; we can show this screen on a call. Tell us if the talent lead should also be copied.'),
'REC-012': (YES, BUILT, REC, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE,
    DETAILS + ' › “Advert & publishing” › “The advert”.',
    'Choose “From a template…” (Field roles, Sales roles, Tech roles, Finance roles) and press “Start”, or “Write one”.',
    'Share it with the manager for comments, then make it final. Older versions stay readable.'),
    'No sign-off gate, as agreed. The manager comments through an emailed link. All versions are kept with the role.'),
'REC-013': (YES, BUILT, EMP + ' / ' + REC, steps(
    'Sign in with any demo login and go to payobook.com/my/refer.',
    'Press “Refer for this role” next to a role and fill in the short form.',
    'Recruiter: on the role, ' + DETAILS + ' › bottom of the page › “Close to referrals” to stop referrals.'),
    'Referrals open by themselves when the role goes live. Confidential roles never appear. '
    'Referred people arrive tagged “Referral”. The email to every colleague is ready and switched off until Rize wants it.'),
'REC-014': (YES, BUILT, REC, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE,
    'Press “Publish to…” at the top of the role.',
    'Each channel (Careers page, LinkedIn, JobStreet, VietnamWorks…) has its own tracked link and a count of applications.',
    'Careers page: “Publish on the careers page”. Other boards: “Copy the advert”, paste it on the board with the link, then “Mark as posted”.',
    'Channels are added in “Set up hiring” › “Channels” (Talent lead).'),
    'The careers page publishes directly. LinkedIn and the job boards are not connected yet: the advert is pasted by hand, '
    'but every application is still counted under its channel. Direct posting needs board accounts from Rize.'),
'REC-030': (YES, BUILT, AG + ' / ' + REC, steps(
    'Sign in as the Agency: the Agency portal opens by itself.',
    'Press “Put someone forward” on a role and send the person.',
    'Recruiter: on the role, ' + DETAILS + ' › “Request & role” › “Agencies” › “Add an agency”.',
    'Talent lead: “Set up hiring” › “Agencies” (agencies, their sign-ins, the 6-month rule).',
    'Performance: search bar › “Hiring numbers” › “An agency, or our own team”.'),
    'The agency sees only its own roles and a simple status: no notes, no pay, no other candidates. '
    'Anyone already with us, or who applied in the last 6 months, is not accepted. The hiring manager is emailed when a role goes to an agency.'),
'REC-001': (YES, BUILT, CA + ' / ' + TL, steps(
    'As a candidate: payobook.com/jobs › a role › “Apply Now!”: expected monthly pay is one of the questions.',
    'Talent lead: “Set up hiring” › “Application forms” › “Go” › the expected pay question › make it required or optional.',
    'Recruiter: open the person\'s card; the figure is there and carries into the offer.'),
    'Seen only by the hiring team (a recruiter can share it with a hiring manager as its own tick).'),
'REC-002': (YES, BUILT, CA + ' / ' + TL, steps(
    'Talent lead: “Set up hiring” › “Application forms” › “Go” › the portfolio question › make it required for that form.',
    'As a candidate: the form will not send without it. A file or a link is accepted.'),
    'Required per form, so only the roles that need it ask for it.'),
'REC-003': (YES, HAVE, REC, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE,
    'A new card shows “First look”: Shortlist, CV reject, Future-fit or Fit for other role.',
    'For senior or new roles, move the person to “Hiring manager review” and share them with the manager first.'),
    'Both routes are ready. Please confirm which roles start with the hiring manager.'),
'REC-004': (YES, BUILT, REC, steps(
    HIRING_REC, ROLE,
    'Each card shows when and where the person applied (for example “Applied 3 days ago · LinkedIn”).',
    CAND + ' “Applied” and the “Timeline” section are near the top.'),
    'Same timeline as REC-031.'),
'REC-015': (YES, BUILT, REC, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE,
    'Tag a person from “First look” on the card, or open the person and use “Tag them”.',
    'Back on the Hiring screen, open the “Resume bank” tab. Narrow by skill, country, team, tag or source; “Add to a role” puts a person on another role.',
    'Sign in as the Hiring manager to see that the Resume bank tab is not there.'),
    'Future-fit people stay in the Resume bank until their keep-until date.'),
'REC-031': (YES, BUILT, REC, steps(
    HIRING_REC, ROLE, CAND,
    'Scroll to “Timeline”: applied, every move with who and when, interviews, emails (with the language they went in), notes and offer events.',
    'The role\'s own history: the “Activity” tab of the role.'),
    'Private recruiter notes are kept out of the timeline on purpose (see REC-037).'),
'REC-016': (YES, BUILT, REC, steps(
    'Sign in as the Recruiter.', HIRING_REC, ROLE, CAND,
    'Press “Arrange an interview”: choose the round, the panel, the time and the place or video link.',
    'Press “Arrange it and invite everybody”. Candidate, panel and recruiter each get an invitation in their own time zone.',
    'Google Calendar: “Set up hiring” › “Who does what” (each recruiter connects their own calendar).'),
    'The automatic Meet link and the holds in the recruiter\'s Google Calendar start once Rize\'s Google admin approves the connection. '
    'On the demo, paste a video link instead. Each interview has a place for the recording or transcript link.'),
'REC-017': (YES, HAVE, 'Automatic', steps(
    'Nothing to press: the day-before and 30-minute reminders go by themselves.',
    'To switch them off: Talent lead › “Set up hiring” › “Automations” › the built-in list.'),
    'Sent to candidate, panel and recruiter. The candidate\'s copy is in their language. SMS is not included.'),
'REC-018': (YES, HAVE, REC, steps(
    HIRING_REC, ROLE, 'Open the “Interviews” tab of the role.',
    'Press “Move it” on the interview, pick the new time, give the reason and say whose side moved it.'),
    'Old and new times are both kept, and short notice is flagged. Totals: “Hiring numbers” › “Interviews that moved”.'),
'REC-019': (YES, BUILT, REC, steps(
    HIRING_REC, ROLE, 'Open the “Interviews” tab of the role.',
    'Press “Done” or “Nobody came” (then say who did not come).',
    'Moving someone past an interview that has no outcome asks “Log how the interview went?”.'),
    'Agreed: the system asks for the outcome but never blocks the move. A no-show gives the recruiter a to-do.'),
'REC-020': (YES, BUILT, 'Panel member / ' + REC, steps(
    'Each panel member gets an email with a private link to their scorecard (no sign-in).',
    'Recruiter: role › “Interviews” tab › “<name>: enter it for them” to type in an opinion given by phone or chat.',
    'The Hiring screen shows “Opinions late” at the top.',
    'Scorecards themselves: Talent lead › “Set up hiring” › “Scorecards”.'),
    'Due within 24 working hours; late opinions are chased every day. Panel members cannot see each other\'s answers until all are in.'),
'REC-021': (YES, BUILT, REC, steps(
    HIRING_REC, ROLE,
    'On a card press “Advance”, or “Not this time”.',
    '“Not this time” asks CV reject or Interview reject, and has a tick for “send the email”.',
    'The email words: Talent lead › “Set up hiring” › “Emails and languages”.'),
    'Separate emails for CV reject and Interview reject, in English, Vietnamese and Bahasa Indonesia.'),
'REC-037': (YES, BUILT, REC, steps(
    HIRING_REC, ROLE, CAND,
    'In “Recruiter notes” press “Add a private note”.',
    'To let one hiring manager read a note, pick their name under the note.'),
    'Only the author and the talent lead read these notes. They never appear on the timeline.'),
'REC-022': (YES, BUILT, REC + ' / ' + HM, steps(
    HIRING_REC,
    'Open a role that has finalists (for example DEMO Site Agronomist › “Review candidates”).',
    'Press “Compare finalists” at the top: every scorecard side by side.',
    'For each person press “Choose”, “Keep warm” or “Not this time”.',
    'Also on the role\'s “Interviews” tab: “Debrief”.'),
    'When the role is filled, the other finalists are closed and told automatically (a switch the talent lead controls).'),
'REC-023': (YES, BUILT, REC, steps(
    HIRING_REC, ROLE, DETAILS + ' › “Offer & joining”.',
    'Under “The offer”, press the “Background” step for the chosen person.',
    'Fill in each check line and attach documents.'),
    'Runs alongside the offer and never blocks it. Anything adverse is flagged to the Head of HR the same day; the recruiter gets a to-do when a check starts. '
    'Check lines: search bar › “What a background check covers”.'),
'REC-024': (YES, HAVE, REC + ' / ' + CA, steps(
    HIRING_REC, ROLE, DETAILS + ' › “Offer & joining”.',
    'Press the “Documents” step, then “Ask for their papers”.',
    'The candidate gets a secure upload page by email; the checklist on the same step fills in as files arrive.'),
    'Two working days, a reminder each day, and the talent lead is told when it is late. The list asked for: search bar › “What a joiner is asked for”. '
    'It is sent when the recruiter presses it, so it can go before or after the check is clear.'),
'REC-025': (YES, BUILT, REC, steps(
    HIRING_REC, ROLE, DETAILS + ' › “Offer & joining”.',
    'Press the “Offer” step, then “Draft the offer”: pay lines (pay, statutory, benefits, variable; monthly, yearly or one-off) with totals and currency.',
    'Press “Send for sign-off”: the hiring manager and HR are told and their answer is recorded.',
    'Press “Send it to them” when ready.'),
    'Sign-offs are recorded and announced, never blocking. The one hard rule: the role\'s hiring request must be agreed first. '
    'Pay is hidden from everyone except the people who must see it.'),
'REC-026': (PART, PARTB, REC, steps(
    HIRING_REC,
    'Open DEMO Territory Manager › “Review candidates” and click Cao Minh Khoa (in “Post-offer”).',
    'In “Signed documents”, the papers usually signed in that country are listed (Vietnam: signed offer letter, probation letter).',
    'Press “Add a signed document” to file each signed copy.'),
    'Agreed on the call: offers are signed outside the system for now and the signed copies are filed here, several per person. '
    'Letters generated by the system and e-signature (DocuSign) follow once Rize shares its letter templates.'),
'REC-027': (YES, BUILT, REC, steps(
    'Nothing to press when the offer is signed: the hiring manager and talent lead are told and the “Before they join” list starts.',
    'To see it: ' + HIRING_REC, 'Open DEMO Territory Manager › “Review candidates” › click Cao Minh Khoa.',
    '“Before they join”: buddy, laptop preferences, meet-the-team chat, first-day details.',
    'On the first day press “Confirm they joined” (this creates the employee), or “Did not join” with a reason.'),
    'Agreed on the call: “signed” and “joined” are two separate moments; the person stays a candidate with the recruiter until they join. '
    'Other finalists are closed and told automatically when nobody else is needed.'),
'REC-033': (YES, BUILT, CA + ' / ' + TL, steps(
    'As a candidate: the application form has a required consent tick, in the form\'s language.',
    'Talent lead: “Set up hiring” › “Consent & retention”: months to keep, per country; preview of what a clean-up would remove.',
    'On a person\'s card: “Kept until …” and “Keep 12 more months”.'),
    'The automatic clean-up stays off until the Head of hiring switches it on.'),
'REC-032': (YES, BUILT, TL, steps(
    'Sign in as the Talent lead.', HIRING, SETUP,
    'Open “Emails and languages” and pick an email.',
    'Switch between English, Tiếng Việt and Bahasa Indonesia and edit the words.',
    '“Preview email” shows it as the candidate will see it; “Send me a test”; “Reset to the standard text” undoes your changes.'),
    'All 16 emails a candidate receives have three language versions. Emails to colleagues are in English. India and Singapore use English.'),
'REC-029': (YES, BUILT, TL, steps(
    'Sign in as the Talent lead.',
    'Search bar › type “hiring numbers” › open “Hiring numbers”.',
    'Choose the period (Last 30 days … Last year) and narrow by department, country or recruiter.',
    '“Download this report” on any section, or “Download everything”, gives an Excel file.'),
    'Time to fill, time to offer, time in each stage, offers accepted, where candidates came from, whose side moved interviews.'),
}

# ---------------------------------------------------------------- other tables
NOTIF = {  # trigger -> (in Payobook?, where to see or change it, comment)
 'MR submitted': ('Yes', 'Role › “Details” › “Request & role” (who was told, who agreed)', 'Reminders and escalation run by themselves.'),
 'Budget approved / MR assigned': ('Yes', 'Role row on the Hiring screen (“… recruits”)', 'Recruiter and their manager are emailed with a to-do.'),
 'JD ready for approval': ('Yes, as “ready for input”', 'Role › “Details” › “Advert & publishing”', 'No approval gate (REC-012): the manager is asked for comments.'),
 'Referral opened': ('Ready, switched off', '“Set up hiring” › “Automations” (built-in list)', 'The email to every colleague is off until Rize wants it; the referral page itself opens automatically.'),
 'Application received': ('Yes', '“Set up hiring” › “Emails and languages”', 'Only Rize\'s own confirmation goes out, in the candidate\'s language.'),
 'Interview scheduled': ('Yes', 'Person › “Arrange an interview”', 'Invitation with calendar file to everybody, in each person\'s time zone.'),
 'Interview reminder (24h)': ('Yes', '“Set up hiring” › “Automations” (built-in list)', 'SMS not included.'),
 'Interview reminder (30 min)': ('Yes', '“Set up hiring” › “Automations” (built-in list)', 'SMS not included.'),
 'Feedback pending': ('Yes', 'Role › “Interviews” tab', 'Chased every day until it is in.'),
 'Feedback overdue': ('Yes', '“Opinions late” number at the top of the Hiring screen', ''),
 'Candidate advanced': ('Yes', '“Set up hiring” › “Emails and languages”', ''),
 'Candidate rejected': ('Yes', 'Person › “Not this time” (tick “send the email”)', 'Separate CV reject and Interview reject emails.'),
 'BGV started': ('Yes', 'The recruiter\'s to-do list', ''),
 'Document request': ('Yes', 'Role › “Details” › “Offer & joining” › “Documents”', 'Two working days, daily reminders, talent lead told when late.'),
 'Offer approval request': ('Yes', 'Role › “Details” › “Offer & joining” › “Offer” › “Send for sign-off”', 'Recorded and announced, never blocking.'),
 'Offer sent for signature': ('Yes', 'Role › “Details” › “Offer & joining” › “Offer”', 'Signing happens outside the system for now (REC-026).'),
 'Offer signed / position closed': ('Yes', 'Person card › “Before they join”', '“Signed” and “joined” are separate moments.'),
 'Delegation activated': ('Yes', '“Hiring tools” › “Covers”', ''),
 'Agency role assigned': ('Yes', 'Role › “Details” › “Request & role” › “Agencies”', ''),
 'No-show logged': ('Yes', 'Role › “Interviews” tab › “Nobody came”', 'Creates a to-do for the recruiter.'),
 'Reschedule requested': ('Yes', 'Role › “Interviews” tab › “Move it”', ''),
 'MR request pending HM completion': ('Yes', 'Role row › “Remind now”', 'Automatic reminders; talent lead told after 3 working days.'),
}
TEMPL = {
 'Manpower Requisition Form': ('Yes', '“Raise a hiring request” (hiring manager) or the emailed request page', ''),
 'JD Template (by role family)': ('Yes', 'Role › “Details” › “Advert & publishing” › “From a template…”', 'Field, Sales, Tech and Finance templates ready.'),
 'Offer Letter (per country)': ('Partly', 'Role › “Details” › “Offer & joining” › “Offer”', 'Pay lines and totals are built; generated letters follow once Rize shares its templates.'),
 'Rejection Email (by stage)': ('Yes', '“Set up hiring” › “Emails and languages”', 'CV reject and Interview reject, three languages.'),
 'Interview Feedback Form (by round)': ('Yes', '“Set up hiring” › “Scorecards”', 'Per kind of role and per round.'),
 'BGV Template': ('Yes', 'Search bar › “What a background check covers”', ''),
 'Document Request Checklist': ('Yes', 'Search bar › “What a joiner is asked for”', ''),
 'Interview Invite + Agenda': ('Yes', '“Set up hiring” › “Emails and languages”', ''),
 'Closure Summary': ('Yes', '“Hiring numbers” › “From offer to joined”', ''),
 'Referral Announcement': ('Ready, switched off', '“Set up hiring” › “Automations”', 'Off until Rize wants it.'),
}
DASH = {
 'Recruiter Workbench': (REC, steps(HIRING_REC, 'The numbers at the top and the four steps (Set up, Prepare & publish, Meet your candidates, Welcome aboard) show the workload; press any of them to narrow the list.'), ''),
 'TA Lead Overview': (TL, steps('Search bar › type “hiring numbers” › open “Hiring numbers”.'), ''),
 'Hiring Manager View': (HM, steps('Sign in as the Hiring manager.', HIRING, 'Only their own roles and a “Shared with you” list.'), ''),
 'Leadership Pipeline': (TL, steps('Search bar › “Hiring numbers”.', 'Scroll to “For leadership”: fill rate, people still to hire, roles open, days to fill by month, by country, sources.'), ''),
}
REPORTS = {
 'Time to Fill / Time to Offer': ('“Hiring numbers” › the numbers at the top', ''),
 'Source Effectiveness': ('“Hiring numbers” › “Where they came from”', ''),
 'Offer Acceptance Rate': ('“Hiring numbers” › “From offer to joined”', 'Offered → accepted → signed → joined, with every drop and its reason.'),
 'Pipeline Ageing': ('“Hiring numbers” › “Who has been waiting longest” (“Only the stalled”)', ''),
 'No-Show Report': ('“Hiring numbers” › “Interviews that moved” (no-shows are listed under the moves)', ''),
 'Delay Analysis (Internal/External)': ('“Hiring numbers” › “Interviews that moved”', 'Our side / the candidate\'s side.'),
 'Agency Performance': ('“Hiring numbers” › “An agency, or our own team”', ''),
 'Requisition Status Report': ('The Hiring screen › “Roles” tab (filter by status, department, country, recruiter)', 'Tell us if you also want this as its own Excel download.'),
}
OQ = {
 'OQ-01': 'Not needed in Payobook. Every role has its own board, and the stages each role shows are set per department and country.',
 'OQ-02': 'No edition limits on pipelines or stages in Payobook.',
 'OQ-03': 'No field cap. The talent lead adds as many questions as a role needs (REC-005).',
 'OQ-04': 'Yes. Every role opens as a drag-and-drop board (REC-006).',
 'OQ-05': 'Yes. Pay and offers are hidden from everyone who does not need them; recruiters choose what each hiring manager sees (REC-008).',
 'OQ-06': 'Yes. Panel members cannot see each other\'s scorecards until all are in (REC-020).',
 'OQ-07': 'Yes. Agencies have their own portal: their roles and their people only (REC-030).',
 'OQ-08': 'Yes. Every candidate email in English, Vietnamese and Bahasa Indonesia; India and Singapore use English. SMS is not included (REC-032).',
 'OQ-09': 'Consent tick on every application; months to keep per country; a clean-up with a preview, off until the Head of hiring switches it on (REC-033).',
 'OQ-10': 'Google Calendar and Meet: built, waiting for Rize\'s Google admin. LinkedIn and job boards: tracked links, advert pasted by hand. E-signature: later. SMS: not included.',
 'OQ-11': 'Yes. The talent lead changes stages, forms, scorecards, emails and automations in “Set up hiring”, without a ticket.',
}
ROLES_T = {
 'Candidate': 'Yes: careers page and emailed links, no login.',
 'Recruiter': 'Yes: demo sign-in “Recruiter”.',
 'TA Lead': 'Yes: demo sign-in “Talent lead”; owns “Set up hiring”.',
 'Head of HR': 'Yes, as “Head of hiring” (no demo sign-in).',
 'Hiring Manager': 'Yes: demo sign-in “Hiring manager”. Views and comments; does not move candidates (agreed).',
 'Finance': 'Yes: a sign-off seat on requests and offers; told about over-budget roles.',
 'Interviewer': 'Yes: a private link per interview; scorecards hidden until all are in.',
 'External Agency': 'Yes: demo sign-in “Agency”; submit only.',
}
UI_T = {
 'Move a candidate': 'Done: drag on the board, “Advance”, or tick several and move them together.',
 'See the pipeline': 'Done: a live board per role with counts per column.',
 'The lock': 'Done: nothing locks; the only rule is that an offer needs an agreed request.',
 'Change the stages': 'Done: “Set up hiring” › “Stages”, by the talent lead.',
 'The application form': 'Done: a form per role, three languages, “Set up hiring” › “Application forms”.',
 'Read the numbers': 'Done: “Hiring numbers”, filterable by market.',
}
EXC = {
 'MR exceeds approved budget': 'Changed by agreement: flagged and announced, never held (REC-010).',
 'HM does not approve JD in time': 'No approval gate any more; manager comments are optional (REC-012).',
 'Agency-run role': 'Yes: agency portal, recruiter owns all communication (REC-030).',
 'Confidential / sensitive replacement': 'Yes: Confidential switch hides the role from referrals, adverts and lists.',
 'Duplicate application': 'Yes: “Possibly the same person” is flagged on the card with a link to the earlier application.',
 'Candidate or interviewer no-show': 'Yes: the outcome is asked for, never blocking (REC-019).',
 'Late or repeated reschedule': 'Yes: reason, whose side, short-notice flag (REC-018).',
 'Candidate withdraws': 'Yes: “Drop-out” with a reason.',
 'Candidate declines offer': 'Yes: “Offer drop” with the candidate\'s reason; the role stays open.',
 'Adverse BGV result': 'Yes: flagged to the Head of HR the same day; the offer is not blocked.',
}
ASSESS_NOTE = 'Not built, as agreed on the 28 Sep call. Screening questions go in the application form instead.'
ROUNDS_NOTE = 'Yes: set per role in “Details” › “Request & role” › “Rounds and scorecards”.'

# ---------------------------------------------------------------- added requirements
ADDED = [
 # (ref, source, area, requirement, supported, type, try as, clicks, comments)
 ('MH-01', 'Original - Must Haves', 'Hiring & Recruitment › MR Notification',
  'Based on the selected country, the assigned recruiter and the recruiter\'s manager are notified (email + portal).',
  YES, HAVE, REC + ' / Head of hiring', R['REC-011'][3], 'The recruiter and their manager are both emailed and given a to-do the moment the role exists.'),
 ('MH-02', 'Original - Must Haves', 'Hiring & Recruitment › JD Finalization',
  'Recruiter drafts the JD, gets hiring manager approval and stores it in a central folder.',
  YES, BUILT, REC, R['REC-012'][3], 'The Zoho Recruit sheet (REC-012) later removed the approval step; Payobook follows that: the manager comments, no sign-off gate. Every version is kept with the role.'),
 ('MH-03', 'Original - Must Haves', 'Hiring & Recruitment › Job Posting',
  'Posting templates; publishing to LinkedIn and job portals from the portal.',
  YES, BUILT, REC, R['REC-014'][3], 'Advert templates per kind of role. Boards are pasted by hand until Rize provides board access; applications are still counted per channel.'),
 ('MH-04', 'Original - Must Haves', 'Hiring & Recruitment › Background Verification',
  'BGV required before the offer draft.',
  YES, BUILT, REC, R['REC-023'][3], 'Changed by the Zoho Recruit sheet (REC-023): the check runs alongside the offer and never blocks it. Adverse results go to the Head of HR the same day.'),
 ('MH-05', 'Original - Must Haves', 'Hiring & Recruitment › Offer Preparation',
  'Salary file → hiring manager review → final offer draft → candidate review. Country-wise offer templates; salary calculator; approval workflow.',
  YES, BUILT, REC + ' / ' + CA, R['REC-025'][3] + '\n5. The candidate gets a private page to read the offer and accept or decline it.',
  'Pay lines with totals per currency; sign-offs recorded, never blocking. Generated letters per country follow once Rize shares its templates.'),
 ('MH-06', 'Original - Must Haves', 'Hiring & Recruitment › Closure Notification',
  'Once signed, the position is marked closed; hiring manager and recruiter\'s manager notified.',
  YES, BUILT, REC, R['REC-027'][3], 'Agreed on the call: the role is filled when the person joins, not when they sign. Both moments are announced.'),
 ('MH-07', 'Original - Must Haves', 'Onboarding › Pre-Onboarding Trigger',
  'When the offer is accepted and the position closed, the hiring manager is emailed to nominate buddies; pre-onboarding starts.',
  YES, BUILT, REC + ' / ' + HM, steps(HIRING_REC, 'Open DEMO Territory Manager › “Review candidates” › click Cao Minh Khoa.',
     '“Before they join” lists: ask the hiring manager to name a buddy, ask the joiner for laptop preferences, set up a meet-the-team chat, send first-day details.',
     'The hiring manager names the buddy from one email (no sign-in).',
     'The standard list: Talent lead › “Set up hiring” › “Before they join”.'),
  'Run by the recruiter, as agreed on the call. Buddy eligibility checks (tenure, probation) and the wider onboarding belong to the Onboarding requirements, not this list.'),
 ('MH-08', 'Original - Must Haves', 'Onboarding › Laptop Procurement',
  'Laptop needs captured before joining (10–15 days before the date of joining).',
  PART, PARTB, REC + ' / ' + CA, steps(HIRING_REC, 'Open DEMO Territory Manager › “Review candidates” › click Cao Minh Khoa.',
     '“Before they join” › “Ask … for their laptop preferences” › “Remind them”.',
     'The joiner answers on a page in their own language; the answer lands on their card.'),
  'Built: the joiner\'s laptop preferences. The purchase approval and asset tracker belong to the Asset Management requirements, not this list.'),
 ('CALL-01', '28 Sep 2026 call', 'Platform', 'A simpler Hiring screen with fewer filters.',
  YES, BUILT, REC, steps(HIRING_REC), 'The old duplicate recruitment menus are gone; the Hiring screen and “Set up hiring” are the only doors.'),
 ('CALL-02', '28 Sep 2026 call', 'Requisition', 'A role can exist before, or without, a hiring request.',
  YES, BUILT, REC, steps('Sign in as the Recruiter.', HIRING_REC, 'Press “Open a role”: five things and the role exists.'),
  'The request only matters for sending the offer.'),
 ('CALL-03', '28 Sep 2026 call', 'Interviews', 'Moving someone to “Recruiter review” sends the recruiter\'s Calendly link automatically.',
  YES, BUILT, REC, steps(HIRING_REC, ROLE, 'Drag a card into “Recruiter review”: the “Let\'s chat” email goes with the recruiter\'s own link.',
     'Each recruiter adds their link in “Set up hiring” › “Who does what”. Switch it off in “Set up hiring” › “Automations”.'),
  'Sent in the candidate\'s language.'),
 ('CALL-04', '28 Sep 2026 call', 'Selection', 'No offer without an agreed hiring request (the one hard rule).',
  YES, BUILT, REC, steps(HIRING_REC, ROLE, DETAILS + ' › “Request & role”: “Request agreed” or who still has to press “Agree”.'),
  'The only place the system says no.'),
 ('CALL-05', '28 Sep 2026 call', 'Communications', 'Only Rize\'s own confirmation email goes out when someone applies.',
  YES, HAVE, TL, steps(HIRING, SETUP, '“Emails and languages” › “Application received”.'), 'In the candidate\'s language.'),
 ('CALL-06', '28 Sep 2026 call', 'Communications', 'Email automations the talent lead sets up herself.',
  YES, BUILT, TL, steps('Sign in as the Talent lead.', HIRING, SETUP, 'Open “Automations” › “Add a rule”: “When … then … right away / after N days”.',
     'Press “Try it on a candidate” (nothing is sent), then switch the rule on.', 'The “What ran” tab lists everything that ran.'),
  'The emails the product always sends are listed beside your rules, each with its own switch.'),
 ('CALL-07', '28 Sep 2026 call', 'Communications', 'Emails go out from Rize\'s own address (@rize.farm).',
  'Rize action', "Needs Rize's IT", '—', '—',
  'Rize\'s IT adds the sending records we provide to the rize.farm domain before go-live. Until then emails come from Payobook\'s address.'),
 ('CALL-08', '28 Sep 2026 call', 'Joining', 'The person stays a candidate, with the recruiter, until the date of joining is confirmed.',
  YES, BUILT, REC, R['REC-027'][3], '“Confirm they joined” creates the employee, contract and login on the real date.'),
 ('CALL-09', '28 Sep 2026 call', 'Joining', 'Pre-onboarding run by the recruiter: buddy, laptop preferences, meet-the-team chats.',
  YES, BUILT, REC, '(same as MH-07)', 'See MH-07: the same “Before they join” list covers this.'),
 ('CALL-10', '28 Sep 2026 call', 'Joining', 'Reminder one week before the expected joining date to recruiter, hiring manager and HR.',
  YES, BUILT, 'Automatic', steps('Nothing to press: one email a week before the date (still on, date changed, or not joining).',
     'On the person\'s card you can also press “Send the “still on?” email now”.', 'Switch: “Set up hiring” › “Automations”.'), ''),
 ('CALL-11', '28 Sep 2026 call', 'Analytics', 'Offer-drop measurement: offered → accepted → joined.',
  YES, BUILT, TL, steps('Search bar › “Hiring numbers”.', 'Section “From offer to joined”.'), 'Every drop with its reason, per role and market.'),
]

# ================================================================ writer
wb = openpyxl.load_workbook(SRC)
WRAP = Alignment(wrap_text=True, vertical='top')
FILLS = {'Yes': 'E3EFE7', 'Partly': 'FBEFD5', 'Ready, switched off': 'EEF0F3',
         'Not now (agreed)': 'EEF0F3', 'Rize action': 'EEF0F3', "Rize's side": 'EEF0F3'}
NEWHEAD_FILL = PatternFill('solid', fgColor='3F7D5C')
NEWHEAD_FONT = Font(name='Arial', size=9, bold=True, color='FFFFFF')
BODY = Font(name='Arial', size=9)
THIN = Side(style='thin', color='C9D1CA')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WIDTH = {'Source': 20, 'Try it as': 18, 'Clicks to reach it': 72, 'Comments': 52,
         'In Payobook?': 16, 'Where to see or change it': 46, 'How Payobook handles it': 60,
         'In Payobook': 60}

def head(ws, row, col, text, widen=True):
    c = ws.cell(row=row, column=col, value=text)
    c.fill, c.font, c.alignment, c.border = NEWHEAD_FILL, NEWHEAD_FONT, Alignment(wrap_text=True, vertical='center'), BOX
    L = get_column_letter(col)
    if widen: ws.column_dimensions[L].width = max(ws.column_dimensions[L].width or 0, WIDTH.get(text, 30))

def put(ws, row, col, val, tint=None):
    c = ws.cell(row=row, column=col, value=val)
    c.alignment, c.border, c.font = WRAP, BOX, BODY
    if tint and val in FILLS:
        c.fill = PatternFill('solid', fgColor=FILLS[val])
    return c

def lines(text, w=70):
    return max(1, sum(1 + len(l) // int(w * 1.15) for l in str(text).split('\n')))

def fit(ws, r):
    n = 2
    for c in range(1, ws.max_column + 1):
        v = ws.cell(r, c).value
        if isinstance(v, str):
            w = ws.column_dimensions[get_column_letter(c)].width or 10
            n = max(n, lines(v, w))
    ws.row_dimensions[r].height = 12.5 * n + 4

def tables(ws, first_header):
    """Yield header row indexes whose column A equals first_header."""
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, 1).value == first_header:
            yield r

def rows_after(ws, hr):
    r = hr + 1
    while r <= ws.max_row and ws.cell(r, 1).value not in (None, '') and not (
            ws.cell(r, 2).value in (None, '') and ws.cell(r, 3).value in (None, '')):
        yield r
        r += 1

seen = set()
for ws in wb.worksheets:
    # the source file stores some column widths as ranges (e.g. H:P); split them so each
    # new column gets its own width
    for key, dim in list(ws.column_dimensions.items()):
        if dim.min and dim.max and dim.max > dim.min:
            w = dim.width
            for i in range(dim.min, dim.max + 1):
                L = get_column_letter(i)
                ws.column_dimensions[L].width = w
                ws.column_dimensions[L].min = ws.column_dimensions[L].max = i
    if ws.title.startswith('1.'):
        ws.column_dimensions['H'].width = 34   # shared by "Source" and the roles table's notes
for ws in wb.worksheets:
    # ---- "What we need" tables
    for hr in tables(ws, 'Ref'):
        if ws.cell(hr, 2).value == 'What we need':
            for i, t in enumerate(['Source', 'Try it as', 'Clicks to reach it', 'Comments']):
                head(ws, hr, 8 + i, t)
            for c in (6, 7):
                ws.column_dimensions[get_column_letter(c)].width = max(ws.column_dimensions[get_column_letter(c)].width or 0, 18)
            for r in rows_after(ws, hr):
                ref = ws.cell(r, 1).value
                sup, typ, who, clicks, com = R[ref]
                seen.add(ref)
                put(ws, r, 6, sup, tint=True); put(ws, r, 7, typ)
                put(ws, r, 8, 'Zoho Recruit requirements'); put(ws, r, 9, who)
                put(ws, r, 10, clicks); put(ws, r, 11, com)
                for c in range(1, 6):
                    ws.cell(r, c).alignment = WRAP
                fit(ws, r)
        elif ws.cell(hr, 2).value == 'Area':      # open questions
            for r in rows_after(ws, hr):
                put(ws, r, 5, OQ[ws.cell(r, 1).value])
                fit(ws, r)
            ws.column_dimensions['E'].width = 70
    # ---- notifications / templates
    for key, data in (('Trigger', NOTIF), ('Template', TEMPL)):
        for hr in tables(ws, key):
            for i, t in enumerate(['In Payobook?', 'Where to see or change it', 'Comments']):
                head(ws, hr, 6 + i, t)
            for r in rows_after(ws, hr):
                a, b, c = data[ws.cell(r, 1).value]
                put(ws, r, 6, a, tint=True); put(ws, r, 7, b); put(ws, r, 8, c)
                fit(ws, r)
    # ---- dashboards / reports
    for hr in tables(ws, 'Dashboard'):
        for i, t in enumerate(['In Payobook?', 'Try it as', 'Clicks to reach it', 'Comments']):
            head(ws, hr, 6 + i, t)
        for r in rows_after(ws, hr):
            who, clicks, com = DASH[ws.cell(r, 1).value]
            put(ws, r, 6, 'Yes', tint=True); put(ws, r, 7, who); put(ws, r, 8, clicks); put(ws, r, 9, com)
            fit(ws, r)
    for hr in tables(ws, 'Report'):
        for i, t in enumerate(['In Payobook?', 'Try it as', 'Clicks to reach it', 'Comments']):
            head(ws, hr, 6 + i, t)
        for r in rows_after(ws, hr):
            where, com = REPORTS[ws.cell(r, 1).value]
            clicks = steps('Sign in as the Talent lead.', 'Search bar › type “hiring numbers” › open “Hiring numbers”.' if 'Hiring numbers' in where else HIRING,
                           where.replace('“Hiring numbers” › ', 'Go to ') if 'Hiring numbers' in where else where,
                           'Download: the small download button on the section, or “Download everything”.')
            put(ws, r, 6, 'Yes', tint=True); put(ws, r, 7, TL); put(ws, r, 8, clicks); put(ws, r, 9, com)
            fit(ws, r)
    # ---- small tables
    for hr in tables(ws, 'Role'):
        if ws.cell(hr, 2).value == 'Create':
            head(ws, hr, 9, 'In Payobook', widen=False)
            for r in rows_after(ws, hr):
                put(ws, r, 9, ROLES_T[ws.cell(r, 1).value]); fit(ws, r)
    for hr in tables(ws, 'Moment'):
        head(ws, hr, 8, 'In Payobook', widen=False)
        for r in rows_after(ws, hr):
            put(ws, r, 8, UI_T[ws.cell(r, 1).value]); fit(ws, r)
    for hr in tables(ws, 'Scenario'):
        head(ws, hr, 4, 'How Payobook handles it')
        for r in rows_after(ws, hr):
            put(ws, r, 4, EXC[ws.cell(r, 1).value]); fit(ws, r)
    for hr in tables(ws, 'Assessment'):
        head(ws, hr, 6, 'In Payobook')
        for r in rows_after(ws, hr):
            put(ws, r, 6, ASSESS_NOTE); fit(ws, r)
    for hr in tables(ws, 'Round'):
        head(ws, hr, 7, 'In Payobook')
        for r in rows_after(ws, hr):
            put(ws, r, 7, ROUNDS_NOTE); fit(ws, r)

missing = set(R) - seen
assert not missing, missing

# ---------------------------------------------------------------- added sheet
ws = wb.create_sheet('10. Added requirements')
ws['A1'] = '10. Added requirements — not in the Zoho Recruit sheet'
ws['A1'].font = Font(name='Arial', bold=True, size=14)
ws['A2'] = ('Lines from the original "HRMS Proposal - Must Have" workbook that the Zoho Recruit sheet left out or changed '
            '(Source: Original - Must Haves), and the features agreed on the 28 Sep 2026 call (Source: 28 Sep 2026 call).')
ws['A2'].alignment = WRAP
ws.merge_cells('A2:J2'); ws.row_dimensions[2].height = 32
cols = ['Ref', 'Source', 'Area', 'What we need', 'Vendor: Supported?', 'Vendor: Solution type',
        'Try it as', 'Clicks to reach it', 'Comments']
widths = [10, 20, 26, 46, 16, 22, 18, 72, 52]
for i, (t, w) in enumerate(zip(cols, widths), 1):
    head(ws, 4, i, t); ws.column_dimensions[get_column_letter(i)].width = w
for n, row in enumerate(ADDED, 5):
    for i, v in enumerate(row, 1):
        put(ws, n, i, v, tint=(i == 5))
    fit(ws, n)
ws.freeze_panes = 'B5'

# ---------------------------------------------------------------- start sheet
st = wb.create_sheet('Start here', 0)
st.column_dimensions['A'].width = 26; st.column_dimensions['B'].width = 36
st.column_dimensions['C'].width = 18; st.column_dimensions['D'].width = 60
r = 1
def line(a, b=None, c=None, d=None, bold=False, size=None, h=None):
    global r
    for i, v in enumerate((a, b, c, d), 1):
        if v is not None:
            cell = st.cell(r, i, v); cell.alignment = WRAP
            cell.font = Font(name='Arial', bold=bold, size=size or 10)
    if h: st.row_dimensions[r].height = h
    r += 1
line('Rize Recruit — try every requirement yourself', bold=True, size=16, h=26)
st.merge_cells('A1:D1')
line('This workbook is the Zoho Recruit requirements sheet with five columns added: whether Payobook supports each line, '
     'how, which sign-in to use, the exact clicks to reach it, and comments. Tab 10 adds the lines from the original Must-Have list '
     'and the 28 Sep call that were not in this sheet.', h=48)
st.merge_cells(start_row=r - 1, start_column=1, end_row=r - 1, end_column=4)
r += 1
line('1. Where to try it', bold=True, size=13)
line('Address', 'https://payobook.com/web/login')
line('The data', 'Made-up demo data. People, roles and companies start with DEMO. Nothing you do here reaches a real person.', h=32)
r += 1
line('2. Demo sign-ins', bold=True, size=13)
line('Sign in as', 'Email', 'Password', 'What you can try')
for c in range(1, 5):
    st.cell(r - 1, c).fill, st.cell(r - 1, c).font = NEWHEAD_FILL, NEWHEAD_FONT
for row in [('Recruiter', 'demo.recruiter@example.com', 'RizeW2!2026', 'Boards, moving people, interviews, offers, joining, the Resume bank.'),
            ('Talent lead', 'demo.talentlead@example.com', 'RizeR1!2026', 'Everything a recruiter does, plus “Set up hiring” and “Hiring numbers”.'),
            ('Hiring manager', 'demo.hiringmanager@example.com', 'RizeR1!2026', 'Raising a request, their own roles, the people shared with them.'),
            ('Agency', 'demo.agency@example.com', 'RizeR7!2026', 'The agency portal: their roles, putting people forward.'),
            ('Candidate', 'No sign-in', '—', 'payobook.com/jobs › a role › “Apply Now!”')]:
    line(*row, h=30)
line('Tip', 'Use a private (incognito) window for each sign-in to compare two people side by side.')
st.merge_cells(start_row=r - 1, start_column=2, end_row=r - 1, end_column=4)
r += 1
line('3. Opening Hiring', bold=True, size=13)
line('Everyone', 'Click the search bar at the top of the screen (or press Ctrl+K / ⌘K), type “hiring” and choose “Who we are hiring”.')
st.merge_cells(start_row=r - 1, start_column=2, end_row=r - 1, end_column=4)
line('Recruiter', 'Also in the left menu: Operate › Lifecycle.')
line('Talent lead', '“Set up hiring” is a button at the top of the Hiring screen. “Hiring numbers”: search bar › type “hiring numbers”.')
st.merge_cells(start_row=r - 1, start_column=2, end_row=r - 1, end_column=4)
r += 1
line('4. Good roles to try', bold=True, size=13)
line('DEMO Territory Manager', 'A full board: every stage, an agency candidate, and Cao Minh Khoa in “Post-offer” with the “Before they join” list.')
st.merge_cells(start_row=r - 1, start_column=2, end_row=r - 1, end_column=4)
line('DEMO Site Agronomist', 'Finalists to compare (“Compare finalists”) and interviews waiting for opinions.')
st.merge_cells(start_row=r - 1, start_column=2, end_row=r - 1, end_column=4)
r += 1
line('5. The added columns', bold=True, size=13)
for a, b in [('Vendor: Supported?', 'Yes, Partly, or a note when the line was changed or left out by agreement.'),
             ('Vendor: Solution type', 'Built for Rize in Payobook, Already in Payobook, Built with the rest later, or Left out by agreement.'),
             ('Source', 'Zoho Recruit requirements, Original - Must Haves, or 28 Sep 2026 call.'),
             ('Try it as', 'Which demo sign-in to use.'),
             ('Clicks to reach it', 'Numbered steps from signing in to the screen. Words in “quotes” are the exact words on the screen.'),
             ('Comments', 'What to look for, what was agreed, and anything that waits on Rize.')]:
    line(a, b); st.merge_cells(start_row=r - 1, start_column=2, end_row=r - 1, end_column=4)

# overview: mention the added tab
ov = wb['Overview']
for c in range(1, 8):
    src, dst = ov.cell(18, c), ov.cell(20, c)
    dst.font, dst.fill, dst.border, dst.alignment = (copy.copy(src.font), copy.copy(src.fill),
                                                     copy.copy(src.border), copy.copy(src.alignment))
ov.cell(20, 1).value = '10. Added requirements'
ov.cell(20, 2).value = 'Lines from the original Must-Have list and the 28 Sep call that this sheet did not have.'
ov.merge_cells('B20:G20'); ov.row_dimensions[20].height = 27.75
ov.cell(21, 1).value = 'Start here'
ov.cell(21, 2).value = 'How to sign in to the demo and try each line yourself.'
for c in range(1, 8):
    src, dst = ov.cell(19, c), ov.cell(21, c)
    dst.font, dst.fill, dst.border, dst.alignment = (copy.copy(src.font), copy.copy(src.fill),
                                                     copy.copy(src.border), copy.copy(src.alignment))
ov.merge_cells('B21:G21'); ov.row_dimensions[21].height = 27.75

for w in wb.worksheets:
    w.page_setup.orientation = 'landscape'
    w.sheet_properties.pageSetUpPr.fitToPage = True
    w.page_setup.fitToWidth, w.page_setup.fitToHeight = 1, 0
wb.active = 0
wb.save(OUT)

# ---- white-label gate
bad = []
for w in openpyxl.load_workbook(OUT).worksheets:
    for row in w.iter_rows(values_only=True):
        for v in row:
            if isinstance(v, str) and 'odoo' in v.lower():
                bad.append((w.title, v[:60]))
print('saved', OUT, 'odoo hits:', bad)
