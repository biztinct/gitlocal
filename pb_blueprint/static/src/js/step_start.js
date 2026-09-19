/** @odoo-module **/

import { Component, useState, useRef, useEffect } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";
import { AUDIENCES, REALLIFE, STEP_META } from "./blueprint_steps";

/**
 * Step 1 — who you are, what you start from, and who you are paying.
 *
 * The one step in B1 that does real work: pressing Continue here creates the
 * draft configuration and seeds it. Everything on this screen is therefore
 * either a decision the seeding needs (name, country, cycle, starter) or a
 * decision the LATER steps need (who you pay, which real-life situations), and
 * nothing is asked twice.
 *
 * After creation the identity fields that the components depend on — country
 * and starting point — become read-only with a "Change" link, because silently
 * accepting a country change after 37 components have been seeded in another
 * country's shape is how a Singapore payroll ends up labelled Vietnam.
 */
export class StepStart extends Component {
    static template = "pb_blueprint.StepStart";
    static props = {
        form: { type: Object },              // {name,country_code,cycle_type,effective_from,template_key}
        situations: { type: Object },        // {audiences:[], reallife:[]}
        starters: { type: Object },          // bp_templates payload
        countries: { type: Array },
        cycles: { type: Array },
        company: { type: String },
        created: { type: Boolean },
        // The workbook is the starting point and it has not been read yet —
        // the one starter that is still owed something after the draft exists.
        needsWorkbook: { type: Boolean, optional: true },
        busy: { type: Boolean },
        progress: { type: Array },           // [{label, done}]
        error: { type: [String, Boolean], optional: true },
        nameError: { type: [String, Boolean], optional: true },
        onSet: { type: Function },
        onPickStarter: { type: Function },
        onImportWorkbook: { type: Function, optional: true },
        onToggleAudience: { type: Function },
        onToggleReallife: { type: Function },
        onUnlock: { type: Function },
        onRetry: { type: Function },
    };

    setup() {
        this.AUDIENCES = AUDIENCES;
        this.REALLIFE = REALLIFE;
        this.meta = STEP_META.start;
        this.nameRef = useRef("name");
        this.state = useState({ hovered: "" });
        // The caret follows the error. The shell sets `nameError`; moving the
        // focus is this component's job because the input lives here.
        useEffect(
            () => { if (this.props.nameError && this.nameRef.el) this.nameRef.el.focus(); },
            () => [this.props.nameError],
        );
    }

    ic(name, size = 16) { return ic(name, size); }

    onField(field, ev) { this.props.onSet(field, ev.target.value); }

    get starters() { return (this.props.starters && this.props.starters.starters) || []; }

    get hasTemplate() { return !!(this.props.starters && this.props.starters.has_template); }

    get countryLabel() {
        const row = (this.props.countries || []).find(
            (c) => c.code === this.props.form.country_code);
        return row ? row.label : this.props.form.country_code;
    }

    get chosen() {
        return this.starters.find((s) => s.key === this.props.form.template_key) || null;
    }

    /**
     * SCHEMECTX P1 — what this configuration will pay in.
     *
     * The help under Country has always promised "Decides the currency". It
     * now shows the answer, live, as the country changes — because an India
     * configuration quietly paying in dong is exactly the defect this closes.
     * Empty when an older server sends no map, and the chip is then hidden
     * rather than guessing.
     */
    get money() {
        const map = (this.props.starters && this.props.starters.currencies) || null;
        if (!map) { return null; }
        return map[this.props.form.country_code] || null;
    }

    /** "₹ INR" — the sign people read, then the name they file under. */
    get moneyLabel() {
        const m = this.money;
        if (!m) { return ""; }
        if (m.symbol && m.name && m.symbol !== m.name) { return `${m.symbol} ${m.name}`; }
        return m.name || m.symbol || "";
    }

    /** One whole sentence, so it translates as one. */
    get moneyLine() {
        const label = this.moneyLabel;
        return label ? _t("Pays in %s", label) : "";
    }

    /** The one amber line, only when nobody has priced this money yet. */
    get moneyWarning() {
        const hints = (this.props.starters && this.props.starters.fx_hint) || null;
        if (!hints) { return ""; }
        return hints[this.props.form.country_code] || "";
    }

    /** The note under the starter grid — it says what was chosen FOR you. */
    get starterNote() {
        const chosen = this.chosen;
        if (!chosen) return "";
        if (chosen.kind === "template") {
            return _t(
                "“%(name)s” is selected. Tax values come from the %(version)s rule pack; you can review them in Pay rules.",
                { name: chosen.name, version: chosen.version || this.countryLabel });
        }
        if (chosen.kind === "excel") {
            // After the draft exists the promise has either been kept or it has
            // not, and the note has to say which. A screen that still reads
            // "your workbook opens as soon as the configuration is created",
            // over a configuration that was created and has nothing in it, is
            // the reason the review looked lost.
            if (this.props.needsWorkbook) {
                return _t("Nothing has come in from your workbook yet. Open the review to bring its columns in — nothing is imported until you say so.");
            }
            return _t("Your workbook opens for review as soon as the configuration is created. Nothing is imported until you say so.");
        }
        return _t("You will start with no components. The country's shared rules stay available in Pay rules.");
    }

    /** Zero dead-ends: a country with no starter says so rather than looking broken. */
    get noStarterNote() {
        if (this.hasTemplate) return "";
        return _t("There is no ready-made starter for %s yet — import a workbook or start from a blank canvas.",
                  this.countryLabel);
    }

    starterMeta(s) {
        if (s.kind !== "template") return "";
        const bits = [];
        if (s.version) bits.push(_t("v%s", s.version));
        if (s.effective_date) bits.push(_t("effective %s", s.effective_date));
        return bits.join(" · ");
    }

    starterCounts(s) {
        if (s.kind !== "template") return "";
        const tables = s.rate_table_count;
        const comps = _t("%s components", s.component_count);
        if (!tables) return comps;
        return tables === 1
            ? _t("%(comps)s · 1 rate table", { comps })
            : _t("%(comps)s · %(n)s rate tables", { comps, n: tables });
    }

    starterIcon(s) {
        if (s.kind === "excel") return "fileSpreadsheet";
        if (s.kind === "blank") return "plus";
        return "layers";
    }

    has(list, key) { return (list || []).includes(key); }
}
