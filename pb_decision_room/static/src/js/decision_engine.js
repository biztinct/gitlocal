/** @odoo-module **/
/**
 * The Decision Room engine — twelve months of a company, from a handful of
 * levers.
 *
 * Ported from the proof of concept at `design_poc/wfplan/src/core.js`, with two
 * substantive changes and nothing else invented:
 *
 *   1. **The company is real.** The proof of concept carried six hard-coded
 *      divisions and fictional US dollars. This engine is handed the SERVER's
 *      baseline — the company's own teams, roles, headcount and monthly pay, in
 *      the company's own currency — and never scales it. Scaling to "₫1.25B" is
 *      the formatter's job and happens once, on screen.
 *   2. **The assumptions are a record.** Contribution rates, the cap, the
 *      allowance share, the overtime multiplier, working days, recruiting and
 *      severance cost, the bonus month and the income-tax ladder come from
 *      `pb.decision.assumptions`, so a reader can be shown exactly what the
 *      picture believed.
 *
 * Everything else is the proof of concept's semantics, kept deliberately:
 * contributions capped, allowances as a share of base, overtime at a multiplier
 * of the hourly rate, the bonus in its month, recruiting cost in the month a
 * hire arrives, severance in the month a role ends, a new person paid in full
 * but only half productive in their first month, leavers and their backfill,
 * the mild seasonal curve, and the demand model — capacity follows the people
 * who earn revenue, revenue is the smaller of demand and capacity.
 *
 * This file imports NOTHING, so `node tools/decision_engine_check.mjs` can load
 * it exactly as it ships. That includes the TRANSLATOR: every sentence below
 * is written `_t("…")`, which the string extractor finds exactly as it finds
 * one in any other file, but `_t` itself is INJECTED at load time by
 * `decision_room.js` rather than imported. Under node the fallback below
 * interpolates and hands back plain English, so the numbered engine checks
 * read the same sentences they always did.
 */

/** The room's translator; replaced by the platform's `_t` at load time. */
let _t = (text, params) => interpolate(text, params);

function interpolate(text, params) {
    const raw = String(text === undefined || text === null ? "" : text);
    if (params === undefined || params === null) { return raw; }
    // The platform's own two rules, mirrored exactly, so a sentence reads the
    // same under `node` as it does on screen: with a dictionary only
    // `%(key)s` is replaced and `%%` is left alone; with a single value `%s`
    // is replaced and `%%` becomes one per cent sign.
    if (typeof params === "object" && !Array.isArray(params)) {
        return raw.replace(/%\(([^)]+)\)s/g,
            (hit, key) => (key in params ? String(params[key]) : ""));
    }
    let out = "";
    for (let i = 0; i < raw.length; i++) {
        if (raw[i] === "%" && raw[i + 1] === "%") { out += "%"; i++; continue; }
        if (raw[i] === "%" && raw[i + 1] === "s") {
            out += String(params); i++; continue;
        }
        out += raw[i];
    }
    return out;
}

export function useTranslator(fn) {
    if (typeof fn === "function") { _t = fn; }
}

/** Mild Vietnamese seasonality. Sums to 12, so a flat year is a flat year. */
export const SEASON = [0.86, 0.78, 0.95, 1.00, 1.02, 1.04,
                       1.02, 1.03, 1.05, 1.08, 1.10, 1.07];

/** What "today" means for the levers the roster cannot tell us. */
export const DEFAULT_ABSENCE = 8;

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const num = (v, fallback = 0) => (Number.isFinite(Number(v)) ? Number(v) : fallback);

export function cloneState(state) {
    return JSON.parse(JSON.stringify(state || {}));
}

// ---------------------------------------------------------------- assumptions
/** Every assumption, with a sane value even when the record is empty. */
export function readAssumptions(a) {
    const raw = a || {};
    return {
        erRate: num(raw.employer_rate_pct, 23.5) / 100,
        eeRate: num(raw.employee_rate_pct, 10.5) / 100,
        cap: Math.max(0, num(raw.contribution_cap, 0)),
        allowance: num(raw.allowance_pct, 12) / 100,
        otMult: num(raw.ot_multiplier, 1.5),
        nightUplift: num(raw.night_uplift_pct, 30) / 100,
        workDays: Math.max(1, num(raw.work_days, 22)),
        recruitMonths: Math.max(0, num(raw.recruit_cost_months, 1)),
        severanceMonths: Math.max(0, num(raw.severance_months, 1.5)),
        ramp: clamp(num(raw.ramp_first_month_pct, 50), 0, 100) / 100,
        attritionYear: Math.max(0, num(raw.attrition_pct_year, 12)),
        bonusMonth: clamp(Math.round(num(raw.bonus_month_index, 1)), 0, 12),
        bonusMonths: Math.max(0, num(raw.bonus_months, 1)),
        otherFixed: Math.max(0, num(raw.other_fixed_monthly, 0)),
        otherPct: num(raw.other_pct_revenue, 25) / 100,
        target: Math.max(0, num(raw.revenue_target, 0)),
        growth: num(raw.demand_growth_pct, 0),
        ladder: raw.pit_ladder && typeof raw.pit_ladder === "object"
            ? raw.pit_ladder : { bands: [] },
        // ---- shifts (Phase 2) -------------------------------------------
        eveningShare: clamp(num(raw.shift_evening_pct, 25), 0, 50),
        nightShare: clamp(num(raw.shift_night_pct, 15), 0, 40),
        eveningUplift: Math.max(0, num(raw.evening_uplift_pct, 0)) / 100,
        demandShares: normalizeShares([
            num(raw.demand_day_pct, 60),
            num(raw.demand_evening_pct, 25),
            num(raw.demand_night_pct, 15),
        ]),
        productivityCost: Math.max(0, num(raw.productivity_cost_per_point, 0)),
    };
}

/** The three shift keys, in the order the day runs. */
export const SHIFTS = ["day", "evening", "night"];

/**
 * Three shares that add up to one.
 *
 * The record CONSTRAINS them to 100 and the server refuses anything else —
 * but an old row, a half-typed dialog or a hand-edited database can still
 * hand this engine 60/25/20, and a picture that silently loses five percent
 * of the work is worse than one that quietly rescales it.
 */
export function normalizeShares(values) {
    const clean = (values || []).map((v) => Math.max(0, num(v, 0)));
    const total = clean.reduce((sum, v) => sum + v, 0);
    if (total <= 0) { return [1, 0, 0]; }
    return clean.map((v) => v / total);
}

/** Monthly income tax on one person's taxable pay. Never touches company cost. */
export function taxOn(taxable, ladder) {
    const bands = (ladder && ladder.bands) || [];
    if (!bands.length || taxable <= 0) { return 0; }
    let tax = 0;
    let previous = 0;
    for (const band of bands) {
        const top = num(band[0], 0);
        const rate = num(band[1], 0) / 100;
        const ceiling = top > 0 ? top : Infinity;
        const slice = Math.min(taxable, ceiling) - previous;
        if (slice <= 0) { break; }
        tax += slice * rate;
        previous = ceiling;
        if (!Number.isFinite(ceiling)) { break; }
    }
    return tax;
}

// --------------------------------------------------------------------- state
/** The default plan: the company exactly as it is today. */
export function defaultState(baseline, assumptions) {
    const a = readAssumptions(assumptions);
    const now = new Date();
    return {
        target: a.target,
        growth: a.growth,
        stress: 0,
        raise: 0,
        raiseMonth: 1,
        ot: 0,
        otFrom: 1,
        attritionOn: false,
        backfill: true,
        bonusMonths: a.bonusMonths,
        productivity: 0,
        absence: DEFAULT_ABSENCE,
        start: clamp(now.getMonth() + 2, 1, 12),
        evening: a.eveningShare,
        night: a.nightShare,
        moves: [],
    };
}

/** Everything inside its range, every field present, nothing else carried. */
export function normalizeState(state, baseline, assumptions) {
    const base = defaultState(baseline, assumptions);
    const s = state || {};
    const teams = ((baseline && baseline.teams) || []);
    const teamByKey = Object.fromEntries(teams.map((t) => [t.key, t]));
    const moves = Array.isArray(s.moves) ? s.moves : [];
    // Evening and night are shares of the SAME people, so they are clamped
    // together: 50 % of a team cannot be on evenings while 40 % is on nights
    // and somebody still opens the doors in the morning. Night gives way,
    // because it is the smaller commitment of the two to unwind.
    let evening = clamp(num(s.evening, base.evening), 0, 50);
    let night = clamp(num(s.night, base.night), 0, 40);
    if (evening + night > 80) { night = Math.max(0, 80 - evening); }
    return {
        evening, night,
        target: Math.max(0, num(s.target, base.target)),
        growth: clamp(num(s.growth, base.growth), -50, 100),
        stress: clamp(num(s.stress, 0), -30, 30),
        raise: clamp(num(s.raise, 0), -20, 40),
        raiseMonth: clamp(Math.round(num(s.raiseMonth, 1)), 1, 12),
        ot: clamp(num(s.ot, 0), 0, 60),
        otFrom: clamp(Math.round(num(s.otFrom, 1)), 1, 12),
        attritionOn: !!s.attritionOn,
        backfill: s.backfill === undefined ? true : !!s.backfill,
        bonusMonths: clamp(num(s.bonusMonths, base.bonusMonths), 0, 4),
        productivity: clamp(num(s.productivity, 0), -20, 40),
        absence: clamp(num(s.absence, DEFAULT_ABSENCE), 0, 40),
        start: clamp(Math.round(num(s.start, base.start)), 1, 12),
        moves: moves
            .filter((m) => m && teamByKey[m.team] && Math.round(num(m.n, 0)))
            .map((m) => ({
                team: m.team,
                role: m.role || null,
                n: Math.round(num(m.n, 0)),
                month: clamp(Math.round(num(m.month, 1)), 1, 12),
            })),
    };
}

/** How many people a move puts into one role, this month. */
function moveShare(move, team, role) {
    if (move.role) { return move.role === role.key ? move.n : 0; }
    const total = team.roles.reduce((sum, r) => sum + r.heads, 0) || 1;
    return move.n * (role.heads / total);
}

// ------------------------------------------------------------------- compute
/**
 * Twelve months of this company under this plan.
 *
 * @param {object} baseline    the server's roster: {teams:[{roles:[…]}], …}
 * @param {object} assumptions the assumptions record
 * @param {object} state       the levers
 * @returns {{rows:Array, year:object, teams:Array}}
 */
export function compute(baseline, assumptions, state) {
    const a = readAssumptions(assumptions);
    const s = normalizeState(state, baseline, assumptions);
    const teams = (baseline && baseline.teams) || [];

    const rows = [];
    const teamOut = teams.map((t) => ({
        key: t.key, name: t.name, revenue: !!t.revenue,
        headsToday: t.heads, heads: new Array(12).fill(0),
        cost: new Array(12).fill(0), year: 0,
        payToday: t.pay_month_avg || 0,
        // December always has the increase: `raiseMonth` cannot be past 12.
        payDec: (t.pay_month_avg || 0) * (1 + s.raise / 100),
    }));
    const revHeads = new Array(12).fill(0);      // paid revenue-earning heads
    const revCapHeads = new Array(12).fill(0);   // the same, ramped
    let revHeadsBase = 0;
    // Shares of the people who earn revenue, as fractions. Day is what is
    // left, so the three always add up to exactly one head per head.
    const shiftPeople = [
        Math.max(0, 1 - (s.evening + s.night) / 100),
        s.evening / 100,
        s.night / 100,
    ];
    const shiftUplift = [0, a.eveningUplift, a.nightUplift];
    const totals = { hires: 0, cuts: 0, leavers: 0 };

    const attritionRate = s.attritionOn ? (a.attritionYear / 100 / 12) : 0;

    for (let m = 0; m < 12; m++) {
        const row = {
            name: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                   "Sep", "Oct", "Nov", "Dec"][m],
            index: m, heads: 0, headsByTeam: {}, base: 0, allowance: 0,
            salary: 0, overtime: 0, premium: 0, bonus: 0, contributions: 0,
            recruit: 0, severance: 0, learning: 0, people: 0, gross: 0,
            withholding: 0, takehome: 0, demand: 0, capacity: 0, revenue: 0,
            coverage: 1, other: 0, profit: 0, margin: 0,
        };
        const otHours = (m + 1) >= s.otFrom ? s.ot : 0;

        teams.forEach((team, ti) => {
            let teamHeads = 0;
            let teamCost = 0;
            for (const role of team.roles) {
                // ---- how many people are in this role, this month --------
                let n = role.heads;
                let arriving = 0;
                let leaving = 0;
                for (const move of s.moves) {
                    if (move.team !== team.key) { continue; }
                    const share = moveShare(move, team, role);
                    if (!share) { continue; }
                    if ((m + 1) >= move.month) { n += share; }
                    if ((m + 1) === move.month) {
                        if (share > 0) { arriving += share; }
                        else { leaving += -share; }
                    }
                }
                if (attritionRate && !s.backfill) {
                    n -= role.heads
                        * (1 - Math.pow(1 - attritionRate, m + 1));
                }
                n = Math.max(0, n);

                // ---- what a month of that costs ---------------------------
                const pay = role.pay_month_avg
                    * (1 + ((m + 1) >= s.raiseMonth ? s.raise / 100 : 0));
                const base = n * pay;
                const allowance = base * a.allowance;
                const hourly = pay / (a.workDays * 8);
                const overtime = n * hourly * a.otMult * otHours;
                // Shift premiums are paid to the people who work the shifts,
                // and only the teams that earn revenue are rostered across the
                // clock in this model — a finance team does not get a night
                // uplift for a night nobody asked it to work.
                const premium = team.revenue
                    ? n * pay * (shiftPeople[1] * shiftUplift[1]
                                 + shiftPeople[2] * shiftUplift[2])
                    : 0;
                const capped = a.cap > 0 ? Math.min(pay, a.cap) : pay;
                const contributions = n * capped * a.erRate;
                const bonus = (a.bonusMonth && (m + 1) === a.bonusMonth)
                    ? base * s.bonusMonths : 0;

                let recruit = arriving * pay * a.recruitMonths;
                const severance = leaving * pay * a.severanceMonths;
                if (attritionRate && s.backfill) {
                    recruit += role.heads * attritionRate * pay
                        * a.recruitMonths;
                }
                if (attritionRate) {
                    totals.leavers += role.heads * attritionRate;
                }
                totals.hires += arriving;
                totals.cuts += leaving;

                // ---- what reaches the employee ---------------------------
                const perPerson = n > 0
                    ? (pay + allowance / n + overtime / n) : 0;
                const employeeIns = capped * a.eeRate;
                const ladder = a.ladder;
                const personal = num(ladder.personal, 0)
                    + num(ladder.dependent, 0);
                const tax = taxOn(perPerson - employeeIns - personal, ladder);
                const withholding = n * (employeeIns + tax);

                const gross = base + allowance + overtime + premium + bonus;

                row.heads += n;
                row.base += base;
                row.allowance += allowance;
                row.salary += base + allowance;
                row.overtime += overtime;
                row.premium += premium;
                row.bonus += bonus;
                row.contributions += contributions;
                row.recruit += recruit;
                row.severance += severance;
                row.gross += gross;
                row.withholding += withholding;

                teamHeads += n;
                teamCost += gross + contributions + recruit + severance;

                if (team.revenue) {
                    // Capacity counts a new arrival at the ramp for the month
                    // they land in: they are paid in full and only partly
                    // productive, and pretending otherwise is the single most
                    // flattering lie a planner can tell.
                    revHeads[m] += n;
                    revCapHeads[m] += n - arriving * (1 - a.ramp);
                    if (m === 0) { revHeadsBase += role.heads; }
                }
            }
            row.headsByTeam[team.key] = teamHeads;
            teamOut[ti].heads[m] = teamHeads;
            teamOut[ti].cost[m] = teamCost;
        });

        // Better hours are not free unless the company says they are: one
        // point of "productive time" costs whatever the assumptions record
        // says it costs, per person, per month. The default is zero, which is
        // exactly the Phase 1 behaviour.
        row.learning = row.heads * Math.max(0, s.productivity)
            * a.productivityCost;
        row.people = row.gross + row.contributions + row.recruit
            + row.severance + row.learning;
        row.takehome = row.gross - row.withholding;
        rows.push(row);
    }

    // ------------------------------------------------ what the year earns
    //
    // THE CALIBRATION, in one sentence: the company AS IT STANDS TODAY, on its
    // assumed shifts, serves the typed revenue target exactly. Everything else
    // is measured from there.
    //
    // So `baseHours` — today's revenue-earning people at today's ordinary
    // hours — is worth `today` (the target, spread along the seasonal curve),
    // which fixes the money one delivered hour earns. Capacity is then simply
    // this month's available hours at that rate, and demand is the same hours
    // moved by growth and stress. Phase 1 did the identical arithmetic without
    // ever naming an hour; Phase 2 needs the hours themselves, because the
    // shift split happens inside them: capacity is spread across day, evening
    // and night by where the PEOPLE are, demand by where the WORK is, and each
    // shift can only serve the smaller of the two. Mismatch the two and hours
    // go unserved while other hours stand idle — which is the whole point of
    // the Work & shifts tab.
    const hoursPerPersonBase = (a.workDays * 8) * (1 - DEFAULT_ABSENCE / 100);
    const baseHours = revHeadsBase > 0
        ? revHeadsBase * hoursPerPersonBase : hoursPerPersonBase;
    const target = s.target;
    for (let m = 0; m < 12; m++) {
        const row = rows[m];
        const otHours = (m + 1) >= s.otFrom ? s.ot : 0;
        const hoursNow = (a.workDays * 8 + otHours)
            * (1 - s.absence / 100) * (1 + s.productivity / 100);
        const capHeads = revHeadsBase > 0 ? revCapHeads[m] : 1;
        const available = capHeads * hoursNow;
        const today = target / 12 * SEASON[m];
        const rate = baseHours > 0 ? today / baseHours : 0;
        const demandHours = baseHours
            * (1 + s.growth / 100 * (m + 1) / 12)
            * (1 + s.stress / 100);
        const heads = revHeadsBase > 0 ? revHeads[m] : 0;

        row.hoursAvailable = available;
        row.hoursDemand = target > 0 ? demandHours : 0;
        row.hoursServed = 0;
        row.shifts = SHIFTS.map((key, i) => {
            const shiftAvailable = available * shiftPeople[i];
            const shiftDemand = target > 0
                ? demandHours * a.demandShares[i] : null;
            const served = target > 0
                ? Math.min(shiftAvailable, shiftDemand) : null;
            if (target > 0) { row.hoursServed += served; }
            return {
                key, heads: heads * shiftPeople[i],
                share: shiftPeople[i],
                available: shiftAvailable,
                demand: shiftDemand,
                served,
                uplift: shiftUplift[i],
            };
        });

        if (target > 0) {
            row.demand = demandHours * rate;
            row.capacity = available * rate;
            row.revenue = row.hoursServed * rate;
            row.coverage = row.demand > 0 ? row.revenue / row.demand : 1;
        } else {
            row.demand = 0;
            row.capacity = 0;
            row.revenue = 0;
            row.coverage = 1;
        }
        row.other = a.otherFixed + row.revenue * a.otherPct;
        row.profit = row.revenue - row.people - row.other;
        row.margin = row.revenue > 0 ? row.profit / row.revenue : 0;
    }

    const sum = (key) => rows.reduce((total, r) => total + r[key], 0);
    const year = {};
    for (const key of ["heads", "base", "allowance", "salary", "overtime",
                       "premium", "bonus", "contributions", "recruit",
                       "severance", "learning", "people", "gross",
                       "withholding", "takehome", "demand", "capacity",
                       "revenue", "other", "profit",
                       "hoursAvailable", "hoursDemand", "hoursServed"]) {
        year[key] = sum(key);
    }
    year.shifts = SHIFTS.map((key, i) => ({
        key,
        heads: rows[11] ? rows[11].shifts[i].heads : 0,
        share: shiftPeople[i],
        uplift: shiftUplift[i],
        demandShare: a.demandShares[i],
        available: rows.reduce((t, r) => t + r.shifts[i].available, 0),
        demand: s.target > 0
            ? rows.reduce((t, r) => t + r.shifts[i].demand, 0) : null,
        served: s.target > 0
            ? rows.reduce((t, r) => t + r.shifts[i].served, 0) : null,
    }));
    year.headcount = rows[11] ? rows[11].heads : 0;
    year.headsAvg = year.heads / 12;
    year.coverage = year.demand > 0 ? year.revenue / year.demand : 1;
    year.unserved = Math.max(0, year.demand - year.revenue);
    year.margin = year.revenue > 0 ? year.profit / year.revenue : 0;
    year.costPerHead = year.headsAvg > 0 ? year.people / year.headsAvg : 0;
    year.peopleShare = year.revenue > 0 ? year.people / year.revenue : 0;
    year.peakMonth = rows.reduce(
        (best, r) => (r.people > rows[best].people ? r.index : best), 0);
    year.worstMonth = rows.reduce(
        (worst, r) => (r.profit < rows[worst].profit ? r.index : worst), 0);
    year.hires = Math.round(totals.hires);
    year.cuts = Math.round(totals.cuts);
    year.leavers = Math.round(totals.leavers);

    teamOut.forEach((t) => {
        t.year = t.cost.reduce((total, v) => total + v, 0);
    });

    return { rows, year, teams: teamOut, state: s };
}

// =====================================================================
//  GROUP Phase 4 — several companies, several currencies, one board
// =====================================================================

/** Every money figure in a computed month. Hours and heads are not money. */
export const MONEY_KEYS = [
    "base", "allowance", "salary", "overtime", "premium", "bonus",
    "contributions", "recruit", "severance", "learning", "people", "gross",
    "withholding", "takehome", "demand", "capacity", "revenue", "other",
    "profit",
];

/** Everything that is a COUNT of something and simply adds up. */
const ADD_KEYS = ["heads", "hoursAvailable", "hoursDemand", "hoursServed"];

/**
 * The rate for one currency, in one month, into the board's money.
 *
 * The table comes from the server and every cell carries `known`. There is no
 * fallback and there never will be: a missing rate answers `known: false` and
 * the caller shows a sentence, exactly as `pb.fx` does on the server (group
 * ledger rule 7).
 */
export function rateFor(rates, code, monthIndex) {
    const target = (rates && rates.target && rates.target.code) || "";
    if (!code || code === target) {
        return { rate: 1, known: true, date: "" };
    }
    const row = ((rates && rates.rows) || {})[code];
    const cell = row && row[monthIndex];
    if (!cell) { return { rate: 0, known: false, date: "" }; }
    return { rate: cell.known ? cell.rate : 0, known: !!cell.known,
             date: cell.rate_date || "" };
}

/**
 * How a group's revenue target is shared out between its companies.
 *
 * The target is a sentence about the WHOLE group, typed in the board's money.
 * Somebody has to decide what share of it each entity is expected to earn, and
 * the only thing the room can see without being told is how much of the
 * group's workforce sits in each one. So that is the share, it is said on
 * screen in those words, and a company can always be planned on its own with
 * its own target if the split is wrong.
 */
export function targetShares(blocks) {
    const weights = blocks.map((block) => {
        const teams = block.teams || [];
        return teams.reduce(
            (sum, t) => sum + (t.heads || 0) * (t.pay_month_avg || 0), 0);
    });
    const total = weights.reduce((sum, v) => sum + v, 0);
    if (total > 0) { return weights.map((v) => v / total); }
    const heads = blocks.map((block) => (block.teams || [])
        .reduce((sum, t) => sum + (t.heads || 0), 0));
    const people = heads.reduce((sum, v) => sum + v, 0);
    if (people > 0) { return heads.map((v) => v / people); }
    return blocks.map(() => 1 / Math.max(1, blocks.length));
}

/**
 * Twelve months of a whole group, one company at a time.
 *
 * Each company is computed with ITS OWN rules — Singapore's contribution
 * ceiling on the Singapore entity, Vietnam's on the Vietnamese one — in ITS
 * OWN money. Only then is anything converted, and only for reading. A company
 * whose money has no rate this month is left OUT of the total and named, which
 * is the only honest thing to do with a number nobody can stand behind.
 *
 * A scope with ONE company returns exactly what `compute()` returns, wrapped —
 * same arithmetic, same keys, same order. That identity is the whole reason
 * this phase could touch the engine at all.
 */
export function computeBlocks(baseline, state, rates) {
    const blocks = (baseline && baseline.blocks) || [];
    if (blocks.length <= 1) {
        const only = blocks[0]
            || { teams: (baseline && baseline.teams) || [], rules: {},
                 currency: {} };
        const plan = compute({ teams: only.teams }, only.rules, state);
        return {
            single: true, converted: false, unknown: [],
            blocks: [{ ...only, plan, share: 1, target: state && state.target }],
            group: plan,
        };
    }
    const shares = targetShares(blocks);
    const target = Math.max(0, num(state && state.target, 0));
    const out = [];
    const unknown = [];
    blocks.forEach((block, i) => {
        const code = (block.currency || {}).code || "";
        // The share is converted INTO the company's own money, because that is
        // the money its people are paid in and its rules are written in.
        const january = rateFor(rates, code, 0);
        const local = january.known && january.rate
            ? (target * shares[i]) / january.rate : 0;
        const plan = compute({ teams: block.teams }, block.rules,
                             { ...state, target: local });
        const misses = [];
        for (let m = 0; m < 12; m++) {
            if (!rateFor(rates, code, m).known) { misses.push(m); }
        }
        if (misses.length) {
            unknown.push({ code, company: block.company, months: misses });
        }
        out.push({ ...block, plan, share: shares[i], target: local,
                   code, known: !misses.length });
    });

    const rows = [];
    for (let m = 0; m < 12; m++) {
        const row = { index: m, name: MONTH_KEYS[m], headsByTeam: {},
                      shifts: [], coverage: 1, margin: 0 };
        for (const key of MONEY_KEYS) { row[key] = 0; }
        for (const key of ADD_KEYS) { row[key] = 0; }
        for (const block of out) {
            const rate = rateFor(rates, block.code, m);
            const source = block.plan.rows[m];
            for (const key of ADD_KEYS) { row[key] += source[key] || 0; }
            Object.assign(row.headsByTeam, source.headsByTeam || {});
            if (!rate.known) { continue; }
            for (const key of MONEY_KEYS) {
                row[key] += (source[key] || 0) * rate.rate;
            }
        }
        row.shifts = SHIFTS.map((key, i) => {
            const add = (name) => out.reduce(
                (sum, b) => sum + (b.plan.rows[m].shifts[i][name] || 0), 0);
            const first = out[0].plan.rows[m].shifts[i];
            return {
                key, heads: add("heads"), share: first.share,
                uplift: first.uplift, available: add("available"),
                demand: target > 0 ? add("demand") : null,
                served: target > 0 ? add("served") : null,
            };
        });
        row.coverage = row.demand > 0 ? row.revenue / row.demand : 1;
        row.margin = row.revenue > 0 ? row.profit / row.revenue : 0;
        rows.push(row);
    }
    const year = {};
    for (const key of [...MONEY_KEYS, ...ADD_KEYS]) {
        year[key] = rows.reduce((sum, r) => sum + r[key], 0);
    }
    year.headcount = rows[11].heads;
    year.headsAvg = year.heads / 12;
    year.coverage = year.demand > 0 ? year.revenue / year.demand : 1;
    year.unserved = Math.max(0, year.demand - year.revenue);
    year.margin = year.revenue > 0 ? year.profit / year.revenue : 0;
    year.costPerHead = year.headsAvg > 0 ? year.people / year.headsAvg : 0;
    year.peopleShare = year.revenue > 0 ? year.people / year.revenue : 0;
    year.peakMonth = rows.reduce(
        (best, r) => (r.people > rows[best].people ? r.index : best), 0);
    year.worstMonth = rows.reduce(
        (worst, r) => (r.profit < rows[worst].profit ? r.index : worst), 0);
    year.hires = out.reduce((sum, b) => sum + b.plan.year.hires, 0);
    year.cuts = out.reduce((sum, b) => sum + b.plan.year.cuts, 0);
    year.leavers = out.reduce((sum, b) => sum + b.plan.year.leavers, 0);
    // Shifts are HOURS and heads, so they simply add up across companies —
    // there is nothing to convert and nothing that can be unknown.
    const shiftSum = (i, key) => out.reduce(
        (sum, b) => sum + (b.plan.year.shifts[i][key] || 0), 0);
    year.shifts = SHIFTS.map((key, i) => ({
        key,
        heads: shiftSum(i, "heads"),
        share: out[0] ? out[0].plan.year.shifts[i].share : 0,
        uplift: out[0] ? out[0].plan.year.shifts[i].uplift : 0,
        demandShare: out[0] ? out[0].plan.year.shifts[i].demandShare : 0,
        available: shiftSum(i, "available"),
        demand: target > 0 ? shiftSum(i, "demand") : null,
        served: target > 0 ? shiftSum(i, "served") : null,
    }));

    const teams = [];
    for (const block of out) {
        const rate0 = rateFor(rates, block.code, 0);
        for (const team of block.plan.teams) {
            teams.push({
                ...team,
                cost: team.cost.map((v, m) => {
                    const rate = rateFor(rates, block.code, m);
                    return rate.known ? v * rate.rate : 0;
                }),
                year: rate0.known ? team.year * rate0.rate : 0,
                company: block.company,
                currency: block.code,
            });
        }
    }
    return {
        single: false,
        converted: true,
        unknown,
        blocks: out,
        group: { rows, year, teams, state: out[0].plan.state },
    };
}

/** The month keys the engine has always used, kept as one list. */
const MONTH_KEYS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
                    "Sep", "Oct", "Nov", "Dec"];

/**
 * What the closed pay runs actually cost, in the board's money, by month.
 *
 * A month with no closed run answers `null` rather than zero, because zero is
 * a number and "we have not run it yet" is not. The line on the stage breaks
 * where the answer breaks.
 */
export function actualSeries(actuals, rates, cumulative = true) {
    const out = new Array(12).fill(null);
    const months = (actuals && actuals.months) || [];
    const byMonth = {};
    for (const row of months) { byMonth[row.month] = row; }
    let running = 0;
    for (let m = 0; m < 12; m++) {
        const row = byMonth[m + 1];
        if (!row) { out[m] = null; continue; }
        let total = 0;
        let known = true;
        for (const key of Object.keys(row.by_company || {})) {
            const entry = row.by_company[key];
            const rate = rateFor(rates, entry.currency, m);
            if (!rate.known) { known = false; continue; }
            total += (entry.cost || 0) * rate.rate;
        }
        if (!known && total === 0) { out[m] = null; continue; }
        running += total;
        out[m] = cumulative ? running : total;
    }
    return out;
}

/** How many people the closed runs actually paid, by month. */
export function actualPeople(actuals) {
    const out = new Array(12).fill(null);
    for (const row of ((actuals && actuals.months) || [])) {
        out[row.month - 1] = row.people || 0;
    }
    return out;
}

/**
 * The last month that reads like a FULL payroll, and the last with anything.
 *
 * This distinction is the whole reason the verdict is trustworthy. A demo
 * database — and a real one in the first week of a month — carries a month
 * where three people were paid a correction. Naming that as "the month" turns
 * a rounding into a headline: "November came in ₫108 billion under plan",
 * which is arithmetically perfect and completely useless. A month counts as
 * full when it paid at least half the people the plan expected.
 */
export function closedMonths(plan, actuals, rates) {
    const monthly = actualSeries(actuals, rates, false);
    const people = actualPeople(actuals);
    let full = -1;
    let any = -1;
    for (let m = 0; m < 12; m++) {
        if (monthly[m] === null) { continue; }
        any = m;
        const heads = plan.rows[m] ? plan.rows[m].heads : 0;
        if (people[m] === null || !heads || people[m] >= heads * 0.5) {
            full = m;
        }
    }
    return { monthly, people, full, any };
}

/**
 * One sentence about the month that has both a plan and an answer.
 *
 * It names the LAST full month, says which way it went, and names the
 * biggest reason it could see — more people than planned, or more money per
 * person. Anything more precise would be a guess, and this sentence is read by
 * somebody who is about to repeat it in a meeting.
 */
export function actualVerdict(plan, actuals, rates, format) {
    const f = format;
    const months = (actuals && actuals.months) || [];
    if (!months.length) {
        return _t("No pay run has been closed for this year yet, so there is "
                  + "nothing to draw over the plan.");
    }
    const { monthly, people, full, any } = closedMonths(plan, actuals, rates);
    const last = full >= 0 ? full : any;
    if (last < 0) {
        return _t("The pay runs for this year cannot be added up in this "
                  + "money yet, because a rate is missing.");
    }
    const partial = full < 0
        ? _t(" Only %(n)s of the %(all)s people in this view have been paid in "
             + "a closed run so far, so this is part of the picture rather "
             + "than all of it.",
             { n: f.int(people[any] || 0),
               all: f.int(Math.round(plan.rows[any].heads)) })
        : "";
    const row = plan.rows[last];
    const gap = monthly[last] - row.people;
    const heads = people[last] === null ? null : people[last] - row.heads;
    const direction = gap <= 0 ? _t("under plan") : _t("over plan");
    let why = _t("pay per person was the difference");
    if (heads !== null && Math.abs(heads) >= 1
        && (Math.abs(heads) / Math.max(1, row.heads))
           > Math.abs(gap) / Math.max(1, row.people) * 0.5) {
        why = heads > 0
            ? _t("there were %s more people on the payroll than planned",
                 f.int(Math.abs(heads)))
            : _t("there were %s fewer people on the payroll than planned",
                 f.int(Math.abs(heads)));
    }
    return _t("%(month)s came in %(money)s %(direction)s; %(why)s.%(partial)s",
              { month: monthName(last), money: f.money(Math.abs(gap)),
                direction, why, partial });
}

// --------------------------------------------------------------------- goals
/**
 * The six things a plan can be asked to be. `value` reads a computed plan;
 * `format` needs the company's formatter, so it is passed in rather than
 * imported — the engine stays free of everything.
 */
export const GOAL_DEFS = {
    margin: {
        key: "margin", label: () => _t("Operating margin"),
        short: () => _t("Margin"),
        sense: "min", unit: "%", step: 0.5, min: -50, max: 80,
        value: (plan) => plan.year.margin * 100,
        format: (v, f) => f.pct(v),
    },
    profit: {
        key: "profit", label: () => _t("Operating profit for the year"),
        short: () => _t("Profit"),
        sense: "min", unit: "money", step: 1, min: -1e15, max: 1e15,
        value: (plan) => plan.year.profit,
        format: (v, f) => f.money(v),
    },
    cost: {
        key: "cost", label: () => _t("Workforce cost for the year"),
        short: () => _t("Cost"),
        sense: "max", unit: "money", step: 1, min: 0, max: 1e15,
        value: (plan) => plan.year.people,
        format: (v, f) => f.money(v),
    },
    coverage: {
        key: "coverage", label: () => _t("Demand served"),
        short: () => _t("Served"),
        sense: "min", unit: "%", step: 0.5, min: 0, max: 100,
        value: (plan) => plan.year.coverage * 100,
        format: (v, f) => f.pct(v),
    },
    heads: {
        key: "heads", label: () => _t("People in December"),
        short: () => _t("Team size"),
        sense: "max", unit: "people", step: 1, min: 0, max: 1e7,
        value: (plan) => plan.year.headcount,
        format: (v, f) => f.people
            ? String(f.people(v)).replace(/^\+/, "") : String(v),
    },
    overtime: {
        key: "overtime", label: () => _t("Overtime per person"),
        short: () => _t("Overtime"),
        sense: "max", unit: "h/mo", step: 1, min: 0, max: 60,
        value: (plan) => plan.state.ot,
        format: (v) => _t("%(n)s h a month", { n: Math.round(v) }),
    },
};

export const GOAL_ORDER = ["margin", "profit", "cost", "coverage", "heads",
                           "overtime"];

/** The goals a company starts with, read off its own baseline. */
export function defaultGoals(basePlan, hasTarget) {
    const year = basePlan.year;
    // Rounded AWAY from the baseline, never towards it: "at least this year's
    // profit" must be a goal today's company MEETS, or the room opens with a
    // red pill saying you are ₫0 short of yourself.
    return {
        margin: { on: !!hasTarget, target: 20 },
        profit: { on: !!hasTarget, target: Math.floor(year.profit) },
        cost: { on: true, target: Math.ceil(year.people * 1.1) },
        coverage: { on: !!hasTarget, target: 97 },
        heads: { on: false, target: Math.ceil(year.headcount * 1.1) },
        overtime: { on: false, target: 8 },
    };
}

export function normalizeGoals(input, basePlan, hasTarget) {
    const fallback = defaultGoals(basePlan, hasTarget);
    const given = input || {};
    const out = {};
    for (const key of GOAL_ORDER) {
        const def = GOAL_DEFS[key];
        const raw = given[key] || fallback[key];
        const value = num(raw && raw.target, fallback[key].target);
        out[key] = {
            on: typeof (raw && raw.on) === "boolean" ? raw.on : fallback[key].on,
            target: clamp(def.step === 1 ? Math.round(value) : value,
                          def.min, def.max),
        };
    }
    return out;
}

export function evaluateGoals(plan, goals, format) {
    const out = [];
    for (const key of GOAL_ORDER) {
        const g = goals[key];
        if (!g || !g.on) { continue; }
        const def = GOAL_DEFS[key];
        const actual = def.value(plan);
        const gap = def.sense === "min" ? (g.target - actual)
            : (actual - g.target);
        // A RELATIVE epsilon: at ₫300 billion a double has about 1e-5 of
        // resolution left, and an absolute 1e-8 makes a goal that is exactly
        // met read as missed by nothing at all.
        const epsilon = Math.max(1e-8, Math.abs(g.target) * 1e-9);
        out.push({
            key, def, short: def.short(), label: def.label(), sense: def.sense,
            actual, target: g.target, gap, met: gap <= epsilon,
            shortfall: Math.max(0, gap) / Math.max(Math.abs(g.target), 1),
            actualText: def.format(actual, format),
            targetText: def.format(g.target, format),
        });
    }
    return out;
}

export function gradeGoals(plan, goals, format) {
    const checks = evaluateGoals(plan, goals, format);
    return {
        checks,
        met: checks.every((c) => c.met),
        failed: checks.filter((c) => !c.met).length,
        score: checks.reduce((total, c) => total + c.shortfall, 0),
    };
}

/** The line the stage draws: cumulative for money, monthly for a percentage. */
export function series(plan, metric) {
    if (metric === "coverage") {
        return plan.rows.map((r) => r.coverage * 100);
    }
    const key = metric === "people" ? "people" : "profit";
    let running = 0;
    return plan.rows.map((r) => (running += r[key]));
}

// ------------------------------------------------------------------- extras
/** The same plan under softer and stronger demand. */
export function stressBand(baseline, assumptions, state, width = 10,
                           run = null) {
    const s = normalizeState(state, baseline, assumptions);
    const go = run || ((trial) => compute(baseline, assumptions, trial));
    return {
        lo: go({ ...s, stress: s.stress - width }),
        hi: go({ ...s, stress: s.stress + width }),
    };
}

/**
 * Why profit is different. Every step is an accounting difference, and they
 * sum EXACTLY to the difference in profit — `check` says so out loud.
 */
export function bridge(plan, ref) {
    const p = plan.year;
    const r = ref.year;
    const steps = [
        [_t("Revenue delivered"), p.revenue - r.revenue,
         _t("The work the team could actually serve, at the same price an "
            + "hour")],
        [_t("Salaries and allowances"), -(p.salary - r.salary),
         _t("How many people are on the payroll, and what they are paid")],
        [_t("Overtime and premiums"), -((p.overtime + p.premium)
                                        - (r.overtime + r.premium)),
         _t("Hours beyond the normal month, and the uplift for evenings and "
            + "nights")],
        [_t("Bonus"), -(p.bonus - r.bonus),
         _t("The yearly bonus, paid in its month")],
        [_t("Contributions"), -(p.contributions - r.contributions),
         _t("Insurance the business pays on top of pay, up to the cap")],
        [_t("Recruiting and severance"),
         -((p.recruit + p.severance + p.learning)
           - (r.recruit + r.severance + r.learning)),
         _t("One-off costs of people joining and leaving, and of better "
            + "hours")],
        [_t("Other costs"), -(p.other - r.other),
         _t("Rent, materials and everything else that is not people")],
    ].map(([label, value, reason]) => ({ label, value, reason, note: reason }));
    const total = steps.reduce((sum, x) => sum + x.value, 0);
    const difference = p.profit - r.profit;
    // A RELATIVE tolerance, because the absolute one is a lie at this size: a
    // double carrying ₫6.5 billion has about 1e-6 of resolution left, so
    // "sums exactly" has to mean "to the last bit the arithmetic has", not to
    // a fixed number of decimal places.
    return {
        start: r.profit, end: p.profit, steps, total,
        check: Math.abs(total - difference)
            <= Math.max(1e-6, Math.abs(difference) * 1e-9),
    };
}

/** Which levers differ from the comparison, the ones that matter first. */
export function changes(state, refState, baseline) {
    const list = [];
    const weight = {
        moves: 6, raise: 5, target: 5, growth: 5, ot: 4, productivity: 4,
        absence: 3, bonusMonths: 3, attritionOn: 3, backfill: 2, stress: 3,
        raiseMonth: 1, otFrom: 1, start: 1, evening: 2, night: 2,
    };
    const teamName = Object.fromEntries(
        ((baseline && baseline.teams) || []).map((t) => [t.key, t.name]));

    const movesOf = (s) => {
        const out = {};
        for (const m of (s.moves || [])) {
            const key = `${m.team}|${m.role || ""}|${m.month}`;
            out[key] = (out[key] || 0) + m.n;
        }
        return out;
    };
    const a = movesOf(state);
    const b = movesOf(refState);
    for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
        const delta = (a[key] || 0) - (b[key] || 0);
        if (!delta) { continue; }
        const [team, role, month] = key.split("|");
        list.push({
            key: "moves", team, role, month: Number(month), delta,
            teamName: teamName[team] || team,
        });
    }
    for (const key of ["raise", "target", "growth", "ot", "productivity",
                       "absence", "bonusMonths", "stress", "raiseMonth",
                       "otFrom", "start", "evening", "night"]) {
        const delta = num(state[key]) - num(refState[key]);
        if (Math.abs(delta) > 1e-9) {
            list.push({ key, delta, from: refState[key], to: state[key] });
        }
    }
    for (const key of ["attritionOn", "backfill"]) {
        if (!!state[key] !== !!refState[key]) {
            list.push({ key, delta: 1, from: refState[key], to: state[key] });
        }
    }
    return list.sort((x, y) => (weight[y.key] || 1) - (weight[x.key] || 1));
}

/** The twelve months, in the reader's language, asked for one at a time. */
export function monthName(index) {
    const i = ((Math.round(num(index, 0)) % 12) + 12) % 12;
    return [_t("January"), _t("February"), _t("March"), _t("April"),
            _t("May"), _t("June"), _t("July"), _t("August"),
            _t("September"), _t("October"), _t("November"),
            _t("December")][i];
}

/** One change, said the way a person would say it. */
export function describeChange(change, format) {
    const f = format;
    switch (change.key) {
        case "moves": {
            // Said as a DIFFERENCE and never as an act. When the comparison is
            // another plan, "letting go of 120 people" would be a sentence
            // about redundancies that nobody is proposing — the plan on screen
            // simply has 120 fewer people in it than the one it is measured
            // against. "Fewer" is true either way round.
            const n = Math.abs(Math.round(change.delta));
            const month = monthName((change.month || 1) - 1);
            const team = change.teamName;
            if (change.delta > 0) {
                return n === 1
                    ? _t("%(n)s more person in %(team)s from %(month)s",
                         { n, team, month })
                    : _t("%(n)s more people in %(team)s from %(month)s",
                         { n, team, month });
            }
            return n === 1
                ? _t("%(n)s fewer person in %(team)s from %(month)s",
                     { n, team, month })
                : _t("%(n)s fewer people in %(team)s from %(month)s",
                     { n, team, month });
        }
        case "raise":
            return change.to > 0
                ? _t("a %(pct)s% salary increase",
                     { pct: Math.abs(change.to).toFixed(1) })
                : _t("a cut of %(pct)s% in salaries",
                     { pct: Math.abs(change.to).toFixed(1) });
        case "target":
            return _t("a revenue target of %s", f.money(change.to));
        case "growth":
            return change.to >= 0
                ? _t("%s%% more work by December", Math.abs(change.to))
                : _t("%s%% less work by December", Math.abs(change.to));
        case "ot":
            return _t("%s hours of overtime per person",
                      Math.round(change.to));
        case "productivity":
            return change.to >= 0
                ? _t("%s%% more productive time", Math.abs(change.to))
                : _t("%s%% less productive time", Math.abs(change.to));
        case "absence":
            return _t("%s%% unavailable time", Math.round(change.to));
        case "bonusMonths":
            return change.to === 0 ? _t("no yearly bonus")
                : _t("%s months of bonus", change.to);
        case "stress":
            return change.to >= 0
                ? _t("demand up %s%%", Math.abs(change.to))
                : _t("demand down %s%%", Math.abs(change.to));
        case "raiseMonth":
            return _t("the increase starting in %s", monthName(change.to - 1));
        case "otFrom":
            return _t("overtime from %s", monthName(change.to - 1));
        case "start":
            return _t("hires arriving in %s", monthName(change.to - 1));
        case "attritionOn":
            return change.to ? _t("people leaving through the year")
                : _t("nobody leaving");
        case "evening":
            return _t("%s%% of the team on evenings", Math.round(change.to));
        case "night":
            return _t("%s%% of the team on nights", Math.round(change.to));
        case "backfill":
            return change.to ? _t("replacing everyone who leaves")
                : _t("not replacing leavers");
        default:
            return "";
    }
}

/** The caption: what you changed, what happened, and why. */
export function story(plan, ref, state, refState, refName, baseline, format) {
    const f = format;
    const list = changes(state, refState, baseline);
    if (!list.length) {
        return {
            title: _t("This is %s. Nothing has changed yet.",
                      String(refName).toLowerCase()),
            copy: _t("Move one lever on the left and watch people, the work "
                     + "you can deliver and profit respond together."),
        };
    }
    const lead = list.slice(0, 2)
        .map((c) => describeChange(c, f)).filter(Boolean).join(_t(" and "));
    const dProfit = plan.year.profit - ref.year.profit;
    const smaller = list.length - 2;
    const rest = smaller > 0
        ? (smaller === 1 ? _t(" with 1 smaller change")
            : _t(" with %s smaller changes", smaller))
        : "";
    const opening = `${lead.charAt(0).toUpperCase()}${lead.slice(1)}`;
    const title = dProfit >= 0
        ? _t("%(lead)s adds %(money)s of profit for the year%(rest)s.",
             { lead: opening, money: f.money(Math.abs(dProfit)), rest })
        : _t("%(lead)s costs %(money)s of profit for the year%(rest)s.",
             { lead: opening, money: f.money(Math.abs(dProfit)), rest });

    const why = [];
    const dCost = plan.year.people - ref.year.people;
    if (Math.abs(dCost) >= 1) {
        why.push(_t("Workforce cost is %(delta)s for the year at %(total)s.",
                    { delta: f.signedMoney(dCost),
                      total: f.money(plan.year.people) }));
    } else {
        why.push(_t("Workforce cost is unchanged."));
    }
    if (state.target > 0) {
        const dCov = (plan.year.coverage - ref.year.coverage) * 100;
        why.push(Math.abs(dCov) >= 0.05
            ? _t("Demand served changes by %(delta)s, to %(now)s.",
                 { delta: f.pp(dCov),
                   now: f.pct(plan.year.coverage * 100) })
            : _t("The share of demand you serve is unchanged."));
        if (plan.year.unserved > 0) {
            why.push(_t("%s of demand still goes unserved.",
                        f.money(plan.year.unserved)));
        }
    } else {
        why.push(_t("Type a revenue target and profit appears here too."));
    }
    const dHeads = plan.year.headcount - ref.year.headcount;
    if (Math.abs(dHeads) >= 1) {
        why.push(_t("%s on payroll by December.", f.people(dHeads)));
    }
    return { title, copy: why.join(" ") };
}

/** What could bite. Shown under the caption, worst first. */
export function warnings(plan, ref, state, format) {
    const f = format;
    const out = [];
    const year = plan.year;
    if (state.target > 0 && year.margin < 0.10) {
        out.push({
            level: "bad",
            text: _t("Margin falls to %s. Below 10%% there is no room for a "
                     + "slow quarter.", f.pct(year.margin * 100)),
        });
    } else if (state.target > 0 && year.margin < 0.15) {
        out.push({
            level: "watch",
            text: _t("Margin at %s is thin.", f.pct(year.margin * 100)),
        });
    }
    const worst = plan.rows[year.worstMonth];
    if (worst && worst.profit < 0 && state.target > 0) {
        const bonusMonth = worst.bonus > 0;
        const hiring = worst.recruit + worst.severance > worst.base * 0.02;
        const why = bonusMonth && hiring
            ? _t("the bonus and the new arrivals land in the same month — "
                 + "move the hires later and it recovers")
            : bonusMonth
                ? _t("the yearly bonus is paid this month; it is normal, but "
                     + "the cash has to be there")
                : hiring
                    ? _t("joining and leaving costs land together this month")
                    : _t("costs outrun revenue this month");
        out.push({
            level: "bad",
            text: _t("%(month)s loses money (%(money)s) — %(why)s.",
                     { month: monthName(worst.index),
                       money: f.money(worst.profit), why }),
        });
    }
    if (year.hires > 150) {
        out.push({
            level: "watch",
            text: _t("%(n)s new people is a lot to recruit at once — roughly "
                     + "%(months)s recruiter-months of work. Spreading them "
                     + "over two or three months is kinder to everyone.",
                     { n: f.int(year.hires),
                       months: Math.ceil(year.hires / 25) }),
        });
    }
    if (state.raise >= 12) {
        out.push({
            level: "watch",
            text: _t("A %s%% increase is well above a normal year. Good for "
                     + "keeping people; check the yearly bill.", state.raise),
        });
    }
    if (state.ot >= 40) {
        out.push({
            level: "watch",
            text: _t("%s hours of overtime a person brushes the legal "
                     + "monthly cap for factory roles. Hiring may cost less.",
                     Math.round(state.ot)),
        });
    }
    if (state.target > 0 && year.coverage < 0.95) {
        out.push({
            level: "watch",
            text: _t("%(share)s of demand goes unserved — %(money)s left on "
                     + "the table.",
                     { share: f.pct((1 - year.coverage) * 100),
                       money: f.money(year.unserved) }),
        });
    }
    if (state.target > 0 && year.capacity > year.demand * 1.15) {
        out.push({
            level: "watch",
            text: _t("The team could deliver more than the work coming in. "
                     + "Fewer hires, or later ones, would keep the margin."),
        });
    }
    return out;
}

// =====================================================================
//  Phase 2 — the detail workspace, the goal finder and the brief
// =====================================================================

/**
 * The evening and night shares that match where the work actually is.
 *
 * "Match shifts to demand": put the same proportion of people on each shift
 * as there is work arriving on it. Rounded to whole percentages, and clamped
 * to the same ranges the levers use, so pressing the button can never produce
 * a state the sliders could not.
 */
export function balanceShifts(baseline, assumptions, state) {
    const a = readAssumptions(assumptions);
    const s = normalizeState(state, baseline, assumptions);
    let evening = clamp(Math.round(a.demandShares[1] * 100), 0, 50);
    let night = clamp(Math.round(a.demandShares[2] * 100), 0, 40);
    if (evening + night > 80) { night = Math.max(0, 80 - evening); }
    return { ...s, evening, night };
}

/**
 * Where a year of pay goes.
 *
 * Two facts this has to keep straight, because getting them wrong is the
 * single most common way a workforce number lies:
 *   * what an employee TAKES HOME is their gross pay less what is withheld —
 *     deductions live INSIDE gross and are not an extra cost to anybody;
 *   * what the BUSINESS pays is gross plus the contributions it pays on top,
 *     plus the one-off costs of people joining, leaving and getting better.
 */
export function payStory(plan) {
    const y = plan.year;
    return {
        gross: y.gross,
        base: y.base,
        allowance: y.allowance,
        overtime: y.overtime,
        premiums: y.premium,
        bonus: y.bonus,
        withholding: y.withholding,
        takehome: y.takehome,
        contributions: y.contributions,
        recruit: y.recruit,
        severance: y.severance,
        learning: y.learning,
        total: y.people,
    };
}

/** Who is on the team in December, next to the comparison. */
export function teamsInDecember(plan, ref) {
    const refByKey = Object.fromEntries(
        (ref.teams || []).map((t) => [t.key, t]));
    return (plan.teams || []).map((t) => {
        const other = refByKey[t.key];
        return {
            key: t.key, name: t.name, revenue: t.revenue,
            heads: t.heads[11],
            refHeads: other ? other.heads[11] : 0,
            payMonth: t.payDec,
            cost: t.year,
        };
    }).filter((t) => t.heads > 0.005 || t.refHeads > 0.005);
}

/** What five more people in one team would do from here. */
export function marginal(baseline, assumptions, state, plan, teamKey, n = 5,
                         run = null) {
    const team = ((baseline && baseline.teams) || [])
        .find((t) => t.key === teamKey);
    if (!team) { return null; }
    const go = run || ((trial) => compute(baseline, assumptions, trial));
    const next = go({
        ...state,
        moves: [...(state.moves || []),
                { team: teamKey, role: null, n, month: state.start }],
    });
    return {
        team, n, plan: next,
        dProfit: next.year.profit - plan.year.profit,
        dCost: next.year.people - plan.year.people,
        dCoverage: (next.year.coverage - plan.year.coverage) * 100,
    };
}

/**
 * How big "one small experiment" has to be to still be a real question.
 *
 * Five more people is a good nudge in a forty-person team and a rounding
 * error in a four-thousand-person one: at that size five people move profit
 * by a tenth of a percent, the card reads "would add ₫0" and the whole idea
 * looks broken. So the experiment is ONE PER CENT of the team, never fewer
 * than five, and rounded to a number a person would actually say out loud —
 * multiples of five once it is past twenty.
 */
export function experimentSize(heads) {
    const raw = Math.round(Math.max(0, num(heads, 0)) * 0.01);
    const n = Math.max(5, raw);
    return n <= 20 ? n : Math.round(n / 5) * 5;
}

/**
 * How many more people one team can take before a goal breaks.
 *
 * Everything else is held exactly where it is: this answers "how much room
 * do we have HERE", not "what is the best plan". The scan is BOUNDED — half
 * the team again, or two hundred people, whichever is smaller — and stepped
 * so that a four-thousand-person team is still answered in a fraction of a
 * second. The step is returned so the tab can say what it walked.
 */
export function headroom(baseline, assumptions, state, goals, teamKey,
                         format, roleKey = null, run = null) {
    const team = ((baseline && baseline.teams) || [])
        .find((t) => t.key === teamKey);
    const enabled = GOAL_ORDER.some((k) => goals && goals[k] && goals[k].on);
    if (!team) { return { points: [], intervals: [], enabled, step: 1,
                          max: 0, team: null }; }
    const role = roleKey
        ? team.roles.find((r) => r.key === roleKey) : null;
    const pool = role ? role.heads : team.heads;
    const max = Math.max(1, Math.min(200, Math.round(pool * 0.5)));
    // At most sixty points on the chart: more than that is a smear, and every
    // extra point is another twelve months of arithmetic.
    const step = [1, 2, 5, 10, 20].find((n) => max / n <= 60) || 25;
    const go = run || ((trial) => compute(baseline, assumptions, trial));
    const points = [];
    for (let add = 0; add <= max; add += step) {
        const trial = go({
            ...state,
            moves: add
                ? [...(state.moves || []),
                   { team: teamKey, role: roleKey || null, n: add,
                     month: state.start }]
                : (state.moves || []),
        });
        const rating = gradeGoals(trial, goals, format);
        points.push({
            add, profit: trial.year.profit,
            cost: trial.year.people,
            coverage: trial.year.coverage,
            met: enabled && rating.met, failed: rating.failed,
        });
    }
    const intervals = [];
    let previous = null;
    for (const point of points) {
        if (!point.met) { previous = null; continue; }
        const last = intervals[intervals.length - 1];
        if (last && previous !== null && previous === point.add - step) {
            last[1] = point.add;
        } else {
            intervals.push([point.add, point.add]);
        }
        previous = point.add;
    }
    return { points, intervals, enabled, step, max, team,
             role: role || null, revenue: !!team.revenue };
}

/** The three lanes, in the order the room shows them. */
export const LANES = ["hire", "develop", "balanced"];

/**
 * Three ways to reach the same goals.
 *
 * A BOUNDED grid, on purpose: people in the biggest revenue-earning team,
 * overtime, and assumed productive time. Everything else the person set —
 * their demand, their pay increase, their shifts, their hiring month — is
 * left exactly alone, because a search that quietly rewrites the decisions
 * somebody has already made is not offering them a path, it is overruling
 * them.
 *
 * Ranked by: fewest goals missed, then by how badly (as a share of each
 * goal, so a percentage and a billion can be compared), then by the cheaper
 * plan, then by the one that changes least.
 */
export function candidates(baseline, assumptions, state, goals, format,
                           run = null) {
    const teams = ((baseline && baseline.teams) || []);
    const earner = teams.filter((t) => t.revenue && t.heads > 0)
        .sort((a, b) => b.heads - a.heads)[0] || teams[0];
    const enabled = GOAL_ORDER.some((k) => goals && goals[k] && goals[k].on);
    if (!earner || !enabled) { return { count: 0, lanes: [], enabled }; }
    const s = normalizeState(state, baseline, assumptions);
    const lanes = { hire: null, develop: null, balanced: null };
    let count = 0;
    const rank = (a, b) => {
        if (!b) { return true; }
        if (a.failed !== b.failed) { return a.failed < b.failed; }
        if (Math.abs(a.score - b.score) > 1e-9) { return a.score < b.score; }
        if (Math.abs(a.result.year.people - b.result.year.people) > 0.01) {
            return a.result.year.people < b.result.year.people;
        }
        return a.change < b.change;
    };
    const uniq = (values) => [...new Set(values)].sort((x, y) => x - y);
    const adds = uniq([0, 0.02, 0.05, 0.10, 0.15]
        .map((p) => Math.round(earner.heads * p)));
    const overtimes = uniq([0, 8, 16, Math.round(s.ot)]);
    const gains = uniq([0, 5, 10, Math.round(s.productivity)]);

    const go = run || ((trial) => compute(baseline, assumptions, trial));
    const visit = (trial) => {
        const result = go(trial);
        const rating = gradeGoals(result, goals, format);
        const add = (trial.moves || [])
            .filter((m) => m.team === earner.key)
            .reduce((total, m) => total + m.n, 0);
        const change = Math.abs(add) + Math.abs(trial.ot - s.ot)
            + Math.abs(trial.productivity - s.productivity);
        const item = { state: trial, result, plan: result, change, ...rating };
        count++;
        const buckets = ["balanced"];
        if (trial.productivity === s.productivity) { buckets.push("hire"); }
        if (!add) { buckets.push("develop"); }
        for (const lane of buckets) {
            if (rank(item, lanes[lane])) { lanes[lane] = item; }
        }
    };

    visit({ ...s });
    for (const add of adds) {
        for (const ot of overtimes) {
            for (const productivity of gains) {
                visit({
                    ...s, ot, productivity,
                    moves: add
                        ? [{ team: earner.key, role: null, n: add,
                             month: s.start }]
                        : [],
                });
            }
        }
    }
    return {
        count, enabled, team: earner,
        lanes: LANES.map((lane) => ({ lane, ...(lanes[lane] || {}) }))
            .filter((l) => !!l.result),
    };
}

/** The reality-check sentence: what happens if demand is not what we said. */
export function stressOutcome(baseline, assumptions, state, plan, format,
                              run = null) {
    const f = format;
    const s = normalizeState(state, baseline, assumptions);
    if (!(s.target > 0)) {
        return _t("Type a revenue target and the room can stress-test the "
                  + "plan.");
    }
    const band = stressBand(baseline, assumptions, s, 10, run);
    const low = Math.min(band.lo.year.profit, band.hi.year.profit);
    const high = Math.max(band.lo.year.profit, band.hi.year.profit);
    const label = s.stress < 0 ? _t("softer demand")
        : (s.stress > 0 ? _t("stronger demand") : _t("your own forecast"));
    const upside = band.hi.year.coverage < 0.95
        ? _t("Stronger demand would leave %s of it unserved: the limit "
             + "becomes your people, not the market.",
             f.pct((1 - band.hi.year.coverage) * 100))
        : _t("The team could absorb the upside without leaving work behind.");
    return _t("Under %(label)s this plan makes %(profit)s and serves "
              + "%(served)s of the work. If demand lands 10% either side of "
              + "that, profit runs from %(low)s to %(high)s. %(upside)s",
              { label, profit: f.money(plan.year.profit),
                served: f.pct(plan.year.coverage * 100),
                low: f.money(low), high: f.money(high), upside });
}

/** Every lever, said in words, for the brief's "everything that was set". */
export function inputLabels() {
    return [
        ["target", _t("Revenue target for the year"), "money"],
        ["growth", _t("More work by December"), "pct"],
        ["stress", _t("Demand reality check"), "pct"],
        ["raise", _t("Salary increase"), "pct"],
        ["raiseMonth", _t("The increase starts in"), "month"],
        ["ot", _t("Overtime per person"), "hours"],
        ["otFrom", _t("Overtime from"), "month"],
        ["evening", _t("People on the evening shift"), "pct"],
        ["night", _t("People on the night shift"), "pct"],
        ["productivity", _t("Productive time"), "pct"],
        ["absence", _t("Unavailable paid time"), "pct"],
        ["bonusMonths", _t("Yearly bonus"), "months"],
        ["start", _t("New people arrive in"), "month"],
        ["attritionOn", _t("Some people leave during the year"), "yesno"],
        ["backfill", _t("Replace everyone who leaves"), "yesno"],
    ];
}

const MONTH_OF = (v) => monthName(clamp(Math.round(num(v, 1)), 1, 12) - 1);

function sayInput(kind, value, format) {
    switch (kind) {
        case "money": return format.money(num(value, 0));
        case "pct": return format.pct(num(value, 0));
        case "hours": return _t("%s h a month", Math.round(num(value, 0)));
        case "months": {
            const n = num(value, 0);
            return n === 1 ? _t("1 month") : _t("%s months", n);
        }
        case "month": return MONTH_OF(value);
        case "yesno": return value ? _t("Yes") : _t("No");
        default: return String(value);
    }
}

/**
 * Everything the printable brief needs, already said in words.
 *
 * The SERVER lays this out and stamps the company, the reader and the date on
 * it; it never recomputes a number, because the twelve computed months only
 * exist here. Every value in this object is a finished string.
 */
export function briefModel(o) {
    const { plan, ref, baseline, assumptions, state, refState, goals,
            format, planName, comparisonName } = o;
    const f = format;
    const checks = evaluateGoals(plan, goals, f);
    const b = bridge(plan, ref);
    const s = normalizeState(state, baseline, assumptions);
    const r = normalizeState(refState || state, baseline, assumptions);
    const told = story(plan, ref, s, r, comparisonName, baseline, f);
    const hasTarget = s.target > 0;
    const money = (v) => f.money(v);

    const outcome = [
        [_t("Revenue delivered"), ref.year.revenue, plan.year.revenue, "money"],
        [_t("Workforce cost"), ref.year.people, plan.year.people, "money"],
        [_t("Other operating costs"), ref.year.other, plan.year.other, "money"],
        [_t("Operating profit"), ref.year.profit, plan.year.profit, "money"],
        [_t("Operating margin"), ref.year.margin * 100,
         plan.year.margin * 100, "pct"],
        [_t("Gross pay to employees"), ref.year.gross, plan.year.gross,
         "money"],
        [_t("Employee deductions"), ref.year.withholding,
         plan.year.withholding, "money"],
        [_t("What reaches employees"), ref.year.takehome, plan.year.takehome,
         "money"],
        [_t("Demand served"), ref.year.coverage * 100,
         plan.year.coverage * 100, "pct"],
        [_t("People in December"), ref.year.headcount, plan.year.headcount,
         "int"],
    ].map(([label, a, c, kind]) => ({
        label,
        ref: kind === "money" ? money(a)
            : (kind === "pct" ? (hasTarget ? f.pct(a) : "—") : f.int(a)),
        plan: kind === "money" ? money(c)
            : (kind === "pct" ? (hasTarget ? f.pct(c) : "—") : f.int(c)),
    }));

    return {
        plan_name: planName,
        // The browser TAB is part of the page a person keeps: a Vietnamese
        // brief saved to a laptop should not be filed under an English name.
        // The client supplies it because a QWeb <title> is not a term the
        // string extractor collects.
        doc_title: _t("Decision brief · %s", planName),
        comparison_name: comparisonName,
        currency_code: f.code || f.symbol,
        // The printable page is stamped with the reader's own language, so a
        // Vietnamese brief says `lang="vi-VN"` and a screen reader, a
        // spell-checker and a browser's own translate button all agree with
        // the words on it.
        lang: String(f.lang || "").replace("_", "-") || "en",
        headline_title: told.title,
        headline_copy: told.copy,
        goals: checks.map((c) => ({
            label: c.label,
            bound: c.sense === "min" ? _t("At least") : _t("At most"),
            target: c.targetText,
            actual: c.actualText,
            met: c.met,
            status: c.met ? _t("Met") : _t("Not met yet"),
        })),
        outcome,
        bridge: b.steps.map((x) => ({
            label: x.label, reason: x.reason,
            value: f.signedMoney(x.value), good: x.value >= 0,
        })),
        bridge_total: f.signedMoney(b.total),
        changes: changes(s, r, baseline)
            .map((c) => describeChange(c, f))
            .filter(Boolean)
            .map((line) => line.charAt(0).toUpperCase() + line.slice(1)),
        inputs: inputLabels().map(([key, label, kind]) => ({
            label,
            ref: sayInput(kind, r[key], f),
            plan: sayInput(kind, s[key], f),
        })),
        months: plan.rows.map((row) => ({
            name: monthName(row.index),
            people: f.int(row.heads),
            cost: money(row.people),
            served: hasTarget ? f.pct(row.coverage * 100) : "—",
            profit: hasTarget ? money(row.profit) : "—",
        })),
        assumptions: o.assumptionLines || [],
    };
}
