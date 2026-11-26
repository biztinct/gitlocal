/**
 * PSCHEME P4 B — "Usual pay scheme by country" on Mapping › Who is paid by what.
 *
 * The safety net for somebody who arrives without a pay scheme of their own is,
 * in order, their team's usual scheme (optional) and then their country's usual
 * scheme. The second one used to be invisible: a rule line only support could
 * see. This section shows it as one plain line per Country of work, lets HR and
 * payroll choose / change / remove it (through the Mapping route, kind
 * `country_set`), and lists every other rule read-only.
 *
 * Hero moment: the invisible safety net becomes a few plain lines — and the one
 * hole in it is the only thing in colour.
 *
 * Quiet when all is well (collapsed, grey summary); open by itself when a hole
 * exists; the reader's own open / closed choice is remembered per browser.
 */
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { SchemeMapBoard } from "@pb_scheme_map/js/scheme_map_board";
import { psIc } from "@pb_scheme_map/js/person_scheme";

const BOARD = "pb.scheme.board";
const STORE = "pb_scheme_map.country_lines.open";

function errorText(e, fallback) {
    const data = (e && e.data) || (e && e.message && e.message.data);
    return (data && data.message) || fallback || _t("That did not work. Try again.");
}
function num(n) { return Number(n || 0).toLocaleString(); }
function peopleWords(n) {
    return Number(n) === 1 ? _t("1 person") : _t("%s people", num(n));
}
function remembered() {
    try {
        const v = window.localStorage.getItem(STORE);
        return v === null ? null : v === "1";
    } catch {
        return null;
    }
}
function remember(open) {
    try { window.localStorage.setItem(STORE, open ? "1" : "0"); } catch { /* private window */ }
}

export class CountryLines extends Component {
    static template = "pb_scheme_map.CountryLines";
    static props = {
        companyId: Number,
        version: { type: Number, optional: true },
        focus: { type: String, optional: true },
        canEdit: { type: Boolean, optional: true },
        studioAction: { type: String, optional: true },
        onChanged: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = psIc;
        this.state = useState({
            data: null, loading: true, error: "", open: false,
            editing: "", mode: "", pick: 0, showOther: false, confirmOther: false,
            saving: false, problem: "", othersOpen: false,
        });
        onWillStart(() => this.load(this.props));
        onWillUpdateProps(async (next) => {
            if (next.companyId !== this.props.companyId || next.version !== this.props.version) {
                await this.load(next);
            }
            if (next.focus && next.focus !== this.props.focus) {
                this.state.open = true;
                this.startChoose(next.focus);
            }
        });
    }

    async load(props) {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.data = await this.orm.call(BOARD, "country_lines", [props.companyId || 0]);
            const kept = remembered();
            this.state.open = this.state.data.holes ? true : (kept === null ? false : kept);
            if (props.focus) {
                this.state.open = true;
                this.startChoose(props.focus);
            }
        } catch (e) {
            this.state.error = errorText(e, _t("The country lines could not be read."));
        }
        this.state.loading = false;
    }

    // ------------------------------------------------------------ reading
    get d() { return this.state.data || { rows: [], others: [], other_schemes: [] }; }
    get rows() { return this.d.rows || []; }
    get others() { return this.d.others || []; }
    get canChange() { return this.props.canEdit !== false && this.d.can_propose && !this.d.blocked; }
    get saveLabel() { return this.d.lane === "route" ? _t("Ask for this change") : _t("Save"); }
    get headLine() {
        if (this.d.holes) {
            return this.d.holes === 1
                ? _t("1 person has no pay scheme and nothing catches them")
                : _t("%s people have no pay scheme and nothing catches them", num(this.d.holes));
        }
        return _t("%(set)s of %(total)s countries have a usual pay scheme",
                  { set: num(this.d.set), total: num(this.rows.length) });
    }
    peopleLine(row) {
        return _t("%(people)s · %(rely)s rely on this today",
                  { people: peopleWords(row.people), rely: num(row.rely) });
    }
    holeLine(row) {
        return row.holes === 1
            ? _t("1 person here has no pay scheme and nothing catches them")
            : _t("%s people here have no pay scheme and nothing catches them", num(row.holes));
    }
    otherRuleLine(row) {
        return row.by_other_rule === 1
            ? _t("1 person is paid by another rule")
            : _t("%s people are paid by another rule", num(row.by_other_rule));
    }
    noSchemeLine(row) { return _t("No active pay scheme for %s yet.", row.country_name); }
    ruleTitle(rule) { return `${rule.words} → ${rule.config}`; }
    ruleSub(rule) { return _t("Reaches %s today · Set up by support", peopleWords(rule.reaches)); }
    get othersTitle() { return _t("Other rules (%s)", num(this.others.length)); }
    rowClass(row) {
        return "smp-cl__row is-" + row.state + (row.holes ? " is-hole" : "")
            + (this.state.editing === row.country ? " is-editing" : "");
    }

    // ------------------------------------------------------------ the chooser
    rowOf(code) { return this.rows.find((r) => r.country === code); }
    get editRow() { return this.rowOf(this.state.editing); }
    get choices() {
        const row = this.editRow;
        if (!row) { return []; }
        const own = row.options || [];
        if (!this.state.showOther) { return own; }
        const ids = new Set(own.map((o) => o.id));
        return own.concat((this.d.other_schemes || [])
            .filter((o) => !ids.has(o.id) && o.country !== row.country)
            .map((o) => Object.assign({ other: true }, o)));
    }
    get otherCount() {
        const row = this.editRow;
        if (!row) { return 0; }
        return (this.d.other_schemes || []).filter((o) => o.country !== row.country).length;
    }
    get otherToggle() { return _t("Show pay schemes of other countries (%s)", num(this.otherCount)); }
    get picked() { return this.choices.find((o) => o.id === this.state.pick) || null; }
    get pickedIsOther() { return !!(this.picked && this.picked.other); }
    get consequence() {
        const row = this.editRow;
        if (!row) { return ""; }
        if (this.state.mode === "remove") {
            return _t("New people in %s without a pay scheme of their own or a team's usual one will not be paid until they get one. Nobody with their own pay scheme changes.",
                      row.country_name);
        }
        if (!this.picked) { return _t("Pick the pay scheme that catches people in %s.", row.country_name); }
        return _t("New people in %(country)s without a pay scheme of their own will be paid by %(scheme)s. Nobody with their own pay scheme changes.",
                  { country: row.country_name, scheme: this.picked.name });
    }
    get canSave() {
        if (this.state.saving) { return false; }
        if (this.state.mode === "remove") { return true; }
        const row = this.editRow;
        if (!this.picked || !row) { return false; }
        if (row.line && row.line.config_id === this.picked.id && !row.line.extra_lines) { return false; }
        return !this.pickedIsOther || this.state.confirmOther;
    }
    cardMeta(o) {
        return [o.other ? o.country_name : "", o.kind_words, o.currency].filter((x) => x).join(" · ");
    }
    startChoose(code) {
        const row = this.rowOf(code);
        if (!row || !this.canChange) { return; }
        this.state.editing = code;
        this.state.mode = "set";
        this.state.pick = row.line ? row.line.config_id : ((row.options || []).length === 1 ? row.options[0].id : 0);
        this.state.showOther = !!(row.line && row.line.other_country);
        this.state.confirmOther = !!(row.line && row.line.other_country);
        this.state.problem = "";
    }
    startRemove(code) {
        if (!this.canChange) { return; }
        this.state.editing = code;
        this.state.mode = "remove";
        this.state.problem = "";
    }
    cancel() { this.state.editing = ""; this.state.mode = ""; this.state.problem = ""; }
    pick(o) {
        this.state.pick = o.id;
        if (!o.other) { this.state.confirmOther = false; }
    }
    onCardKey(o, ev) {
        const list = this.choices;
        const i = list.findIndex((x) => x.id === o.id);
        let next = null;
        if (ev.key === "ArrowDown" || ev.key === "ArrowRight") { next = list[(i + 1) % list.length]; }
        if (ev.key === "ArrowUp" || ev.key === "ArrowLeft") { next = list[(i - 1 + list.length) % list.length]; }
        if (ev.key === " " || ev.key === "Enter") { ev.preventDefault(); this.pick(o); return; }
        if (ev.key === "Escape") { ev.stopPropagation(); this.cancel(); return; }
        if (next) {
            ev.preventDefault();
            this.pick(next);
            const el = ev.currentTarget.parentElement.querySelector(`[data-id="${next.id}"]`);
            if (el) { el.focus(); }
        }
    }
    toggleOther() { this.state.showOther = !this.state.showOther; }
    toggleConfirm(ev) { this.state.confirmOther = ev.target.checked; }
    toggle() {
        this.state.open = !this.state.open;
        remember(this.state.open);
    }
    toggleOthers() { this.state.othersOpen = !this.state.othersOpen; }
    onPanelKey(ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); this.cancel(); }
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey) && this.canSave) { this.save(); }
    }

    // ------------------------------------------------------------ writing
    async save() {
        const row = this.editRow;
        if (!row || !this.canSave) { return; }
        this.state.saving = true;
        this.state.problem = "";
        try {
            const answer = await this.orm.call(BOARD, "country_set", [
                this.props.companyId, row.country,
                this.state.mode === "remove" ? false : this.state.pick,
                this.pickedIsOther && this.state.confirmOther]);
            if (answer && answer.ok === false) {
                this.state.problem = answer.message || _t("Nothing was changed.");
            } else {
                this.notif.add((answer && answer.message) || _t("Saved."),
                               { type: answer && answer.pending ? "info" : "success" });
                this.cancel();
                await this.load(this.props);
                if (this.props.onChanged) { await this.props.onChanged(); }
            }
        } catch (e) {
            this.state.problem = errorText(e, _t("Nothing was changed. Try again."));
        }
        this.state.saving = false;
    }
    async removeRule(rule) {
        if (!rule.removable || !this.canChange) { return; }
        try {
            const answer = await this.orm.call(BOARD, "other_rule_remove", [rule.id, this.props.companyId]);
            this.notif.add((answer && answer.message) || _t("Saved."),
                           { type: answer && answer.pending ? "info" : "success" });
            await this.load(this.props);
            if (this.props.onChanged) { await this.props.onChanged(); }
        } catch (e) {
            this.notif.add(errorText(e, _t("Nothing was changed. Try again.")), { type: "warning" });
        }
    }
    addScheme() {
        this.action.doAction(this.props.studioAction || "pb_formula_studio.action_pb_formula_studio",
                             { clearBreadcrumbs: false }).catch(() => {});
    }
}

SchemeMapBoard.components = { ...(SchemeMapBoard.components || {}), CountryLines };
