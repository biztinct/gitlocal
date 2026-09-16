# -*- coding: utf-8 -*-
{
# The opening line of this description is what the Apps list prints, so it is
# a USER-VISIBLE string and carries no programme code (ledger GR7, TIDY T10).
# Built as RIZE Wave 2 phase E1.
    'name': 'Payobook Training',
    'summary': 'Put your people through a course, let them take the test, and '
               'hand them the certificate',
    'description': """
Training, from the employee's side of it.

THE PROBLEM. A company that trains its people keeps the evidence in three
places: a folder of videos somebody shares, a spreadsheet of who has watched
them, and a memory of who passed. Nobody can say what a person still has to
do this month, and the person themselves cannot see it at all.

WHAT THIS MODULE IS

  * **One page that is theirs.** Every employee has a training page of their
    own. It lists the courses they are on, how far through each one they are,
    what is left, and whether the test at the end is still locked. Nothing
    else — no catalogue to browse, no site to get lost on.
  * **The lesson, on our page.** A video, a document, a written page, a
    picture or a short quiz, all rendered here, with one button that says
    "Mark as done" and a link to the next one. The progress bar on the course
    moves the moment they press it.
  * **A test that only opens when the work is done.** The test at the end of a
    course cannot be taken until every lesson is finished, and the page says
    how many are left rather than simply refusing. The score comes back
    straight away, a pass hands over the certificate, and a fail says how many
    goes are left.
  * **Enrolling people takes one press.** The training team picks a course,
    searches for people by name — accents and all — and puts them on it.
    Everybody they added sees it on their own page within the second.
  * **Who has done what.** One board: the courses, how many are on each, how
    far the average person has got, who has passed the test and who has not
    started.

WHAT IT DELIBERATELY DOES NOT DO. It does not rebuild a video player, a
progress tracker, a quiz engine, a question bank or a certificate generator.
Those already exist in this build and are good; this module is the Payobook
layer over them, and the reason every learner page is ours is that the pages
that came with them are a public web site, and an employee's training is not
public.
""",
    'version': '19.0.1.0.2',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'portal',
        'website',
        # THE CONTENT ENGINE AND THE TEST ENGINE (ruling D14). Courses,
        # lessons, per-person completion and the in-lesson quiz are
        # `website_slides`; the scored test, the attempt limit and the
        # certificate are `survey`; `website_slides_survey` is the join
        # between them (the certification lesson).
        'website_slides',
        'survey',
        'website_slides_survey',
        'pb_hub',               # the global command-bar registry
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_me_portal',         # the .pbme employee-page kit
        'pb_learn',             # the hub this lens joins
    ],
    'data': [
        'security/pb_training_security.xml',
        'views/training_views.xml',
        'views/portal_templates.xml',
        'views/survey_skin.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_training/static/src/scss/training.scss',
            'pb_training/static/src/js/training_board.js',
            'pb_training/static/src/js/training_palette.js',
            'pb_training/static/src/xml/training_board.xml',
        ],
        'web.assets_frontend': [
            'pb_training/static/src/scss/portal_training.scss',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
