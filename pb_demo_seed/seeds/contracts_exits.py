# -*- coding: utf-8 -*-
"""One fixed-term contract, from "it ends in six weeks" to "get the laptop back".

THIS IS ONE STORY, NOT TWO. The requirements sheet treats contract management
and offboarding as separate sections, and in a product they are — but in a
person's life they are the same fortnight. A fixed term runs down, somebody asks
for an extension, somebody decides, and if the decision is no then a leaving
checklist opens and an asset that has been out for eleven months has to come
back. Splitting that across two demo people would show two screens and no
consequence.

THE DECISION HAS BEEN MADE AND THE CONSEQUENCE HAS NOT LANDED. The extension was
asked for and turned down; the checklist is open, the four desks are still to
clear, and the laptop is still assigned. That is the state in which a demo is
worth giving: everything explained, one thing left to do, and a button that does
it.

BUILT LAST so it is removed first — the leaving checklist points at the contract
review, which points at the contract, which points at the person.
"""

import logging

from odoo import fields

_logger = logging.getLogger(__name__)


def build(ctx):
    people = ctx.get('people', {})
    leaver = people.get('fixed_term')
    manager = people.get('manager')
    if not leaver:
        return
    contract = ctx.get('contract_fixed_term')
    if not contract:
        return

    review = _contract_review(ctx, leaver, contract, manager)
    _extension_request(ctx, leaver, contract, review)
    case = _leaving_checklist(ctx, leaver, contract)
    if case and review:
        review.sudo().exit_case_id = case.id
    _handover(ctx, leaver, case, people)


# ----------------------------------------------------------------------
def _contract_review(ctx, leaver, contract, manager):
    """The decision the system raised sixty days out, and how it went.

    `lead_days` is left at the product's own sixty rather than set to match the
    dates: the requirements ask for "at least two months prior, configurable",
    and a demo that quietly overrides the configurable number is demonstrating
    something the customer will not get.
    """
    end_date = contract.date_end or ctx.days(45)
    return ctx.create('pb.contract.review', {
        'contract_id': contract.id,
        'employee_id': leaver.id,
        'end_date': end_date,
        'lead_days': 60,
        'trigger_date': ctx.days(-15),
        'state': 'done',
        'decision': 'terminate',
        'decided_by': ctx.env.user.id,
        'decided_at': fields.Datetime.now(),
        'decision_note': 'The seasonal programme he was hired for finishes with '
                         'this harvest and there is no permanent vacancy in '
                         'Agronomy this year. He has been told, and he has been '
                         'told he can apply again for the spring intake.',
        'manager_user_id': ctx.env.user.id,
        'notified': True,
    }, label='Contract decision — %s' % leaver.name)


def _extension_request(ctx, leaver, contract, review):
    """The manager did ask. Keeping the refused request is the honest record.

    Deleting a turned-down request would make the timeline read as though
    nobody tried, which is exactly the conversation an HR team has to be able
    to reconstruct a year later.
    """
    if not review:
        return None
    return ctx.create('pb.contract.extension', {
        'review_id': review.id,
        'contract_id': contract.id,
        'employee_id': leaver.id,
        'reason': 'Asked for six more months. He is the only technician '
                  'certified on the new sprayer and the spring intake does not '
                  'start until March.',
        'months': 6,
        'new_date_start': ctx.days(46),
        'new_date_end': ctx.months(7),
        'approver_user_id': ctx.env.user.id,
        'approve_by': ctx.days(-10),
        'state': 'refused',
    }, label='Extension request — %s' % leaver.name)


def _leaving_checklist(ctx, leaver, contract):
    """Open it the way the product does, then adopt what the product made.

    `action_open()` generates the checklist steps, the four desk clearances and
    the exit questionnaire. The steps and clearances belong to the checklist and
    go with it; the questionnaire does not, so it is adopted into the register
    explicitly rather than left behind.
    """
    template = _template(ctx, 'offboarding')
    last_day = contract.date_end or ctx.days(45)
    marks = ctx.mark('pb.feedback.request', 'pb.employee.checkin')
    case = ctx.create('pb.journey.case', {
        'employee_id': leaver.id,
        'case_type': 'offboarding',
        'template_id': template.id if template else False,
        'anchor_date': last_day,
        'state': 'draft',
        'source': 'manual',
        'note': 'Fixed-term contract ending. Not a resignation.',
    }, label='Leaving checklist — %s' % leaver.name)

    if template:
        case.sudo().action_open()
    else:
        case.sudo().state = 'active'

    ctx.adopt_since(marks, 'pb.feedback.request',
                    label='Exit questionnaire — %s' % leaver.name)
    ctx.adopt_since(marks, 'pb.employee.checkin',
                    label='Exit conversation — %s' % leaver.name)

    # One desk already cleared, three to go. A checklist on which nothing has
    # moved cannot show that the gate is a gate.
    for clearance in case.sudo().clearance_ids:
        if clearance.dept == 'hr':
            clearance.sudo().write({
                'state': 'cleared',
                'cleared_at': fields.Datetime.now(),
                'cleared_by': ctx.env.user.id,
                'note': 'Final leave balance agreed and the letter is drafted.',
            })
    return case


def _handover(ctx, leaver, case, people):
    """What he is handing over, and to whom.

    The asset is deliberately NOT returned. Its assignment stays open and the
    laptop stays "assigned", so the mandatory-return gate on the final
    settlement has something real to hold up — which is the requirement the
    asset sheet actually states.
    """
    if not case:
        return
    successor = people.get('probation')
    items = [
        ('Sprayer certification and the maintenance log', 'the field team'),
        ('Trial plot records for the current season', 'the agronomy team'),
        ('Supplier contacts for spare parts', 'the field supervisor'),
    ]
    for sequence, (topic, _to) in enumerate(items):
        ctx.create('pb.kt.item', {
            'case_id': case.id,
            'topic': topic,
            'from_employee_id': leaver.id,
            'to_employee_id': successor.id if successor else False,
            'sequence': (sequence + 1) * 10,
            'state': 'done' if sequence == 0 else 'todo',
            'done_at': fields.Datetime.now() if sequence == 0 else False,
            'notes': 'Demo handover item.',
        }, label='Handover — %s' % topic[:60])


def _template(ctx, case_type):
    templates = ctx.env['pb.journey.template'].sudo().search(
        [('case_type', '=', case_type)])
    if not templates:
        return None
    return max(templates, key=lambda t: len(t.step_ids))
