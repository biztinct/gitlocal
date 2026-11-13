# -*- coding: utf-8 -*-
"""Give existing wires the feed their source field already belongs to.

A wire has to name its feed or nothing can fetch it: the pay run's sync plan is
derived from `endpoint_id`, so a wire without one is pulled by nothing and its
component falls back to a default on every run — silently, because the run
still reports success.

On the reference tenant four wires were saved this way, BASESALARY among them,
so base pay resolved to 0 and every deduction (a percentage of it) resolved to
0 with it. The board only sends an endpoint when the reader has picked ONE
feed; in the "All feeds" view it sent none. The catalogue knew the answer the
whole time.

Only unambiguous matches are filled. Two feeds carrying a field of the same
name is a real shape, and guessing between them would wire payroll to the wrong
feed — worse than leaving it for a person, which the run now reports as an
exception naming the component.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT w.id, w.source_field, min(ep.id), count(DISTINCT ep.id)
          FROM hr_integration_field_mapping w
          JOIN hr_integration_endpoint_field f
            ON f.path = w.source_field
          JOIN hr_integration_endpoint ep
            ON ep.id = f.endpoint_id
           AND ep.connector_id = w.connector_id
         WHERE w.endpoint_id IS NULL
           AND w.source_field IS NOT NULL
           AND w.target_rule_id IS NOT NULL
      GROUP BY w.id, w.source_field
    """)
    rows = cr.fetchall()
    if not rows:
        return
    routed = [(wid, eid) for wid, _f, eid, n in rows if n == 1]
    ambiguous = [f for _w, f, _e, n in rows if n > 1]
    for wire_id, endpoint_id in routed:
        cr.execute("UPDATE hr_integration_field_mapping SET endpoint_id = %s "
                   "WHERE id = %s", (endpoint_id, wire_id))
    _logger.info(
        "VALUEKIND P5: routed %s wire(s) to the feed carrying their source "
        "field; %s left for a person because more than one feed carries the "
        "same name (%s).",
        len(routed), len(ambiguous), ', '.join(sorted(set(ambiguous))) or '-')
