/** @odoo-module **/
/**
 * History — what changed, and who did it.
 *
 * ONE LINE PER THING THAT HAPPENED, in the words the engine wrote when it
 * happened rather than a sentence assembled here from keys. That is deliberate:
 * the summary was written at the moment, with the names as they were then, so a
 * person who was renamed or a route that was replaced does not rewrite the
 * past. The same rows feed the audit console.
 *
 * IT IS READ-ONLY, ALWAYS AND FOR EVERYONE. The engine refuses to change or
 * delete one of these rows at model level, so there is nothing to offer here
 * beyond reading and filtering.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { initials, when } from "@pb_approval_config/js/sentence";

export class HistoryTab extends Component {
    static template = "pb_approval_config.HistoryTab";
    static props = { companyId: { type: Number, optional: true } };

    setup() {
        this.ic = ic;
        this.initials = initials;
        this.when = when;
        this.orm = useService("orm");

        this.state = useState({
            loading: true, failed: "", rows: [], cursor: 0, kind: "",
            more: false,
        });

        onWillStart(async () => { await this.load(); });
    }

    get filters() {
        return [
            { key: "", label: _t("Everything") },
            { key: "publishes", label: _t("Published routes") },
            { key: "decisions", label: _t("Decisions") },
            { key: "exceptions", label: _t("Exceptions") },
            { key: "handovers", label: _t("People and cover") },
        ];
    }

    async load(append) {
        this.state.loading = !append;
        this.state.failed = "";
        try {
            const result = await this.orm.call(
                "pb.approval.matrix", "get_history",
                [this.props.companyId || false, this.state.kind || false,
                 append ? this.state.cursor : false]);
            this.state.rows = append
                ? this.state.rows.concat(result.rows) : result.rows;
            this.state.cursor = result.cursor;
            this.state.more = Boolean(result.cursor);
        } catch (error) {
            this.state.failed = (error.data && error.data.message)
                || _t("This could not be read.");
        } finally {
            this.state.loading = false;
        }
    }

    async setKind(kind) {
        this.state.kind = kind;
        this.state.cursor = 0;
        await this.load();
    }

    async loadMore() { await this.load(true); }
}
