# Phase-4 — Moonshots Design Document

Companion to `PHASE1_FORMULA_ENGINE_PLAN.md`, `PHASE2_3_FORMULA_ENGINE_DESIGN.md` and `FORMULA_ENGINE_VISION.html` (all in this folder).

Moonshots are bets, not commitments — but two of them decompose cleanly into **deterministic cores plus machinery that Phases 1–3 already build**, so they can be designed to implementation grade today: **M1 (employee-facing pay-change explainer)** and **M2 (probabilistic payroll)**. The remaining five stay as briefs with design-complete triggers, same convention as Part B of the Phase-2/3 document.

The single rule that makes both featured moonshots safe to build: **the LLM never computes and never sees beyond its scope; deterministic code computes, the LLM narrates.** This is the same ladder as everywhere else in the vision (cloud → local → deterministic floor), applied to the two highest-stakes surfaces yet: employees and budgets.

---

# M1 — Employee-facing "Why did my pay change?" conversational explainer

**What it is.** An employee opens their payslip in the portal and asks, in English or Vietnamese, why this month's net differs from last month's. The system answers with the actual causes — "your overtime dropped from 22h to 8h (−2,100,000 ₫) and the PIT bracket rate changed on July 1 (−180,000 ₫)" — and can take follow-up questions. It never guesses, never leaks, never advises.

## Why this is buildable (not just a demo)

Every payslip already stores `formula_input_values` and `formula_computed_values` as JSON (`hr_payslip_formula.py`), the dependency graph is queryable (`get_intelligence`, Phase 1 ✅), and formula changes between periods are attributable once F7 version history lands. That means the *causes* of a pay delta are **fully derivable by deterministic code** — the conversational layer is presentation, not analysis.

## Decisions

- **D-M1.1 — Deterministic delta decomposition is the product; the chat is a skin.** A `hr.payslip` method decomposes net-pay delta into an exact, ranked cause list (skeleton S5). This decomposition ships value even with AI disabled: rendered as a "What changed" panel on the payslip (portal + backend) with template sentences. The conversational layer is an optional rung on top.
- **D-M1.2 — The LLM never produces a number.** The narrative is generated from a structured cause list where every amount is a template slot filled by deterministic code *after* generation (prompt says `{{cause_1_amount}}`, renderer substitutes). A hallucinated amount is a compliance incident; template slots make it structurally impossible.
- **D-M1.3 — Scoped by construction, not by prompt.** The portal controller resolves `employee_id` from the authenticated session (`request.env.user.employee_id`), passes it into every RPC, and the conversation tools available to the LLM are exactly two: `get_pay_delta(payslip_id)` (record-rule-checked) and `get_component_explanation(rule_code)` (config metadata + F5's explain output — no amounts of other employees, no SQL). The PayAI data-query engine (`payroll_data_query.py`) is **never** mounted on this surface.
- **D-M1.4 — Cause taxonomy is closed.** Every delta contribution is classified into exactly one of: `input_changed` (OT hours, attendance, bonus, commission), `formula_changed` (F7 version between the two periods → release note from B3 if present), `contract_changed` (wage/advantage delta via `hr.contract.advantage.change`), `proration` (partial period flags), `carryover` (mid↔end cycle mapping), `new_component` / `removed_component`, `residual` (must be ≈ 0 — see S5 invariant). Unknown causes don't exist; a nonzero residual is a bug alarm, not a shrug.
- **D-M1.5 — Refusal and escalation are first-class.** Questions outside the taxonomy ("should I change my tax declaration?", "why does my colleague earn more?") get a fixed refusal template + an "Ask HR" button that opens a ticket carrying the conversation transcript. Every conversation is logged to a model HR can review; there is an HR kill-switch per company (`ir.config_parameter` `pb_explainer.enabled`).
- **D-M1.6 — Bilingual from the decomposition up.** Cause templates exist in EN and VI keyed by taxonomy entry; component names come from the payslip scheme's bilingual labels (F9). The LLM rung receives the language explicitly.

## Data model (new module `pb_pay_explainer`, depends on portal self-service)

```
hr.payslip.delta.explanation          # cached decomposition, computed on demand
  payslip_id, prev_payslip_id (m2o), decomposition_json (Text)
  residual (Float), state: ok/residual_alarm
  narrative_en (Text), narrative_vi (Text)   # cached template render

pb.explainer.conversation             # employee-scoped chat log
  employee_id, payslip_id, message_ids (o2m: role, text, tool_calls_json)
  escalated (Boolean), hr_reviewed (Boolean)
```

## Pipeline

1. **Decompose** (S5): exact per-component deltas → per-cause attribution → ranked list, residual invariant checked.
2. **Template render**: cause list → EN/VI sentences with amounts substituted → "What changed" panel. *This is the deterministic floor and the default UX.*
3. **Conversational rung** (optional): `_llm_chat` with a system prompt containing the structured cause list + component metadata + refusal rules; tools limited per D-M1.3; amounts via slots per D-M1.2.
4. **Escalate/log** per D-M1.5.

## Work plan

| Task | AC |
|---|---|
| TM1.1 Decomposition method + explanation model (S5) | On a demo employee with a known OT change: cause list contains exactly the OT input cause with the exact amount; residual < 1 ₫; runtime < 1 s per payslip |
| TM1.2 Formula-change attribution via F7 | Change a rate between two demo periods → decomposition attributes the affected component's delta to `formula_changed` citing the version row, not to inputs |
| TM1.3 "What changed" panel (portal + backend payslip view), EN/VI templates | Panel renders from cache; recompute button; zero-delta payslip says "nothing changed" (not an empty panel); works with AI fully disabled |
| TM1.4 Portal controller + scoping | A portal user crafting another employee's payslip_id gets a 403 from record rules (test explicitly); no route accepts employee_id as a parameter |
| TM1.5 Conversational rung + refusal/escalation + HR log | Amount-slot substitution verified (grep the rendered narrative: every number matches decomposition values); out-of-scope question → refusal template + ticket; kill-switch hides the chat but keeps the panel |
| TM1.6 Safety pass | Red-team checklist: prompt injection via question text cannot alter tool scope (tools are server-registered, not prompt-declared); conversation log complete; VI diacritics render in templates |

**Dependencies:** F7 (formula-change attribution — degrade gracefully: without F7 those deltas classify as `formula_changed (details unavailable)`), employee self-service portal (the table-stakes gap — M1 is the feature that justifies building it), Phase-1 F5 `_llm_chat`.
**Trigger to build:** self-service portal exists + F7 in production.

## S5 — Skeleton: delta decomposition (the risky spot)

```python
# pb_pay_explainer/models/hr_payslip_delta.py
class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def get_pay_delta(self, prev_slip=None):
        """Exact, ranked decomposition of net-pay change vs the previous slip.
        Deterministic. The residual invariant is the correctness proof:
            sum(component deltas over payslip-visible signed components)
              == net_delta  (exact, by construction)
        and every component delta is attributed to >=1 cause whose amounts
        sum back to that component's delta (attribution residual ~ 0)."""
        self.ensure_one()
        prev = prev_slip or self._find_previous_slip()      # same employee, same cycle_type
        cur_v = json.loads(self.formula_computed_values or '{}')
        prv_v = json.loads(prev.formula_computed_values or '{}')
        cur_i = json.loads(self.formula_input_values or '{}')
        prv_i = json.loads(prev.formula_input_values or '{}')
        cfg = self.formula_config_id
        graph = self.env['pb.formula.studio'].get_intelligence(cfg.id)   # Phase-1 RPC
        upstream = _closure(graph['edges'])                  # col -> set(input cols)

        causes = []
        for rule in cfg.rule_ids.filtered('appears_on_payslip'):
            code = rule.code
            d = _num(cur_v.get(code)) - _num(prv_v.get(code))
            if abs(d) < 0.5:
                continue
            # -- attribution, in priority order (D-M1.4 closed taxonomy) --
            # 1) formula changed between the two periods? (F7 versions)
            ver = self._formula_version_between(rule, prev.date_to, self.date_to)
            # 2) which upstream INPUTS changed?
            changed_inputs = [c for c in upstream[rule.column_letter]
                              if abs(_num(cur_i.get(_code_of(c))) - _num(prv_i.get(_code_of(c)))) > 1e-9]
            # 3) contract / proration / carryover flags …
            causes.append({
                'component': code, 'label': rule.name, 'delta': d,
                'cause': ('formula_changed' if ver else
                          'input_changed' if changed_inputs else
                          self._structural_cause(rule, prev)),   # contract/proration/carryover/new/removed
                'detail': {'version_id': ver and ver.id,
                           'inputs': [{'code': _code_of(c),
                                       'from': _num(prv_i.get(_code_of(c))),
                                       'to': _num(cur_i.get(_code_of(c)))} for c in changed_inputs]},
            })
        net_delta = _num(cur_v.get('NETPAY')) - _num(prv_v.get('NETPAY'))
        residual = net_delta - sum(c['delta'] * _sign(cfg, c['component']) for c in causes)
        # residual > tolerance => taxonomy missed something: ALARM, never ship a wrong story
        causes.sort(key=lambda c: -abs(c['delta']))
        return {'net_delta': net_delta, 'causes': causes,
                'residual': residual, 'ok': abs(residual) < 1.0}
```

Attribution subtlety the implementer must handle: a component can have BOTH a formula change and input changes in the same period. Split its delta by re-evaluating the component three ways with F8's overlay evaluator — (old formula, old inputs), (old formula, new inputs), (new formula, new inputs) — the two differences are the input-attributed and formula-attributed shares. This is the only place recomputation is needed; everything else is stored-JSON arithmetic.

---

# M2 — Probabilistic payroll: OT/attendance scenario ranges for budget planning

**What it is.** Payroll cost is presented as a point number today, but OT, attendance, commissions and turnover make it a distribution. M2 gives finance a forecast: "July payroll: P50 ₫ 128.4B, P10–P90 ₫ 126.1B – 131.9B; 78% of the variance is Manufacturing OT" — with scenario overlays ("headcount +50 in Q3", "minimum wage +6%").

## Decisions

- **D-M2.1 — Empirical resampling, not parametric distributions.** Input history is already stored per employee per period (`formula_input_values` on every payslip). Draw scenarios by resampling each employee's own historical input vectors (12+ months), jointly per employee — resampling whole months preserves the real correlations between OT/attendance/bonus that parametric marginals destroy. Segment fallback (division × job level) for employees with < 6 months of history. No distribution-fitting UI in v1.
- **D-M2.2 — Two evaluation tiers, honestly labeled** (extends B8's rule): *interactive* = stratified sample of ~200 employees, results marked "estimate from sample"; *committed forecast* = full population, chunked like F6/F8. Sampled numbers are never presented as final.
- **D-M2.3 — Vectorized compiled config for full runs.** 4.5k employees × 500 draws × ~60 formulas ≈ 135M evaluations — per-rule Python `eval` will not survive that. Compile the config once per forecast: each rule's `python_formula` → a numpy expression over arrays (columns = employees×draws), `IF(c,a,b)` → `np.where`, MIN/MAX/ROUND → numpy equivalents, execution in the existing topological order. This compiler (`formula_engine/vector_compiler.py`) is the moonshot's real engineering — and it later pays for itself in ordinary payrun performance. **Fallback:** if a rule uses a non-compilable construct, the compiler reports it and the forecast runs tier-1 (sampled, per-rule eval) with a visible "N rules non-vectorizable" note — never silently slow.
- **D-M2.4 — Variance attribution is computed, not guessed.** Per input: freeze that input at its P50 across draws, re-run (cheap once vectorized), attribute variance reduction — a Sobol-style first-order estimate. Output = tornado chart data, top-10 inputs. This is what makes the feature a *planning* tool rather than a chart.
- **D-M2.5 — Scenario overlays reuse F8/F14 machinery**: an overlay is `{rule overrides (formula changes), population changes (headcount +/- per segment, wage +x%), input shifts (OT +20% in division D)}` applied before compilation. Legislation scenarios come from B4 packs when those exist.
- **D-M2.6 — Trend honesty.** v1 applies only two adjustments to resampled history: seasonality (same-month weighting when ≥ 24 months of history) and explicit user-set growth factors. No silent trend extrapolation — finance must see every assumption listed on the forecast.

## Data model (new module `pb_payroll_forecast`)

```
hr.payroll.forecast
  name, config_ids (m2m), scope_domain (Char), horizon_months (Int), n_draws (Int, default 500)
  tier: sampled/full, assumptions_json (growth factors, seasonality flag)
  scenario_overlay_json, state: draft/running/done
  results_json          # per month: {p10,p50,p90,mean}, per division, per component
  variance_json         # tornado: [{input_code, share}]
  non_vectorizable_rules (Text)

hr.payroll.forecast.draw_cache        # optional, for drill-down; pruned aggressively
```

## Work plan

| Task | AC |
|---|---|
| TM2.1 Input-history extractor + empirical sampler (S6) | For a demo employee with 12 months of history, 1,000 draws reproduce that employee's historical OT mean/variance within 5%; joint resampling verified (correlation between OT and attendance preserved vs shuffled baseline) |
| TM2.2 `vector_compiler.py`: python_formula → numpy, topological execution, non-compilable reporting | Compiled evaluation of the VN config over all demo employees equals per-rule eval results exactly (byte-compare rounded outputs) — this is the compiler's ground-truth harness; a deliberately exotic rule lands in `non_vectorizable_rules`, not in wrong numbers |
| TM2.3 Chunked MC driver + percentile aggregation | Full-population 500-draw forecast on the demo world completes < 10 min with progress; re-run with same seed is identical (seeded RNG — pass the seed in, per the no-`Math.random` discipline server-side too) |
| TM2.4 Variance attribution (D-M2.4) | Seeding the demo world so one division's OT dominates variance → tornado ranks it first with share ≥ its analytically expected value ± 10% |
| TM2.5 Scenario overlays | "+6% wage from month 2" shifts P50 by the hand-computed amount; overlay list renders on the forecast header (D-M2.6) |
| TM2.6 Cockpit UI: fan chart (P10–P90 band per month), tornado, division breakdown, assumptions panel, sampled/full badge | Chart.js (already in stack); interactive tier answers < 15 s; switching to full queues the chunked run |

**Dependencies:** F8 overlay evaluation (hard), ≥ 6–12 months of stored input history (the pb_demo generator should synthesize a 12-month backfill — extend it; this also serves F6's multi-period fixture), F11 rate tables benefit the compiler but aren't required.
**Trigger to build:** F8 in production + backfilled demo history validating the sampler.

## S6 — Skeleton: sampler + MC driver + variance attribution (the risky spots)

```python
# pb_payroll_forecast/models/input_sampler.py
class InputSampler:
    """Empirical joint resampler. One draw for one employee = one whole
    historical month's input vector (D-M2.1: joint, correlation-preserving)."""

    def __init__(self, env, employees, months_back=12, seed=None):
        self.rng = np.random.default_rng(seed)          # seeded: reproducible forecasts
        self.history = self._load_history(env, employees, months_back)
        # history[emp_id] = list of input dicts, one per historical month
        self.segment_pool = self._build_segment_pools() # (division, job_level) -> vectors

    def draw(self, emp_id, month_offset, seasonality=False):
        pool = self.history.get(emp_id) or self.segment_pool[self._segment(emp_id)]
        if seasonality and len(pool) >= 24:
            pool = self._same_month_weighted(pool, month_offset)
        return pool[self.rng.integers(len(pool))]        # whole-vector resample

    def draw_matrix(self, emp_ids, input_codes, n_draws, month_offset):
        """-> {code: ndarray shape (len(emp_ids) * n_draws,)} for the compiler."""
        ...

# pb_hr_payroll_formula/formula_engine/vector_compiler.py
SAFE_MAP = {'IF': 'np.where', 'MIN': 'np.minimum', 'MAX': 'np.maximum',
            'ROUND': '_vround', 'ABS': 'np.abs', ...}

def compile_config(rules, execution_order):
    """Each rule's python_formula -> a lambda over a dict of ndarrays.
    Returns (evaluate(inputs: {code: ndarray}) -> {code: ndarray},
             non_vectorizable: [rule codes]).
    CORRECTNESS HARNESS IS NON-NEGOTIABLE (TM2.2): compiled results must
    equal the scalar evaluator exactly on real data before any forecast ships."""
    ...

# variance attribution (D-M2.4) — first-order freeze method
def variance_shares(evaluate, base_inputs, total_cost_of):
    base = total_cost_of(evaluate(base_inputs))
    var_total = base.var()
    shares = {}
    for code in candidate_inputs:                        # top inputs by raw variance
        frozen = dict(base_inputs)
        frozen[code] = np.full_like(base_inputs[code], np.median(base_inputs[code]))
        var_frozen = total_cost_of(evaluate(frozen)).var()
        shares[code] = max(0.0, (var_total - var_frozen) / var_total)
    return shares   # normalize for the tornado; label as first-order estimate
```

---

# Remaining moonshot briefs

**M3 — Live multiplayer grid.** Shared cursors + co-editing in Grid Studio. Architecture: Odoo's `bus.bus` websocket for presence + cell-lock leases (soft locks: "Anh is editing T", last-write-wins with F7 restore as the safety net — full OT/CRDT is not justified for ~2 concurrent editors on 100 cells). **Decision: presence + soft locks + version-history recovery, not operational transforms.** Depends: Grid (✅), F7. Trigger: evidence of real concurrent-editing conflicts from F7 logs (two users versioning the same rule within minutes).

**M4 — Compliance Watch.** AI monitors legislation sources per country, drafts formula changes as B3 releases. Architecture: curated source registry (official gazette URLs/RSS per country) → scheduled fetch + diff → `_llm_chat` extracts candidate changes with citations → drafts land as F7-versioned proposals in a B2 sandbox with B4 pack tests attached; a human certifies. **Decision: AI proposes into the existing sandbox→release pipeline; it never gets a new write path of its own.** Depends: B2, B3, B4. Trigger: B4 packs exist for ≥ 2 countries.

**M5 — Full NL config generation.** "Vietnam retail, 2 cycles, PIT + SI" → working draft config with tests. Architecture: composition over B4 packs (retrieve nearest pack, apply deltas via NL→formula from Phase-1 F5) — *not* freehand generation; every generated config must arrive with generated sample tests and a failing-test gate before it can leave draft. Depends: B4, F5, Phase-2 test framework. Trigger: B4 with ≥ 3 packs.

**M6 — Voice-driven payroll ops.** Voice for approvals and queries. The PayAI chat already has voice input (`rpc_send_voice_message`); the gap is action safety: voice may *navigate and read* freely, but any mutation (approve a release, run payroll) requires an on-screen typed/clicked confirmation. **Decision: voice reads, hands write.** Depends: B3 approvals. Trigger: mobile approval flow (Tier-2 tablet mode) sees real usage.

**M7 — Cross-company anonymized benchmark.** "Your OT load is 2.1× sector median." Requires a multi-tenant aggregation service with k-anonymity (suppress any cell with < 5 companies), explicit per-company opt-in, and a separate legal review — the engineering (per-component ratio aggregation of data the system already computes) is the easy half. **Decision: opt-in, k≥5 suppression, aggregates only ever leave the tenant — raw values never.** Trigger: ≥ 10 tenant companies on managed hosting; legal sign-off precedes any code.

---

# Sequencing & posture

| Moonshot | Earliest realistic start | Gate |
|---|---|---|
| M1 explainer | after F7 + self-service portal | TM1.6 safety pass is a release blocker, not a task |
| M2 probabilistic | after F8 + demo history backfill | TM2.2 compiler ground-truth harness is a release blocker |
| M3 multiplayer | after F7 usage data | conflict evidence |
| M4 compliance watch | after B2/B3/B4 | human certification stays mandatory forever |
| M5 NL config | after B4 ≥ 3 packs | failing-test gate |
| M6 voice ops | after B3 + tablet mode | voice reads, hands write |
| M7 benchmark | after 10+ tenants | legal first |

M1 and M2 are the two worth pre-investing in: M1 forces the self-service portal (a table-stakes gap) into existence with a differentiator attached, and M2's vector compiler doubles as a payrun performance upgrade. Both have their risky spots skeletoned (S5, S6) and their correctness invariants stated — the residual alarm and the compiler ground-truth harness are what keep "magical" from becoming "wrong."
