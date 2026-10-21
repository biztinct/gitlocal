/** @odoo-module **/
/**
 * Learning › TESTS (LEARNING L0) — the existing list of tests, in the hub.
 *
 * A DELIBERATE L0 SHORTCUT: the stock list of certification tests
 * (`pb_training.action_pb_training_tests`: `survey.survey` where
 * `certification` is set) mounted through the web client's own `View`, with
 * a small header row of two doors — "New test" (the board's own `new_test`
 * verb, which opens a blank, already-scored certification) and "Question
 * bank". Phase L5 redesigns this tab; nothing here is meant to outlive it.
 *
 * View-wrapper precedent: Expenses › Claims / Home › Ask HR (NAV P2):
 * `noBreadcrumbs` is a PROP, `searchViewId: false` loads the model's search
 * view, `selectRecord` / `createRecord` are handed in (ledger rows, NAV P2).
 */
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { View } from "@web/views/view";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "survey.survey";

export class PbTrainingTestsLens extends Component {
    static template = "pb_training.PbTrainingTestsLens";
    static components = { View };
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notif = useService("notification");
        // Built ONCE: a fresh props object per render would reload the view.
        this.viewProps = {
            resModel: MODEL,
            type: "list",
            // Same as the Tests action: a TEST is a certification survey.
            domain: [["certification", "=", true]],
            context: { default_certification: true,
                       default_survey_type: "assessment" },
            display: { controlPanel: {} },
            noBreadcrumbs: true,
            searchViewId: false,
            selectRecord: (resId) => this.openTest(resId),
            createRecord: () => this.newTest(),
        };
    }

    ic(n, s = 16) { return ic(n, s); }

    /** A CLICK handler: the test's own form, in the main breadcrumb. */
    openTest(resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Test"),
            res_model: MODEL,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /** The board's own verbs, so the defaults live in one place. */
    async run(verb) {
        try {
            const res = await this.orm.call("pb.training", "act", [verb, {}]);
            if (res && res.type) { await this.action.doAction(res); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("That could not be opened."), { type: "danger" });
        }
    }

    newTest() { return this.run("new_test"); }
    openQuestions() { return this.run("open_questions"); }
}
