// Geometry from the shipped component, including scrolled-off-screen rows.
const fs = require('fs'), assert = require('assert'), vm = require('vm');
const source = fs.readFileSync(__dirname + '/../static/src/js/scheme_map_board.js', 'utf8');
const helper = source.slice(source.indexOf('export function boundedSchemeCurve'), source.indexOf('const MODEL'));
const context = {Math}; vm.createContext(context);
vm.runInContext(helper.replace('export ', ''), context);
const frame = {top: 200, left: 20, width: 1200, height: 600};
const pane = {top: 220, bottom: 780};
let count = 0;
for (const top of [-300, 200, 450, 1100]) {
    for (const targetTop of [210, 600, 1300]) {
        const d = context.boundedSchemeCurve(frame,
            {top, height: 50, right: 600}, {top: targetTop, height: 80, left: 680}, pane, pane);
        const points = d.match(/-?\d+(?:\.\d+)?/g).map(Number);
        for (let i = 0; i < points.length; i += 2) {
            assert(points[i] >= 0 && points[i] <= frame.width);
            assert(points[i+1] >= 26 && points[i+1] <= 574);
        }
        assert.equal(points[1], points[3]);
        assert.equal(points[5], points[7]);
        count++;
    }
}
console.log(count, 'bounded curves passed, with aligned horizontal tangents');
