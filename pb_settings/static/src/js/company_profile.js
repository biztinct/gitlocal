/** @odoo-module **/
/**
 * `pb_company_profile` — "Your company".
 *
 * ACCESS P9. One record, the caller's own, and thirteen fields on it: the name,
 * the address, how people reach you, the tax and registration numbers, and the
 * logo. Everything else about a company — the currency, where it sits in a
 * group of companies, whether it exists at all, the web address it is reached
 * at — belongs to whoever runs the platform and is not on this page.
 *
 * WHAT MAKES IT MORE THAN A FORM. Nobody edits a company's address for its own
 * sake; they edit it because something PRINTS it. So the right-hand column is
 * not decoration: it is the three places these details actually come out — the
 * top of a payslip, the header of a statutory filing, and the letterhead on an
 * offer or a leaver's letter — drawn live from what is currently in the boxes.
 * Type a new name and you watch the payslip change. That is the difference
 * between "field updated" and knowing what you have just done.
 *
 * FOUR THINGS THIS FILE IS CAREFUL ABOUT.
 *
 *  1. **It sends no company id, ever.** `pb.company.profile` resolves the
 *     caller's own company from the user record and takes no company argument.
 *     Nothing here could name another company even if it wanted to, which is
 *     the point: the browser is not where that decision is made.
 *  2. **Only what CHANGED is sent.** The payload is built by comparing the
 *     boxes against the last saved values, so a save says exactly what it did
 *     ("Saved — the company name and the tax number are updated") and the audit
 *     trail carries one line per real change rather than thirteen per press.
 *  3. **A refusal is shown as a sentence, in place.** The server answers a
 *     blocked field or a bad value with plain English; it is rendered in an
 *     amber bar above the form rather than thrown at Odoo's error dialog, which
 *     would show a technical box for what is a normal, expected answer.
 *  4. **Nothing is a dead end (W5/W29).** There is a way back to Settings, an
 *     explicit list of what this page will NOT change and who to ask about each
 *     one, and a "recent changes" strip that shows the save landing.
 */
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";

/**
 * The boxes, and what each one is.
 *
 * `kind` mirrors the server's whitelist exactly — text, a picked id, or the
 * picture — and a field that is not in this object cannot be typed into, sent,
 * or saved. The server refuses anything not on its own list regardless; this is
 * the same rule stated where the boxes are drawn, not a second authority.
 */
const FIELDS = {
    name: { kind: "text", label: _t("Company name"), wide: true,
            hint: _t("Exactly as it should appear on a payslip.") },
    street: { kind: "text", label: _t("Street"), wide: true },
    street2: { kind: "text", label: _t("Street (second line)"), wide: true },
    city: { kind: "text", label: _t("City") },
    zip: { kind: "text", label: _t("Post code") },
    country_id: { kind: "pick", label: _t("Country") },
    state_id: { kind: "pick", label: _t("State or province") },
    phone: { kind: "text", label: _t("Phone") },
    email: { kind: "text", label: _t("Email") },
    website: { kind: "text", label: _t("Website"), wide: true,
               hint: _t("Including https://") },
    vat: { kind: "text", label: _t("Tax number") },
    company_registry: { kind: "text", label: _t("Registration number") },
};

/** The order and the grouping — four short blocks, not one long column. */
const SECTIONS = [
    { key: "identity", icon: "building", title: _t("Name and logo"),
      note: _t("What this company is called, everywhere it is printed."),
      fields: ["name"] },
    { key: "address", icon: "mapPin", title: _t("Registered address"),
      note: _t("The address that goes on payslips, filings and letters."),
      fields: ["street", "street2", "city", "zip", "country_id", "state_id"] },
    { key: "contact", icon: "mail", title: _t("How people reach you"),
      note: _t("Printed on letters, and used when this system writes to somebody on your behalf."),
      fields: ["phone", "email", "website"] },
    { key: "numbers", icon: "landmark", title: _t("Tax and registration"),
      note: _t("The numbers a statutory filing is checked against. Worth getting right once."),
      fields: ["vat", "company_registry"] },
];

/** Every field name the surface may send. Derived, never written twice. */
export const EDITABLE = [...Object.keys(FIELDS), "logo"];

/** About 4 MB — the same bound the server keeps, said in the browser first so
 *  a big picture is refused before it is uploaded rather than after. */
const MAX_LOGO_BYTES = 4 * 1024 * 1024;

export class PbCompanyProfile extends Component {
    static template = "pb_settings.PbCompanyProfile";
    static components = { HubBackChip };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.back = hubBack(this.props);
        this.sections = SECTIONS;

        this.state = useState({
            loading: true,
            refused: "",        // the whole surface is not for this person
            error: "",          // one refusal or bad value, shown in place
            saving: false,
            form: {},           // what is in the boxes now
            clean: {},          // what was in them when they were last saved
            names: {},          // picked ids -> the words for them
            labels: {},
            fixed: [],
            countries: [],
            states: [],
            history: [],
            logoUrl: "",
            logoPreview: "",    // a picture chosen but not saved yet
            logoNew: null,      // null unchanged | false remove | base64 new
            pulse: "",          // which box was touched last, for the preview
            formKey: 0,         // bumped to redraw the boxes from `form`
        });

        this._pulseTimer = null;
        onWillStart(async () => { await this._load(); });
        onWillUnmount(() => { if (this._pulseTimer) { clearTimeout(this._pulseTimer); } });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    async _load() {
        try {
            const res = await this.orm.call("pb.company.profile", "profile", []);
            this._apply(res);
        } catch (e) {
            // The one error that is not a bug: somebody who may not be here.
            this.state.refused = this._message(e);
        } finally {
            this.state.loading = false;
        }
    }

    _apply(res) {
        const form = {}, names = {};
        for (const key of Object.keys(FIELDS)) {
            const raw = res.company[key];
            form[key] = raw === false || raw === undefined ? "" : raw;
            if (FIELDS[key].kind === "pick") {
                names[key] = res.company[key + "_name"] || "";
            }
        }
        this.state.form = form;
        this.state.clean = { ...form };
        this.state.names = names;
        this.state.labels = res.labels || {};
        this.state.fixed = res.fixed || [];
        this.state.countries = res.countries || [];
        this.state.states = res.states || [];
        this.state.history = res.history || [];
        this.state.logoUrl = res.has_logo ? res.logo_url : "";
        this.state.logoPreview = "";
        this.state.logoNew = null;
        this.state.formKey += 1;
    }

    /** The plain sentence out of a server refusal — never a stack trace. */
    _message(e) {
        return (e && e.data && e.data.message)
            || (e && e.message)
            || _t("Something went wrong. Please try again.");
    }

    // ---------------------------------------------------------------- labels
    /** The country's own word for its tax number, when it has one. */
    labelOf(key) {
        if (key === "vat" && this.state.labels.vat) { return this.state.labels.vat; }
        if (key === "company_registry" && this.state.labels.company_registry) {
            return this.state.labels.company_registry;
        }
        return FIELDS[key].label;
    }

    hintOf(key) {
        if (key === "company_registry" && this.state.labels.registry_hint) {
            return _t("For example %s", this.state.labels.registry_hint);
        }
        return FIELDS[key].hint || "";
    }

    fieldsOf(section) {
        return section.fields.map((k) => ({ key: k, ...FIELDS[k] }));
    }

    /**
     * The key that decides when a box is REDRAWN from the state rather than
     * left as the reader typed it.
     *
     * Two things force it, and both are programmatic changes the browser will
     * not pick up on its own. `formKey` covers Discard and a completed save —
     * an `<input>`'s value attribute does not move the value a person has
     * already typed, so the element has to be recreated. And the province box
     * additionally carries the COUNTRY, because changing the country replaces
     * its whole option list: without the country in the key the old selection
     * would sit there as a name that is no longer in the list.
     */
    fieldKey(f) {
        const country = f.key === "state_id" ? this.state.form.country_id : "";
        return `${f.key}:${this.state.formKey}:${country}`;
    }

    optionsOf(key) {
        return key === "country_id" ? this.state.countries : this.state.states;
    }

    // ----------------------------------------------------------------- edits
    _touch(key) {
        this.state.pulse = key;
        if (this._pulseTimer) { clearTimeout(this._pulseTimer); }
        this._pulseTimer = setTimeout(() => { this.state.pulse = ""; }, 1400);
    }

    onText(key, ev) {
        this.state.form[key] = ev.target.value;
        this.state.error = "";
        this._touch(key);
    }

    async onPick(key, ev) {
        const raw = ev.target.value;
        const id = raw ? parseInt(raw, 10) : "";
        this.state.form[key] = id || "";
        this.state.names[key] = raw
            ? (this.optionsOf(key).find((o) => o.id === id) || {}).name || ""
            : "";
        this.state.error = "";
        this._touch(key);

        if (key === "country_id") {
            // A province belongs to a country, so changing the country empties
            // the province rather than leaving a mismatch the server would
            // then have to refuse. The list is fetched for the new country.
            this.state.form.state_id = "";
            this.state.names.state_id = "";
            this.state.states = [];
            if (id) {
                try {
                    this.state.states = await this.orm.call(
                        "pb.company.profile", "states", [id]);
                } catch (e) {
                    this.state.error = this._message(e);
                }
            }
        }
    }

    // ------------------------------------------------------------------ logo
    onLogoDrop(ev) {
        ev.preventDefault();
        const file = ev.dataTransfer && ev.dataTransfer.files
            && ev.dataTransfer.files[0];
        if (file) { this._readLogo(file); }
    }

    onLogoPick(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (file) { this._readLogo(file); }
        ev.target.value = "";       // the same file can be picked again
    }

    _readLogo(file) {
        if (!/^image\//.test(file.type)) {
            this.state.error = _t("That file is not a picture. Please choose a PNG or a JPG.");
            return;
        }
        if (file.size > MAX_LOGO_BYTES) {
            this.state.error = _t("That picture is too big. Please use one under 4 MB.");
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const url = String(reader.result || "");
            this.state.logoPreview = url;
            this.state.logoNew = url.split(",")[1] || "";
            this.state.error = "";
            this._touch("logo");
        };
        reader.onerror = () => {
            this.state.error = _t("That picture could not be read. Please try another one.");
        };
        reader.readAsDataURL(file);
    }

    removeLogo() {
        this.state.logoPreview = "";
        this.state.logoNew = false;
        this._touch("logo");
    }

    get logoSrc() {
        if (this.state.logoPreview) { return this.state.logoPreview; }
        if (this.state.logoNew === false) { return ""; }
        return this.state.logoUrl;
    }

    // ----------------------------------------------------------------- dirty
    get changedKeys() {
        return Object.keys(FIELDS).filter(
            (k) => String(this.state.form[k] ?? "") !== String(this.state.clean[k] ?? ""));
    }

    get dirty() {
        return this.changedKeys.length > 0 || this.state.logoNew !== null;
    }

    get dirtyNote() {
        const n = this.changedKeys.length + (this.state.logoNew !== null ? 1 : 0);
        return n === 1 ? _t("1 change not saved yet")
                       : _t("%s changes not saved yet", n);
    }

    // ------------------------------------------------------------------ save
    async save() {
        if (this.state.saving || !this.dirty) { return; }
        const values = {};
        for (const key of this.changedKeys) {
            const raw = this.state.form[key];
            values[key] = FIELDS[key].kind === "pick"
                ? (raw ? parseInt(raw, 10) : false)
                : String(raw ?? "");
        }
        if (this.state.logoNew !== null) {
            values.logo = this.state.logoNew === false ? false : this.state.logoNew;
        }

        this.state.saving = true;
        this.state.error = "";
        try {
            const res = await this.orm.call(
                "pb.company.profile", "save", [values]);
            this._apply(res.profile);
            this.notification.add(res.sentence, { type: "success" });
        } catch (e) {
            // Expected, not exceptional: the server refuses a blocked field or
            // a value it cannot use, and says why in words. Showing that in
            // place is the whole difference between a refusal and a crash.
            this.state.error = this._message(e);
        } finally {
            this.state.saving = false;
        }
    }

    discard() {
        this.state.form = { ...this.state.clean };
        this.state.logoNew = null;
        this.state.logoPreview = "";
        this.state.error = "";
        this.state.pulse = "";
        this.state.formKey += 1;
    }

    // --------------------------------------------------------------- preview
    get previewName() {
        return this.state.form.name || _t("Your company name");
    }

    /** The address as one block, empty lines dropped. */
    get previewAddress() {
        const f = this.state.form;
        const lineOne = [f.street, f.street2].filter(Boolean).join(", ");
        const lineTwo = [f.city, this.state.names.state_id, f.zip]
            .filter(Boolean).join(", ");
        const lineThree = this.state.names.country_id || "";
        return [lineOne, lineTwo, lineThree].filter(Boolean);
    }

    get previewContact() {
        const f = this.state.form;
        return [f.phone, f.email, f.website].filter(Boolean).join("  ·  ");
    }

    get previewVat() { return this.state.form.vat || ""; }
    get previewRegistry() { return this.state.form.company_registry || ""; }

    /** The sample is the reader's own name and this month — a preview of a
     *  stranger's payslip reads as stock art rather than as their product. */
    get sampleWho() { return user.name || _t("An employee"); }

    get samplePeriod() {
        try {
            return new Date().toLocaleDateString(undefined,
                { month: "long", year: "numeric" });
        } catch { return ""; }
    }

    get sampleDate() {
        try {
            return new Date().toLocaleDateString(undefined,
                { day: "numeric", month: "long", year: "numeric" });
        } catch { return ""; }
    }

    fresh(key) { return this.state.pulse === key; }

    /** True while any of the address boxes is the one being typed into. */
    get addressFresh() {
        return ["street", "street2", "city", "zip", "country_id", "state_id"]
            .includes(this.state.pulse);
    }
}

registry.category("actions").add("pb_company_profile", PbCompanyProfile);
