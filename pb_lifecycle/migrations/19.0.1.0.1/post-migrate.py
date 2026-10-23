# -*- coding: utf-8 -*-
"""1.0.0 -> 1.0.1 — the seeded checklists and letters become COMPANY-LESS.

WHY A MIGRATION AND NOT JUST A DATA EDIT. Both seed files are `noupdate="1"`,
which is right — a company that has reworded a letter must keep its wording
through every upgrade — but it also means the corrected `company_id` in the XML
reaches no database that already installed 1.0.0. On that database the seeds
carry the company of whoever happened to run the install, and the record rule
(`company_id = False OR in company_ids`) then hides them from every other
company: the Start-a-journey dialog offers "there is no checklist for this yet"
to people who have two.

So the fix is applied by hand, and ONLY to the records this module seeded (found
through `ir_model_data`, never by name) and ONLY where nobody has since assigned
a company deliberately — a row whose company is not the one the install stamped
is somebody's decision and is left alone.
"""
import logging

_logger = logging.getLogger(__name__)

_SEEDED = {
    'pb.journey.template': (
        'journey_template_onboarding', 'journey_template_offboarding'),
    'pb.letter.template': (
        'letter_template_experience', 'letter_template_probation_pass',
        'letter_template_incentive'),
}


def migrate(cr, version):
    if not version:
        return
    for model, names in _SEEDED.items():
        table = model.replace('.', '_')
        cr.execute("""
            UPDATE %s SET company_id = NULL
             WHERE id IN (SELECT res_id FROM ir_model_data
                           WHERE module = 'pb_lifecycle'
                             AND model = %%s
                             AND name IN %%s)
               AND company_id IS NOT NULL
        """ % table, (model, tuple(names)))
        _logger.info('pb_lifecycle: %s %s row(s) shared across companies',
                     cr.rowcount, model)

    # `pb.journey.template.step.company_id` is RELATED and STORED, so it is a
    # real column that a raw UPDATE on the parent does not touch — and a step
    # left on the old company is invisible to the very read that turns a
    # checklist into a journey, which would open every journey with no steps at
    # all. Follow the parent explicitly.
    cr.execute("""
        UPDATE pb_journey_template_step s
           SET company_id = t.company_id
          FROM pb_journey_template t
         WHERE t.id = s.template_id
           AND s.company_id IS DISTINCT FROM t.company_id
    """)
    _logger.info('pb_lifecycle: %s checklist step(s) re-pointed at their '
                 "checklist's company", cr.rowcount)
