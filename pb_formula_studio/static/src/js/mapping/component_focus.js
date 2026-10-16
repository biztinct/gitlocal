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
