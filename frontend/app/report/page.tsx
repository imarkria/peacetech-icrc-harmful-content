"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Info, ShieldCheck } from "../../components/icons";
import { isSpecialistAuthenticated } from "../../components/app-shell";
import { createReportRequest } from "../../lib/api";

export default function ReportPage() {
  const pathname = usePathname();
  const specialist = pathname.startsWith("/specialist/report");
  const [url, setUrl] = useState("");
  const [reason, setReason] = useState("");
  const [urlError, setUrlError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [specialistReady, setSpecialistReady] = useState(!specialist);
  const [specialistAllowed, setSpecialistAllowed] = useState(false);

  useEffect(() => {
    if (!specialist) return;
    const allowed = isSpecialistAuthenticated();
    setSpecialistAllowed(allowed);
    setSpecialistReady(true);
    if (!allowed) window.location.href = "/specialist/login";
  }, [specialist]);

  if (specialist && !specialistReady) return <section className="inner-page"><div className="page-container"><p className="hero-note">Loading…</p></div></section>;
  if (specialist && !specialistAllowed) return null;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    let valid = true;
    try {
      const parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
    } catch {
      setUrlError("Enter a valid link beginning with https://");
      valid = false;
    }
    if (!valid) return;

    setSubmitting(true);
    setSubmitError("");
    try {
      const result = await createReportRequest({
        url,
        category: "other",
        reason: reason.trim() || undefined,
      }, specialist ? "SPECIALIST" : "PUBLIC");
      window.sessionStorage.setItem("last-report", JSON.stringify({ url, category: "other", reason: reason.trim(), reference: result.reference, queued: result.queued, source: specialist ? "SPECIALIST" : "PUBLIC" }));
      window.location.href = `/report/success?ref=${encodeURIComponent(result.reference)}&source=${specialist ? "specialist" : "public"}&queued=${result.queued}`;
    } catch {
      setSubmitError("We could not submit your report. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <section className="inner-page">
        <div className="page-container content-narrow">
        <Link className="breadcrumb" href="/"><ArrowLeft size={14} /> Back to home</Link>
        <div className="page-heading"><h1>{specialist ? "Submit a link for review" : "Report harmful content"}</h1><p>{specialist ? "Your submission will go directly to the authorised reviewer queue." : "Submit a link containing harmful content related to sexual violence in armed conflicts. No sign-in is required."}</p></div>
        <form className="form-card" onSubmit={submit} noValidate>
          <div className="form-section">
            <label className="form-label" htmlFor="url">Link to report <span>*</span></label>
            <p className="form-helper">Enter the direct URL.</p>
            <input id="url" className={`text-input ${urlError ? "text-input-error" : ""}`} value={url} onChange={(event) => { setUrl(event.target.value); setUrlError(""); }} placeholder="https://t.me/channel/post" type="url" autoComplete="url" />
            {urlError && <p className="field-error">{urlError}</p>}
          </div>
          <div className="form-section">
            <label className="form-label" htmlFor="reason">Reason <span className="optional-label">(optional)</span></label>
            <p className="form-helper">Briefly describe why the link may be harmful. Do not include personal information.</p>
            <textarea id="reason" className="textarea-input" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="For example: the post appears to encourage violence against…" maxLength={1000} rows={5} />
            <div className="field-meta"><span>Optional context.</span><span>{reason.length}/1000</span></div>
          </div>
          <div className="form-footer">
            <p className="privacy-note"><Info size={14} /> We store the URL and optional reason.</p>
            {submitError && <p className="field-error">{submitError}</p>}
            <button className="button-primary" type="submit" disabled={submitting}>{submitting ? "Submitting…" : "Submit report"} {!submitting && <ArrowRight size={16} />}</button>
          </div>
        </form>
        <p className="hero-note"><ShieldCheck size={15} /> {specialist ? "Direct queue submission for authorised ICRC specialists." : "No sign-in required. Reports are screened before reviewer access."}</p>
      </div>
    </section>
  );
}
