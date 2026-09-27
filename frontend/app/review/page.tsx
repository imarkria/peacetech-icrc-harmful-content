"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {useSearchParams} from "next/navigation";
import {
    ArrowRight,
    ClipboardCheck,
    FileWarning,
    Info,
    Search
} from "../../components/icons";
import {isReviewerAuthenticated} from "../../components/app-shell";
import {ApiError, getReviewQueue} from "../../lib/api";
import {decisionLabels, DetectedLink, formatRelativeDate} from "../../lib/review-data";

const PAGE_SIZE = 10;

function sourceLabel(source: DetectedLink["source"]) {
    if (source === "PUBLIC") return "Public";
    if (source === "SPECIALIST") return "Specialist";
    return "Scrap";
}

export default function ReviewQueuePage() {
    const searchParams = useSearchParams();
    const requestedTab = searchParams.get("status") === "reviewed" ? "REVIEWED" : "PENDING";
    const [links, setLinks] = useState<DetectedLink[]>([]);
    const [tab, setTab] = useState<"PENDING" | "REVIEWED">(requestedTab);
    const [query, setQuery] = useState("");
    const [ready, setReady] = useState(false);
    const [error, setError] = useState("");
    const [counts, setCounts] = useState({pending: 0, reviewed: 0});
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const [totalPages, setTotalPages] = useState(1);

    useEffect(() => {
        setTab(requestedTab);
        setPage(1);
    }, [requestedTab]);

    useEffect(() => {
        if (!isReviewerAuthenticated()) {
            window.location.href = "/reviewer/login";
            return;
        }

        let cancelled = false;
        setReady(false);
        setError("");
        getReviewQueue(tab, query, page, PAGE_SIZE).then((result) => {
            if (cancelled) return;
            setLinks(result.items);
            setCounts({pending: result.pending_count, reviewed: result.reviewed_count});
            setTotal(result.total);
            setTotalPages(result.total_pages);
            setReady(true);
        }).catch((requestError) => {
            if (cancelled) return;
            if (requestError instanceof ApiError && requestError.status === 401) {
                window.location.href = "/reviewer/login";
                return;
            }
            setError("We could not load the review queue. Please try again or contact an administrator.");
            setReady(true);
        });

        return () => {
            cancelled = true;
        };
    }, [tab, query, page]);

    const visibleLinks = links;
    const pendingCount = counts.pending;
    const reviewedCount = counts.reviewed;

    if (!ready) return <section className="inner-page">
        <div className="page-container"><p className="hero-note">Loading reviewer workspace…</p></div>
    </section>;

    return <section className="inner-page">
        <div className="page-container">
            <div className="review-header">
                <div className="page-heading"><span className="eyebrow">ICRC reviewer workspace</span><h1>Review
                    queue</h1><p>Review potential harmful content related to sexual violence in armed conflicts.</p></div>
            </div>
            <div className="stats-row">
                <div className="stat-card">
                    <div className="stat-label">Needs review <FileWarning size={15}/></div>
                    <strong className="stat-value">{pendingCount}</strong><span className="stat-trend">Links awaiting review</span>
                </div>
                <div className="stat-card">
                    <div className="stat-label">Decisions <ClipboardCheck size={15}/></div>
                    <strong className="stat-value">{reviewedCount}</strong><span
                    className="stat-trend">Decisions recorded</span>
                </div>
            </div>
            <div className="queue-panel">
                <div className="queue-toolbar">
                    <div className="tabs">
                        <button className={`tab ${tab === "PENDING" ? "tab-active" : ""}`} onClick={() => {
                            setTab("PENDING");
                            setPage(1);
                        }}>Pending <span className="count">{pendingCount}</span></button>
                        <button className={`tab ${tab === "REVIEWED" ? "tab-active" : ""}`} onClick={() => {
                            setTab("REVIEWED");
                            setPage(1);
                        }}>Reviewed <span className="count">{reviewedCount}</span></button>
                    </div>
                    <label style={{position: "relative"}}><Search size={14} style={{
                        position: "absolute",
                        left: 10,
                        top: 10,
                        color: "var(--muted)"
                    }}/><input className="search-input" style={{paddingLeft: 31}} value={query}
                               onChange={(event) => {
                                   setQuery(event.target.value);
                                   setPage(1);
                               }} placeholder="Search links"
                               aria-label="Search links"/></label></div>
                {error ? <div className="auth-error" style={{margin: "20px"}}><Info size={15}/><span>{error}</span>
                </div> : visibleLinks.length === 0 ?
                    <div className="queue-empty"><span className="empty-icon"><ClipboardCheck size={23}/></span>
                        <h3>{tab === "PENDING" ? "No pending links" : "No reviewed links"}</h3>
                        <p>{query ? "No links match this search." : tab === "PENDING" ? "There are no pending links." : "No decisions have been recorded."}</p>
                    </div> : <>
                        <div className="queue-list-header">
                            <span>Source link</span><span>Source</span><span>Decision</span><span>Action</span>
                        </div>
                        {visibleLinks.map((link) => <div className="queue-row" key={link.id}>
                            <div className="url-cell"><span className="url-title">{link.url}</span><span
                                className="url-subtitle">{sourceLabel(link.source)} · {formatRelativeDate(link.detectedAt)}</span>
                            </div>
                            <div className="source-value">{sourceLabel(link.source)}</div>
                            <div
                                className={link.review ? "decision-recorded" : "decision-pending"}>{link.review ? decisionLabels[link.review.decision] : "Not decided"}</div>
                            <Link className="row-action"
                                  href={`/review/${link.id}`}>{link.status === "PENDING" ? "Review" : "View"}
                                <ArrowRight size={14}/></Link></div>)}
                        {totalPages > 1 && <div className="queue-pagination">
                            <span>Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total}</span>
                            <div className="pagination-actions">
                                <button className="button-secondary pagination-button" type="button"
                                        disabled={page === 1} onClick={() => setPage((current) => current - 1)}>Previous
                                </button>
                                <span>Page {page} of {totalPages}</span>
                                <button className="button-secondary pagination-button" type="button"
                                        disabled={page >= totalPages}
                                        onClick={() => setPage((current) => current + 1)}>Next
                                </button>
                            </div>
                        </div>}
                    </>}</div>
        </div>
    </section>
        ;
}
