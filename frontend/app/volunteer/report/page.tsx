"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, Info, ShieldCheck } from "../../../components/icons";
import { ApiError, createVolunteerReportRequest, getMeRequest, HarmType } from "../../../lib/api";
import { categoryLabels, ViolationCategory } from "../../../lib/review-data";

const categories: ViolationCategory[] = ["sexual_violence", "child_related_harm", "hate_related", "other"];
const harmTypeLabels: Record<HarmType, string> = {
  threat_incitement: "Threat or incitement",
  glorification: "Glorification or justification",
  mockery: "Mockery or jokes",
  victim_identification: "Identifies or exposes a survivor",
  stigmatization: "Shames survivors or families",
  sexually_explicit: "Sexually explicit",
  denial_or_disinformation: "Denial or disinformation",
  unverified_claim: "Unverified claim of an incident",
};
const urgencies = [
  { value: "urgent", label: "Urgent", help: "Immediate risk to a person (threat, exposed survivor)" },
  { value: "high", label: "High", help: "Clearly harmful, spreading" },
  { value: "standard", label: "Standard", help: "Needs a check" },
] as const;

export default function VolunteerReportPage() {
  const [ready, setReady] = useState(false);
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState<ViolationCategory>("sexual_violence");
  const [harmTypes, setHarmTypes] = useState<HarmType[]>([]);
  const [urgency, setUrgency] = useState<(typeof urgencies)[number]["value"]>("high");
  const [context, setContext] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ reference: string; duplicate: boolean } | null>(null);

  useEffect(() => {
    getMeRequest()
      .then((user) => (user.role === "VOLUNTEER" ? setReady(true) : (window.location.href = "/reviewer")))
      .catch(() => (window.location.href = "/reviewer/login"));
  }, []);

  function toggle(type: HarmType) {
    setHarmTypes((current) => (current.includes(type) ? current.filter((t) => t !== type) : [...current, type]));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
    } catch {
      setError("Enter a valid link beginning with https://");
      return;
    }
    if (context.trim().length < 10) {
      setError("Add a few words of context for the reviewer (at least 10 characters).");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const response = await createVolunteerReportRequest({ url, category, harm_types: harmTypes, urgency, context: context.trim() });
      setResult(response);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        window.location.href = "/reviewer/login";
        return;
      }
      setError("The report could not be sent. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setUrl("");
    setHarmTypes([]);
    setContext("");
    setUrgency("high");
    setResult(null);
  }

  if (!ready) return <section className="inner-page"><div className="page-container"><p className="hero-note">Loading…</p></div></section>;

  if (result) return <section className="page-container success-wrap"><div className="success-card">
    <div className="success-icon"><CheckCircle2 size={32} /></div><span className="eyebrow">Volunteer report</span>
    <h1>Thank you.</h1>
    <p>{result.duplicate
      ? "This content was already in the review queue. Your report was added to it and raises its priority."
      : "Your report is in the priority lane of the review queue."}</p>
    <span className="reference-code">Reference · {result.reference}</span>
    <div className="success-actions"><button className="button-primary" type="button" onClick={reset}>Report another link <ArrowRight size={16} /></button></div>
  </div></section>;

  return (
    <section className="inner-page">
      <div className="page-container content-narrow">
        <div className="page-heading"><span className="eyebrow">Trained volunteer</span><h1>Report a link</h1>
          <p>Your reports skip the automatic check and go straight to ICRC reviewers, in the priority lane.</p></div>
        <form className="form-card" onSubmit={submit} noValidate>
          <div className="form-section">
            <label className="form-label" htmlFor="url">Link <span>*</span></label>
            <p className="form-helper">The direct URL of the post (Telegram, Facebook, Instagram, TikTok, X or other).</p>
            <input id="url" className="text-input" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://t.me/channel/post" type="url" />
          </div>
          <div className="form-section">
            <span className="form-label">Category <span>*</span></span>
            <div className="category-options">
              {categories.map((item) => (
                <div className="category-option" key={item}>
                  <input id={item} name="category" type="radio" checked={category === item} onChange={() => setCategory(item)} />
                  <label htmlFor={item}><span className="category-radio" /><span className="category-label">{categoryLabels[item]}</span></label>
                </div>
              ))}
            </div>
          </div>
          <div className="form-section">
            <span className="form-label">What does the post do? <span className="optional-label">(all that apply)</span></span>
            <div className="category-options">
              {(Object.keys(harmTypeLabels) as HarmType[]).map((type) => (
                <div className="category-option" key={type}>
                  <input id={type} type="checkbox" checked={harmTypes.includes(type)} onChange={() => toggle(type)} />
                  <label htmlFor={type}><span className="category-radio" /><span className="category-label">{harmTypeLabels[type]}</span></label>
                </div>
              ))}
            </div>
          </div>
          <div className="form-section">
            <span className="form-label">Urgency <span>*</span></span>
            <div className="category-options">
              {urgencies.map((item) => (
                <div className="category-option" key={item.value}>
                  <input id={`urgency-${item.value}`} name="urgency" type="radio" checked={urgency === item.value} onChange={() => setUrgency(item.value)} />
                  <label htmlFor={`urgency-${item.value}`}><span className="category-radio" /><span className="category-label">{item.label}<br /><small>{item.help}</small></span></label>
                </div>
              ))}
            </div>
          </div>
          <div className="form-section">
            <label className="form-label" htmlFor="context">Context for the reviewer <span>*</span></label>
            <p className="form-helper">Where you saw it, how far it spreads, local meaning of words. No names or personal details of survivors.</p>
            <textarea id="context" className="textarea-input" value={context} onChange={(event) => setContext(event.target.value)} maxLength={2000} rows={5} />
            <div className="field-meta"><span>Required.</span><span>{context.length}/2000</span></div>
          </div>
          <div className="form-footer">
            <p className="privacy-note"><Info size={14} /> Your account is linked to this report so reviewers can follow up.</p>
            {error && <p className="field-error">{error}</p>}
            <button className="button-primary" type="submit" disabled={submitting}>{submitting ? "Sending…" : "Send report"} {!submitting && <ArrowRight size={16} />}</button>
          </div>
        </form>
        <p className="hero-note"><ShieldCheck size={15} /> Do not download, copy or share sensitive content. <Link href="/">Back to home</Link></p>
      </div>
    </section>
  );
}
