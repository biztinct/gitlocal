/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { PbFormulaStudio } from "@pb_formula_studio/js/formula_studio";

describe.current.tags("desktop");

function deferred() {
    let resolve, reject;
    const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
    return { promise, resolve, reject };
}

function fixture(call) {
    return {
        state: {
            loaded: true, config: { id: 1, country: "VN" },
            selectedId: null, configSwitcherOpen: true,
        },
        orm: { call },
        load: PbFormulaStudio.prototype.load,
    };
}

function payload(id = 2) {
    return { empty: false, config: { id, country: "ID" }, components: [], samples: [] };
}

test("switching from Vietnam hides its payroll until Indonesia and its graph are ready", async () => {
    const data = deferred(), graph = deferred();
    const studio = fixture((model, method) => {
        if (method === "get_studio_data") return data.promise;
        if (method === "get_intelligence") return graph.promise;
        return Promise.resolve(null);
    });
    const pending = PbFormulaStudio.prototype.chooseConfig.call(studio, 2);
    expect(studio.state.loaded).toBe(false);
    expect(studio.state.configSwitcherOpen).toBe(false);
    data.resolve(payload());
    await Promise.resolve();
    await Promise.resolve();
    // The new identity alone must not expose a partially loaded workspace.
    expect(studio.state.loaded).toBe(false);
    graph.resolve({ nodes: [], edges: [] });
    await pending;
    expect(studio.state.loaded).toBe(true);
    expect(studio.state.config.country).toBe("ID");
});

test("a failed switch restores the previous payroll instead of leaving a loading screen", async () => {
    const data = deferred();
    const studio = fixture(() => data.promise);
    const pending = studio.load(2).catch(error => error.message);
    expect(studio.state.loaded).toBe(false);
    data.reject(new Error("Connection lost"));
    expect(await pending).toBe("Connection lost");
    expect(studio.state.loaded).toBe(true);
    expect(studio.state.config.country).toBe("VN");
});

test("refreshing the same payroll after a save keeps the workspace visible", async () => {
    const data = deferred();
    const studio = fixture((model, method) => method === "get_studio_data"
        ? data.promise : Promise.resolve(null));
    const pending = studio.load(1);
    expect(studio.state.loaded).toBe(true);
    data.resolve(payload(1));
    await pending;
    expect(studio.state.loaded).toBe(true);
});

test("menu entry loads the picker without computing an unselected payroll", async () => {
    const studio = fixture(() => { throw new Error("Unexpected payroll read"); });
    studio.state.config = {};
    studio.state.loaded = false;
    studio._loadCsBoard = async () => {
        studio.state.csBoard = { ok: true, cards: [{ id: 2 }], can_edit: false };
    };
    await PbFormulaStudio.prototype.loadInitial.call(studio);
    expect(studio.state.configSwitcherOpen).toBe(true);
    expect(studio.state.config).toEqual({});
    expect(studio.state.canEdit).toBe(false);
});

test("explicit payroll links and the creation flow still load their target", async () => {
    const loaded = [];
    const studio = { load: async id => loaded.push(id) };
    await PbFormulaStudio.prototype.loadInitial.call(studio, 7);
    await PbFormulaStudio.prototype.loadInitial.call(studio, undefined, true);
    expect(loaded).toEqual([7, undefined]);
});

test("a tenant with no payroll schemes keeps its create-first screen", async () => {
    const studio = fixture(() => { throw new Error("Unexpected payroll read"); });
    studio._loadCsBoard = async () => {
        studio.state.csBoard = { ok: true, cards: [], can_edit: true };
    };
    await PbFormulaStudio.prototype.loadInitial.call(studio);
    expect(studio.state.empty).toBe(true);
    expect(studio.state.loaded).toBe(true);
    expect(studio.state.configSwitcherOpen).toBe(false);
});

test("closing the initial picker loads a workspace before dismissing it", async () => {
    const data = deferred();
    const studio = fixture((model, method) => method === "get_studio_data"
        ? data.promise : Promise.resolve(null));
    studio.state.config = {};
    studio.state.loaded = false;
    const pending = PbFormulaStudio.prototype.closeConfigSwitcher.call(studio);
    expect(studio.state.configSwitcherOpen).toBe(true);
    data.resolve(payload());
    await pending;
    expect(studio.state.loaded).toBe(true);
    expect(studio.state.configSwitcherOpen).toBe(false);
    expect(studio.state.config.id).toBe(2);
});

test("a failed first selection returns to the picker for another attempt", async () => {
    const studio = fixture(() => Promise.reject(new Error("Connection lost")));
    studio.state.loaded = false;
    studio.state.config = {};
    const error = await PbFormulaStudio.prototype.chooseConfig.call(studio, 2)
        .catch(error => error.message);
    expect(error).toBe("Connection lost");
    expect(studio.state.configSwitcherOpen).toBe(true);
    expect(studio.state.loaded).toBe(false);
});
