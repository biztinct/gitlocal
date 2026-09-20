# -*- coding: utf-8 -*-
"""What Payobook does when the connected system says something.

The policy is DATA, not code, for one reason: every HR department spells its
own leaving process differently. "Resigned", "Notice period", "Exit initiated",
"Đã nghỉ việc" — the word that means "start the exit checklist" is the tenant's
word, and a tenant must be able to add it without a developer and without a
deploy.

The default answer to a word nobody has taught us is NEVER a guess. A record
that matches no rule is written down for a human to look at; nothing is created
and nothing is changed. Opening the wrong journey for the wrong person is a far
more expensive mistake than a row in a review list.
"""

from odoo import api, fields, models, _

TRIGGERS = [
    ('created', 'Someone new arrived'),
    ('status', 'Their employment status changed'),
    ('updated', 'Their details changed'),
]

ACTIONS = [
    ('onboard', 'Start their joining checklist'),
    ('offboard', 'Start their leaving checklist'),
    ('update', 'Just update the record'),
    ('ignore', 'Do nothing'),
    ('review', 'Put it in the review list'),
]

TRIGGER_LABEL = dict(TRIGGERS)
ACTION_LABEL = dict(ACTIONS)


def normalise_value(raw):
    """The comparison a status match uses: case- and space-insensitive.

    Zoho hands back whatever the tenant typed into their own form — "Resigned",
    " resigned", "RESIGNED". All three mean the same thing to a person and must
    mean the same thing here, or the rule that works today stops working the
    day somebody edits the picklist label.
    """
    if not raw:
        return ''
    return ' '.join(str(raw).split()).strip().lower()


class PbZohoEventRule(models.Model):
    _name = 'pb.zoho.event.rule'
    _description = 'Arrival Rule'
    _order = 'sequence, id'

    name = fields.Char(
        string='Rule', compute='_compute_name', store=True,
        help='Written out as a sentence, so the list reads like the policy it is.')
    sequence = fields.Integer(
        string='Order', default=10,
        help='The first rule that matches wins. Put the specific ones first.')
    trigger = fields.Selection(
        TRIGGERS, string='When', required=True, default='status')
    match_value = fields.Char(
        string='And the status word is',
        help='The exact word the connected system sends, for example '
             '"Resigned". Capitals and extra spaces do not matter. '
             'Leave it empty to match any status.\n\n'
             'It narrows a "someone new arrived" rule too, which is how '
             'Payobook avoids handing a joining checklist to a person whose '
             'record turns up for the first time already marked as having '
             'left.')
    action = fields.Selection(
        ACTIONS, string='Then Payobook will', required=True, default='review')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty to apply this rule in every company.')
    note = fields.Text(string='Why this rule exists')

    @api.depends('trigger', 'match_value', 'action')
    def _compute_name(self):
        for rec in self:
            when = TRIGGER_LABEL.get(rec.trigger, rec.trigger or '')
            if rec.match_value:
                word = rec.match_value.strip()
                if rec.trigger == 'status':
                    when = _('Their status becomes "%s"', word)
                else:
                    # A narrowed 'created'/'updated' rule reads as a sentence
                    # too, or the list shows four identical "Someone new
                    # arrived" rows that only differ in a column nobody is
                    # looking at.
                    when = _('%(when)s and their status is "%(word)s"',
                             when=when, word=word)
            rec.name = '%s → %s' % (
                when, ACTION_LABEL.get(rec.action, rec.action or ''))

    @api.model
    def rules_for(self, trigger, company_id=False):
        """The active rules that could answer this trigger, best first."""
        domain = [('trigger', '=', trigger)]
        if company_id:
            domain += ['|', ('company_id', '=', False),
                       ('company_id', '=', company_id)]
        return self.sudo().search(domain, order='sequence, id')

    @api.model
    def decide(self, trigger, status_value=False, company_id=False):
        """The first rule that matches, or an empty recordset.

        An empty recordset is NOT an error and the caller must not treat it as
        one — it is "nobody has taught us this word yet", and the pipeline turns
        it into a review row.
        """
        wanted = normalise_value(status_value)
        for rule in self.rules_for(trigger, company_id):
            if rule.match_value and normalise_value(rule.match_value) != wanted:
                continue
            return rule
        return self.browse()
