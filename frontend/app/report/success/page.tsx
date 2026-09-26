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

  return <section className="page-container success-wrap"><div className="success-card"><div className="success-icon"><CheckCircle2 size={32} /></div><span className="eyebrow">Report submitted</span><h1>Link saved.</h1><p>The link was stored for future model development. It was not added to the reviewer queue.</p><span className="reference-code">Reference · {reference}</span><div className="success-actions"><Link className="button-primary" href="/report">Submit another report <ArrowRight size={16} /></Link><Link className="button-secondary" href="/">Back to home</Link></div></div></section>;
}
