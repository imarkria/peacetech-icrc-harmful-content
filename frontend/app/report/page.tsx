"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { ArrowLeft, ArrowRight, Info, ShieldCheck } from "../../components/icons";
import { categoryLabels, ViolationCategory } from "../../lib/review-data";

const categories: ViolationCategory[] = ["sexual_violence", "child_related_harm", "hate_related", "other"];

export default function ReportPage() {
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState<ViolationCategory | "">("");
  const [reason, setReason] = useState("");
  const [urlError, setUrlError] = useState("");
  const [categoryError, setCategoryError] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    let valid = true;
    try {
      const parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
    } catch {
      setUrlError("Enter a valid link beginning with https://");
      valid = false;
    }
    if (!category) {
      setCategoryError("Select the category that best describes the link.");
      valid = false;
    }
    if (!valid) return;

    const reference = `SS-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
    window.sessionStorage.setItem("last-report", JSON.stringify({ url, category, reason: reason.trim(), reference }));
    window.location.href = `/report/success?ref=${reference}`;
  }

  return (
    <section className="inner-page">
      <div className="page-container content-narrow">
        <Link className="breadcrumb" href="/"><ArrowLeft size={14} /> Back to home</Link>
        <div className="page-heading"><span className="eyebrow">Public report</span><h1>Report a potentially harmful link</h1><p>Share a link you believe may relate to harmful content. </p></div>
        <form className="form-card" onSubmit={submit} noValidate>
          <div className="form-section">
            <label className="form-label" htmlFor="url">Link to report <span>*</span></label>
            <p className="form-helper">Please submit the direct URL where the content can be found.</p>
            <input id="url" className={`text-input ${urlError ? "text-input-error" : ""}`} value={url} onChange={(event) => { setUrl(event.target.value); setUrlError(""); }} placeholder="https://t.me/channel/post" type="url" autoComplete="url" />
            {urlError && <p className="field-error">{urlError}</p>}
          </div>
          {/*<div className="form-section">*/}
          {/*  <span className="form-label">What areas may be violated? <span>*</span></span>*/}
          {/*  <p className="form-helper">Choose the categories that describe what you saw.</p>*/}
          {/*  <div className="category-options">*/}
          {/*    {categories.map((item) => (*/}
          {/*      <div className="category-option" key={item}>*/}
          {/*        <input id={item} name="category" type="radio" checked={category === item} onChange={() => { setCategory(item); setCategoryError(""); }} />*/}
          {/*        <label htmlFor={item}><span className="category-radio" /><span className="category-label">{categoryLabels[item]}</span></label>*/}
          {/*      </div>*/}
          {/*    ))}*/}
          {/*  </div>*/}
          {/*  {categoryError && <p className="field-error">{categoryError}</p>}*/}
          {/*</div>*/}
          <div className="form-section">
            <label className="form-label" htmlFor="reason">Why are you reporting this link? <span className="optional-label">(optional)</span></label>
            <p className="form-helper">Briefly explain what raised your concern. Please do not include names, contact details, or other personal information.</p>
            <textarea id="reason" className="textarea-input" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="For example: the post appears to encourage violence against…" maxLength={1000} rows={5} />
            <div className="field-meta"><span>Optional context helps future research.</span><span>{reason.length}/1000</span></div>
          </div>
          <div className="form-footer">
            <p className="privacy-note"><Info size={14} /> We store the link, category, and any optional reason you provide. Please do not include personal information.</p>
            <button className="button-primary" type="submit">Submit report <ArrowRight size={16} /></button>
          </div>
        </form>
        <p className="hero-note"><ShieldCheck size={15} /> Your report is anonymous and will be kept for future research and model training.</p>
      </div>
    </section>
  );
}
