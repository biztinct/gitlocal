/** @odoo-module **/
/**
 * `pb_training_numbers` — the Training lens on the Insights hub.
 *
 * TWO RATIOS FIRST AND ONE SENTENCE ABOVE THEM. A training programme is judged
 * on whether people FINISH what they were set and whether they PASS the test
 * at the end, and a screen that opens on a grid of figures makes a reader do
 * the arithmetic the sentence could have done for them (R113).
 *
 * NOTHING HERE RECOMPUTES A NUMBER. The server computes every figure, every
 * ratio and every split; a second opinion written in JavaScript would only
 * ever disagree with the one that counts, and the spreadsheet is built from
 * the same read so it cannot disagree with the screen either.
 *
 * THE EMPTY STATE TEACHES. A range with nothing in it says so in words, with
 * the dates in the sentence, rather than drawing six zeros — a screen of
 * zeros is how a working feature gets reported as broken.
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — the set is
 * CLOSED and an unknown name renders a plain circle with no error, so a name
 * used here is a name that is in that file.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The ranges somebody actually asks for, in the order they ask for them. */
const RANGES = [
    { key: "30", label: _t("Last 30 days"), days: 30 },
    { key: "90", label: _t("Last 3 months"), days: 90 },
    { key: "180", label: _t("Last 6 months"), days: 180 },
    { key: "365", label: _t("Last year"), days: 365 },
];

export class PbTrainingNumbers extends Component {
    static template = "pb_training.PbTrainingNumbers";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ranges = RANGES;

        this.state = useState({
            loaded: false,
            allowed: true,
            empty: true,
            busy: false,
            range: "90",
            from: "",
            to: "",
            custom: false,
            filters: { department_id: 0, channel_id: 0, reason: "" },
            headline: "",
            total: 0,
            tiles: [],
            byDepartment: [],
            byCourse: [],
            byReason: [],
            trend: [],
            claims: {},
            lists: { courses: [], departments: [] },
            reasons: [],
        });

        onWillStart(async () => {
            this.pickRange("90", { reload: false });
            await this.load();
        });
    }

    ic(n, s = 16) { return ic(n, s); }

    /** A date, as the value a `date` input wants. */
    static iso(when) {
        const pad = (n) => String(n).padStart(2, "0");
        return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-`
            + `${pad(when.getDate())}`;
    }

    pickRange(key, { reload = true } = {}) {
        const row = RANGES.find((r) => r.key === key);
        this.state.range = key;
        this.state.custom = !row;
        if (row) {
            const to = new Date();
            const from = new Date();
            from.setDate(from.getDate() - row.days);
            this.state.from = PbTrainingNumbers.iso(from);
            this.state.to = PbTrainingNumbers.iso(to);
        }
        if (reload) { return this.load(); }
        return null;
    }

    onDate(which, ev) {
        this.state[which] = ev.target.value;
        this.state.custom = true;
        this.state.range = "";
        return this.load();
    }

    /** Only the filters that are actually set — an empty one is not a filter. */
    activeFilters() {
        const f = this.state.filters;
        const out = {};
        if (f.department_id) { out.department_id = Number(f.department_id); }
        if (f.channel_id) { out.channel_id = Number(f.channel_id); }
        if (f.reason) { out.reason = f.reason; }
        return out;
    }

    async setFilter(key, value) {
        // A CHIP THAT IS ALREADY ON IS A CHIP THAT TURNS OFF. Otherwise the
        // only way back to everything is a page reload, which is a dead end.
        this.state.filters[key] =
            String(this.state.filters[key]) === String(value) ? (
                key === "reason" ? "" : 0) : value;
        await this.load();
    }

    get anyFilter() {
        return Object.keys(this.activeFilters()).length > 0;
    }

    async clearFilters() {
        this.state.filters.department_id = 0;
        this.state.filters.channel_id = 0;
        this.state.filters.reason = "";
        await this.load();
    }

    async load() {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.training.analytics", "get_numbers",
                [this.state.from, this.state.to, this.activeFilters()]);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                empty: !!d.empty,
                headline: d.headline || "",
                total: d.total || 0,
                tiles: d.tiles || [],
                byDepartment: d.by_department || [],
                byCourse: d.by_course || [],
                byReason: d.by_reason || [],
                trend: d.trend || [],
                claims: d.claims || {},
                lists: d.lists || { courses: [], departments: [] },
                reasons: d.reasons || [],
                loaded: true,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            console.warn("pb_training: the training numbers could not be read",
                         e);
        } finally {
            this.state.busy = false;
        }
    }

    /** The widest bar in a table is 100%; everything else is relative to it. */
    share(rows, value, key = "total") {
        const top = Math.max(...rows.map((r) => Number(r[key] || 0)), 0);
        if (!top) { return 0; }
        return Math.round((Number(value || 0) / top) * 100);
    }

    /** A ratio nobody can answer yet is a dash, never a zero. */
    pct(value) {
        return (value === null || value === undefined) ? "—" : `${value}%`;
    }

    /**
     * The split row's own sentence.
     *
     * "— finished" is what a dash pasted in front of a word looks like, and it
     * reads as a typo rather than as "there is nothing to measure here". A row
     * whose every assignment has more time agreed has no completion ratio at
     * all, and the honest answer is a sentence.
     */
    finishedWord(row) {
        if (row.completion === null || row.completion === undefined) {
            return _t("nothing to measure yet");
        }
        return _t("%s%% finished", row.completion);
    }

    /** The tallest week in the trend is the full height of the chart. */
    trendHeight(value) {
        const top = Math.max(
            ...this.state.trend.map((w) => Math.max(w.set, w.done)), 0);
        if (!top) { return 2; }
        return Math.max(Math.round((Number(value || 0) / top) * 100), 2);
    }

    async download() {
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.training.analytics", "export_xlsx",
                [this.state.from, this.state.to, this.activeFilters()]);
            if (!res || !res.file_b64) { return; }
            // A DATA URL AND NOT A SERVER ROUTE. The file is built for this
            // reader, from this reader's own company set, and leaving it on
            // the server as an attachment would be a copy of the company's
            // training figures sitting in a table nobody remembers to clear.
            const a = document.createElement("a");
            a.href = `data:${res.mimetype};base64,${res.file_b64}`;
            a.download = res.filename || "training.xlsx";
            document.body.appendChild(a);
            a.click();
            a.remove();
            this.notif.add(_t("The spreadsheet is in your downloads."),
                           { type: "success" });
        } catch (e) {
            const message = (e && e.data && e.data.message)
                || _t("That did not work.");
            this.notif.add(message, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("pb_training_numbers", PbTrainingNumbers);
