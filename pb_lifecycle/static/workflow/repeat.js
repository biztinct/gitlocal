"use strict";
/* WF2 P5c — "Repeat for each…": a group of steps run once per line
   (each receipt on a claim, each answer to a list question, each person on
   a team). The server runs one line per run; this file is the design side:
   the step in "More possibilities", the framed group on Journey, By stage,
   Across and the Flowchart canvas (drawn the way parallel paths are drawn:
   a labelled lane and a join), "+" and drag inside it, its inspector with a
   live sample, "the person on the line", line details in rules and notices,
   the per-line list on the progress page, "Show lines" in Activity and the
   line on the person's task page.
   Loaded last; it only adds and wraps shipped functions by assignment
   (ledger G45). A workflow without a repeat renders exactly as before:
   every wrapper hands the shipped function the same arguments and returns
   its output untouched. */

UI_ICONS.repeat = '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>';
TYPES.repeat = ["Repeat for each…", "Do the same steps for every line"];
GROUPS.push("repeat");
const REP_REFUSED = {
  matrix: "An approval cannot be repeated for each line: one record has one approval.",
  stage_move: "Moving the record to a stage cannot be repeated for each line.",
  start: "Starting another workflow cannot be repeated for each line.",
  repeat: "A repeat cannot sit inside another repeat.",
  parallel: "Work in parallel cannot sit inside a repeat. Use “Together” on the repeat instead.",
  subprocess: "A saved group cannot sit inside a repeat. Add its steps one by one.",
  action: "A module action cannot be repeated for each line.",
  update: "Updating the record cannot be repeated for each line yet.",
  reference: "Existing work is shown once, outside the repeat.",
};
const hasRepeat = (d) => !!d?.nodes?.some((n) => n.type === "repeat");
const repSources = () => S.w?.metadata?.line_sources || { area: [], teams: [], hard_cap: 200, default_cap: 50 };

/* --------------------------------------------------------------- words */
function repAnswerSources(d = S.w?.definition) {
  const out = [];
  for (const n of d?.nodes || [])
    if (n.type === "input" && d.order.includes(n.id))
      for (const f of n.form?.fields || [])
        if (["multiselect", "rows"].includes(f.type)) out.push({ step: n.id, field: f.id, label: f.label, stepTitle: n.title, rows: f.type === "rows" });
  return out;
}
function repWords(n, d = S.w?.definition) {
  const s = n?.source || {};
  if (n?.each && (S.page === "progress" || !S.w)) return { singular: n.singular || "line", plural: n.plural || "lines", each: n.each };
  if (s.kind === "area") {
    const a = repSources().area.find((x) => x.key === s.key);
    if (a) {
      const one = String(a.singular || a.label || "line").toLowerCase();
      return { singular: one, plural: String(a.label || one).toLowerCase(), each: `For each ${one}` };
    }
  }
  if (s.kind === "team") {
    const t = repSources().teams.find((x) => x.id === s.id);
    return { singular: "person", plural: "people", each: t ? `For each person on ${t.name}` : "For each person on a team" };
  }
  if (s.kind === "answers") {
    const a = repAnswerSources(d).find((x) => x.step === s.step && x.field === s.field);
    if (a?.rows) return { singular: "line", plural: "lines", each: `For each line of “${a.label}”` };
    return { singular: "answer", plural: "answers", each: a ? `For each answer to “${a.label}”` : "For each answer" };
  }
  return { singular: "line", plural: "lines", each: n?.each || "For each line" };
}
function repHow(n) {
  return `${n.mode === "one_by_one" ? "One by one" : "Together"} · ${n.join === "any" ? "carries on when the first is done" : "carries on when every one is done"}`;
}
function repLineFields(n) {
  const s = n?.source || {};
  if (s.kind === "area") return repSources().area.find((x) => x.key === s.key)?.fields || [];
  if (s.kind === "team") return [{ key: "person", label: "Person", type: "person" }];
  if (s.kind === "answers")
    return repAnswerSources().find((x) => x.step === s.step && x.field === s.field)?.rows
      ? [
          { key: "description", label: "Description", type: "text" },
          { key: "amount", label: "Amount", type: "number" },
        ]
      : [{ key: "value", label: "Answer", type: "text" }];
  return [];
}
function repAround(d, key) {
  return ancestorsOf(d, key).find((g) => g.type === "repeat") || null;
}
const _p5cSummary = summary;
function repSourceWords(n) {
  const s = n?.source || {};
  if (s.kind === "area") {
    const a = repSources().area.find((x) => x.key === s.key);
    return a ? `${a.label} on this ${String(contract().label || "record").toLowerCase()}` : "Choose what to repeat for";
  }
  if (s.kind === "answers") {
    const a = repAnswerSources().find((x) => x.step === s.step && x.field === s.field);
    return a ? `Answers to “${a.label}”` : "Choose what to repeat for";
  }
  if (s.kind === "team") return `People on ${repSources().teams.find((x) => x.id === s.id)?.name || "a team"}`;
  return "Choose what to repeat for";
}
summary = function (n) {
  if (n.type === "repeat") return `${repSourceWords(n)} · ${n.mode === "one_by_one" ? "one by one" : "together"}`;
  return _p5cSummary(n);
};

/* ------------------------------------------------------------- the shape */
const _p5cContainers = containers;
containers = function (d) {
  const out = _p5cContainers(d);
  for (const n of d.nodes) if (n.type === "repeat" && !n.branches) out.push({ key: n.id, ids: n.steps || [], parent: n });
  return out;
};
const _p5cGroupParents = groupParents;
groupParents = function (d) {
  const out = _p5cGroupParents(d);
  for (const n of d.nodes) if (n.type === "repeat") for (const c of n.steps || []) out[c] = [n, null];
  return out;
};
function repRefusal(d, ids, into) {
  if (!into || into.type !== "repeat") return "";
  for (const k of ids) {
    const x = byId(d, k);
    if (x && REP_REFUSED[x.type]) return `${REP_REFUSED[x.type]} Put it before or after “${into.title}”.`;
  }
  return "";
}
const _p5cMoveStep = moveStep;
moveStep = function (d, id, t) {
  const n = byId(d, id),
    to = containers(d).find((c) => c.key === t.key);
  if (n?.type === "repeat" && t.key !== "main") throw Error("Keep “Repeat for each…” on the main path, not inside a path or group.");
  const why = repRefusal(d, descendants(d, id), to?.parent);
  if (why) throw Error(why);
  return _p5cMoveStep(d, id, t);
};
const _p5cAppendNode = appendNode;
appendNode = function (d, n, t) {
  const to = containers(d).find((c) => c.key === t.key);
  if (n.type === "repeat" && t.key !== "main") throw Error("Add “Repeat for each…” on the main path, not inside a path or group.");
  if (to?.parent?.type === "repeat" && REP_REFUSED[n.type]) throw Error(`${REP_REFUSED[n.type]} Put it before or after “${to.parent.title}”.`);
  return _p5cAppendNode(d, n, t);
};
function repDefaultSource() {
  const a = repSources().area[0];
  if (a) return { kind: "area", key: a.key, fields: (a.fields || []).map((f) => f.key) };
  const q = repAnswerSources()[0];
  if (q) return { kind: "answers", step: q.step, field: q.field };
  const t = repSources().teams[0];
  if (t) return { kind: "team", id: t.id };
  return null;
}
const _p5cMakeNode = makeNode;
makeNode = function (type, stage) {
  if (type !== "repeat") return _p5cMakeNode(type, stage);
  const n = { id: uid("repeat"), type: "repeat", title: "Repeat for each…", stage, steps: [], mode: "together", join: "all", max_lines: repSources().default_cap || 50 };
  const src = repDefaultSource();
  if (src) {
    n.source = src;
    n.title = repWords(n).each;
  }
  return n;
};
const _p5cPalette = palette;
palette = function () {
  const html = _p5cPalette(),
    item = `<button class="palette-item" data-act="add" data-type="repeat" data-drag-type="repeat" title="${TYPES.repeat[0]}"><span class="type-icon repeat">${svgIcon("repeat")}</span><span class="words">${TYPES.repeat[0]}<small>${TYPES.repeat[1]}</small></span></button>`,
    marker = '<p class="palette-sub">';
  const k = html.indexOf(marker);
  return k > 0 ? html.slice(0, k) + item + html.slice(k) : html;
};

/* ------------------------------------------------- Journey and By stage */
function repFrameHead(n, progress = false) {
  return `<div class="repeat-head"><span class="repeat-chip">${svgIcon("repeat")}${esc(repWords(n).each)}</span><small>${esc(repHow(n))}</small></div>`;
}
const _p5cJourneySeq = journeySeq;
journeySeq = function (d, ts, ids, key, stage, next = null) {
  if (!ids.some((id) => byId(d, id)?.type === "repeat")) return _p5cJourneySeq(d, ts, ids, key, stage, next);
  const none = "\u0000none";
  const slot = (before) => {
    const t = ts.find((t) => t.key === key && t.stage === stage && t.before === before);
    return t ? drop(t) : "";
  };
  return (
    ids
      .map((id) => {
        const n = byId(d, id);
        if (n?.type !== "repeat") return _p5cJourneySeq(d, ts, [id], key, stage, none);
        const inner = _p5cJourneySeq(d, ts, n.steps || [], n.id, n.stage);
        const empty = (n.steps || []).length
          ? ""
          : `<p class="repeat-empty">${svgIcon("plus")}Add the steps to do for each ${esc(repWords(n).singular)}, or drag steps in.</p>`;
        return slot(id) + nodeCard(n) + `<div class="repeat-frame" data-repeat="${esc(n.id)}">${repFrameHead(n)}${empty}${inner}<div class="repeat-foot">${svgIcon("check")}${n.join === "any" ? "Carries on when the first one is done" : "Carries on when every one is done"}</div></div>`;
      })
      .join("") + slot(next)
  );
};

/* ------------------------------------------ Across and the Flowchart */
/* Drawn with the shipped group grammar: the repeat becomes, for drawing
   only, a group with one labelled lane holding its steps (same ids, so "+"
   slots, drag and selection work on the real definition). */
function repAsLanes(d) {
  if (!hasRepeat(d)) return d;
  return {
    ...d,
    nodes: d.nodes.map((n) => {
      if (n.type !== "repeat") return n;
      const { steps, ...rest } = n;
      return { ...rest, branches: [{ id: n.id, label: "", steps: steps || [] }] };
    }),
  };
}
const _p5cGraphLayout = graphLayout;
graphLayout = function (d) {
  const g = _p5cGraphLayout(d);
  if (!d.nodes.some((n) => n.type === "repeat")) return g;
  g.frames = [];
  for (const n of d.nodes.filter((n) => n.type === "repeat")) {
    const inner = descendants(d, n.id).filter((k) => k !== n.id && g.pos[k]),
      top = g.pos[n.id] ? g.pos[n.id].y + 145 : 0,
      join = g.pos[n.id + "__join"];
    if (!g.pos[n.id] || !join) continue;
    const xs = inner.map((k) => g.pos[k].x).concat([g.pos[n.id].x]),
      left = Math.min(...xs) - 20,
      right = Math.max(...xs) + 330 + 20;
    g.frames.push({ id: n.id, x: left, y: top, w: right - left, h: join.y + 36 + 14 - top, any: n.join === "any" });
  }
  return g;
};
const _p5cFlowchart = flowchart;
flowchart = function (d, progress = false) {
  if (!hasRepeat(d)) return _p5cFlowchart(d, progress);
  const lanes = repAsLanes(d);
  let html = _p5cFlowchart(lanes, progress);
  const g = S.geometry;
  for (const n of d.nodes.filter((n) => n.type === "repeat")) {
    const j = g?.pos[n.id + "__join"];
    if (j) html = html.replace(`left:${j.x}px;top:${j.y}px">Continue</div>`, `left:${j.x}px;top:${j.y}px">${n.join === "any" ? "First one done" : "Every one done"}</div>`);
  }
  const frames = (g?.frames || [])
    .map((f) => {
      const n = byId(d, f.id);
      return `<div class="repeat-box ${progress ? "is-progress" : ""}" data-repeat="${esc(f.id)}" style="left:${f.x}px;top:${f.y}px;width:${f.w}px;height:${f.h}px"><span class="repeat-chip">${svgIcon("repeat")}${esc(repWords(n, d).each)}</span><small>${esc(n.mode === "one_by_one" ? "One by one" : "Together")}</small></div>`;
    })
    .join("");
  const marker = `transform:scale(${S.zoom})">`,
    k = html.indexOf(marker);
  return k > 0 ? html.slice(0, k + marker.length) + frames + html.slice(k + marker.length) : html;
};
const _p5cHorizontal = horizontalJourney;
horizontalJourney = function (d) {
  if (!hasRepeat(d)) return _p5cHorizontal(d);
  const lanes = repAsLanes(d);
  for (const n of lanes.nodes) if (n.type === "repeat") n.branches[0].label = `${repWords(byId(d, n.id), d).each} · ${n.mode === "one_by_one" ? "one by one" : "together"}`;
  return _p5cHorizontal(lanes);
};

/* --------------------------------------------------------- the inspector */
function repSourceOptions(n) {
  const s = n.source || {},
    cur = s.kind === "area" ? `area:${s.key}` : s.kind === "answers" ? `answers:${s.step}:${s.field}` : s.kind === "team" ? `team:${s.id}` : "";
  const groups = [];
  const area = repSources().area;
  if (area.length)
    groups.push(`<optgroup label="Lines of this ${esc(String(contract().label || "record").toLowerCase())}">${area.map((a) => `<option value="area:${esc(a.key)}" ${cur === "area:" + a.key ? "selected" : ""}>${esc(a.label)}</option>`).join("")}</optgroup>`);
  const qs = repAnswerSources();
  if (qs.length)
    groups.push(`<optgroup label="Answers to a list question">${qs.map((q) => `<option value="answers:${esc(q.step)}:${esc(q.field)}" ${cur === `answers:${q.step}:${q.field}` ? "selected" : ""}>${esc(q.label)} (in “${esc(q.stepTitle)}”)</option>`).join("")}</optgroup>`);
  if (repSources().teams.length)
    groups.push(`<optgroup label="People on a team">${repSources().teams.map((t) => `<option value="team:${t.id}" ${cur === "team:" + t.id ? "selected" : ""}>${esc(t.name)}</option>`).join("")}</optgroup>`);
  return `<select data-rep="source" aria-label="Repeat for"><option value="" ${cur ? "" : "selected"}>Choose…</option>${groups.join("")}</select>`;
}
function repInspector(n) {
  const words = repWords(n),
    cap = repSources().hard_cap || 200;
  const seg = (attr, rows, value) =>
    `<div class="segmented rep-seg" role="group">${rows.map(([k, l]) => `<button type="button" class="${value === k ? "on" : ""}" data-${attr}="${k}" aria-pressed="${value === k}">${l}</button>`).join("")}</div>`;
  let html = `<div class="rep-inspector">`;
  html += field("Repeat for", repSourceOptions(n), !n.source ? "Lines of this record, the answers to a list question asked earlier, or the people on a team." : "");
  html += `<div class="rep-sample" id="rep-sample" data-pending="1" aria-live="polite">${n.source ? '<p class="muted small">Looking at an example…</p>' : ""}</div>`;
  html += field("How the lines run", seg("rep-mode", [["together", "Together"], ["one_by_one", "One by one"]], n.mode || "together"), n.mode === "one_by_one" ? `The next ${esc(words.singular)} starts when the one before it is done.` : `Every ${esc(words.singular)} starts at once.`);
  html += field(
    "Carry on",
    `<select data-rep="join">${opts(
      [
        ["all", `When every ${words.singular} is done`],
        ["any", `When the first ${words.singular} is done`],
      ],
      n.join || "all",
      null,
    )}</select>`,
    n.join === "any" ? "The other lines stop when the first one is done." : "",
  );
  html += field("At most", `<div class="row rep-cap"><input type="number" data-rep="max_lines" min="1" max="${cap}" value="${esc(n.max_lines || 50)}"><span>${esc(words.plural)}</span></div>`, `Up to ${cap}. With more than this, nothing starts and it says why.`);
  html += hint(`The ${esc(words.plural)} are read when the repeat starts. One added later is not picked up.`, "info");
  if (!(n.steps || []).length) html += stepEmpty("repeat", `Add the steps to do for each ${esc(words.singular)} with the + inside the frame, or drag steps in.`);
  else html += `<p class="rep-inside">${svgIcon("repeat")}<span>${n.steps.length === 1 ? "1 step" : n.steps.length + " steps"} for each ${esc(words.singular)}: ${n.steps.map((k) => esc(byId(S.w.definition, k)?.title || "")).join(", ")}</span></p>`;
  return html + "</div>";
}
const _p5cInspector = inspector;
inspector = function () {
  const html = _p5cInspector();
  const n = S.w && byId(S.w.definition, S.selected);
  if (!n) return html;
  if (n.type === "repeat") {
    const marker = '<details class="filter-section"';
    const k = html.indexOf(marker);
    return k > 0 ? html.slice(0, k) + repInspector(n) + html.slice(k) : html;
  }
  const around = repAround(S.w.definition, n.id);
  if (!around) return html;
  const chip = `<p class="rep-inside-chip">${svgIcon("repeat")}<span>Runs ${esc(repWords(around).each.replace(/^For each/, "for each"))}. Line details can be used in its rules and words.</span></p>`;
  const k = html.indexOf("<label>Step name</label>");
  return k >= 0 ? html.slice(0, k) + chip + html.slice(k) : html;
};
const _p5cOwnerControl = ownerControl;
ownerControl = function (path, owner, label, noRecord = false, allowTeam = false) {
  let html = _p5cOwnerControl(path, owner, label, noRecord, allowTeam);
  const n = S.w && byId(S.w.definition, S.selected),
    around = n && path === "owner" ? repAround(S.w.definition, n.id) : null,
    person = around ? repLineFields(around).find((f) => f.type === "person") : null;
  if (!person) return html;
  return html.replace(/(<select data-edit="owner\.kind">)/, `$1<option value="line" ${owner?.kind === "line" ? "selected" : ""}>The person on the line</option>`);
};
const _p5cOwnerName = ownerName;
ownerName = function (n) {
  return n?.owner?.kind === "line" ? "The person on the line" : _p5cOwnerName(n);
};
const _p5cAvailable = availableFields;
availableFields = function () {
  const fields = _p5cAvailable();
  const d = S.w?.definition;
  if (!hasRepeat(d)) return fields;
  const sel = S.selected && byId(d, S.selected),
    around = sel ? repAround(d, sel.id) : null,
    extra = [];
  const kinds = { text: "char", number: "float", date: "date", person: "many2one", yesno: "boolean" };
  if (around) {
    const one = repWords(around).singular,
      This = `This ${one}`;
    extra.push({ key: "line.label", label: `${This} · name`, type: "char" }, { key: "line.number", label: `${This} · number`, type: "integer" });
    for (const f of repLineFields(around))
      extra.push({ key: `line.${f.key}`, label: `${This} · ${f.label}`, type: kinds[f.type] || "char", ...(f.type === "person" ? { options: S.w.metadata.users.map((u) => [u.id, u.name]) } : {}) });
  }
  for (const r of d.nodes.filter((x) => x.type === "repeat" && x.id !== around?.id)) {
    const w = repWords(r);
    extra.push({ key: `step.${r.id}.count`, label: `${r.title} · how many ${w.plural}`, type: "integer" }, { key: `step.${r.id}.done`, label: `${r.title} · how many done`, type: "integer" });
    for (const k of descendants(d, r.id)) {
      const t = byId(d, k);
      if (t?.type === "task" && (t.buttons || []).length > 1)
        for (const b of t.buttons) extra.push({ key: `step.${r.id}.${t.id}__${b.key}`, label: `${r.title} · how many “${b.label}”`, type: "integer" });
    }
  }
  /* A line's own answers are not values outside its repeat. */
  const inner = new Set(d.nodes.filter((x) => x.type === "repeat" && x.id !== around?.id).flatMap((r) => descendants(d, r.id).filter((k) => k !== r.id)));
  const kept = fields.filter((f) => !(f.key.startsWith("step.") && inner.has(f.key.split(".")[1])));
  const k = kept.findIndex((f) => f.key === "person.user_id");
  return k >= 0 ? [...kept.slice(0, k), ...extra, ...kept.slice(k)] : [...kept, ...extra];
};
const _p5cDetailOptions = detailOptions;
detailOptions = function () {
  const rows = _p5cDetailOptions();
  for (const f of availableFields()) if (f.key.startsWith("line.")) rows.push([f.key, f.label]);
  return rows;
};

/* edits: source, how, carry on, cap, "the person on the line" */
document.addEventListener(
  "change",
  (e) => {
    const t = e.target;
    if (!t?.dataset || S.page !== "editor" || !S.w) return;
    const n = byId(S.w.definition, S.selected);
    if (!n) return;
    if (t.dataset.edit === "owner.kind" && t.value === "line") {
      e.stopImmediatePropagation();
      const around = repAround(S.w.definition, n.id),
        person = around && repLineFields(around).find((f) => f.type === "person");
      mutate(() => {
        n.owner = { kind: "line", field: person?.key || "person" };
      });
      return;
    }
    const key = t.dataset.rep;
    if (!key || n.type !== "repeat") return;
    e.stopImmediatePropagation();
    if (key === "source") {
      const [kind, a, b] = t.value.split(":");
      mutate(() => {
        const was = repWords(n).each;
        if (!kind) delete n.source;
        else if (kind === "area") n.source = { kind, key: a, fields: (repSources().area.find((x) => x.key === a)?.fields || []).map((f) => f.key) };
        else if (kind === "answers") n.source = { kind, step: a, field: b };
        else n.source = { kind, id: Number(a) };
        if (!n.title || n.title === "Repeat for each…" || n.title === was) n.title = repWords(n).each;
      });
      setTimeout(() => $('[data-rep="source"]')?.focus({ preventScroll: true }), 0);
      return;
    }
    if (key === "join") return mutate(() => (n.join = t.value));
    if (key === "max_lines") {
      const v = Math.max(1, Math.min(repSources().hard_cap || 200, Math.round(Number(t.value) || 1)));
      mutate(() => (n.max_lines = v), false);
      t.value = v;
      refreshWork();
    }
  },
  true,
);
document.addEventListener(
  "click",
  (e) => {
    const b = e.target.closest?.("[data-rep-mode]");
    if (!b || S.page !== "editor" || !S.w) return;
    const n = byId(S.w.definition, S.selected);
    if (!n || n.type !== "repeat") return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const v = b.dataset.repMode;
    if (n.mode === v) return;
    mutate(() => (n.mode = v));
    setTimeout(() => $(`[data-rep-mode="${v}"]`)?.focus({ preventScroll: true }), 0);
  },
  true,
);

/* the live sample: "This claim has 4 receipts: Taxi…, Hotel…" */
function repSampleHtml(p, n) {
  if (!p) return '<p class="muted small">Looking at an example…</p>';
  if (!p.ok) return "";
  const w = p.words || repWords(n);
  if (!p.known)
    return `<p class="rep-sample-row">${svgIcon("info")}<span>The ${esc(w.plural)} come in when the question is answered, so there is no example yet.</span></p>`;
  if (!p.count) return `<p class="rep-sample-row">${svgIcon("info")}<span>${esc(p.record)} has no ${esc(w.plural)} at the moment.</span></p>`;
  const names = (p.names || []).map((x) => `<b>${esc(x)}</b>`).join(", "),
    more = p.count - (p.names || []).length,
    over = p.count > p.cap;
  return `<p class="rep-sample-row ${over ? "is-over" : ""}">${svgIcon(over ? "alert" : "repeat")}<span>${esc(p.record)} has ${p.count} ${esc(p.count === 1 ? w.singular : w.plural)}: ${names}${more > 0 ? ` …and ${more} more` : ""}.${over ? ` That is more than the ${p.cap} this repeats for, so it would start none.` : ""}</span></p>`;
}
async function repSampleFill() {
  const host = $("#rep-sample[data-pending]");
  if (!host) return;
  host.removeAttribute("data-pending");
  const n = byId(S.w.definition, S.selected);
  if (!n?.source) return;
  const key = JSON.stringify([S.w.id, n.id, n.source, n.max_lines]);
  if (S.repSample?.key === key && S.repSample.data) {
    host.innerHTML = repSampleHtml(S.repSample.data, n);
    return;
  }
  clearTimeout(S.repTimer);
  S.repTimer = setTimeout(async () => {
    try {
      await save();
      const data = await rpc("repeat_sample", [S.w.id, n.id]);
      S.repSample = { key, data };
      if (host.isConnected) host.innerHTML = repSampleHtml(data, n);
    } catch (err) {
      console.warn("repeat_sample", err.message);
      if (host.isConnected) host.innerHTML = "";
    }
  }, 260);
}
new MutationObserver(() => {
  if (document.querySelector("#rep-sample[data-pending]")) repSampleFill();
}).observe(document.body, { childList: true, subtree: true });

/* ---------------------------------------------------- progress and runs */
const _p5cPeopleProgress = peopleProgress;
peopleProgress = function (step) {
  const html = _p5cPeopleProgress(step);
  if (!step?.lines?.length) return html;
  const w = step.line_words || { plural: "lines" };
  const rows = step.lines
    .map(
      (l) =>
        `<li class="rep-line is-${esc(l.state)}"><span class="rep-n">${l.number}</span><div class="grow"><strong>${esc(l.label)}</strong><small>${pill(status(l.state), l.state)}${l.who ? " · " + esc(l.who) : ""}${l.answer ? ` · <span class="answer-chip">${svgIcon("buttons")}${esc(l.answer)}</span>` : ""}</small>${l.reason ? `<small class="rep-why">${esc(l.reason)}</small>` : ""}</div>${l.failed_step_id && S.progress?.can_manage ? btn("retry-line", "Retry", "history", "small", `data-run="${l.run_id}" data-id="${l.failed_step_id}" aria-label="Retry ${esc(l.label)}"`) : ""}</li>`,
    )
    .join("");
  return html + `<div class="rep-lines"><p class="again-title">${svgIcon("repeat")}Each ${esc(w.singular || "line")}</p><ol>${rows}</ol></div>`;
};
const _p5cActivity = activity;
activity = function (embedded = false) {
  let html = _p5cActivity(embedded);
  if (!embedded || !S.w || !hasRepeat(S.w.definition)) return html;
  const toggle = btn("toggle-lines", S.showLines ? "Hide lines" : "Show lines", "repeat", "plain", `aria-pressed="${!!S.showLines}"`);
  const at = html.indexOf('data-act="refresh-runs"'),
    k = at > 0 ? html.lastIndexOf("<button", at) : -1;
  return k > 0 ? html.slice(0, k) + toggle + html.slice(k) : html;
};
const _p5cTimeSteps = timeSteps;
timeSteps = function (steps) {
  let html = _p5cTimeSteps(steps);
  for (const s of steps || [])
    if (s.kind === "repeat") html = html.replace(`<b>${esc(s.title)}</b><small>Nobody yet`, `<b>${esc(s.title)}</b><small>${svgIcon("repeat")}${esc(s.line_words || "Counted once, with all its lines")}`);
  return html;
};
const _p5cTaskExtras = taskExtras;
taskExtras = function (t) {
  const html = _p5cTaskExtras(t);
  if (!t?.line) return html;
  return `<div class="line-chip" role="note">${svgIcon("repeat")}<span><b>${esc(t.line.label)}</b>${t.line.words ? " · " + esc(t.line.words) : ""}</span></div>` + html;
};
const _p5cAction = action;
action = async function (name, el) {
  if (name === "toggle-lines") {
    S.showLines = !S.showLines;
    S.runs = await rpc("runs", [S.w.id], { show_lines: !!S.showLines });
    render();
    return;
  }
  if (name === "retry-line") {
    await rpc("run_action", [Number(el.dataset.run), "retry", Number(el.dataset.id)]);
    notify("Tried that line again.");
    const keep = S.selected;
    S.progress = await rpc("progress", [S.progress.id]);
    S.selected = keep;
    render();
    return;
  }
  if (name === "add-at" && S.w) {
    /* The "+" inside a repeat offers only what may run once per line, and a
       repeat itself only on the main path, so nothing offered is refused. */
    const t = targets(S.w.definition).find((t) => t.id === el?.dataset?.id),
      into = t ? containers(S.w.definition).find((c) => c.key === t.key)?.parent : null;
    if (t && t.key !== "main") {
      S.insertTarget = t;
      const rows = Object.entries(TYPES).filter(([type]) => type !== "repeat" && !(into?.type === "repeat" && REP_REFUSED[type]));
      modal(
        into?.type === "repeat" ? `Add a step for each ${repWords(into).singular}` : "Add a step",
        `<div class="choice-list">${rows.map(([type, x]) => btn("add-picked", esc(x[0]), type, "", `data-type="${type}"`)).join("")}</div>${into?.type === "repeat" ? '<p class="muted small">Approvals, stage moves, hand-overs and other once-per-record steps go before or after the repeat.</p>' : ""}`,
      );
      return;
    }
  }
  const r = await _p5cAction(name, el);
  if (S.showLines && S.w && ((name === "tab" && el?.dataset?.id === "runs") || name === "refresh-runs")) {
    S.runs = await rpc("runs", [S.w.id], { show_lines: true });
    if (S.tab === "runs") render();
  }
  return r;
};
