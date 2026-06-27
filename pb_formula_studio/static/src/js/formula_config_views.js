/** @odoo-module **/

// Redirect the native "New" on the Formula Configurations list & kanban to the
// guided Formula Studio wizard (one creation path; the raw form is edit-only).
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";

function openStudioWizard(self) {
    return self._fcAction.doAction({
        type: "ir.actions.client",
        tag: "pb_formula_studio",
        params: { open_wizard: 1 },
    });
}

// Opening a config row lands on its bespoke Settings surface in the cockpit
// (instead of the dense native form).
function openStudioSettings(self, resId) {
    if (!resId) return;
    return self._fcAction.doAction({
        type: "ir.actions.client",
        tag: "pb_formula_studio",
        params: { config_id: resId, open_settings: 1 },
    });
}

export class FormulaConfigListController extends ListController {
    setup() {
        super.setup();
        this._fcAction = useService("action");
    }
    async createRecord() {
        return openStudioWizard(this);
    }
    async openRecord(record) {
        return openStudioSettings(this, record.resId);
    }
}

export class FormulaConfigKanbanController extends KanbanController {
    setup() {
        super.setup();
        this._fcAction = useService("action");
    }
    async createRecord() {
        return openStudioWizard(this);
    }
    async openRecord(record) {
        return openStudioSettings(this, record.resId);
    }
}

registry.category("views").add("formula_config_list", {
    ...listView,
    Controller: FormulaConfigListController,
});
registry.category("views").add("formula_config_kanban", {
    ...kanbanView,
    Controller: FormulaConfigKanbanController,
});
