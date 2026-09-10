/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Step 3 — Connect, as words. No components, no services, nothing to mount.
 *
 * Every sentence the three task cards say is built here, from the numbers the
 * server sent, so a hoot test can assert the wording without a browser and the
 * card can never invent a phrase of its own.
 *
 * **Every `_t()` in this file is inside a function.** A label built at module
 * scope is constructed before any language is known, which ships English for
 * ever — and, in a unit test, hands back an object that refuses to be read at
 * all until translations are loaded (BP28, BP36). Building the words at the
 * moment they are shown costs nothing and takes that whole class of failure
 * off the table.
 */

/** The two tasks a person can actually do, plus the one that is information. */
export const CONNECT_TASKS = ["mapping", "payslip", "approvals"];

/** The order the lanes are named in a coverage line. */
export const LANES = ["api", "excel", "records", "cycle"];

/**
 * The pill on a card: what the server says, in one word a person can act on.
 *
 * `needs_review` is deliberately not called "out of date" — nothing is wrong,
 * the configuration simply changed after somebody finished this task, and the
 * card goes on to say exactly what changed.
 */
export function statusPill(status) {
    switch (status) {
        case "in_progress":
            return { key: "in_progress", cls: "is-open", label: _t("In progress") };
        case "configured":
            return { key: "configured", cls: "is-done", label: _t("Done") };
        case "skipped":
            return { key: "skipped", cls: "is-skip", label: _t("Skipped") };
        case "needs_review":
            return { key: "needs_review", cls: "is-review",
                     label: _t("Needs another look") };
        case "info":
            return { key: "info", cls: "is-info", label: _t("Already in place") };
        default:
            return { key: "not_started", cls: "is-idle", label: _t("Not started") };
    }
}

/**
 * "you opened it but nothing is connected yet", said once, under the pill.
 *
 * `covered` is what the coverage line says. A card that reads "1 of 52 inputs
 * has a source" must not also say nothing is connected — found in the browser,
 * on the first return from the mapping screen, which is exactly the moment a
 * person is looking for confirmation that their work landed.
 */
export function statusHint(status, covered = 0) {
    switch (status) {
        case "in_progress":
            return Number(covered) > 0
                ? _t("Mark it done when you are happy with it.")
                : _t("You opened it, and nothing is connected yet.");
        case "skipped":
            return _t("Skipped for now. Nothing is weaker for it — you can come back whenever you like.");
        case "needs_review":
            return _t("This was finished, and the configuration has changed since.");
        default:
            return "";
    }
}

/** The name of one lane, for "4 from the connected system". */
export function laneLabel(lane) {
    switch (lane) {
        case "api": return _t("from the connected system");
        case "excel": return _t("from spreadsheets");
        case "records": return _t("from employee records");
        case "cycle": return _t("carried from the mid-month run");
        default: return "";
    }
}

/**
 * "12 of 19 inputs have a source · 4 from the connected system · 6 from
 * spreadsheets", with only the lanes that have anything in them named.
 *
 * A lane at zero is not information, it is noise: naming four lanes on a
 * configuration that uses one is how a reader stops reading the line at all.
 */
export function coverageLine(mapping) {
    const m = mapping || {};
    const inputs = Number(m.inputs || 0);
    if (!inputs) {
        return _t("This configuration has no inputs to map yet.");
    }
    const mapped = Number(m.mapped || 0);
    const bits = [
        mapped === 1
            ? _t("1 of %s inputs has a source", inputs)
            : _t("%(mapped)s of %(inputs)s inputs have a source",
                 { mapped, inputs }),
    ];
    const lanes = m.by_lane || {};
    for (const lane of LANES) {
        const n = Number(lanes[lane] || 0);
        if (n > 0) {
            bits.push(`${n} ${laneLabel(lane)}`);
        }
    }
    return bits.join(" · ");
}

/** "31 of 38 components placed · 7 in the tray · 4 sections". */
export function payslipLine(payslip) {
    const p = payslip || {};
    const total = Number(p.total || 0);
    if (!total) {
        return _t("There are no components to place yet.");
    }
    const placed = Number(p.placed || 0);
    const tray = Number(p.tray || 0);
    const sections = Number(p.sections || 0);
    const bits = [_t("%(placed)s of %(total)s components placed",
                     { placed, total })];
    if (tray) {
        bits.push(tray === 1 ? _t("1 in the tray") : _t("%s in the tray", tray));
    }
    if (sections) {
        bits.push(sections === 1 ? _t("1 section") : _t("%s sections", sections));
    }
    return bits.join(" · ");
}

/** "3 components were added since you mapped: OTWD, OTWE, OTHO". */
export function changedLine(task, codes) {
    const list = codes || [];
    if (!list.length) {
        return "";
    }
    const names = list.slice(0, 6).join(", ")
        + (list.length > 6 ? _t(" and %s more", list.length - 6) : "");
    if (task === "mapping") {
        return list.length === 1
            ? _t("1 component was added since you mapped: %s", names)
            : _t("%(n)s components were added since you mapped: %(names)s",
                 { n: list.length, names });
    }
    return list.length === 1
        ? _t("1 component was added since you arranged the payslip: %s", names)
        : _t("%(n)s components were added since you arranged the payslip: %(names)s",
             { n: list.length, names });
}

/** "1 component you had placed has gone since: PHONEALLOW". */
export function removedLine(codes) {
    const list = codes || [];
    if (!list.length) {
        return "";
    }
    const names = list.slice(0, 6).join(", ")
        + (list.length > 6 ? _t(" and %s more", list.length - 6) : "");
    return list.length === 1
        ? _t("1 component you had placed has gone since: %s", names)
        : _t("%(n)s components you had placed have gone since: %(names)s",
             { n: list.length, names });
}

/**
 * "Manage later: Settings → Source mapping · same configuration".
 *
 * Said on every card, because the commonest fear at this point in a setup is
 * that skipping something now means losing it for good.
 */
export function manageLater(task) {
    switch (task) {
        case "mapping":
            return _t("Manage later: Settings → Source mapping · same configuration");
        case "payslip":
            return _t("Manage later: Settings → Payslip layout · same configuration");
        default:
            return _t("Manage later: Pay runs → Approvals · every configuration");
    }
}

/**
 * True when the person may press "Mark as done".
 *
 * It appears only once there is something to be done ABOUT — a button that
 * would be refused by the server the moment it is pressed is a button that
 * should not be on the screen (and the server refuses it anyway: rule 9).
 */
export function canMarkDone(task, readiness) {
    const r = readiness || {};
    const covered = task === "mapping"
        ? Number((r.mapping || {}).mapped || 0)
        : Number((r.payslip || {}).placed || 0);
    return covered > 0;
}

/** How far through this step somebody is: "1 of 2 done". */
export function connectProgress(status) {
    const s = status || {};
    const done = ["mapping", "payslip"].filter(
        (k) => s[k] === "configured").length;
    return { done, total: 2 };
}
