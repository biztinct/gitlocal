/** @odoo-module **/
/**
 * The sentence, the chips, and the small helpers every approval surface shares.
 *
 * WHY THE SENTENCE IS WRITTEN TWICE. The server owns the authoritative one:
 * `biz.approval.engine.summary()` is what a published version stores and what
 * the Matrix row reads. This file is its MIRROR, and it exists for one reason —
 * the builder has to answer on every keystroke, and a round trip per keystroke
 * is not an answer. The two are reconciled on every save: `save_draft` returns
 * the server's sentence and the builder shows that one from then on. If they
 * ever disagree, the server's is the true one and the mirror is the bug.
 *
 * It is a PORT, not an interpretation: `sentence()` and `routeLabels()` below
 * follow `definition.py`'s `sentence()` and `route_labels()` clause for clause,
 * including the rule that a "tell somebody" step is never counted as a check.
 *
 * Every string here goes through `_t`. Nothing here says a model name, a state
 * key or anything else a person has not seen on their own screen.
 */
import { _t } from "@web/core/l10n/translation";

/** A step that is a check. "Tell somebody" is never one. */
export function decisionSteps(definition) {
    return ((definition && definition.steps) || [])
        .filter((step) => step.kind !== "notify");
}

/** An amount with thousands separators, in the money it is actually in. */
export function money(amount, currency) {
    const n = Number(amount || 0);
    const text = n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return currency ? `${text} ${currency}` : text;
}

/** The same amount, shortened, for a chip that has no room for all of it. */
export function shortMoney(amount, currency) {
    const n = Number(amount || 0);
    let text;
    if (Math.abs(n) >= 1e9) {
        text = `${(n / 1e9).toLocaleString(undefined, { maximumFractionDigits: 2 })}bn`;
    } else if (Math.abs(n) >= 1e6) {
        text = `${(n / 1e6).toLocaleString(undefined, { maximumFractionDigits: 1 })}m`;
    } else {
        text = n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    }
    return currency ? `${text} ${currency}` : text;
}

/** A date and time a person can read, in their own machine's locale. */
export function when(value) {
    if (!value) { return ""; }
    const date = new Date(String(value).replace(" ", "T") + "Z");
    if (isNaN(date.getTime())) { return String(value); }
    return date.toLocaleString(undefined, {
        weekday: "short", day: "numeric", month: "short",
        hour: "2-digit", minute: "2-digit",
    });
}

/** Just the day, for a hand-over that lasts days rather than minutes. */
export function day(value) {
    if (!value) { return ""; }
    const date = new Date(`${value}T00:00:00`);
    if (isNaN(date.getTime())) { return String(value); }
    return date.toLocaleDateString(undefined, {
        day: "numeric", month: "short", year: "numeric",
    });
}

/** Plain words for one step's "who decides" — no keys, no model names. */
export function whoLabel(who, roles, people) {
    const w = who || {};
    const roleNames = roles || {};
    const names = people || {};
    if (w.mode === "role") {
        const name = roleNames[w.role] || w.role || "";
        return w.scope === "company"
            ? _t("%s · whole company", name)
            : _t("%s for this part of the business", name);
    }
    if (w.mode === "manager") { return _t("Their manager"); }
    if (w.mode === "skip") { return _t("Their manager's manager"); }
    if (w.mode === "people") {
        const list = (w.user_ids || []).map((id) => names[id] || _t("Somebody"));
        if (list.length > 1) {
            return w.all
                ? _t("%s · everyone", list.join(" + "))
                : _t("%s · any one", list.join(" + "));
        }
        return list.join(" + ");
    }
    if (w.mode === "team") {
        return _t("Any one of %s", w.label || _t("the team"));
    }
    if (w.mode === "preparer") { return _t("Whoever sent it in"); }
    return "";
}

/** The same, but as a phrase that fits inside the sentence. */
function whoPhrase(who, roles, people) {
    const w = who || {};
    if (w.mode === "role") {
        const name = (roles || {})[w.role] || w.role || "";
        return w.scope === "company"
            ? _t("the %s", name)
            : _t("the %s for its part of the business", name);
    }
    if (w.mode === "manager") { return _t("their manager"); }
    if (w.mode === "skip") { return _t("their manager's manager"); }
    if (w.mode === "people") {
        const list = (w.user_ids || [])
            .map((id) => (people || {})[id] || _t("somebody"));
        if (list.length > 1 && !w.all) {
            return _t("any one of %s", list.join(", "));
        }
        return list.join(w.all ? _t(" and ") : ", ");
    }
    if (w.mode === "team") {
        return _t("any member of %s", w.label || _t("the team"));
    }
    return "";
}

/** One typed condition, as a clause. Mirrors `definition.condition_phrase`. */
export function conditionPhrase(condition, factLabels) {
    if (!condition) { return ""; }
    const label = (factLabels || {})[condition.fact] || condition.fact || "";
    const value = condition.value;
    if (typeof value === "boolean") {
        return value ? _t("%s is yes", label) : _t("%s is no", label);
    }
    const shown = Array.isArray(value) ? value.join(", ") : String(value);
    const phrases = {
        eq: _t("is"), ne: _t("is not"), gt: _t("is more than"),
        gte: _t("is at least"), lt: _t("is less than"),
        lte: _t("is at most"), in: _t("is one of"),
        not_in: _t("is not one of"),
    };
    return `${label} ${phrases[condition.op] || _t("is")} ${shown}`;
}

/**
 * The short chips a Matrix row shows. Port of `definition.route_labels`.
 */
export function routeLabels(definition, roles, people, currency) {
    const out = [];
    const tiers = (definition && definition.tiers) || {};
    for (const step of decisionSteps(definition)) {
        if (step.kind === "fast") {
            out.push(_t("No approval needed"));
            continue;
        }
        let label = whoLabel(step.who, roles, people);
        if (tiers.enabled && step.min_amount) {
            label = _t("%(who)s (%(amount)s and above)", {
                who: label, amount: shortMoney(step.min_amount, currency),
            });
        }
        out.push(label);
    }
    return out;
}

/**
 * One readable line describing the whole route. Port of `definition.sentence`.
 */
export function sentence(definition, roles, people, factLabels, currency) {
    const steps = decisionSteps(definition);
    if (!steps.length) {
        return _t("Nothing is checked yet. Add a step below.");
    }
    const tiers = (definition && definition.tiers) || {};
    const parts = [];
    steps.forEach((step, index) => {
        const last = index === steps.length - 1;
        if (step.kind === "fast") {
            parts.push(_t("it is applied at once and recorded"));
            return;
        }
        const who = step.who || {};
        let verb;
        if (who.mode === "people" && who.all
                && (who.user_ids || []).length > 1) {
            verb = _t("must all approve");
        } else if (step.kind === "review") {
            verb = _t("reviews it");
        } else {
            verb = last ? _t("gives final approval") : _t("approves");
        }
        let tail = "";
        if (tiers.enabled && step.min_amount) {
            tail += _t(" when the amount is %s or more",
                       money(step.min_amount, currency));
        }
        if (step.condition) {
            tail += _t(", only when %s",
                       conditionPhrase(step.condition, factLabels));
        }
        parts.push(`${whoPhrase(who, roles, people)} ${verb}${tail}`);
    });
    let line = _t("After it is sent in, %s.", parts[0]);
    for (const part of parts.slice(1)) {
        line = `${line} ${_t("Then %s.", part)}`;
    }
    if (((definition && definition.steps) || [])
            .some((step) => step.kind === "notify")) {
        line = `${line} ${_t("Other people are told along the way.")}`;
    }
    return line;
}

/** The words each kind of step wears on its card. */
export function kindLabel(kind) {
    return {
        review: _t("Review"),
        approve: _t("Final approval"),
        joint: _t("Joint approval · everyone must approve"),
        any: _t("Any one of them decides"),
        notify: _t("Tell somebody · never counted as a check"),
        fast: _t("No approval needed · applied at once and recorded"),
    }[kind] || "";
}

/** The four words a status pill can say, and the tone it wears. */
export function statusMeta(status) {
    return {
        live: { label: _t("In use"), tone: "ok" },
        draft: { label: _t("Draft"), tone: "muted" },
        needs: { label: _t("Needs people"), tone: "warn" },
        soon: { label: _t("Not connected yet"), tone: "blue" },
        // A row another row already answers. NOT "not connected": that says
        // nobody is checking it, about something somebody is.
        covered: { label: _t("Decided with another"), tone: "muted" },
    }[status] || { label: "", tone: "muted" };
}

/** Initials for an avatar, from whatever name we were given. */
export function initials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) { return "?"; }
    if (parts.length === 1) { return parts[0].slice(0, 2).toUpperCase(); }
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** A fresh step key that cannot collide with one already in the document. */
export function nextStepKey(definition) {
    const used = new Set(((definition && definition.steps) || [])
        .map((step) => step.key));
    let n = 1;
    while (used.has(`s${n}`)) { n += 1; }
    return `s${n}`;
}

/** A deep copy of plain JSON. The definition document is JSON and only JSON. */
export function copy(value) {
    return JSON.parse(JSON.stringify(value === undefined ? null : value));
}
