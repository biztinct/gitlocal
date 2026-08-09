#!/usr/bin/env node
/* =============================================================================
   Step 1 of the content pipeline.

   Loads the authoring source in a bare VM context and dumps a normalised JSON
   tree on stdout. Parsing JS with a Python regex was the obvious alternative
   and it is the wrong one: these files contain nested template literals, HTML
   with braces, and Vietnamese text with quotes. The only parser guaranteed to
   agree with the browser is the one the browser uses.

   ORDER MATTERS. practice-data.js is loaded first because it declares `B` and
   the fixture, and data.js references both. `const` at the top level of a
   runInContext script lands in the context's lexical scope, so a second file
   redeclaring `B` would throw — which is why data.js deliberately does not.

   Usage:  node tools/dump_content.js > /tmp/content.json
   ========================================================================== */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");

const sandbox = { console, window: {}, document: undefined };
vm.createContext(sandbox);

for (const f of ["practice-data.js", "data.js"]) {
    const src = fs.readFileSync(path.join(ROOT, f), "utf8");
    vm.runInContext(src, sandbox, { filename: f });
}

/* `const` at the top level of runInContext lands in the context's lexical
   scope, which is reachable by evaluating the name — but not by property
   lookup on the sandbox object. Pull each one out by evaluation, and fail
   loudly rather than emitting a tree with a silently missing branch: a
   generator that reads `undefined` writes an empty data file, and an empty
   data file installs cleanly. */
function grab(name) {
    try {
        return vm.runInContext(name, sandbox);
    } catch (e) {
        throw new Error(`the authoring source does not define ${name}: ${e.message}`);
    }
}

const out = {
    schemaVersion: grab("PRACTICE_META").schemaVersion,
    /* content */
    i18n: grab("I18N"),
    glossary: grab("GLOSSARY"),
    stations: grab("STATIONS"),
    lessons: grab("LESSONS"),
    morphs: grab("MORPHS"),
    missions: grab("MISSIONS"),
    missionSteps: grab("MISSION_STEPS"),
    screenCtx: grab("SCREEN_CTX"),
    qa: grab("QA"),
    columns: grab("COLUMNS"),
    practiceAnchors: grab("PRACTICE_ANCHORS"),
    sidebarLeaf: grab("SIDEBAR_LEAF"),
    /* product facts, for the checks that read them */
    tenantDefaults: grab("TENANT_DEFAULTS"),
    menu: grab("MENU"),
    statusLabels: grab("STATUS_LABELS"),
    chains: grab("CHAINS"),
    caseData: grab("CASE"),
    practice: grab("PRACTICE"),
    subScreens: grab("SUB_SCREENS"),
};

process.stdout.write(JSON.stringify(out, null, 1));
