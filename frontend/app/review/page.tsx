"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, BarChart3, ClipboardCheck, FileWarning, Info, Search, ShieldCheck, UserRound } from "../../components/icons";
import { AppShell, isReviewerAuthenticated } from "../../components/app-shell";
import { CategoryBadge, StatusBadge } from "../../components/status-badge";
import { DetectedLink, formatRelativeDate, getStoredLinks } from "../../lib/review-data";

export default function ReviewQueuePage() {
  const [links, setLinks] = useState<DetectedLink[]>([]);
  const [tab, setTab] = useState<"PENDING" | "REVIEWED">("PENDING");
  const [query, setQuery] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isReviewerAuthenticated()) {
      window.location.href = "/login";
      return;
    }
    setLinks(getStoredLinks());
    setReady(true);
  }, []);

  const visibleLinks = useMemo(() => links.filter((link) => link.status === tab && `${link.url} ${link.channel}`.toLowerCase().includes(query.toLowerCase())), [links, tab, query]);
  const pendingCount = links.filter((link) => link.status === "PENDING").length;
  const reviewedCount = links.filter((link) => link.status === "REVIEWED").length;

  if (!ready) return <section className="inner-page"><div className="page-container"><p className="hero-note">Loading reviewer workspace…</p></div></section>;

  return <section className="inner-page"><div className="page-container"><div className="review-header"><div className="page-heading"><span className="eyebrow">ICRC reviewer workspace</span><h1>Review queue</h1><p>Validate model-detected links and create a reliable human-labelled dataset. Sensitive media is not rendered in this interface.</p></div><div className="reviewer-chip"><span className="avatar">AR</span><span>Alex Rivera · Reviewer</span></div></div><div className="stats-row"><div className="stat-card"><div className="stat-label">Needs review <FileWarning size={15} /></div><strong className="stat-value">{pendingCount}</strong><span className="stat-trend">Potential signals in queue</span></div><div className="stat-card"><div className="stat-label">Reviewed <ClipboardCheck size={15} /></div><strong className="stat-value">{reviewedCount}</strong><span className="stat-trend">Human labels recorded</span></div><div className="stat-card"><div className="stat-label">Model signals <BarChart3 size={15} /></div><strong className="stat-value">{links.length}</strong><span className="stat-trend">Seed data for this MVP</span></div></div><div className="queue-panel"><div className="queue-toolbar"><div className="tabs"><button className={`tab ${tab === "PENDING" ? "tab-active" : ""}`} onClick={() => setTab("PENDING")}>Pending <span className="count">{pendingCount}</span></button><button className={`tab ${tab === "REVIEWED" ? "tab-active" : ""}`} onClick={() => setTab("REVIEWED")}>Reviewed <span className="count">{reviewedCount}</span></button></div><label style={{ position: "relative" }}><Search size={14} style={{ position: "absolute", left: 10, top: 10, color: "var(--muted)" }} /><input className="search-input" style={{ paddingLeft: 31 }} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search links" aria-label="Search links" /></label></div>{visibleLinks.length === 0 ? <div className="queue-empty"><span className="empty-icon"><ClipboardCheck size={23} /></span><h3>{tab === "PENDING" ? "The queue is clear" : "No reviewed links yet"}</h3><p>{query ? "Try a different search term." : tab === "PENDING" ? "New model signals will appear here when they are ready." : "Completed reviews will be listed here."}</p></div> : <><div className="queue-list-header"><span>Source link</span><span>Model label</span><span>Confidence</span><span>Status</span><span>Action</span></div>{visibleLinks.map((link) => <div className="queue-row" key={link.id}><div className="url-cell"><span className="url-title">{link.url}</span><span className="url-subtitle">{link.channel} · {formatRelativeDate(link.detectedAt)}</span></div><div><CategoryBadge category={link.predictedCategory} /></div><div className="confidence-cell">{Math.round(link.confidence * 100)}%<div className="confidence-track"><span style={{ width: `${link.confidence * 100}%` }} /></div></div><div><StatusBadge status={link.status} /></div><Link className="row-action" href={`/review/${link.id}`}>{link.status === "PENDING" ? "Review" : "View"} <ArrowRight size={14} /></Link></div>)}</>}</div><p className="review-footer-note"><Info size={14} /> Queue data is seeded locally for the MVP. Public reports are stored separately and do not appear here.</p></div></section>;
}
