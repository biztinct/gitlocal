/** @odoo-module **/
/**
 * Learning › OVERVIEW (LEARNING L0) — the training team's first screen.
 *
 * HERO MOMENT: one plain sentence, 22px, built on the server ("38 people are
 * on 6 courses. 4 are past their date. 11 finished this month."), with the
 * three things somebody has to act on as chips right under it — grey at
 * zero, amber when somebody is waiting (quiet board). A chip is a door: it
 * opens the lens that holds that queue, on the right inner tab.
 *
 * One read (`pb.training.overview`), whose numbers are the boards' own
 * numbers (see the facade). Every state is drawn: reading, could not read
 * (with Try again), not for you (with the way to My learning), nothing yet
 * (calm grey), and the working page.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";
import { LEARNING_HUB_XMLID } from "@pb_learning_hub/js/learning_hub";

/** The context key a Learning lens reads its inner tab from (`propsFromContext`). */
export const TRAINING_TAB_KEY = "pb_training_tab";

const QUEUE_ICON = { claims: "receipt", requests: "clock", late: "alert" };

export class PbLearningOverview extends Component {
    static template = "pb_training.PbLearningOverview";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loaded: false, failed: false, data: {} });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call("pb.training", "overview", []);
        } catch (e) {
            console.warn("pb_training: the learning overview could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() {
        this.state.loaded = false;
        await this.load();
    }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get queue() { return this.data.queue || []; }
    get month() { return this.data.month || { due: 0, past: 0, finished: 0 }; }
    get departments() { return this.data.departments || []; }

    queueIcon(row) { return QUEUE_ICON[row.key] || "info"; }

    /** The month line, as words — never a number without its noun. */
    get monthBits() {
        const m = this.month;
        return [
            { key: "due", n: m.due,
              text: m.due === 1 ? _t("1 due this month") : _t("%s due this month", m.due) },
            { key: "past", n: m.past, warn: true,
              text: m.past === 1 ? _t("1 past their date") : _t("%s past their date", m.past) },
            { key: "finished", n: m.finished, good: true,
              text: m.finished === 1 ? _t("1 finished") : _t("%s finished", m.finished) },
        ];
    }

    peopleWords(n) { return n === 1 ? _t("1 person") : _t("%s people", n); }

    lateWords(n) {
        return n === 1 ? _t("1 past their date") : _t("%s past their date", n);
    }

    /** A CLICK handler: the lens that holds this queue, on its own tab. */
    openQueue(row) {
        openHub(this.action, {
            xmlid: LEARNING_HUB_XMLID,
            lens: row.lens,
            context: row.tab ? { [TRAINING_TAB_KEY]: row.tab } : {},
        });
    }

    openLens(lens) {
        openHub(this.action, { xmlid: LEARNING_HUB_XMLID, lens });
    }
}
