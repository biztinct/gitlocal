# -*- coding: utf-8 -*-
"""The trial-period gate, joined by DATA and not by code.

`pb_probation` already refuses to pass a trial period while anything REQUIRED
is outstanding, and it asks that question of `pb.training.status`
(`probation_review.py:833` → `training.py:215`). That machine is good, it is
live, and this phase does not touch a line of it.

So the join is one column. An assignment whose trial period waits for it
ensures a `pb.training.status` row — on a track called "Assigned training"
whose `job_ids` is EMPTY, which is precisely what stops `ensure_for_employee`
spreading it to everybody with the same job title (`training.py:88-92`) — and
points it back here. Finishing the course ticks the row; re-opening the course
un-ticks it. `_check_training_gate()` keeps working unchanged and names the
course in its refusal, because the item is named after the course.

WHY A POINTER BACK AND NOT JUST A ROW. Without `assignment_id` nothing can tell
a row this module made from a row somebody typed on the trial-period screen,
and the day a course is un-assigned the wrong one would be cleaned up. It also
lets the trial-period screen say WHERE the requirement came from.
"""

from odoo import fields, models


class PbTrainingStatus(models.Model):
    _inherit = 'pb.training.status'

    assignment_id = fields.Many2one(
        'pb.training.assignment', string='From the assigned course',
        index=True, ondelete='set null', readonly=True,
        help='Set when this row was made by a course somebody was put on. '
             'It is then ticked by finishing that course rather than by hand.')
