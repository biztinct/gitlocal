/** @odoo-module **/
import { describe, expect, test } from "@odoo/hoot";
import { JourneyBoard } from "@pb_formula_studio/js/mapping/journey_board";
import { MappingCanvas } from "@pb_formula_studio/js/mapping/mapping_canvas";
import { journeyLinkDoor } from "@pb_formula_studio/js/mapping/component_focus";

describe.current.tags("desktop");

function board() {
    const c = Object.create(JourneyBoard.prototype);
    const card = (id, rows, door, groups = []) => ({ id, rows, door, groups });
    c.props = { data: { lanes: {
        systems: [card("unused", [{id: "f:other"}]), card("file", [
            {id: "f:VN|First", label: "First"}, {id: "f:VN|Wage", label: "Wage"},
        ], {mode: "import"})],
        scheme: [card("scheme", [{id: "s:1", label: "First"}, {id: "s:2", label: "Wage"}])],
        source: [card("source", [{id: "p:emp:name", label: "Name", group: "emp"},
            {id: "p:con:wage", label: "Wage", group: "con"}], {mode: "employee"},
            [{id: "emp"}, {id: "con"}])],
    }, links: [{a: "f:VN|Wage", b: "s:2", kind: "excel"},
        {a: "s:2", b: "p:con:wage", kind: "record"}] } };
    c.ui = {pin: "", hover: "", q: "", open: {}, componentId: 0};
    c.boardRef = {el: {scrollTop: 580}};
    c._animate = () => {};
    return c;
}

test("a selected flow promotes every connected row and restores order and scroll on clear", () => {
    const c = board();
    const file = c.cardsFor("systems")[1], source = c.cardsFor("source")[0];
    c.pinRow(file.rows[1]);
    expect(c.cardsFor("systems").map(r => r.id)).toEqual(["file", "unused"]);
    expect(c.selectedRows(file).map(r => r.id)).toEqual(["f:VN|Wage"]);
    expect(c.selectedRows(source).map(r => r.id)).toEqual(["p:con:wage"]);
    expect(c.rowsInGroup(source, "con")).toEqual([]);
    expect(c.rowsInGroup(source, "emp").length).toBe(1);
    expect(c.isOpen(source)).toBe(true);
    expect(c._pendingScroll).toBe(0);
    expect(c.ui.open).toEqual({});
    c.clearTrace();
    expect(c._pendingScroll).toBe(580);
    expect(c.cardsFor("systems").map(r => r.id)).toEqual(["unused", "file"]);
    expect(c.rowsInGroup(source, "con").length).toBe(1);
    expect(c.isOpen(source)).toBe(false);
});

test("spreadsheet and employee arrows resolve exact component and field identities", () => {
    const c = board();
    expect(journeyLinkDoor(c.index, c.d.links[0])).toEqual({mode: "import", componentId: 2,
        connection: {componentId: 2, side: "right", leftId: "c:VN|Wage"}});
    expect(journeyLinkDoor(c.index, c.d.links[1])).toEqual({mode: "employee", componentId: 2,
        connection: {componentId: 2, side: "left", rightId: "f:hr.contract:wage"}});
});

test("system and transformation outputs open system mapping on the correct connector", () => {
    const c = board();
    c.props.data.lanes.feeds = [{id: "e:9", door: {mode: "api", connector: 4, endpoint: 9},
        rows: [{id: "e:9:person.name", label: "person.name"}]}];
    c.props.data.lanes.transforms = [{id: "t:4", door: {mode: "transform", connector: 4},
        rows: [{id: "r:5", label: "Net amount", tag: "NET"}]}];
    expect(journeyLinkDoor(c.index, {a: "e:9:person.name", b: "s:2"})).toEqual({mode: "api",
        connector: 4, endpoint: 9, componentId: 2,
        connection: {componentId: 2, side: "right", leftId: "f:person.name"}});
    expect(journeyLinkDoor(c.index, {a: "r:5", b: "s:2"}).connection.leftId).toBe("f:NET");
    expect(journeyLinkDoor(c.index, {a: "r:5", b: "s:2"}).mode).toBe("api");
});

test("canvas arrival selects the exact wire and centres both ends without search filters", async () => {
    const c = Object.create(MappingCanvas.prototype);
    c.props = {wires: [{id: "wrong", leftId: 2, rightId: "f:hr.employee:name"},
        {id: "right", leftId: 2, rightId: "f:hr.contract:wage"}]};
    c.ui = {};
    c.rootRef = {el: {}};
    const reset = [];
    c.resetQuery = side => reset.push(side);
    c.leaveItem = () => {};
    let centred;
    c.centreBoth = wire => {centred = wire.id;};
    c.focusConnection({componentId: 2, side: "left", rightId: "f:hr.contract:wage"});
    await new Promise(requestAnimationFrame);
    expect(centred).toBe("right");
    expect(c.ui.focusId).toBe(2);
    expect(reset).toEqual(["left", "right"]);
});
