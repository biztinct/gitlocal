"""Exact elapsed-time calculation. Inputs are timezone-aware instants.

Punches are retained externally; this function never modifies them. Breaks are
unpaid intervals, normal_end is the explicit OT boundary, and penalties reduce
already-worked hours in chronological order (normal first, then overtime).
"""
from datetime import timedelta


def calculate(punches, start, normal_end, end, breaks, bands, category,
              day_kind='weekday', night_intervals=()):
    punches = sorted(set(punches))
    if len(punches) < 2:
        return {'error': 'A first and last punch are required.'}
    if not start < normal_end <= end:
        return {'error': 'Normal-hours boundary must be inside the shift.'}
    first, last = punches[0], punches[-1]
    if last <= first:
        return {'error': 'Check-out must follow check-in.'}
    late = max(0., (first - start).total_seconds() / 60)
    matching = [b for b in bands if b['category'] == category
                and b['minimum'] <= late and (b['maximum'] is None or late < b['maximum'])]
    if late > 0 and len(matching) != 1:
        return {'error': 'No single lateness band covers this arrival.', 'late_minutes': late}
    if matching and not matching[0]['confirmed']:
        return {'error': 'The deduction for this lateness band needs confirmation.', 'late_minutes': late}
    penalty = matching[0]['hours'] if matching else 0.
    low, high = max(first, start), last
    if high <= low:
        return {'error': 'Punches do not overlap this shift.'}
    # Disjoint segment boundaries avoid deducting an overlapping break twice.
    boundaries = sorted({low, high, *[p for a, b in breaks for p in (a, b) if low < p < high],
                         *[p for a, b in night_intervals for p in (a, b) if low < p < high],
                         *([normal_end] if low < normal_end < high else [])})
    normal = overtime = night = unpaid = worked = 0.
    remaining_penalty = penalty
    segments = []
    for a, b in zip(boundaries, boundaries[1:]):
        hours = (b - a).total_seconds() / 3600
        if any(x <= a and b <= y for x, y in breaks):
            unpaid += hours
            continue
        worked += hours
        removed = min(hours, remaining_penalty)
        remaining_penalty -= removed
        paid = hours - removed
        kind = 'normal' if a < normal_end and day_kind == 'weekday' else day_kind if day_kind != 'weekday' else 'weekday_ot'
        if kind == 'normal':
            normal += paid
        else:
            overtime += paid
        if any(x <= a and b <= y for x, y in night_intervals):
            night += paid
        segments.append({'start': a.isoformat(), 'end': b.isoformat(), 'kind': kind,
                         'worked': hours, 'deduction': removed, 'paid': paid})
    return {'first': first.isoformat(), 'last': last.isoformat(), 'late_minutes': late,
            'gross_hours': (last-first).total_seconds()/3600,
            'break_hours': unpaid, 'worked_hours': worked,
            'penalty_hours': penalty-remaining_penalty, 'requested_penalty_hours': penalty,
            'normal_hours': normal, 'overtime_hours': overtime, 'night_hours': night,
            'segments': segments, 'day_kind': day_kind}
