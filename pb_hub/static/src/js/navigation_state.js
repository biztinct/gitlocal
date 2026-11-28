/** @odoo-module **/
import { onWillUnmount, useSubEnv } from "@odoo/owl";
import { useSetupAction } from "@web/search/action_hook";

// Controller-lifetime memory, deliberately not local/session storage. A new
// action, company switch, logout or reload cannot inherit another task's data.
const memories = new WeakMap();
export function actionMemory(action) {
    if (!action || typeof action !== "object") { return { views: {} }; }
    if (!memories.has(action)) { memories.set(action, { views: {} }); }
    return memories.get(action);
}

export function provideNavigationMemory(action) {
    const memory = actionMemory(action);
    useSubEnv({ pbNavigationMemory: memory });
    return memory;
}

/** Preserve controls, not business records. The caller reloads its live data. */
export function useNavigationState(component, key, snapshot) {
    const memory = component.env.pbNavigationMemory || actionMemory(component.props.action);
    const remember = () => {
        memory.views[key] = snapshot();
        return { pbNavigation: memory.views };
    };
    useSetupAction({ getLocalState: remember });
    onWillUnmount(remember);
    return memory.views[key] || component.props.state?.pbNavigation?.[key] || null;
}
