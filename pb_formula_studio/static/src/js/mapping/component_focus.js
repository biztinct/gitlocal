/** @odoo-module **/

/** Follow a component's sources without including other components that share them. */
export function componentJourneyScope(index, componentId, contains = []) {
    const targetId = `s:${componentId}`;
    const target = index.rows.get(targetId);
    const rowIds = new Set(target ? [targetId] : []);
    const queue = [...rowIds];
    for (let n = 0; n < queue.length; n++) {
        for (const id of index.nb.get(queue[n]) || []) {
            if (rowIds.has(id) || (id.startsWith('s:') && id !== targetId)) continue;
            rowIds.add(id);
            queue.push(id);
        }
    }
    const cardIds = new Set([...rowIds].map(id => index.cardOf.get(id)).filter(Boolean));
    // A system contains a feed rather than linking directly to each field.
    let changed = true;
    while (changed) {
        changed = false;
        for (const edge of contains) {
            if (cardIds.has(edge.to) && !cardIds.has(edge.from)) {
                cardIds.add(edge.from);
                changed = true;
            }
        }
    }
    return { target, rowIds, cardIds };
}

/** A Journey row id and a mapping-canvas item id have different namespaces. */
export function journeyLinkDoor(index, link) {
    const ids = [link.a, link.b];
    const scheme = ids.find(id => id.startsWith("s:"));
    const other = scheme ? ids.find(id => id !== scheme)
        : (ids.find(id => id.startsWith("r:")) || ids[0]);
    const card = index.byCard.get(index.cardOf.get(other));
    if (!card?.door) return null;
    if (!scheme) return { ...card.door, focus: index.rows.get(other)?.label || "" };
    const componentId = Number(scheme.slice(2));
    const connection = { componentId, side: "right" };
    let mode = card.door.mode;
    if (other.startsWith("f:")) {
        connection.leftId = "c:" + other.slice(2);
    } else if (other.startsWith("p:")) {
        mode = "employee";
        connection.side = "left";
        const [, group, ...parts] = other.split(":");
        const key = parts.join(":");
        if (group === "emp" || group === "con") {
            connection.rightId = `f:hr.${group === "emp" ? "employee" : "contract"}:${key}`;
        } else if (group === "bank") connection.rightId = "b:" + key;
    } else {
        // A transformation's output is available on the System fields board.
        mode = "api";
        const row = index.rows.get(other);
        connection.leftId = "f:" + (other.startsWith("r:") ? row?.tag : other.split(":").slice(2).join(":"));
    }
    return { ...card.door, mode, componentId, connection };
}
