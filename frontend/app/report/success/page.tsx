"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, ShieldCheck } from "../../../components/icons";

export default function ReportSuccessPage() {
  const [reference, setReference] = useState("SS-THANKYOU");
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setReference(params.get("ref") || "SS-THANKYOU");
  }, []);

  return <section className="page-container success-wrap"><div className="success-card"><div className="success-icon"><CheckCircle2 size={32} /></div><span className="eyebrow">Report received</span><h1>Thank you for speaking up.</h1><p>Your report has been recorded securely. It will be kept for future research and model training.</p><span className="reference-code">Reference · {reference}</span><div className="success-actions"><Link className="button-primary" href="/report">Submit another report <ArrowRight size={16} /></Link><Link className="button-secondary" href="/">Return home</Link></div><p className="hero-note" style={{ justifyContent: "center" }}><ShieldCheck size={14} /> No account or follow-up is required.</p></div></section>;
}
