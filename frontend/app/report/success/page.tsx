"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CheckCircle2, ShieldCheck } from "../../../components/icons";

export default function ReportSuccessPage() {
  const [reference, setReference] = useState("SS-THANKYOU");
  const [queued, setQueued] = useState(true);
  const [specialist, setSpecialist] = useState(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setReference(params.get("ref") || "SS-THANKYOU");
    setQueued(params.get("queued") !== "false");
    setSpecialist(params.get("source") === "specialist");
  }, []);

  const message = specialist || queued
    ? "Your report was saved and added to the reviewer queue."
    : "Your report was saved. It will enter the reviewer queue only if the screening model marks it as potentially harmful.";
  return <section className="page-container success-wrap"><div className="success-card"><div className="success-icon"><CheckCircle2 size={32} /></div><span className="eyebrow">Submission received</span><h1>Thank you.</h1><p>{message} It may also support future research.</p><span className="reference-code">Reference · {reference}</span><div className="success-actions"><Link className="button-primary" href={specialist ? "/specialist/report" : "/report"}>Submit another link <ArrowRight size={16} /></Link><Link className="button-secondary" href="/">Back to home</Link></div></div></section>;
}
