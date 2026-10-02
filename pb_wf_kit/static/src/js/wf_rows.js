/** @odoo-module **/
/**
 * The ONE row budget every Workforce read-model shares (§2.6, P1b).
 *
 * Before this, three surfaces capped at three different numbers — the Week Grid
 * at 200, the Timeline at 120, the exception cohort at 400 — so "the first N
 * employees" meant a different N depending on which lens you were looking at,
 * and an officer who narrowed a department to make the grid complete still got
 * a truncated timeline. The cap is a product decision, not a per-facade detail.
 *
 * Python mirrors of this constant live in the facades that cap
 * (`pb_today/models/pb_today.py`, `pb_time_hub/models/time_hub.py`,
 * `pb_hr_workforce/models/attendance_weekentry.py`); `pb_today`'s static test
 * asserts all of them equal this number, because a constant duplicated in four
 * files is a constant that drifts.
 *
 * Truncation is always REPORTED (a notification or an in-surface notice), never
 * silent: a board that quietly shows 200 of 4 500 people is a board that lies.
 */
export const WF_ROW_CAP = 200;
