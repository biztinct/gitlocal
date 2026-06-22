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

export class FormulaConfigListController extends ListController {
    setup() {
        super.setup();
        this._fcAction = useService("action");
    }
    async createRecord() {
        return openStudioWizard(this);
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
}

registry.category("views").add("formula_config_list", {
    ...listView,
    Controller: FormulaConfigListController,
});
registry.category("views").add("formula_config_kanban", {
    ...kanbanView,
    Controller: FormulaConfigKanbanController,
});
