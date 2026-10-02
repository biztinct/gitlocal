"use client";
import { useEffect, useRef, useState, ReactNode } from "react";
import {
  stages,
  candidates as seedCandidates,
  roles as seedRoles,
  emails,
  jdSections,
} from "./content";
import holidayData from "./holidays.json";
import leavePolicies from "./leave-policies.json";
const countries = ["Singapore", "Vietnam", "Indonesia", "India"];
const badge = (t: string, c = "") => <span className={"badge " + c}>{t}</span>;
function Field({
  label,
  options,
  type = "text",
  value,
  onChange,
  required = false,
  hint,
}: {
  label: string;
  options?: string[];
  type?: string;
  value?: string;
  onChange?: (v: string) => void;
  required?: boolean;
  hint?: string;
}) {
  return (
    <label className={"field " + (type === "textarea" ? "full" : "")}>
      <span>
        {label}
        {required && " *"}
      </span>
      {options ? (
        <select
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          required={required}
        >
          {options.map((x) => (
            <option key={x} value={x.startsWith("Select an answer") ? "" : x}>
              {x}
            </option>
          ))}
        </select>
      ) : type === "textarea" ? (
        <textarea
          rows={4}
          defaultValue={value}
          onChange={(e) => onChange?.(e.target.value)}
          required={required}
        />
      ) : (
        <input
          type={type}
          defaultValue={value}
          onChange={(e) => onChange?.(e.target.value)}
          required={required}
        />
      )}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function Steps({
  labels,
  current = 0,
}: {
  labels: string[];
  current?: number;
}) {
  return (
    <div className="steps">
      {labels.map((s, i) => (
        <div
          key={s}
          className={i === current ? "current" : i < current ? "done" : ""}
        >
          <span>{i < current ? "✓" : i + 1}</span>
          <b>{s}</b>
        </div>
      ))}
    </div>
  );
}
function Modal({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="modalhead">
        <div>
          <div className="eyebrow">PAYOBOOK · DESIGN PREVIEW</div>
          <h2>{title}</h2>
        </div>
        <button aria-label="Close dialog" onClick={close}>
          ×
        </button>
      </div>
      <div className="modalbody">{children}</div>
    </dialog>
  );
}
export default function Page() {
  const [module, setModule] = useState("Hiring"),
    [tab, setTab] = useState("Overview"),
    [modal, setModal] = useState(""),
    [toast, setToast] = useState(""),
    [tenant, setTenant] = useState("Rize"),
    [brand, setBrand] = useState("Rize"),
    [query, setQuery] = useState(""),
    [country, setCountry] = useState("All countries"),
    [candidateList, setCandidateList] = useState(seedCandidates),
    [roleList, setRoleList] = useState(seedRoles),
    [selected, setSelected] = useState(0),
    [candidateTab, setCandidateTab] = useState("Overview"),
    [stageFilter, setStageFilter] = useState("All active stages"),
    [newStage, setNewStage] = useState("Recruiter Phone Call"),
    [wizard, setWizard] = useState(0),
    [request, setRequest] = useState<Record<string, string>>({
      name: "Senior Agronomist",
      requestor: "Alex Morgan",
      team: "Agronomy",
      country: "Vietnam",
      reason: "New Hire",
      manager: "Sam Lee",
      level: "Individual contributor",
      budget: "600000000",
      currency: "VND",
      date: "2026-11-02",
      approver: "Dhruv",
      jd: "Define the role",
      sensitive: "No",
    }),
    [savedRequest, setSavedRequest] = useState(false),
    [templateIndex, setTemplateIndex] = useState(0),
    [emailList, setEmailList] = useState(emails),
    [companyJds, setCompanyJds] = useState<Record<string, string[][]>>({
      Rize: jdSections,
    }),
    [jdTab, setJdTab] = useState("Role content"),
    [jd, setJd] = useState<Record<string, string>>({
      "What the role is about":
        "Build tools that help field teams turn complex agricultural data into clear, useful decisions.",
      "What you’ll be doing":
        "Partner with agronomists, product managers and engineers. Research field workflows and deliver accessible, practical solutions.",
      "Must-have skills & characteristics":
        "Strong craft, systems thinking and experience working with cross-functional teams.",
      "Nice-to-have skills & characteristics":
        "Experience with climate technology, agriculture or field operations.",
      "Interview Process (optional)":
        "Recruiter Phone Call → Discussion 1 → Discussion 2 → Discussion 3",
    }),
    [probationTab, setProbationTab] = useState("Reviews"),
    [peers, setPeers] = useState(["Alex Morgan", "Sam Lee", "Kai Lim"]),
    [verdict, setVerdict] = useState("Confirm"),
    [reviewSent, setReviewSent] = useState(false),
    [reviewApproved, setReviewApproved] = useState(false),
    [holidayTab, setHolidayTab] = useState("Calendar"),
    [month, setMonth] = useState(8),
    [reconciled, setReconciled] = useState<Record<string, string>>({}),
    [holidayPublished, setHolidayPublished] = useState(false),
    [applicationStep, setApplicationStep] = useState(0),
    [formCountry, setFormCountry] = useState("Singapore"),
    [words, setWords] = useState(""),
    [consent, setConsent] = useState("Yes"),
    [formDone, setFormDone] = useState(false),
    [source, setSource] = useState("linkedin"),
    [medium, setMedium] = useState("social"),
    [campaign, setCampaign] = useState("design-sep-2026"),
    [reviewScores, setReviewScores] = useState<Record<string, string>>({}),
    [feedbackSaved, setFeedbackSaved] = useState(false),
    [nominationSent, setNominationSent] = useState(false),
    [scheduleDone, setScheduleDone] = useState(false),
    [actionLog, setActionLog] = useState<string[]>([]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.has("utm_source"))
      setSource(params.get("utm_source") || "direct");
    if (params.has("utm_medium")) setMedium(params.get("utm_medium") || "");
    if (params.has("utm_campaign"))
      setCampaign(params.get("utm_campaign") || "");
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(t);
  }, [toast]);
  const notify = (s: string) => setToast(s + " · Preview only");
  const go = (m: string, t = "Overview") => {
    setModule(m);
    setTab(t);
    setQuery("");
    setCountry("All countries");
  };
  const open = (m: string) => {
    setModal(m);
    setFormDone(false);
  };
  const cand = candidateList[selected];
  const visibleCandidates = candidateList.filter(
    (c) =>
      (!query ||
        (c.name + " " + c.role).toLowerCase().includes(query.toLowerCase())) &&
      (country === "All countries" || country === c.country) &&
      (stageFilter === "All active stages"
        ? ![
            "CV Reject",
            "Interview Reject",
            "Drop Out",
            "Offer Drop out",
          ].includes(c.stage)
        : stageFilter === c.stage),
  );
  const activeHolidays = holidayData.filter(
    (h) => reconciled[h.country] !== "combined" || !h.conflict,
  );
  const holidays = activeHolidays.filter(
    (h) =>
      (country === "All countries" || h.country === country) &&
      (!query || h.name.toLowerCase().includes(query.toLowerCase())),
  );
  const unresolved = ["Indonesia", "Vietnam"].filter((c) => !reconciled[c]);
  const countWords = words.trim() ? words.trim().split(/\s+/).length : 0;
  const currentEmail = emailList[templateIndex];
  const substitutions: Record<string, string> = {
    first_name: "Maya",
    role: "Product Designer",
    brand,
    company_intro:
      tenant === "Rize"
        ? "A quick bit about us while you wait: we're building the tech to make rice farming more sustainable and less carbon-heavy across Southeast Asia. It's messy, meaningful work - and we're glad you want in."
        : `We’re glad you’re interested in joining ${brand}. We look forward to learning more about you.`,
    website: tenant === "Rize" ? "rize.farm" : "company.example",
    linkedin: tenant === "Rize" ? "Rize LinkedIn" : "Company LinkedIn",
    hr_name: "Alex Morgan",
    duration: "30",
    scheduling_link: "[Candidate booking link]",
    sender_name: "Alex",
    tasks: "Explore a field-team workflow and explain your approach.",
    format: "A short document or presentation is welcome.",
    deadline: "28 September 2026",
    submission_link: "[Secure assignment upload link]",
    reason: "we’re aligning a couple of internal decisions on the role",
    update_date: "25 September 2026",
  };
  const resolve = (s: string) =>
    s.replace(
      /\{\{(\w+)\}\}/g,
      (_, k) => substitutions[k] || `[Missing: ${k}]`,
    );
  const renderFilter = () => (
    <div className="filters">
      <input
        aria-label="Search records"
        placeholder={
          module === "Holiday Calendar"
            ? "Search holidays…"
            : "Search a person, role or team…"
        }
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <select
        aria-label="Country filter"
        value={country}
        onChange={(e) => setCountry(e.target.value)}
      >
        {["All countries", ...countries].map((c) => (
          <option key={c}>{c}</option>
        ))}
      </select>
    </div>
  );
  const candidateOpen = (i: number) => {
    setSelected(i);
    setCandidateTab("Overview");
    setNewStage(
      stages[Math.min(stages.indexOf(candidateList[i].stage) + 1, 9)],
    );
    open("candidate");
  };
  const requestField = (
    label: string,
    key: string,
    options?: string[],
    type = "text",
  ) => (
    <Field
      label={label}
      options={options}
      type={type}
      value={request[key] || ""}
      onChange={(v) => setRequest({ ...request, [key]: v })}
      required={!["remarks", "assignment", "round3"].includes(key)}
    />
  );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span className="brandmark">P</span>
          <span>
            Payobook<small>PAYROLL SUITE</small>
          </span>
        </div>
        <small>WORKSPACE</small>
        <select
          aria-label="Client workspace"
          className="workspace"
          value={tenant}
          onChange={(e) => {
            setTenant(e.target.value);
            setBrand(e.target.value);
          }}
        >
          <option>Rize</option>
          <option>Acme</option>
        </select>
        <nav>
          <p>⌂　 Home</p>
          <small>OPERATE</small>
          <p>♧　 People</p>
          <p className="selected">◇　 Lifecycle</p>
          {["Hiring", "Probation", "Holiday Calendar"].map((t) => (
            <button
              key={t}
              onClick={() => go(t)}
              className={module === t ? "sub active" : "sub"}
            >
              {t}
            </button>
          ))}
          <p>▦　 Workforce</p>
          <p>▤　 Pay Run</p>
          <small>UNDERSTAND</small>
          <p>◷　 Insights</p>
          <button className="sub" onClick={() => open("settings")}>
            Workspace settings
          </button>
        </nav>
        <div className="asidefoot">
          <b>Talent workspace</b>
          <p>Every next step, together.</p>
          <button onClick={() => open("guide")}>Explore this preview ↗</button>
        </div>
      </aside>
      <div className="content">
        <header>
          <span>
            Lifecycle <i>/</i> {module}
          </span>
          <span className="badge">DESIGN PREVIEW · DEMO DATA</span>
          <button
            className="avatar"
            onClick={() => open("guide")}
            aria-label="Preview guide"
          >
            ?
          </button>
        </header>
        <div className="mobileNav">
          {["Hiring", "Probation", "Holiday Calendar"].map((m) => (
            <button key={m} onClick={() => go(m)}>
              {m}
            </button>
          ))}
        </div>
        <main>
          <div className="heading">
            <div>
              <div className="eyebrow">
                {module === "Hiring"
                  ? "PEOPLE, FROM THE VERY BEGINNING"
                  : module === "Probation"
                    ? "HELP EVERY NEW START BECOME A STRONG ONE"
                    : "A SHARED VIEW OF TIME AWAY"}
              </div>
              <h1>
                {module === "Hiring"
                  ? "A great hire starts here."
                  : module === "Probation"
                    ? "A confident next chapter."
                    : "Different places. One calendar."}
              </h1>
              <p>
                {module === "Hiring"
                  ? "Bring the right people in. Give every journey a clear next step."
                  : module === "Probation"
                    ? "Thoughtful feedback, clear milestones, and no last-minute surprises."
                    : "Plan across your entities. Know who’s away before you book."}
              </p>
            </div>
            <button
              className="primary"
              onClick={() => {
                if (module === "Hiring") {
                  setWizard(0);
                  setSavedRequest(false);
                  open("request");
                } else open(module === "Probation" ? "policy" : "import");
              }}
            >
              {module === "Hiring"
                ? "＋ New hiring request"
                : module === "Probation"
                  ? "Review policy"
                  : "Review & publish calendar"}
            </button>
          </div>
          <div className="journey">
            {[
              "Request & approve",
              "Prepare & publish",
              "Meet & evaluate",
              "Offer & join",
              "Grow & confirm",
            ].map((s, i) => (
              <button
                key={s}
                onClick={() => {
                  if (i === 0) {
                    go("Hiring", "Roles");
                  }
                  if (i === 1) {
                    go("Hiring", "Templates");
                    setJdTab("Role content");
                  }
                  if (i === 2) go("Hiring", "Candidates");
                  if (i === 3) {
                    go("Hiring", "Candidates");
                    setStageFilter("Offer Stage");
                  }
                  if (i === 4) go("Probation");
                }}
              >
                <span>{String(i + 1).padStart(2, "0")}</span>
                <b>{s}</b>
                <small>
                  {
                    [
                      "Define the role",
                      "Tell your story",
                      "Find the right fit",
                      "Welcome someone new",
                      "Build their future",
                    ][i]
                  }
                </small>
              </button>
            ))}
          </div>
          {module === "Hiring" && (
            <>
              <div
                className="tabs"
                role="tablist"
                aria-label="Hiring workspace"
              >
                {[
                  "Overview",
                  "Roles",
                  "Candidates",
                  "Interviews",
                  "Sources",
                  "Templates",
                ].map((x) => (
                  <button
                    role="tab"
                    aria-selected={tab === x}
                    className={tab === x ? "active" : ""}
                    key={x}
                    onClick={() => {
                      setTab(x);
                      setQuery("");
                    }}
                  >
                    {x}
                  </button>
                ))}
              </div>
              {tab === "Overview" && (
                <>
                  <section className="hero">
                    <div>
                      <span className="eyebrow">YOUR NEXT MOVE</span>
                      <h2>Keep good candidates moving.</h2>
                      <p>
                        Three moments that deserve your attention.
                        <br />A little momentum makes a big difference.
                      </p>
                      <button
                        className="primary"
                        onClick={() => setTab("Candidates")}
                      >
                        Review candidates →
                      </button>
                    </div>
                    <div className="herometric">
                      <strong>{roleList.length}</strong>
                      <span>roles in your workspace</span>
                      <div className="mini-bars">
                        {[35, 50, 80, 65, 95, 78, 110].map((n, i) => (
                          <div key={i} style={{ height: n }} />
                        ))}
                      </div>
                      <small>Illustrative weekly activity</small>
                    </div>
                    <div className="heroaside">
                      <b>Everything has an owner.</b>
                      <p>
                        Approvals, interviews and feedback come together in one
                        place.
                      </p>
                      {badge("4 entities connected", "green")}
                    </div>
                  </section>
                  <div className="sectiontitle">
                    <h2>Make the next step count.</h2>
                    <span>22 September 2026 · Illustrative activity</span>
                  </div>
                  <div className="twocol">
                    <section className="panel">
                      <h3>Needs your attention {badge("3")}</h3>
                      {[
                        [
                          "Approve a new role",
                          "Senior Agronomist · Vietnam",
                          "Budget reviewed",
                        ],
                        [
                          "Review panel feedback",
                          "Maya Chen · Product Designer",
                          "Due today",
                        ],
                        [
                          "Prepare an offer",
                          "Arjun Mehta · Data Engineer",
                          "References complete",
                        ],
                      ].map((r, i) => (
                        <div className="row" key={r[0]}>
                          <div className="round">↗</div>
                          <div>
                            <b>{r[0]}</b>
                            <p>{r[1]}</p>
                          </div>
                          {badge(r[2], i === 1 ? "amber" : "")}
                          <button
                            onClick={() =>
                              i === 0
                                ? open("approval")
                                : candidateOpen(i === 1 ? 0 : 1)
                            }
                          >
                            Open →
                          </button>
                        </div>
                      ))}
                    </section>
                    <section className="panel">
                      <span className="eyebrow">THE WEEK AHEAD</span>
                      <h3>Make room for conversations.</h3>
                      {[
                        ["24", "Product Designer", "Discussion 1 · 10:30 SGT"],
                        ["25", "Senior Agronomist", "Panel review · 14:00 ICT"],
                      ].map((e) => (
                        <div className="event" key={e[0]}>
                          <b>{e[0]}</b>
                          <div>
                            <strong>{e[1]}</strong>
                            <p>{e[2]}</p>
                          </div>
                        </div>
                      ))}
                      <button
                        className="textbtn"
                        onClick={() => setTab("Interviews")}
                      >
                        Open interview planner →
                      </button>
                    </section>
                  </div>
                  <div className="quickgrid">
                    {[
                      [
                        "Application experience",
                        "A welcoming, focused form.",
                        "application",
                      ],
                      [
                        "Employee referrals",
                        "Good people know good people.",
                        "referral",
                      ],
                      [
                        "Your company voice",
                        "Consistent, thoughtful communication.",
                        "email",
                      ],
                    ].map((x) => (
                      <button
                        key={x[0]}
                        className="quickcard"
                        onClick={() => {
                          setApplicationStep(0);
                          open(x[2]);
                        }}
                      >
                        <span className="round">↗</span>
                        <b>{x[0]}</b>
                        <p>{x[1]}</p>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {tab === "Roles" && (
                <>
                  {renderFilter()}
                  <div className="cards">
                    {roleList
                      .filter(
                        (r) =>
                          (country === "All countries" ||
                            r.country === country) &&
                          `${r.name} ${r.team}`
                            .toLowerCase()
                            .includes(query.toLowerCase()),
                      )
                      .map((r, i) => (
                        <button
                          className="rolecard"
                          key={i}
                          onClick={() =>
                            open(
                              r.state === "Awaiting approval"
                                ? "approval"
                                : "role",
                            )
                          }
                        >
                          <div className="cardtop">
                            <span className="round">◇</span>
                            {badge(
                              r.state,
                              r.state === "Awaiting approval"
                                ? "amber"
                                : "green",
                            )}
                          </div>
                          <h2>{r.name}</h2>
                          <p>
                            {r.team} · {r.country}
                          </p>
                          <div className="roleprogress">
                            <span />
                            <span />
                            <span />
                            <span className="future" />
                            <span className="future" />
                          </div>
                          <div className="carddetails">
                            <span>
                              {r.count} candidate{r.count === 1 ? "" : "s"}
                            </span>
                            <b>{r.budget}</b>
                          </div>
                          <footer>
                            <span>Owner · {r.owner}</span>
                            <span>View journey →</span>
                          </footer>
                        </button>
                      ))}
                  </div>
                  <div className="notice">
                    Sensitive replacement roles stay private and do not open to
                    referrals. Annual budgets keep their own currency.
                  </div>
                </>
              )}
              {tab === "Candidates" && (
                <>
                  {renderFilter()}
                  <div className="splitline">
                    <div>
                      <h2>The right context for every conversation.</h2>
                      <p>
                        Every job keeps the same 15 stages. Filter a stage to
                        focus your work.
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setApplicationStep(0);
                        open("application");
                      }}
                    >
                      Preview application ↗
                    </button>
                  </div>
                  <div className="stagechips">
                    <button
                      className={
                        stageFilter === "All active stages" ? "chosen" : ""
                      }
                      onClick={() => setStageFilter("All active stages")}
                    >
                      All active stages
                    </button>
                    {stages.map((s) => (
                      <button
                        className={stageFilter === s ? "chosen" : ""}
                        key={s}
                        onClick={() => setStageFilter(s)}
                      >
                        {s}
                        {s === "Assignment" ? " · optional" : ""}
                        <span>
                          {candidateList.filter((c) => c.stage === s).length}
                        </span>
                      </button>
                    ))}
                  </div>
                  <div className="tablewrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Candidate</th>
                          <th>Stage</th>
                          <th>Source</th>
                          <th>Next step</th>
                          <th>Time in stage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visibleCandidates.map((c) => (
                          <tr key={c.name}>
                            <td>
                              <button
                                className="personbutton"
                                onClick={() =>
                                  candidateOpen(candidateList.indexOf(c))
                                }
                              >
                                <span className="avatar">{c.initials}</span>
                                <span>
                                  <b>{c.name}</b>
                                  <small>
                                    {c.role} · {c.country}
                                  </small>
                                </span>
                              </button>
                            </td>
                            <td>
                              {badge(
                                c.stage,
                                c.stage === "On Hold" ? "amber" : "",
                              )}
                            </td>
                            <td>{c.source}</td>
                            <td>{c.note}</td>
                            <td>{c.days} days</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!visibleCandidates.length && (
                      <div className="empty">
                        <h3>No candidates in this view.</h3>
                        <p>Choose another stage or clear your search.</p>
                        <button
                          onClick={() => {
                            setQuery("");
                            setCountry("All countries");
                            setStageFilter("All active stages");
                          }}
                        >
                          Clear filters
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
              {tab === "Interviews" && (
                <>
                  <div className="splitline">
                    <div>
                      <h2>Prepared people. Better conversations.</h2>
                      <p>
                        Candidate, panel, agenda and feedback deadline —
                        together.
                      </p>
                    </div>
                    <button
                      className="primary"
                      onClick={() => open("schedule")}
                    >
                      ＋ Schedule interview
                    </button>
                  </div>
                  <div className="twocol">
                    <section className="panel">
                      <h3>Thursday, 24 September</h3>
                      <div className="interview">
                        <div className="time">
                          10:30 <small>SGT · UTC+8</small>
                        </div>
                        <div>
                          <h3>Maya Chen · Product Designer</h3>
                          <p>
                            Discussion 1 · 45 minutes
                            <br />
                            Alex Morgan & Kai Lim · Product craft and systems
                            thinking
                          </p>
                          {badge(
                            scheduleDone
                              ? "Preview scheduled"
                              : "Ready to schedule",
                            "green",
                          )}
                          <div className="actions">
                            <button onClick={() => open("schedule")}>
                              Schedule / reschedule
                            </button>
                            <button onClick={() => open("feedback")}>
                              Interview kit & feedback
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className="notice">
                        Reminders: 24 hours and 30 minutes before. Feedback due
                        within 24 working hours, using the interviewer’s
                        calendar.
                      </div>
                    </section>
                    <section className="panel">
                      <h3>Keep the process fair.</h3>
                      <p>
                        Record a reason when plans change. Separate internal and
                        external delays in reporting.
                      </p>
                      <button onClick={() => open("no-show")}>
                        Record a no-show or delay
                      </button>
                      <hr />
                      <h3>Referral conflict check</h3>
                      <p>
                        A candidate’s referrer cannot join their interview
                        panel.
                      </p>
                      {badge("Checked before scheduling", "green")}
                    </section>
                  </div>
                </>
              )}
              {tab === "Sources" && (
                <>
                  <div className="splitline">
                    <div>
                      <h2>Know where your next hire comes from.</h2>
                      <p>
                        Automatic attribution on every application, with first
                        and latest touch preserved.
                      </p>
                    </div>
                    {badge("Attribution preview")}
                  </div>
                  <div className="twocol">
                    <section className="panel">
                      <h3>
                        Source performance{" "}
                        <small>DEMO COHORT · 6 CANDIDATES</small>
                      </h3>
                      {["LinkedIn", "Referral", "Careers page", "Agency"].map(
                        (s) => (
                          <div className="sourcebar" key={s}>
                            <span>{s}</span>
                            <div>
                              <i
                                style={{
                                  width: `${(candidateList.filter((c) => c.source === s).length / 6) * 100}%`,
                                }}
                              />
                            </div>
                            <b>
                              {
                                candidateList.filter((c) => c.source === s)
                                  .length
                              }
                            </b>
                          </div>
                        ),
                      )}
                      <div className="metricgrid">
                        <div>
                          <b>—</b>
                          <p>
                            Time to fill
                            <br />
                            No joined candidates
                          </p>
                        </div>
                        <div>
                          <b>—</b>
                          <p>
                            Offer acceptance
                            <br />
                            No completed offers
                          </p>
                        </div>
                        <div>
                          <b>1</b>
                          <p>
                            Agency candidate
                            <br />
                            Internal owner assigned
                          </p>
                        </div>
                      </div>
                    </section>
                    <section className="panel">
                      <h3>Create a tracked job link</h3>
                      <Field
                        label="Source"
                        value={source}
                        onChange={setSource}
                      />
                      <Field
                        label="Medium"
                        value={medium}
                        onChange={setMedium}
                      />
                      <Field
                        label="Campaign"
                        value={campaign}
                        onChange={setCampaign}
                      />
                      <div className="code">
                        /careers/product-designer?utm_source=
                        {encodeURIComponent(source)}&utm_medium=
                        {encodeURIComponent(medium)}&utm_campaign=
                        {encodeURIComponent(campaign)}
                      </div>
                      <button
                        onClick={() => {
                          setApplicationStep(0);
                          open("application");
                        }}
                      >
                        Preview tracked application →
                      </button>
                    </section>
                  </div>
                  <div className="notice">
                    Production design: capture UTM source, medium, campaign,
                    term, content, landing page and referring domain.
                    Unattributed visits remain “Direct / unknown”; referrals and
                    agency records retain explicit provenance.
                  </div>
                </>
              )}
              {tab === "Templates" && (
                <>
                  <div className="splitline">
                    <div>
                      <h2>Your voice, at every step.</h2>
                      <p>
                        Company defaults stay consistent. Recruiters focus on
                        the role.
                      </p>
                    </div>
                    <button onClick={() => open("settings")}>
                      Brand & automation settings
                    </button>
                  </div>
                  <div className="quickgrid">
                    <button className="quickcard" onClick={() => open("jd")}>
                      <span className="round">▤</span>
                      <h3>Job description studio</h3>
                      <p>
                        5 company sections + role-specific content, approval and
                        publication.
                      </p>
                      <b>Open JD studio →</b>
                    </button>
                    <button className="quickcard" onClick={() => open("email")}>
                      <span className="round">✉</span>
                      <h3>Candidate communications</h3>
                      <p>
                        All 5 supplied templates, configurable tokens and a
                        rendered preview.
                      </p>
                      <b>Open email studio →</b>
                    </button>
                    <button
                      className="quickcard"
                      onClick={() => open("policy")}
                    >
                      <span className="round">◇</span>
                      <h3>Probation policy</h3>
                      <p>
                        Country duration, peer count, timing, review routing and
                        outcome letters.
                      </p>
                      <b>Review configuration →</b>
                    </button>
                  </div>
                  <section className="panel">
                    <h3>Trigger map</h3>
                    {emails.map((e) => (
                      <div className="row" key={e.name}>
                        <div className="round">↗</div>
                        <div>
                          <b>{e.trigger}</b>
                          <p>{e.name}</p>
                        </div>
                        {badge(
                          e.name === "Application received"
                            ? "Automatic receipt"
                            : "Recruiter review before send",
                        )}
                        <button
                          onClick={() => {
                            setTemplateIndex(emails.indexOf(e));
                            open("email");
                          }}
                        >
                          Edit →
                        </button>
                      </div>
                    ))}
                  </section>
                </>
              )}
            </>
          )}
          {module === "Probation" && (
            <>
              <div className="tabs">
                {["Reviews", "30 · 60 · 90 days", "Policy & routing"].map(
                  (t) => (
                    <button
                      className={probationTab === t ? "active" : ""}
                      onClick={() => setProbationTab(t)}
                      key={t}
                    >
                      {t}
                    </button>
                  ),
                )}
              </div>
              {probationTab === "Reviews" ? (
                <>
                  <section className="hero probationhero">
                    <div>
                      <span className="eyebrow">MAKE FEEDBACK COUNT</span>
                      <h2>Clarity before the deadline.</h2>
                      <p>
                        One review is ready for a thoughtful conversation.
                        <br />
                        Bring the evidence together, then decide.
                      </p>
                      <button
                        className="primary"
                        onClick={() => open("review")}
                      >
                        Continue Linh’s review →
                      </button>
                    </div>
                    <div className="orb">
                      <span>08</span>
                      <b>days to decision</b>
                      <small>30 September 2026</small>
                    </div>
                    <div className="heroaside">
                      <b>
                        {reviewApproved
                          ? "HR review complete"
                          : reviewSent
                            ? "Awaiting HR review"
                            : "Ready for manager review"}
                      </b>
                      <p>
                        3 peer responses received.
                        <br />
                        All required training complete.
                      </p>
                      {badge("Full-time employee", "green")}
                    </div>
                  </section>
                  <div className="sectiontitle">
                    <h2>Every new start, supported.</h2>
                    <span>Demo reviews · private to authorised reviewers</span>
                  </div>
                  <div className="cards">
                    <button className="rolecard" onClick={() => open("review")}>
                      <div className="cardtop">
                        <div className="avatar">LN</div>
                        {badge(
                          reviewApproved
                            ? "Ready to communicate"
                            : reviewSent
                              ? "HR approval pending"
                              : "Manager review",
                          "amber",
                        )}
                      </div>
                      <h2>Linh Nguyen</h2>
                      <p>Agronomist · Vietnam</p>
                      <Steps
                        labels={["Peers", "Review", "HR", "Outcome"]}
                        current={reviewApproved ? 3 : reviewSent ? 2 : 1}
                      />
                      <div className="carddetails">
                        <span>3 / 3 peers complete</span>
                        <b>Ends 30 Sep</b>
                      </div>
                      <footer>
                        Next:{" "}
                        {reviewApproved
                          ? "Communicate decision"
                          : reviewSent
                            ? "HR reviews recommendation"
                            : "Record the 1:1 and recommendation"}{" "}
                        →
                      </footer>
                    </button>
                    <button
                      className="rolecard"
                      onClick={() => open("nominate")}
                    >
                      <div className="cardtop">
                        <div className="avatar">DP</div>
                        {badge(
                          nominationSent
                            ? "Feedback requested"
                            : "Nominate peers",
                        )}
                      </div>
                      <h2>Dewi Putri</h2>
                      <p>Operations · Indonesia</p>
                      <Steps
                        labels={["Peers", "Review", "HR", "Outcome"]}
                        current={0}
                      />
                      <div className="carddetails">
                        <span>
                          {nominationSent
                            ? peers.length + " nominated"
                            : "Choose 3–4 colleagues"}
                        </span>
                        <b>Ends 12 Oct</b>
                      </div>
                      <footer>
                        Next:{" "}
                        {nominationSent
                          ? "Track peer feedback"
                          : "Manager nominates peers"}{" "}
                        →
                      </footer>
                    </button>
                  </div>
                  <div className="notice">
                    Interns and part-time or full-time consultants are outside
                    this probation SOP. Agronomists must finish mandatory
                    training before clearance.
                  </div>
                </>
              ) : probationTab === "30 · 60 · 90 days" ? (
                <section className="panel">
                  <h2>Small conversations. Stronger starts.</h2>
                  <p>
                    HRBP and new hire check-ins are planned from the joining
                    date, including milestones after a shorter probation ends.
                  </p>
                  <div className="quickgrid">
                    {[
                      [
                        "30",
                        "How are you settling in?",
                        "Support, concerns and first impressions.",
                      ],
                      [
                        "60",
                        "Find your rhythm.",
                        "Adaptation, understanding and early performance.",
                      ],
                      [
                        "90",
                        "Look ahead together.",
                        "Readiness, progress and remaining concerns.",
                      ],
                    ].map((x) => (
                      <div className="checkin" key={x[0]}>
                        <strong>{x[0]}</strong>
                        <small>DAY CHECK-IN</small>
                        <h3>{x[1]}</h3>
                        <p>{x[2]}</p>
                        <button onClick={() => open("checkin")}>
                          Open check-in
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
              ) : (
                <section className="panel">
                  <h2>A clear policy, tailored by country.</h2>
                  <p>
                    Evaluation starts 21 days before the end date. HR milestones
                    at 15 and 5 days remain visible.
                  </p>
                  <Steps
                    labels={[
                      "Nominate 3–4 peers",
                      "3 working days for feedback",
                      "Manager 1:1 within 2 days",
                      "HR / CEO review",
                      "Communicate outcome",
                    ]}
                    current={0}
                  />
                  <button onClick={() => open("policy")}>
                    Configure policy →
                  </button>
                </section>
              )}
            </>
          )}
          {module === "Holiday Calendar" && (
            <>
              <div className="calendarsummary">
                {countries.map((c) => (
                  <button
                    key={c}
                    onClick={() =>
                      setCountry(country === c ? "All countries" : c)
                    }
                    className={country === c ? "selected" : ""}
                  >
                    <span>{c === "India" ? "India · Karnataka" : c}</span>
                    <b>
                      {activeHolidays.filter((h) => h.country === c).length}
                    </b>
                    <small>dates in draft · 2026</small>
                  </button>
                ))}
              </div>
              <div className="tabs">
                {[
                  "Calendar",
                  "Compare countries",
                  "Import review",
                  "Leave policies",
                ].map((t) => (
                  <button
                    className={holidayTab === t ? "active" : ""}
                    key={t}
                    onClick={() => setHolidayTab(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              {renderFilter()}
              {holidayTab === "Calendar" ? (
                <>
                  <div className="splitline">
                    <div>
                      <h2>
                        {new Date(2026, month, 1).toLocaleDateString("en", {
                          month: "long",
                          year: "numeric",
                        })}
                      </h2>
                      <p>
                        {country === "All countries"
                          ? "All four entities"
                          : country}{" "}
                        ·{" "}
                        {holidayPublished
                          ? "Published in this preview"
                          : "Draft from supplied workbook"}
                      </p>
                    </div>
                    <div className="actions">
                      <button
                        aria-label="Previous month"
                        onClick={() => setMonth(Math.max(0, month - 1))}
                        disabled={month === 0}
                      >
                        ←
                      </button>
                      <button onClick={() => setMonth(8)}>September</button>
                      <button
                        aria-label="Next month"
                        onClick={() => setMonth(Math.min(11, month + 1))}
                        disabled={month === 11}
                      >
                        →
                      </button>
                    </div>
                  </div>
                  <div className="calendar">
                    {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
                      (d) => (
                        <div className="dayhead" key={d}>
                          {d}
                        </div>
                      ),
                    )}
                    {Array.from(
                      { length: (new Date(2026, month, 1).getDay() + 6) % 7 },
                      (_, i) => (
                        <div className="day blank" key={"blank" + i} />
                      ),
                    )}
                    {Array.from(
                      { length: new Date(2026, month + 1, 0).getDate() },
                      (_, i) => {
                        const date = `2026-${String(month + 1).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`;
                        return (
                          <div
                            className={
                              "day " + (date === "2026-09-22" ? "today" : "")
                            }
                            key={date}
                          >
                            <span>{i + 1}</span>
                            {holidays
                              .filter((h) => h.date === date)
                              .map((h) => (
                                <button
                                  key={h.country + h.name}
                                  onClick={() => {
                                    setCountry(h.country);
                                    open("holiday-detail");
                                  }}
                                  className={"holiday country-" + h.country}
                                >
                                  <b>{h.country}</b>
                                  {h.name}
                                </button>
                              ))}
                          </div>
                        );
                      },
                    )}
                  </div>
                  <div className="notice">
                    Holiday names and dates reproduce the supplied workbook as a
                    draft, not a verified statutory calendar.{" "}
                    {unresolved.length} country discrepancies still need review.
                  </div>
                </>
              ) : holidayTab === "Compare countries" ? (
                <div className="tablewrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Date · Holiday</th>
                        {countries.map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {Array.from(new Set(holidays.map((h) => h.date)))
                        .sort()
                        .map((d) => (
                          <tr key={d}>
                            <td>
                              <b>{d}</b>
                              <small>
                                {Array.from(
                                  new Set(
                                    holidays
                                      .filter((h) => h.date === d)
                                      .map((h) => h.name),
                                  ),
                                ).join(" / ")}
                              </small>
                            </td>
                            {countries.map((c) => (
                              <td key={c}>
                                {holidays.some(
                                  (h) => h.date === d && h.country === c,
                                )
                                  ? badge("Day off", "green")
                                  : "—"}
                              </td>
                            ))}
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : holidayTab === "Import review" ? (
                <section className="panel">
                  <h2>Resolve differences before publishing.</h2>
                  <p>
                    The combined sheet omits two dates present in country
                    sheets. Country sheets are the provisional starting point.
                  </p>
                  {["Indonesia", "Vietnam"].map((c) => (
                    <div className="row" key={c}>
                      <div className="round">!</div>
                      <div>
                        <b>
                          {c} ·{" "}
                          {c === "Indonesia"
                            ? "Pancasila Day, 1 June"
                            : "Vietnam Cultural Day, 24 November"}
                        </b>
                        <p>
                          {c === "Indonesia"
                            ? "Combined: 17 dates · Country: 18 dates"
                            : "Combined: 12 dates · Country: 13 dates"}
                        </p>
                      </div>
                      <select
                        aria-label={c + " source resolution"}
                        value={reconciled[c] || ""}
                        onChange={(e) =>
                          setReconciled({ ...reconciled, [c]: e.target.value })
                        }
                      >
                        <option value="">Choose source…</option>
                        <option value="country">Keep country sheet date</option>
                        <option value="combined">Use combined sheet</option>
                      </select>
                    </div>
                  ))}
                  <div className="notice">
                    All leave-policy values and unusual holiday labels still
                    require tenant HR validation. Source dates are preserved
                    until explicitly reconciled.
                  </div>
                  <button
                    className="primary"
                    disabled={!!unresolved.length}
                    onClick={() => {
                      setHolidayPublished(true);
                      notify("Calendar published in preview");
                    }}
                  >
                    {holidayPublished
                      ? "Published in preview"
                      : "Publish resolved preview"}
                  </button>
                </section>
              ) : (
                <section className="panel">
                  <h2>Leave policies, separate from public holidays.</h2>
                  <p>
                    The supplied policy grid is a tenant draft. Configure
                    entitlement, carry-forward and eligibility separately from
                    calendar days.
                  </p>
                  <div className="tablewrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Policy</th>
                          <th>Draft entitlement</th>
                          <th>Carry forward</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Annual leave</td>
                          <td>20 days across all four countries</td>
                          <td>Per configured policy</td>
                        </tr>
                        <tr>
                          <td>National and festival holidays</td>
                          <td>Country / location calendar</td>
                          <td>No</td>
                        </tr>
                        <tr>
                          <td>Menstrual leave</td>
                          <td>Indonesia: 2 days/month; other entities: 1</td>
                          <td>No; cannot combine months</td>
                        </tr>
                        <tr>
                          <td>Other leave categories</td>
                          <td>
                            Sick, maternity, paternity, miscarriage, adoption,
                            childcare, bereavement, marriage, child’s marriage,
                            family / household death, baptism / khitan
                          </td>
                          <td>Per country and eligibility</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="notice">
                    These are supplied policy values, not legal advice or
                    validated legal entitlements. Production policy setup needs
                    current country review.
                  </div>
                  <button onClick={() => open("leave-policy")}>
                    Review full draft policy matrix →
                  </button>
                </section>
              )}
            </>
          )}
          <footer className="previewfoot">
            Interactive design preview · Fictional people and activity · Changes
            last for this page session · No emails, invitations or live records
            are created.
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          ✓ {toast}
        </div>
      )}
      {modal && (
        <Modal
          title={
            (
              {
                request: "Let’s shape the role.",
                candidate: cand.name,
                approval: "A clear decision, with the context.",
                role: "Product Designer",
                application: `Your next chapter at ${brand}`,
                referral: "Recommend someone great.",
                jd: "Job description studio",
                email: "Candidate communication studio",
                review: "Linh Nguyen · Probation review",
                nominate: "Choose people who know their work.",
                policy: "Probation policy & routing",
                settings: "Make it yours.",
                import: "Review your calendar before publishing",
                schedule: "Plan the next conversation.",
                feedback: "Discussion 1 · Interview kit",
                guide: "Explore the proposed experience.",
                "leave-policy": "Country leave policy matrix",
              } as Record<string, string>
            )[modal] || "Complete the next step"
          }
          close={() => setModal("")}
        >
          {modal === "request" &&
            (savedRequest ? (
              <div className="success">
                <div className="round">✓</div>
                <h2>Your request has a clear next step.</h2>
                <p>
                  {request.name} is awaiting approval from {request.approver}.
                  Country routing will notify the assigned recruiter and their
                  manager after approval.
                </p>
                <Steps
                  labels={[
                    "Request submitted",
                    "Budget verified",
                    "Approver decision",
                    "JD & publishing",
                  ]}
                  current={1}
                />
                <button
                  className="primary"
                  onClick={() => {
                    setModal("");
                    go("Hiring", "Roles");
                  }}
                >
                  View hiring requests →
                </button>
              </div>
            ) : (
              <>
                <Steps
                  labels={[
                    "Role essentials",
                    "Role & interview plan",
                    "Budget & timing",
                    "Review & submit",
                  ]}
                  current={wizard}
                />
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (wizard < 3) setWizard(wizard + 1);
                    else {
                      setSavedRequest(true);
                      setRoleList([
                        ...roleList,
                        {
                          name: request.name,
                          country: request.country,
                          team: request.team,
                          state: "Awaiting approval",
                          count: 0,
                          budget:
                            request.currency +
                            " " +
                            Number(request.budget).toLocaleString(),
                          owner: request.requestor,
                        },
                      ]);
                    }
                  }}
                >
                  {wizard === 0 && (
                    <>
                      <h3>Start with who you need, and why.</h3>
                      <div className="formgrid">
                        {requestField("Manpower requestor", "requestor")}
                        {requestField("Department / function", "team")}
                        {requestField(
                          "Country of position",
                          "country",
                          countries,
                        )}
                        {requestField("Position title", "name")}
                        {requestField("Reason for new position", "reason", [
                          "New Hire",
                          "Replacement",
                        ])}
                        {requestField("Sensitive replacement?", "sensitive", [
                          "No",
                          "Yes",
                        ])}
                        {requestField("Reporting manager", "manager")}
                        {requestField(
                          "Position / level of this role",
                          "level",
                          [
                            "Individual contributor",
                            "Manager",
                            "Leadership",
                            "Regional",
                          ],
                        )}
                      </div>
                      <div className="notice">
                        Only authorised hiring managers / function heads can
                        raise requests.{" "}
                        {request.sensitive === "Yes"
                          ? "Referrals will remain closed for this sensitive role."
                          : "Referrals open automatically after approval."}
                      </div>
                    </>
                  )}
                  {wizard === 1 && (
                    <>
                      <h3>Give recruiters and interviewers a head start.</h3>
                      <div className="formgrid">
                        {requestField("Job description approach", "jd", [
                          "Define the role",
                          "Upload JD",
                          "Share sample JD",
                        ])}
                        {request.jd === "Define the role" ? (
                          requestField(
                            "Describe the role and expected outcomes",
                            "definition",
                            undefined,
                            "textarea",
                          )
                        ) : (
                          <Field
                            label={
                              request.jd === "Upload JD"
                                ? "Upload job description"
                                : "Upload sample job description"
                            }
                            type="file"
                            required
                          />
                        )}
                        {requestField("Assignment", "assignment", [
                          "Not required",
                          "Required",
                        ])}
                        {request.assignment === "Required" && (
                          <Field
                            label="Attach assignment document"
                            type="file"
                            required
                          />
                        )}
                        {[1, 2, 3].map((n) => (
                          <div className="full interviewform" key={n}>
                            <h3>Discussion {n}</h3>
                            <div className="formgrid">
                              {requestField(
                                `Discussion ${n} interviewer`,
                                "interviewer" + n,
                              )}
                              {requestField(
                                `Discussion ${n} focus`,
                                "focus" + n,
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="notice">
                        Screening → Panel Review → Recruiter Phone Call precede
                        this interview plan. Referrers are excluded from the
                        candidate’s panel.
                      </div>
                    </>
                  )}
                  {wizard === 2 && (
                    <>
                      <h3>Make budget and timing explicit.</h3>
                      <div className="formgrid">
                        {requestField(
                          "Annual budget for the role",
                          "budget",
                          undefined,
                          "number",
                        )}
                        {requestField("Currency", "currency", [
                          "VND",
                          "SGD",
                          "IDR",
                          "INR",
                          "USD",
                        ])}
                        {requestField(
                          "Expected position close date",
                          "date",
                          undefined,
                          "date",
                        )}
                        {requestField("MR approver", "approver")}
                        {requestField(
                          "Remarks",
                          "remarks",
                          undefined,
                          "textarea",
                        )}
                      </div>
                      <div className="notice">
                        Budget goes to recruiter + HR / Finance for
                        verification. Any excess returns to the hiring manager
                        with an alert. The approver is a tenant-configured role;
                        Rize’s example defaults to Dhruv.
                      </div>
                    </>
                  )}
                  {wizard === 3 && (
                    <>
                      <h3>One last look before it moves forward.</h3>
                      <dl className="summarylist">
                        {[
                          ["Role", request.name],
                          [
                            "Requestor / team",
                            request.requestor + " · " + request.team,
                          ],
                          [
                            "Country / reporting manager",
                            request.country + " · " + request.manager,
                          ],
                          ["Reason", request.reason],
                          ["JD approach", request.jd],
                          [
                            "Annual budget",
                            request.currency +
                              " " +
                              Number(request.budget).toLocaleString(),
                          ],
                          ["Target close date", request.date],
                          ["Approval owner", request.approver],
                          [
                            "Referrals",
                            request.sensitive === "Yes"
                              ? "Closed — sensitive replacement"
                              : "Open after approval",
                          ],
                        ].map((x) => (
                          <div key={x[0]}>
                            <dt>{x[0]}</dt>
                            <dd>{x[1]}</dd>
                          </div>
                        ))}
                      </dl>
                      <div className="notice">
                        This submits a demo request only. No notification is
                        sent.
                      </div>
                    </>
                  )}
                  <div className="modalfooter">
                    <button
                      type="button"
                      onClick={() =>
                        wizard ? setWizard(wizard - 1) : setModal("")
                      }
                    >
                      {wizard ? "← Back" : "Cancel"}
                    </button>
                    <button className="primary" type="submit">
                      {wizard === 3 ? "Submit demo request →" : "Continue →"}
                    </button>
                  </div>
                </form>
              </>
            ))}
          {modal === "approval" && (
            <>
              <Steps
                labels={[
                  "Request",
                  "Budget check",
                  "Approval",
                  "Recruiter assigned",
                ]}
                current={2}
              />
              <div className="twocol">
                <section>
                  <h2>Senior Agronomist</h2>
                  <p>Vietnam · Agronomy · New headcount</p>
                  <dl className="summarylist">
                    <div>
                      <dt>Annual request</dt>
                      <dd>VND 600,000,000</dd>
                    </div>
                    <div>
                      <dt>Budget available</dt>
                      <dd>VND 720,000,000</dd>
                    </div>
                    <div>
                      <dt>Target close</dt>
                      <dd>2 November 2026</dd>
                    </div>
                    <div>
                      <dt>Requestor</dt>
                      <dd>Sam Lee</dd>
                    </div>
                  </dl>
                  {badge("Budget verified · demo", "green")}
                </section>
                <section className="panel">
                  <h3>What approval unlocks</h3>
                  <p>
                    Assigned recruiter + recruiter manager notified.
                    <br />
                    JD finalisation and hiring-manager sign-off.
                    <br />
                    Referrals activated unless sensitive.
                    <br />
                    Publication after JD approval.
                  </p>
                </section>
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setRoleList(
                    roleList.map((r) =>
                      r.name === "Senior Agronomist"
                        ? { ...r, state: "JD in review" }
                        : r,
                    ),
                  );
                  setModal("");
                  notify("Request approved; next step is JD sign-off");
                }}
              >
                <Field label="Decision note" type="textarea" required />
                <div className="modalfooter">
                  <button
                    type="button"
                    onClick={() => {
                      notify("Request returned for clarification");
                      setModal("");
                    }}
                  >
                    Return for clarification
                  </button>
                  <button className="primary">Approve demo request →</button>
                </div>
              </form>
            </>
          )}
          {modal === "role" && (
            <>
              <p>Product · Singapore · Alex Morgan owns this role</p>
              <Steps
                labels={[
                  "Approved",
                  "JD approved",
                  "Published",
                  "Candidates",
                  "Offer & join",
                ]}
                current={3}
              />
              <div className="quickgrid">
                <button className="quickcard" onClick={() => open("jd")}>
                  <h3>Role brief & JD</h3>
                  <p>Company story and role-specific requirements.</p>
                  <b>Open studio →</b>
                </button>
                <button
                  className="quickcard"
                  onClick={() => {
                    setModal("");
                    setTab("Candidates");
                    setQuery("Product Designer");
                  }}
                >
                  <h3>Candidate journey</h3>
                  <p>Panel feedback, next action and communications.</p>
                  <b>View candidates →</b>
                </button>
                <button
                  className="quickcard"
                  onClick={() => open("delegation")}
                >
                  <h3>Recruiter coverage</h3>
                  <p>Delegate with manager approval and an audit trail.</p>
                  <b>Arrange cover →</b>
                </button>
              </div>
              <div className="notice">
                Public posting design: approved JD → tracked channel link /
                publishing adapter → record publication. LinkedIn and other job
                boards require their own supported integrations.
              </div>
              <div className="actions">
                <button onClick={() => open("application")}>
                  Preview careers page
                </button>
                <button onClick={() => open("referral")}>
                  Preview referral form
                </button>
              </div>
            </>
          )}
          {modal === "candidate" && (
            <>
              <div className="candidatehead">
                <span className="bigavatar">{cand.initials}</span>
                <div>
                  <h2>{cand.name}</h2>
                  <p>
                    {cand.role} · {cand.country} · {cand.source}
                  </p>
                </div>
                {badge(cand.stage)}
              </div>
              <div className="tabs">
                {[
                  "Overview",
                  "Interview & feedback",
                  "Communications",
                  "Source & history",
                  "Offer & joining",
                ].map((t) => (
                  <button
                    key={t}
                    className={candidateTab === t ? "active" : ""}
                    onClick={() => setCandidateTab(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              {candidateTab === "Overview" && (
                <>
                  <div className="nextaction">
                    <div>
                      <small>NEXT BEST ACTION</small>
                      <h3>{cand.note}</h3>
                      <p>
                        Owner · Alex Morgan · {cand.days} days in this stage
                      </p>
                    </div>
                    <button className="primary" onClick={() => open("move")}>
                      Move candidate →
                    </button>
                  </div>
                  <div className="twocol">
                    <section>
                      <h3>Professional profile</h3>
                      <p>
                        Fictional profile for design review. Experience in
                        cross-functional teams, practical problem solving and
                        complex operational workflows.
                      </p>
                      <div className="filecard">
                        <b>Resume / CV</b>
                        <span>Sample document slot · PDF / DOCX</span>
                      </div>
                      <dl className="summarylist">
                        <div>
                          <dt>Work authorisation</dt>
                          <dd>Citizen / permanent resident · demo</dd>
                        </div>
                        <div>
                          <dt>Relocation</dt>
                          <dd>Depends on role / terms</dd>
                        </div>
                        <div>
                          <dt>Motivation</dt>
                          <dd>
                            Interested in practical work with measurable impact.
                          </dd>
                        </div>
                      </dl>
                    </section>
                    <section className="panel">
                      <h3>Journey so far</h3>
                      <div className="timeline">
                        <p>
                          <b>Application received</b>
                          <br />
                          Receipt prepared · source captured
                        </p>
                        <p>
                          <b>Screening completed</b>
                          <br />
                          Recruiter reviewed profile
                        </p>
                        <p>
                          <b>{cand.stage}</b>
                          <br />
                          {cand.note}
                        </p>
                      </div>
                    </section>
                  </div>
                </>
              )}
              {candidateTab === "Interview & feedback" && (
                <>
                  <h3>A shared brief. Independent feedback.</h3>
                  <p>
                    Discussion 1 · Product craft and systems thinking · 45
                    minutes
                  </p>
                  <div className="notice">
                    Interviewers submit their own scorecards before viewing
                    other panel responses. Candidate referrers cannot sit on
                    this panel.
                  </div>
                  <div className="actions">
                    <button onClick={() => open("schedule")}>
                      Schedule interview
                    </button>
                    <button onClick={() => open("feedback")}>
                      Open scorecard
                    </button>
                    <button onClick={() => open("debrief")}>
                      Record panel debrief
                    </button>
                  </div>
                  {feedbackSaved && (
                    <p>{badge("Your scorecard submitted", "green")}</p>
                  )}
                </>
              )}
              {candidateTab === "Communications" && (
                <>
                  <h3>Keep the candidate in the loop.</h3>
                  <p>
                    The five supplied templates can be reviewed and personalised
                    before sending.
                  </p>
                  {emails.map((e, i) => (
                    <div className="row" key={e.name}>
                      <div>
                        <b>{e.name}</b>
                        <p>{e.trigger}</p>
                      </div>
                      <button
                        onClick={() => {
                          setTemplateIndex(i);
                          open("email");
                        }}
                      >
                        Preview message →
                      </button>
                    </div>
                  ))}
                </>
              )}
              {candidateTab === "Source & history" && (
                <>
                  <dl className="summarylist">
                    <div>
                      <dt>Original source</dt>
                      <dd>{cand.source}</dd>
                    </div>
                    <div>
                      <dt>UTM source</dt>
                      <dd>
                        {cand.source === "LinkedIn"
                          ? "linkedin"
                          : "Not supplied"}
                      </dd>
                    </div>
                    <div>
                      <dt>UTM medium / campaign</dt>
                      <dd>
                        {cand.source === "LinkedIn"
                          ? "social / design-sep-2026"
                          : "No campaign recorded"}
                      </dd>
                    </div>
                    <div>
                      <dt>Latest touch</dt>
                      <dd>Careers page · direct</dd>
                    </div>
                    <div>
                      <dt>Application landing page</dt>
                      <dd>/careers/product-designer</dd>
                    </div>
                  </dl>
                  <h3>Activity history</h3>
                  {actionLog.length ? (
                    actionLog.map((l, i) => <p key={i}>{l}</p>)
                  ) : (
                    <p>No changes made in this preview session.</p>
                  )}
                  <div className="notice">
                    Agency candidates retain vendor attribution. An internal
                    recruiter remains the communication owner.
                  </div>
                </>
              )}
              {candidateTab === "Offer & joining" && (
                <>
                  <Steps
                    labels={[
                      "Reference check",
                      "Documents",
                      "Salary approval",
                      "Signature",
                      "Joined",
                    ]}
                    current={cand.stage === "Offer Stage" ? 2 : 0}
                  />
                  <div className="checklist">
                    <p>✓ Manual background verification and reference notes</p>
                    <p>○ Request offer documents · 2 working-day deadline</p>
                    <p>○ Salary file → hiring-manager review → offer draft</p>
                    <p>○ Candidate review → electronic signature</p>
                    <p>
                      ○ Position closure notification → joining confirmation
                    </p>
                  </div>
                  <div className="notice">
                    A signed offer closes the opening. “Joined” is recorded only
                    after the person actually joins; an offer drop-out remains a
                    separate outcome.
                  </div>
                  <button onClick={() => open("offer")}>
                    Open offer workspace →
                  </button>
                </>
              )}
            </>
          )}
          {modal === "move" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setCandidateList(
                  candidateList.map((c, i) =>
                    i === selected
                      ? {
                          ...c,
                          stage: newStage,
                          note:
                            newStage === "Joined"
                              ? "Start onboarding & probation"
                              : "Next action assigned to recruiter",
                          days: 0,
                        }
                      : c,
                  ),
                );
                setActionLog([
                  ...actionLog,
                  `${cand.name}: ${cand.stage} → ${newStage} · Alex Morgan · preview`,
                ]);
                setModal("candidate");
                notify("Stage updated; communication is queued for review");
              }}
            >
              <h3>
                {cand.name}: {cand.stage} → {newStage}
              </h3>
              <Field
                label="Destination stage"
                options={stages}
                value={newStage}
                onChange={setNewStage}
              />
              <Field label="Reason / handover note" type="textarea" required />
              {newStage === "On Hold" && (
                <Field label="Promised update date" type="date" required />
              )}
              {newStage === "Assignment" && (
                <Field label="Assignment deadline" type="date" required />
              )}
              {newStage === "Joined" && (
                <Field label="Actual joining date" type="date" required />
              )}
              <div className="notice">
                This records the stage and audit note in the preview. Candidate
                communication remains a separate, reviewable action.
              </div>
              <div className="modalfooter">
                <button type="button" onClick={() => setModal("candidate")}>
                  Cancel
                </button>
                <button className="primary">Confirm stage change</button>
              </div>
            </form>
          )}
          {modal === "application" &&
            (formDone ? (
              <div className="success">
                <h2>You’re all set.</h2>
                <p>
                  Thanks for your interest in {brand}. The proposed receipt
                  explains the next steps and two-week response expectation.
                </p>
                {badge("Preview submission — nothing was sent", "green")}
                <button onClick={() => open("email")}>
                  Read application receipt →
                </button>
              </div>
            ) : (
              <>
                <div className="careershead">
                  <b>{brand}</b>
                  <span>Product Designer · {formCountry} · Full time</span>
                </div>
                <Steps
                  labels={["About you", "Work & relocation", "Your motivation"]}
                  current={applicationStep}
                />
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (applicationStep < 2)
                      setApplicationStep(applicationStep + 1);
                    else if (countWords >= 150 && countWords <= 250)
                      setFormDone(true);
                  }}
                >
                  {applicationStep === 0 ? (
                    <div className="formgrid">
                      <Field label="Full name" required />
                      <Field label="Email address" type="email" required />
                      <Field label="Phone number" type="tel" required />
                      <Field
                        label="Country / location"
                        options={countries}
                        value={formCountry}
                        onChange={setFormCountry}
                        required
                      />
                      <Field label="LinkedIn profile URL" type="url" required />
                      <Field
                        label="Website / portfolio (optional)"
                        type="url"
                      />
                      <Field
                        label="Resume / CV upload"
                        type="file"
                        required
                        hint="Preview only: selected files stay in your browser; no upload occurs."
                      />
                    </div>
                  ) : applicationStep === 1 ? (
                    <>
                      <Field
                        label={`Do you currently have the right to work in ${formCountry}?`}
                        required
                        options={[
                          "Select an answer",
                          "Yes, I have a valid work permit/visa",
                          "Yes, I am a citizen/permanent resident",
                          "No, I would require visa sponsorship",
                          "I’m unsure",
                        ]}
                      />
                      <Field
                        label={`Are you willing to relocate to ${formCountry === "Singapore" ? "Singapore" : formCountry === "India" ? "Bengaluru" : formCountry === "Vietnam" ? "Ho Chi Minh City" : "Jakarta"} if the role requires it?`}
                        required
                        options={["Yes", "No", "Depends on the role/terms"]}
                      />
                      <div className="notice">
                        Work authorisation answers provide context for the
                        hiring team. They do not automatically reject the
                        application.
                      </div>
                    </>
                  ) : (
                    <>
                      <Field
                        label={`Why are you interested in joining ${brand}?`}
                        type="textarea"
                        value={words}
                        onChange={setWords}
                        required
                      />
                      <p
                        className={
                          countWords < 150 || countWords > 250 ? "error" : ""
                        }
                      >
                        {countWords} / 150–250 words
                      </p>
                      <label className="checkbox">
                        <input type="checkbox" required />I consent to {brand}{" "}
                        processing this application for recruitment.
                      </label>
                      <div className="notice">
                        Automatic source capture (demo): {source} / {medium} /{" "}
                        {campaign}. Production records all UTM fields and
                        referrer without asking candidates to re-enter them.
                      </div>
                    </>
                  )}
                  <div className="modalfooter">
                    <button
                      type="button"
                      onClick={() =>
                        applicationStep
                          ? setApplicationStep(applicationStep - 1)
                          : setModal("")
                      }
                    >
                      {applicationStep ? "Back" : "Close"}
                    </button>
                    <button
                      className="primary"
                      disabled={
                        applicationStep === 2 &&
                        (countWords < 150 || countWords > 250)
                      }
                    >
                      {applicationStep === 2
                        ? "Submit preview application"
                        : "Continue →"}
                    </button>
                  </div>
                </form>
              </>
            ))}
          {modal === "referral" &&
            (formDone ? (
              <div className="success">
                <h2>Good people know good people.</h2>
                <p>
                  Your demo referral is ready for recruiter review. The referrer
                  is excluded from the candidate’s interview panel.
                </p>
                {badge("Preview only — no referral was sent", "green")}
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setFormDone(true);
                }}
              >
                <Steps
                  labels={[
                    "Your details",
                    "Candidate & consent",
                    "Relationship declaration",
                  ]}
                  current={1}
                />
                <h3>Your details</h3>
                <div className="formgrid">
                  <Field label="Your email address" type="email" required />
                  <Field label="Your full name" required />
                  <Field label="Your department / function" required />
                  <Field label="Your designation" required />
                  <Field
                    label="Your employment type"
                    options={["Full time", "Part time", "Contractor", "Intern"]}
                    required
                  />
                  <Field
                    label="Your employment entity"
                    options={countries.map((c) => brand + " " + c)}
                    required
                  />
                  <Field
                    label="Role referred for"
                    options={roleList
                      .filter((r) => r.state === "Open for candidates")
                      .map((r) => r.name)}
                    required
                  />
                  <Field
                    label="Has the candidate consented to this referral?"
                    options={["Yes", "No"]}
                    value={consent}
                    onChange={setConsent}
                    required
                  />
                </div>
                {consent === "No" ? (
                  <div className="notice">
                    Please obtain the candidate’s consent before providing their
                    information.
                  </div>
                ) : (
                  <>
                    <h3>Candidate details</h3>
                    <div className="formgrid">
                      {[
                        "Candidate full name",
                        "Candidate nationality",
                        "Candidate’s current location",
                        "Relationship with candidate",
                      ].map((x) => (
                        <Field key={x} label={x} required />
                      ))}
                      <Field
                        label="Candidate’s LinkedIn profile"
                        type="url"
                        required
                      />
                      <Field
                        label="Candidate’s updated resume"
                        type="file"
                        required
                      />
                      <Field
                        label="Candidate’s contact number"
                        type="tel"
                        required
                      />
                      <Field
                        label="Candidate’s email address"
                        type="email"
                        required
                      />
                      <Field
                        label="Remarks or important notes"
                        type="textarea"
                      />
                    </div>
                    <label className="checkbox">
                      <input type="checkbox" required />I confirm that I have
                      declared any personal or familial relationship with the
                      candidate above.
                    </label>
                    <label className="checkbox">
                      <input type="checkbox" required />I understand that I must
                      not be part of the interview panel if I’ve referred this
                      candidate.
                    </label>
                  </>
                )}
                <div className="modalfooter">
                  <span>Files stay in this browser in the preview.</span>
                  <button className="primary" disabled={consent === "No"}>
                    Submit demo referral →
                  </button>
                </div>
              </form>
            ))}
          {modal === "jd" && (
            <>
              <div className="tabs">
                {["Role content", "Company sections", "Preview & approve"].map(
                  (t) => (
                    <button
                      className={jdTab === t ? "active" : ""}
                      key={t}
                      onClick={() => setJdTab(t)}
                    >
                      {t}
                    </button>
                  ),
                )}
              </div>
              {jdTab === "Role content" ? (
                <>
                  <p>
                    Recruiters write these sections. Company defaults are
                    maintained centrally.
                  </p>
                  {Object.entries(jd).map(([k, v]) => (
                    <Field
                      key={k}
                      label={k}
                      type="textarea"
                      value={v}
                      onChange={(s) => setJd({ ...jd, [k]: s })}
                      required={!k.includes("optional")}
                    />
                  ))}
                  <button
                    className="primary"
                    onClick={() => setJdTab("Preview & approve")}
                  >
                    Preview complete JD →
                  </button>
                </>
              ) : jdTab === "Company sections" ? (
                <>
                  <div className="notice">
                    These five sections are shared across JDs for {brand}. Rize
                    uses the supplied wording; other tenants configure their own
                    story.
                  </div>
                  {(
                    companyJds[tenant] || [
                      [
                        "About " + brand,
                        `Introduce ${brand} and what it does.`,
                      ],
                      [
                        "What We Are Building",
                        "Describe your product or services.",
                      ],
                      ["Our Mission", "Describe your mission."],
                      ["Where We Operate", "List your locations."],
                      [
                        "Why Join " + brand,
                        "Describe your employee proposition.",
                      ],
                    ]
                  ).map(([k, v]) => (
                    <details key={k}>
                      <summary>
                        {k} {badge("Company default")}
                      </summary>
                      <Field
                        label={k + " text"}
                        type="textarea"
                        value={v}
                        onChange={(text) =>
                          setCompanyJds({
                            ...companyJds,
                            [tenant]: (
                              companyJds[tenant] || [
                                [
                                  "About " + brand,
                                  `Introduce ${brand} and what it does.`,
                                ],
                                [
                                  "What We Are Building",
                                  "Describe your product or services.",
                                ],
                                ["Our Mission", "Describe your mission."],
                                ["Where We Operate", "List your locations."],
                                [
                                  "Why Join " + brand,
                                  "Describe your employee proposition.",
                                ],
                              ]
                            ).map((row) => (row[0] === k ? [k, text] : row)),
                          })
                        }
                      />
                    </details>
                  ))}
                  <button
                    onClick={() =>
                      notify("Company wording saved for design review")
                    }
                  >
                    Save company wording
                  </button>
                </>
              ) : (
                <>
                  <div className="jdpreview">
                    <div className="eyebrow">{brand} CAREERS</div>
                    <h1>Product Designer</h1>
                    <p>Singapore · Product · Full time</p>
                    {(
                      companyJds[tenant] || [
                        [
                          "About " + brand,
                          `Join ${brand} and contribute to our next chapter.`,
                        ],
                      ]
                    ).map(([k, v]) => (
                      <section key={k}>
                        <h3>{k}</h3>
                        <p className="prewrap">{v}</p>
                      </section>
                    ))}
                    {Object.entries(jd).map(([k, v]) => (
                      <section key={k}>
                        <h3>{k}</h3>
                        <p>{v}</p>
                      </section>
                    ))}
                  </div>
                  <div className="modalfooter">
                    <span>Approval owner · Hiring manager</span>
                    <button
                      className="primary"
                      onClick={() =>
                        notify("JD submitted for hiring-manager approval")
                      }
                    >
                      Request JD approval
                    </button>
                  </div>
                </>
              )}
            </>
          )}
          {modal === "email" && (
            <>
              <div className="filters">
                <select
                  aria-label="Email template"
                  value={templateIndex}
                  onChange={(e) => setTemplateIndex(Number(e.target.value))}
                >
                  {emailList.map((e, i) => (
                    <option key={e.name} value={i}>
                      {e.name}
                    </option>
                  ))}
                </select>
                {badge("Trigger · " + currentEmail.trigger)}
              </div>
              <div className="twocol equal">
                <section>
                  <h3>Edit template</h3>
                  <Field
                    key={"subject" + templateIndex}
                    label="Subject"
                    value={currentEmail.subject}
                    onChange={(s) =>
                      setEmailList(
                        emailList.map((e, i) =>
                          i === templateIndex ? { ...e, subject: s } : e,
                        ),
                      )
                    }
                  />
                  <Field
                    key={"body" + templateIndex}
                    label="Message"
                    type="textarea"
                    value={currentEmail.body}
                    onChange={(s) =>
                      setEmailList(
                        emailList.map((e, i) =>
                          i === templateIndex ? { ...e, body: s } : e,
                        ),
                      )
                    }
                  />
                  <p>
                    Available tokens:{" "}
                    {
                      "{{first_name}}, {{role}}, {{brand}}, {{sender_name}}, {{website}}, {{linkedin}}"
                    }
                    . Context-specific fields resolve from the interview,
                    assignment or hold record.
                  </p>
                </section>
                <section className="emailpreview">
                  <div className="emailbrand">{brand}</div>
                  <h3>{resolve(currentEmail.subject)}</h3>
                  <div className="prewrap">{resolve(currentEmail.body)}</div>
                </section>
              </div>
              <div className="modalfooter">
                <span>
                  Preview uses fictional candidate Maya. Nothing is sent.
                </span>
                <button
                  className="primary"
                  onClick={() => notify("Template saved in this session")}
                >
                  Save template
                </button>
              </div>
            </>
          )}
          {modal === "review" && (
            <>
              <Steps
                labels={[
                  "Peer feedback",
                  "Manager & 1:1",
                  "HR review",
                  "Communicate",
                ]}
                current={reviewApproved ? 3 : reviewSent ? 2 : 1}
              />
              <div className="twocol">
                <section>
                  <h3>Peer feedback · 3 responses</h3>
                  <p>
                    Scale: 1 strongly disagree → 4 strongly agree. Aggregated
                    feedback visible only to authorised reviewers.
                  </p>
                  {[
                    ["Enjoys working together", "3.7"],
                    ["Communication", "3.3"],
                    ["Execution", "3.7"],
                    ["Beyond responsibilities", "3.0"],
                    ["Quality & timeliness", "3.7"],
                    ["Recommend permanent position", "3.7"],
                  ].map((x) => (
                    <div className="scoreline" key={x[0]}>
                      <span>{x[0]}</span>
                      <div>
                        <i style={{ width: (Number(x[1]) / 4) * 100 + "%" }} />
                      </div>
                      <b>{x[1]} / 4</b>
                    </div>
                  ))}
                  <h3>Qualitative feedback</h3>
                  <p>
                    <b>Strengths:</b> Thoughtful field preparation, reliable
                    follow-through and collaborative problem-solving.
                  </p>
                  <p>
                    <b>Development:</b> Communicate risks earlier; simplify
                    handovers; build confidence presenting recommendations.
                  </p>
                  <button onClick={() => open("peer-feedback")}>
                    Preview peer feedback form
                  </button>
                </section>
                <section className="panel">
                  <h3>Readiness to decide</h3>
                  <div className="checklist">
                    <p>✓ 3 / 3 peer responses complete</p>
                    <p>✓ Agronomist training · 4 / 4 modules</p>
                    <p>✓ 30-day and 60-day check-ins recorded</p>
                    <p>✓ Review opened 21 days before end date</p>
                  </div>
                  {badge("Decision due 30 September", "amber")}
                  <p>
                    Recommendations go to the HR Lead. Leadership / regional
                    positions also go to the CEO. Clarifications must be
                    resolved before the employee is told.
                  </p>
                </section>
              </div>
              {reviewApproved ? (
                <div className="nextaction">
                  <div>
                    <h3>Ready to communicate: {verdict}</h3>
                    <p>
                      HR has reviewed the recommendation in this preview. The
                      manager communicates the decision; HR prepares the outcome
                      letter.
                    </p>
                  </div>
                  <button className="primary" onClick={() => open("outcome")}>
                    Preview outcome letter
                  </button>
                </div>
              ) : reviewSent ? (
                <div className="nextaction">
                  <div>
                    <h3>HR review pending</h3>
                    <p>
                      Manager recommendation: {verdict}. No employee status has
                      changed.
                    </p>
                  </div>
                  <button
                    className="primary"
                    onClick={() => {
                      setReviewApproved(true);
                      notify("HR approval recorded in preview");
                    }}
                  >
                    Simulate HR approval →
                  </button>
                </div>
              ) : (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    setReviewSent(true);
                    notify("Recommendation routed to HR");
                  }}
                >
                  <hr />
                  <h3>Manager evaluation</h3>
                  <p>
                    Scale: 1 Below Expectations · 2 Slightly Below · 3 Slightly
                    Above · 4 Above Expectations
                  </p>
                  <div className="formgrid">
                    {[
                      "Quality of work and productivity",
                      "Team and culture fit",
                      "Adaptability",
                      "Initiative and resourcefulness",
                    ].map((x) => (
                      <Field
                        key={x}
                        label={x}
                        options={["1", "2", "3", "4"]}
                        value={reviewScores[x] || "3"}
                        onChange={(v) =>
                          setReviewScores({ ...reviewScores, [x]: v })
                        }
                      />
                    ))}
                    <Field
                      label="Leadership capabilities"
                      options={["Not applicable", "1", "2", "3", "4"]}
                    />
                    <Field label="1:1 conducted on" type="date" required />
                    <Field
                      label="Strengths with examples"
                      type="textarea"
                      required
                    />
                    <Field
                      label="Areas for improvement"
                      type="textarea"
                      required
                    />
                    <Field
                      label="Manager recommendation"
                      options={["Confirm", "Extend", "Not passed"]}
                      value={verdict}
                      onChange={setVerdict}
                    />
                    {verdict === "Extend" && (
                      <>
                        <Field
                          label="Specific improvement outcomes"
                          type="textarea"
                          required
                        />
                        <Field label="Proposed end date" type="date" required />
                        <div className="notice full">
                          Default improvement horizon: 1 month. Country policy
                          and employment terms must permit the chosen action.
                          Vietnam exceptions require HR review; no automatic
                          contract or role change.
                        </div>
                      </>
                    )}
                    {verdict === "Not passed" && (
                      <div className="notice full">
                        HR reviews the proposed exit and applicable country
                        process before any employee communication or status
                        change.
                      </div>
                    )}
                  </div>
                  <div className="modalfooter">
                    <span>
                      Employee status changes only after approval and
                      communication.
                    </span>
                    <button className="primary">Submit recommendation →</button>
                  </div>
                </form>
              )}
            </>
          )}
          {modal === "nominate" && (
            <>
              <p>
                Select 3–4 colleagues with meaningful interaction during the
                probation period. Managers can include peers, reports and
                leadership.
              </p>
              {[
                "Alex Morgan",
                "Sam Lee",
                "Kai Lim",
                "Nora Patel",
                "Taylor James",
              ].map((n) => (
                <label className="peeroption" key={n}>
                  <span className="avatar">
                    {n
                      .split(" ")
                      .map((x) => x[0])
                      .join("")}
                  </span>
                  <span>
                    {n}
                    <small>Cross-functional colleague · Demo</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={peers.includes(n)}
                    onChange={(e) =>
                      setPeers(
                        e.target.checked
                          ? [...peers, n]
                          : peers.filter((p) => p !== n),
                      )
                    }
                  />
                </label>
              ))}
              <div className="notice">
                {peers.length} selected · Feedback due in 3 working days.
                Reminder 2 hours before the deadline; one 1-day extension can be
                requested.
              </div>
              <div className="modalfooter">
                <button onClick={() => open("peer-feedback")}>
                  Preview feedback form
                </button>
                <button
                  className="primary"
                  disabled={peers.length < 3 || peers.length > 4}
                  onClick={() => {
                    setNominationSent(true);
                    setModal("");
                    notify("Peer nominations recorded");
                  }}
                >
                  Confirm nominations →
                </button>
              </div>
            </>
          )}
          {modal === "peer-feedback" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                notify("Confidential peer feedback recorded");
                setModal("review");
              }}
            >
              <h3>Peer feedback for Linh Nguyen</h3>
              <p>
                Feedback is confidential and shared only with authorised people
                involved in the review.
              </p>
              <Field
                label="How often do you professionally engage with this colleague?"
                options={[
                  "Very regularly — almost daily",
                  "Regularly — at least weekly",
                  "Infrequently — less than weekly",
                  "Hardly ever",
                ]}
              />
              <p>
                Scale: 1 Strongly disagree · 2 Disagree · 3 Agree · 4 Strongly
                agree
              </p>
              {[
                "I enjoy working with the employee",
                "The employee communicates effectively and efficiently",
                "The employee demonstrates strong execution capabilities for their role",
                "The employee goes beyond official responsibilities when required",
                "The employee produces good quality deliverables in a timely fashion",
                "I would recommend the employee for a permanent position",
              ].map((x) => (
                <Field label={x} key={x} options={["1", "2", "3", "4"]} />
              ))}
              <Field label="Three areas of strength" type="textarea" required />
              <Field
                label="Three areas for improvement"
                type="textarea"
                required
              />
              <Field label="Further comments or suggestions" type="textarea" />
              <button className="primary">Submit demo feedback</button>
            </form>
          )}
          {modal === "policy" && (
            <>
              <div className="notice">
                Rize profile: full-time employees only; excludes interns and
                consultants. Defaults shown for review, not a statement of
                country law.
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  notify("Policy configuration saved in preview");
                }}
              >
                <div className="formgrid">
                  <Field label="Country" options={countries} />
                  <Field
                    label="Probation duration (months)"
                    options={["2", "3"]}
                  />
                  <Field
                    label="Open evaluation days before end"
                    type="number"
                    value="21"
                  />
                  <Field
                    label="Peer nomination range"
                    options={["3–4 (SOP default)", "3–5 (original proposal)"]}
                  />
                  <Field
                    label="Feedback window (working days)"
                    options={["3", "2"]}
                  />
                  <Field
                    label="Manager 1:1 window (working days)"
                    value="2"
                    type="number"
                  />
                  <Field
                    label="Reminder before deadline (hours)"
                    value="2"
                    type="number"
                  />
                  <Field
                    label="One-time extension (working days)"
                    value="1"
                    type="number"
                  />
                  <Field
                    label="Improvement horizon (months)"
                    value="1"
                    type="number"
                  />
                  <Field label="Final review owner" value="HR Lead" />
                  <Field
                    label="Leadership / regional additional reviewer"
                    value="CEO"
                  />
                  <Field
                    label="HR reminder milestones (days before end)"
                    value="15, 5"
                  />
                </div>
                <label className="checkbox">
                  <input type="checkbox" defaultChecked />
                  Require mandatory agronomist training before clearance
                </label>
                <label className="checkbox">
                  <input type="checkbox" defaultChecked />
                  Plan 30, 60 and 90-day HRBP check-ins
                </label>
                <label className="checkbox">
                  <input type="checkbox" defaultChecked />
                  Hold employee communication while approval questions remain
                  open
                </label>
                <div className="modalfooter">
                  <span>
                    Policy revisions retain effective dates and history in
                    production.
                  </span>
                  <button className="primary">Save preview policy</button>
                </div>
              </form>
            </>
          )}
          {modal === "import" && (
            <>
              <Steps
                labels={[
                  "Read workbook",
                  "Reconcile sources",
                  "Review impact",
                  "Publish",
                ]}
                current={unresolved.length ? 1 : 2}
              />
              <h3>2026 calendar · four entities</h3>
              <p>
                Indonesia: 18 dates · Vietnam: 13 · Singapore: 11 · India
                (Karnataka): 13, before source reconciliation.
              </p>
              <div className="notice">
                Two discrepancies: Pancasila Day (1 June, Indonesia) and Vietnam
                Cultural Day (24 November) appear only in country sheets. No
                dates will silently disappear or be duplicated.
              </div>
              <div className="quickgrid">
                <div className="panel">
                  <h3>Entity calendars</h3>
                  <p>
                    Attach each date to the correct country and legal entity.
                  </p>
                </div>
                <div className="panel">
                  <h3>Working-day deadlines</h3>
                  <p>
                    Recalculate hiring and probation due dates against the
                    assigned calendar.
                  </p>
                </div>
                <div className="panel">
                  <h3>Interview planning</h3>
                  <p>
                    Warn when candidate or panel locations observe a day off.
                  </p>
                </div>
              </div>
              <div className="modalfooter">
                <span>
                  Draft dates need HR validation before production import.
                </span>
                <button
                  className="primary"
                  onClick={() => {
                    setModal("");
                    setHolidayTab("Import review");
                  }}
                >
                  Resolve differences →
                </button>
              </div>
            </>
          )}
          {modal === "schedule" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setScheduleDone(true);
                notify("Interview scheduled in preview");
                setModal("");
              }}
            >
              <div className="formgrid">
                <Field
                  label="Candidate"
                  options={candidateList.map((c) => c.name)}
                />
                <Field
                  label="Interview stage"
                  options={[
                    "Recruiter Phone Call",
                    "Discussion 1",
                    "Discussion 2",
                    "Discussion 3",
                  ]}
                />
                <Field label="Date" type="date" required />
                <Field label="Time" type="time" required />
                <Field
                  label="Time zone"
                  options={[
                    "Asia/Singapore · UTC+8",
                    "Asia/Ho_Chi_Minh · UTC+7",
                    "Asia/Jakarta · UTC+7",
                    "Asia/Kolkata · UTC+5:30",
                  ]}
                />
                <Field
                  label="Duration (minutes)"
                  options={["30", "45", "60"]}
                />
                <Field
                  label="Interviewer"
                  options={["Alex Morgan", "Kai Lim", "Sam Lee"]}
                />
                <Field label="Agenda / focus" type="textarea" required />
                <Field
                  label="Rescheduling reason (if applicable)"
                  type="textarea"
                />
                <Field
                  label="Delay attribution"
                  options={["Not a reschedule", "Internal", "External"]}
                />
              </div>
              <div className="notice">
                Production checks panel conflicts, referral conflicts and entity
                holidays before invitation. Calendar integration: Google
                Calendar; email and calendar invites to candidate, interviewer
                and recruiter. Reminders at 24 hours and 30 minutes.
              </div>
              <button className="primary">Schedule demo interview</button>
            </form>
          )}
          {modal === "feedback" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setFeedbackSaved(true);
                notify("Scorecard submitted");
                setModal("candidate");
                setCandidateTab("Interview & feedback");
              }}
            >
              <h3>Product craft & systems thinking</h3>
              <p>
                Ask for a concrete example of simplifying a complex workflow.
                Probe choices, trade-offs, accessibility and outcomes.
              </p>
              <div className="notice">
                Your scorecard is independent. Other interviewer responses
                remain hidden until you submit. Due within 24 working hours.
              </div>
              {[
                "Problem framing",
                "Design craft",
                "Collaboration",
                "Clarity of thinking",
              ].map((x) => (
                <Field
                  key={x}
                  label={x}
                  options={[
                    "Not assessed",
                    "Strong no",
                    "No",
                    "Yes",
                    "Strong yes",
                  ]}
                />
              ))}
              <Field label="Evidence and examples" type="textarea" required />
              <Field
                label="Recommendation"
                options={[
                  "Move forward",
                  "Discuss in debrief",
                  "Do not progress",
                ]}
              />
              <button className="primary">Submit demo scorecard</button>
            </form>
          )}
          {modal === "settings" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                notify("Workspace configuration saved in preview");
              }}
            >
              <div className="formgrid">
                <Field
                  label="Client legal name"
                  value={tenant === "Rize" ? "Rize Farm" : tenant}
                />
                <Field
                  label="Candidate-facing brand name"
                  value={brand}
                  onChange={setBrand}
                />
                <Field
                  label="Website"
                  value={
                    tenant === "Rize"
                      ? "https://rize.farm"
                      : "https://company.example"
                  }
                />
                <Field label="LinkedIn URL" type="url" />
                <Field
                  label="MR approver role"
                  value={tenant === "Rize" ? "Dhruv" : "Configured approver"}
                />
                <Field label="Country recruiter" value="Alex Morgan" />
                <Field label="Recruiter manager" value="Sam Lee" />
                <Field
                  label="Application acknowledgement"
                  options={["Automatic on receipt", "Review before send"]}
                />
              </div>
              <div className="notice">
                Legal entity name, short brand name, links, JD sections, email
                templates and routing are independent tenant settings.
                Rize-specific prose is never inherited by Acme.
              </div>
              <button className="primary">Save preview settings</button>
            </form>
          )}
          {modal === "guide" && (
            <>
              <h2>One connected experience.</h2>
              <p>
                This is a design preview before application implementation. Try
                the paths below; every email, approval, upload and calendar
                action is simulated.
              </p>
              <div className="quickgrid">
                {[
                  [
                    "Hiring",
                    "Request a role, review candidates and edit communication.",
                  ],
                  [
                    "Probation",
                    "Read peer feedback, record a 1:1 and route the decision.",
                  ],
                  [
                    "Holiday Calendar",
                    "Compare entities and reconcile conflicting workbook dates.",
                  ],
                ].map((x) => (
                  <button
                    className="quickcard"
                    key={x[0]}
                    onClick={() => {
                      go(x[0]);
                      setModal("");
                    }}
                  >
                    <h3>{x[0]}</h3>
                    <p>{x[1]}</p>
                  </button>
                ))}
              </div>
              <h3>Design research</h3>
              <p>
                Connected pipeline and interview-plan patterns informed by{" "}
                <a
                  href="https://www.ashbyhq.com/platform/recruiting/ats"
                  target="_blank"
                  rel="noreferrer"
                >
                  Ashby
                </a>
                ; structured, independent scorecards informed by{" "}
                <a
                  href="https://support.greenhouse.io/hc/en-us/articles/4414777492891-Scorecard-overview"
                  target="_blank"
                  rel="noreferrer"
                >
                  Greenhouse
                </a>
                . Visual tokens come from the existing Payobook theme.
              </p>
              <h3>Source decisions to resolve</h3>
              <p>
                Probation peer range: SOP says 3–4, original workbook says 3–5.
                The SOP is the provisional default. Holiday country sheets are
                the provisional source; differences remain visible in Import
                review.
              </p>
              <p>
                Original proposal has no “Holiday Calendar” tab. The supplied
                holiday workbook is used for that module. Full requirements and
                implementation mapping accompany the preview in the repository.
              </p>
            </>
          )}
          {modal === "offer" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                notify("Offer saved for hiring-manager review");
              }}
            >
              <Steps
                labels={[
                  "BGV",
                  "Documents",
                  "Salary review",
                  "Offer & signature",
                  "Joining",
                ]}
                current={2}
              />
              <div className="formgrid">
                <Field
                  label="Reference / BGV findings"
                  type="textarea"
                  required
                />
                <Field label="BGV evidence" type="file" />
                <Field label="Salary file" type="file" />
                <Field label="Annual salary" type="number" required />
                <Field
                  label="Currency"
                  options={["SGD", "VND", "IDR", "INR"]}
                />
                <Field label="Proposed joining date" type="date" required />
              </div>
              <div className="notice">
                Offer draft is blocked until reference checks and required
                documents are complete. Signature provider is tenant-configured
                (DocuSign / Zoho). Nothing is sent by this preview.
              </div>
              <button className="primary">Save for manager review</button>
            </form>
          )}
          {modal === "outcome" && (
            <>
              <div className="emailpreview">
                <div className="emailbrand">{brand}</div>
                <h3>Probation outcome · {verdict}</h3>
                <p>Dear Linh,</p>
                <p>
                  {verdict === "Confirm"
                    ? "Congratulations on successfully completing your probation. We look forward to your continued contribution."
                    : verdict === "Extend"
                      ? "Following our review, we propose a defined improvement period. Your confirmed timeline, support and specific outcomes will be included in the approved letter."
                      : "Following our review and discussion, HR will communicate the approved outcome and applicable next steps directly."}
                </p>
                <p>
                  Talent Team
                  <br />
                  {brand}
                </p>
              </div>
              <div className="notice">
                Proposed outcome template. Production requires the approved
                decision, dates and improvement plan before communication.
                Archived with the evaluation and correspondence.
              </div>
              <button
                onClick={() =>
                  notify("Outcome communication recorded in preview")
                }
              >
                Simulate communication complete
              </button>
            </>
          )}
          {[
            "no-show",
            "debrief",
            "delegation",
            "checkin",
            "holiday-detail",
            "leave-policy",
          ].includes(modal) && (
            <Auxiliary
              kind={modal}
              brand={brand}
              notify={notify}
              country={country}
            />
          )}
        </Modal>
      )}
    </div>
  );
}
function Auxiliary({
  kind,
  brand,
  notify,
  country,
}: {
  kind: string;
  brand: string;
  notify: (s: string) => void;
  country: string;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        notify("Record saved in this session");
      }}
    >
      {kind === "no-show" ? (
        <>
          <Field
            label="Person who did not attend"
            options={["Candidate", "Interviewer"]}
          />
          <Field label="Delay attribution" options={["External", "Internal"]} />
          <Field label="Reason / circumstances" type="textarea" required />
          <div className="notice">
            Rescheduling requests should be made at least 30 minutes before the
            meeting. All no-shows are logged.
          </div>
        </>
      ) : kind === "debrief" ? (
        <>
          <Field label="Panel debrief notes" type="textarea" required />
          <Field
            label="Final selection decision"
            options={[
              "Proceed to reference check",
              "Further discussion required",
              "Interview Reject",
            ]}
          />
        </>
      ) : kind === "delegation" ? (
        <>
          <Field label="Covering recruiter" options={["Sam Lee", "Kai Lim"]} />
          <Field label="From" type="date" required />
          <Field label="Until" type="date" required />
          <Field label="Reason for delegation" type="textarea" required />
          <div className="notice">
            Recruiter-manager approval is required. Role responsibility and all
            changes remain in the audit log.
          </div>
        </>
      ) : kind === "checkin" ? (
        <>
          <Field
            label="Milestone"
            options={["30 days", "60 days", "90 days"]}
          />
          <Field label="HRBP" value="Alex Morgan" />
          <Field label="How are things going?" type="textarea" required />
          <Field
            label="Support needed / follow-up actions"
            type="textarea"
            required
          />
          <Field label="Next check-in date" type="date" />
        </>
      ) : kind === "holiday-detail" ? (
        <>
          <h3>
            {country} · {brand} entity calendar
          </h3>
          <p>
            Dates come from the supplied 2026 workbook. The draft calendar is
            used to illustrate visibility, country filtering and scheduling
            context.
          </p>
          <Field
            label="Holiday category"
            options={[
              "National / festival holiday",
              "Company holiday",
              "Collective leave",
            ]}
          />
          <Field label="HR review note" type="textarea" />
        </>
      ) : (
        <>
          <h3>Full leave matrix</h3>
          <p>
            Supplied workbook values, retained verbatim for HR review. These are
            client policy inputs, not verified statutory entitlements.
          </p>
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  <th>Leave</th>
                  {countries.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                  <th>Rule</th>
                </tr>
              </thead>
              <tbody>
                {leavePolicies.map((p) => (
                  <tr key={p.name}>
                    <td>{p.name}</td>
                    {countries.map((c) => (
                      <td key={c}>{(p as Record<string, string>)[c]}</td>
                    ))}
                    <td>{p.rule}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="notice">
            Entitlements are not imported by this preview. Production setup must
            review country eligibility, employment terms and current rules
            before enabling balances.
          </div>
        </>
      )}
      <button className="primary">Save preview record</button>
    </form>
  );
}
