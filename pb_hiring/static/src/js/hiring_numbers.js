/** @odoo-module **/
/**
 * `pb_hiring_numbers` — the Hiring lens on the Insights hub.
 *
 * EIGHT NUMBERS, THREE TABLES AND ONE SENTENCE, and the sentence comes first.
 * A hiring process is judged on how long it takes and how often the answer is
 * yes, and a screen that opens on a grid of figures makes a reader do the
 * arithmetic that the sentence could have done for them.
 *
 * EVERY FIGURE IS ABOUT ONE COHORT — the roles AGREED inside the range. That
 * is what makes them comparable to each other: "we filled nine" and "we made
 * twelve offers" are about the same nine roles, so the reader can do sums
 * across the tiles. The server computes all of it; nothing here recomputes a
 * number, because a second opinion written in JavaScript would only ever
 * disagree with the one that counts.
 *
 * THE EMPTY STATE TEACHES. A range with no roles agreed in it says so in
 * words, with the dates in the sentence, rather than drawing eight zeros —
 * and a screen of zeros is how a working feature gets reported as broken.
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

export class PbHiringNumbers extends Component {
    static template = "pb_hiring.PbHiringNumbers";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ranges = RANGES;

        this.state = useState({
            loaded: false,
            allowed: true,
            empty: true,
            range: "90",
            from: "",
            to: "",
            custom: false,
            headline: "",
            requests: 0,
            tiles: [],
            stages: [],
            sources: [],
            delays: [],
            noShows: [],
            agency: [],
            busy: false,
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
            this.state.from = PbHiringNumbers.iso(from);
            this.state.to = PbHiringNumbers.iso(to);
        }
        if (reload) { this.load(); }
    }

    onCustom() {
        this.state.range = "custom";
        this.state.custom = true;
        this.load();
    }

    async load() {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.hiring.analytics", "get_board",
                                          [this.state.from, this.state.to]);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                empty: !!d.empty,
                headline: d.headline || "",
                requests: d.requests || 0,
                from: d.from || this.state.from,
                to: d.to || this.state.to,
                tiles: d.tiles || [],
                stages: d.stages || [],
                sources: d.sources || [],
                delays: d.delays || [],
                noShows: d.no_shows || [],
                agency: d.agency || [],
                loaded: true,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            console.warn("pb_hiring: the hiring numbers could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    /** A figure nobody can answer yet is a dash, never a zero. */
    shown(tile) {
        if (tile.value === null || tile.value === undefined) { return "—"; }
        if (typeof tile.value === "number") {
            return Math.round(tile.value * 10) / 10;
        }
        return tile.value;
    }

    /** The widest bar in a table is 100%; everything else is relative to it. */
    share(rows, value, key) {
        const top = Math.max(...rows.map((r) => Number(r[key] || 0)), 0);
        if (!top) { return 0; }
        return Math.round((Number(value || 0) / top) * 100);
    }

    async download() {
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.hiring.analytics", "export_xlsx",
                [this.state.from, this.state.to]);
            if (!res || !res.file_b64) { return; }
            // A DATA URL AND NOT A SERVER ROUTE. The file is built for this
            // reader, from this reader's own company set, and leaving it on
            // the server as an attachment would be a copy of the company's
            // hiring figures sitting in a table nobody remembers to clear.
            const a = document.createElement("a");
            a.href = `data:${res.mimetype};base64,${res.file_b64}`;
            a.download = res.filename || "hiring.xlsx";
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

registry.category("actions").add("pb_hiring_numbers", PbHiringNumbers);
