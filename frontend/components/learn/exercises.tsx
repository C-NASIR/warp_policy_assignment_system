"use client";

import { CheckCircle2, CircleAlert, FlaskConical, RotateCcw } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { resolveAveryAssignments, resolveEffectiveDateOutcome, resolvePriorityOutcome } from "@/lib/learn-exercises";

const progressKey = "policyos-learn-progress-v1";

function PracticeBanner() {
  return <div className="learn-practice-banner"><FlaskConical size={16} /><span><strong>Isolated practice</strong><small>Uses fictional data in this browser only. Nothing is sent to or saved in your workspace.</small></span></div>;
}

export function LessonProgress({ articleId, total }: { articleId: string; total: number }) {
  const [ready, setReady] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [completed, setCompleted] = useState<string[]>([]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        const stored = window.localStorage.getItem(progressKey);
        if (stored) {
          const parsed = JSON.parse(stored) as { enabled?: boolean; completed?: string[] };
          setEnabled(parsed.enabled === true);
          setCompleted(Array.isArray(parsed.completed) ? parsed.completed.filter((item): item is string => typeof item === "string") : []);
        }
      } catch {
        window.localStorage.removeItem(progressKey);
      }
      setReady(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function save(nextEnabled: boolean, nextCompleted: string[]) {
    setEnabled(nextEnabled);
    setCompleted(nextCompleted);
    if (nextEnabled) window.localStorage.setItem(progressKey, JSON.stringify({ enabled: true, completed: nextCompleted }));
    else window.localStorage.removeItem(progressKey);
  }

  if (!ready) return <div className="learn-progress-placeholder" aria-hidden="true" />;

  if (!enabled) {
    return <button className="learn-progress-enable" type="button" onClick={() => save(true, [])}>Track lesson progress on this device</button>;
  }

  const isComplete = completed.includes(articleId);
  return <div className="learn-progress"><label><input type="checkbox" checked={isComplete} onChange={(event) => save(true, event.target.checked ? [...new Set([...completed, articleId])] : completed.filter((item) => item !== articleId))} /><span><strong>{isComplete ? "Lesson complete" : "Mark lesson complete"}</strong><small>{completed.length} of {total} articles completed on this device</small></span></label><button type="button" onClick={() => save(false, [])}>Stop tracking</button></div>;
}

export function AveryAssignmentLab() {
  const [state, setState] = useState("California");
  const [department, setDepartment] = useState("Engineering");
  const [employmentType, setEmploymentType] = useState("Full-time");
  const [location, setLocation] = useState("San Francisco");
  const [engineeringGroup, setEngineeringGroup] = useState(true);
  const [override, setOverride] = useState(false);
  const [payPrediction, setPayPrediction] = useState("");
  const [accessPrediction, setAccessPrediction] = useState("");
  const [checked, setChecked] = useState(false);
  const results = useMemo(() => resolveAveryAssignments({ state, department, employmentType, location, engineeringGroup, override }), [state, department, employmentType, location, engineeringGroup, override]);
  const pay = results.find((item) => item.field === "Pay schedule")?.values[0] ?? "No assignment";
  const accessCount = results.find((item) => item.field === "Application access")?.values.length ?? 0;
  const correct = payPrediction === pay && Number(accessPrediction) === accessCount;

  function reset() {
    setState("California"); setDepartment("Engineering"); setEmploymentType("Full-time"); setLocation("San Francisco"); setEngineeringGroup(true); setOverride(false); setPayPrediction(""); setAccessPrediction(""); setChecked(false);
  }

  return <div className="learn-exercise"><PracticeBanner /><div className="learn-exercise-head"><div><p className="eyebrow">Employee facts → assignments</p><h2>Avery assignment lab</h2><p>Change the facts and explicit membership, predict two outcomes, then inspect every explanation.</p></div><button type="button" className="button secondary small" onClick={reset}><RotateCcw size={13} /> Reset</button></div><div className="learn-exercise-grid"><section><h3>Fictional inputs</h3><div className="learn-control-grid"><label>State<select value={state} onChange={(event) => { setState(event.target.value); setChecked(false); }}><option>California</option><option>Texas</option></select></label><label>Department<select value={department} onChange={(event) => { setDepartment(event.target.value); setChecked(false); }}><option>Engineering</option><option>Product</option></select></label><label>Employee type<select value={employmentType} onChange={(event) => { setEmploymentType(event.target.value); setChecked(false); }}><option>Full-time</option><option>Contractor</option></select></label><label>Work location<select value={location} onChange={(event) => { setLocation(event.target.value); setChecked(false); }}><option>San Francisco</option><option>Remote</option></select></label></div><label className="learn-check"><input type="checkbox" checked={engineeringGroup} onChange={(event) => { setEngineeringGroup(event.target.checked); setChecked(false); }} /> Explicit Engineering group membership</label><label className="learn-check"><input type="checkbox" checked={override} onChange={(event) => { setOverride(event.target.checked); setChecked(false); }} /> Monthly Pay schedule override</label></section><section><h3>Your prediction</h3><label>Pay schedule<select value={payPrediction} onChange={(event) => { setPayPrediction(event.target.value); setChecked(false); }}><option value="">Choose…</option><option>Bi-weekly</option><option>Semi-monthly</option><option>Monthly</option><option>No assignment</option></select></label><label>Application access value count<select value={accessPrediction} onChange={(event) => { setAccessPrediction(event.target.value); setChecked(false); }}><option value="">Choose…</option><option value="0">0</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></label><button className="button" type="button" disabled={!payPrediction || accessPrediction === ""} onClick={() => setChecked(true)}>Check prediction</button>{checked && <Feedback correct={correct}>{correct ? "Correct. Your prediction follows matching, group origin, cardinality, priority, and override order." : `Not yet. The resolved pay value is ${pay}, with ${accessCount} Application access value${accessCount === 1 ? "" : "s"}. Read the explanations and try another combination.`}</Feedback>}</section></div>{checked && <div className="learn-results" aria-live="polite">{results.length ? results.map((item) => <article key={item.field}><span>{item.field}</span><strong>{item.values.join(", ")}</strong><small>{item.explanation}</small></article>) : <p>No assignments resolve for this combination.</p>}</div>}</div>;
}

export function PriorityLab() {
  const [cardinality, setCardinality] = useState<"one" | "many">("one");
  const [californiaPriority, setCaliforniaPriority] = useState(20);
  const [usPriority, setUsPriority] = useState(10);
  const [prediction, setPrediction] = useState("");
  const [checked, setChecked] = useState(false);
  const outcome = resolvePriorityOutcome(cardinality, californiaPriority, usPriority);

  return <div className="learn-exercise"><PracticeBanner /><div className="learn-exercise-head"><div><p className="eyebrow">Candidate resolution</p><h2>Priority and cardinality lab</h2><p>Use the same two values to see why one fields select while many fields combine.</p></div></div><div className="learn-exercise-grid"><section><label>Field cardinality<select value={cardinality} onChange={(event) => { setCardinality(event.target.value as "one" | "many"); setPrediction(""); setChecked(false); }}><option value="one">One value</option><option value="many">Many values</option></select></label><label>California Pay priority <strong>{californiaPriority}</strong><input type="range" min="0" max="30" value={californiaPriority} onChange={(event) => { setCaliforniaPriority(Number(event.target.value)); setChecked(false); }} /></label><label>US Employee Pay priority <strong>{usPriority}</strong><input type="range" min="0" max="30" value={usPriority} onChange={(event) => { setUsPriority(Number(event.target.value)); setChecked(false); }} /></label></section><section><label>Predict the result<select value={prediction} onChange={(event) => { setPrediction(event.target.value); setChecked(false); }}><option value="">Choose…</option><option>Bi-weekly</option><option>Semi-monthly</option><option>Bi-weekly + Semi-monthly</option><option>Conflict</option></select></label><button className="button" type="button" disabled={!prediction} onClick={() => setChecked(true)}>Resolve candidates</button>{checked && <Feedback correct={prediction === outcome}>{prediction === outcome ? `Correct: ${outcome}.` : `The result is ${outcome}. ${cardinality === "many" ? "Different unique values are retained regardless of priority." : californiaPriority === usPriority ? "Different top-ranked values make a deliberate conflict." : "The higher-priority candidate wins."}`}</Feedback>}</section></div></div>;
}

export function EffectiveDateLab() {
  const [versionOneEnd, setVersionOneEnd] = useState("2026-09-30");
  const [versionTwoStart, setVersionTwoStart] = useState("2026-10-01");
  const [evaluationDate, setEvaluationDate] = useState("2026-10-01");
  const [prediction, setPrediction] = useState("");
  const [checked, setChecked] = useState(false);
  const overlap = versionOneEnd >= versionTwoStart;
  const outcome = resolveEffectiveDateOutcome(versionOneEnd, versionTwoStart, evaluationDate);

  return <div className="learn-exercise"><PracticeBanner /><div className="learn-exercise-head"><div><p className="eyebrow">Evaluation date → version</p><h2>Effective-date lab</h2><p>Move the inclusive boundaries, create a gap or overlap, and predict which version can participate.</p></div></div><div className="learn-exercise-grid"><section><label>Version 1 ends<input type="date" min="2026-09-01" value={versionOneEnd} onChange={(event) => { if (event.target.value) setVersionOneEnd(event.target.value); setChecked(false); }} /></label><label>Version 2 starts<input type="date" value={versionTwoStart} onChange={(event) => { if (event.target.value) setVersionTwoStart(event.target.value); setChecked(false); }} /></label><label>Evaluation date<input type="date" value={evaluationDate} onChange={(event) => { if (event.target.value) setEvaluationDate(event.target.value); setChecked(false); }} /></label>{overlap && <p className="learn-inline-warning"><CircleAlert size={14} /> PolicyOS rejects overlapping version ranges.</p>}</section><section><label>Predict the effective result<select value={prediction} onChange={(event) => { setPrediction(event.target.value); setChecked(false); }}><option value="">Choose…</option><option>Bi-weekly (version 1)</option><option>Weekly (version 2)</option><option>No policy result (gap)</option><option>Invalid overlap</option></select></label><button className="button" type="button" disabled={!prediction} onClick={() => setChecked(true)}>Check date</button>{checked && <Feedback correct={prediction === outcome}>{prediction === outcome ? `Correct: ${outcome}.` : `The result is ${outcome}. Start and end dates are inclusive, gaps supply no behavior, and overlaps are invalid.`}</Feedback>}</section></div></div>;
}

const questions = [
  { prompt: "Avery is in the Engineering group but does not match Engineering Access directly. Does the policy apply?", options: ["No", "Yes, through the group", "Only after an override"], answer: "Yes, through the group", explanation: "Explicit group attachment is an independent policy origin." },
  { prompt: "Two different values tie at the highest priority on a one field. What happens?", options: ["The oldest wins", "Both are retained", "Resolution reports a conflict"], answer: "Resolution reports a conflict", explanation: "PolicyOS will not choose an arbitrary one-field winner." },
  { prompt: "What does an override do to a many-value field?", options: ["Adds one value", "Replaces the complete policy-derived set", "Lowers policy priority"], answer: "Replaces the complete policy-derived set", explanation: "Overrides are field-level replacement after policy resolution." },
  { prompt: "Which record answers who changed Avery's assignment?", options: ["Assignment history", "Audit log", "Policy match count"], answer: "Audit log", explanation: "Audit records actor and action; history records what value was true." },
  { prompt: "Does approving a sensitive request commit it?", options: ["Yes", "No, the approving user must execute it", "Only in demo mode"], answer: "No, the approving user must execute it", explanation: "Approval authorizes the exact request; execution commits it." },
] as const;

export function AveryKnowledgeCheck() {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const score = questions.reduce((total, question, index) => total + (answers[index] === question.answer ? 1 : 0), 0);

  function submit(event: FormEvent) { event.preventDefault(); setSubmitted(true); }
  return <form className="learn-exercise learn-quiz" onSubmit={submit}><PracticeBanner /><div className="learn-exercise-head"><div><p className="eyebrow">Five-question check</p><h2>Explain Avery&apos;s result</h2><p>Select one answer for every question. Feedback remains on this page and is never submitted.</p></div></div>{questions.map((question, index) => <fieldset key={question.prompt}><legend>{index + 1}. {question.prompt}</legend>{question.options.map((option) => <label key={option}><input type="radio" name={`question-${index}`} value={option} checked={answers[index] === option} onChange={() => { setAnswers((current) => ({ ...current, [index]: option })); setSubmitted(false); }} /> {option}</label>)}{submitted && <Feedback correct={answers[index] === question.answer}>{question.explanation}</Feedback>}</fieldset>)}<div className="learn-quiz-footer"><button className="button" disabled={Object.keys(answers).length !== questions.length}>Check all answers</button>{submitted && <strong aria-live="polite">{score} of {questions.length} correct{score === questions.length ? " — course complete." : " — review the feedback and try again."}</strong>}</div></form>;
}

function Feedback({ correct, children }: { correct: boolean; children: React.ReactNode }) {
  return <p className={`learn-feedback ${correct ? "correct" : "incorrect"}`} role="status">{correct ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}<span>{children}</span></p>;
}
