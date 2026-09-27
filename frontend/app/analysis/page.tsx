"use client";

import {useEffect, useMemo, useState} from "react";
import {BarChart3, Info} from "../../components/icons";
import {ApiError, AnalysisCount, AnalysisSummary, getAnalysisSummary} from "../../lib/api";
import {decisionLabels, sourceLabels} from "../../lib/review-data";
import {CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";

const evidenceLabels: Record<string, string> = {
    "HP-01": "Could trigger violence",
    "HP-02": "Stigmatises or exposes survivors",
    "HP-03": "Reveals a person at risk",
    "HP-04": "Dehumanises a group or side",
    "HP-05": "Spreads fear",
    "HP-06": "Normalises sexual violence",
    "HP-07": "Undermines humanitarian safety",
};

function labelForDecision(key: string) {
    return decisionLabels[key as keyof typeof decisionLabels] || key;
}

function BarList({items, label, percentage = false}: { items: AnalysisCount[]; label: (key: string) => string; percentage?: boolean }) {
    const max = Math.max(...items.map((item) => item.count), 1);
    const total = items.reduce((sum, item) => sum + item.count, 0) || 1;
    if (items.length === 0) return <p className="analysis-empty">No reviewed data yet.</p>;

    return <div className="analysis-bars">{items.map((item) => <div className="analysis-bar-row" key={item.key}>
        <div className="analysis-bar-label"><span>{label(item.key)}</span><strong>{percentage ? `${((item.count / total) * 100).toFixed(1)}%` : item.count}</strong></div>
        <div className="analysis-bar-track"><span style={{width: `${((percentage ? item.count / total : item.count / max) * 100)}%`}}/></div>
    </div>)}</div>;
}

const lineColors: Record<string, string> = {
    SEXUAL_VIOLENCE: "#d71920",
    CHILD_RELATED_HARM: "#b45309",
    HATE_RELATED: "#7c3aed",
    OTHER: "#0f766e",
    NOT_A_VIOLATION: "#64748b",
    UNCLEAR: "#2563eb",
};

function TrendChart({series}: { series: AnalysisSummary["post_trends"] }) {
    const [selectedKey, setSelectedKey] = useState<string | null>(null);
    const keys = Object.keys(series);
    const dates = Array.from(new Set(keys.flatMap((key) => series[key].map((item) => item.date)))).sort();
    if (keys.length === 0 || dates.length === 0) return <p className="analysis-empty">No review activity yet.</p>;

    const chartData = dates.map((date) => {
        const row: Record<string, string | number> = {date};
        for (const key of keys) row[key] = series[key].find((item) => item.date === date)?.count || 0;
        return row;
    });
    return <div className="analysis-line-chart"><ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{top: 12, right: 18, left: 0, bottom: 8}}>
            <CartesianGrid stroke="#eadfdf" strokeDasharray="3 3"/>
            <XAxis dataKey="date" tick={{fill: "#706566", fontSize: 11}}
                   tickFormatter={(value: string) => value.slice(5)}/>
            <YAxis allowDecimals={false} width={30} tick={{fill: "#706566", fontSize: 11}}/>
            <Tooltip labelFormatter={(value) => `Post date: ${value}`}
                     formatter={(value) => [value, "Reviewed posts"]}/>
            <Legend content={({payload}) => <div className="chart-legend-row">
                {(payload || []).map((entry) => {
                    const key = String(entry.dataKey);
                    const active = !selectedKey || selectedKey === key;
                    return <button key={key} type="button" className={active ? "chart-legend-item chart-legend-active" : "chart-legend-item chart-legend-muted"} onClick={() => setSelectedKey((current) => current === key ? null : key)}>
                        <span className="chart-legend-dot" style={{background: lineColors[key] || "#334155"}} />{labelForDecision(key)}
                    </button>;
                })}
            </div>}/>
            {keys.map((key) => <Line key={key} type="monotone" dataKey={key} name={key}
                stroke={lineColors[key] || "#334155"} strokeOpacity={selectedKey && selectedKey !== key ? 0 : 1}
                strokeWidth={selectedKey === key ? 4 : 2.5}
                dot={{r: selectedKey === key ? 5 : 3, fill: lineColors[key] || "#334155", opacity: selectedKey && selectedKey !== key ? 0 : 1}} activeDot={{r: 6}}/>)}
        </LineChart>
    </ResponsiveContainer></div>;
}

export default function AnalysisPage() {
    const [data, setData] = useState<AnalysisSummary | null>(null);
    const [error, setError] = useState("");

    useEffect(() => {
        setData(null);
        setError("");
        getAnalysisSummary().then(setData).catch((requestError) => {
            if (requestError instanceof ApiError && requestError.status === 401) {
                window.location.href = "/reviewer/login";
                return;
            }
            setError("Unable to load analysis. Make sure the backend is running on http://localhost:8000.");
        });
    }, []);

    const publicCount = useMemo(() => data?.source_counts.find((item) => item.key === "PUBLIC")?.count || 0, [data]);
    const scrapCount = useMemo(() => data?.source_counts.find((item) => item.key === "SCRAP")?.count || 0, [data]);

    if (!data && !error) return <section className="inner-page">
        <div className="page-container"><p className="hero-note">Loading analysis…</p></div>
    </section>;

    return <section className="inner-page">
        <div className="page-container analysis-page">
            <div className="page-heading analysis-heading"><span className="eyebrow">Reviewer workspace</span><h1>Data
                analysis</h1><p>Summary of posts with a completed human decision.</p></div>
            {error ? <div className="auth-error"><Info size={15}/><span>{error}</span></div> : data && <>
                <div className="stats-row analysis-stats">
                    {/*<div className="stat-card">*/}
                    {/*    <div className="stat-label">Reviewed posts <BarChart3 size={15}/></div>*/}
                    {/*    <strong className="stat-value">{data.reviewed_total}</strong><span className="stat-trend">Human decisions recorded</span>*/}
                    {/*</div>*/}
                    {/*<div className="stat-card">*/}
                    {/*    <div className="stat-label">Public reports</div>*/}
                    {/*    <strong className="stat-value">{publicCount}</strong><span className="stat-trend">Reviewed public submissions</span>*/}
                    {/*</div>*/}
                    {/*<div className="stat-card">*/}
                    {/*    <div className="stat-label">Scrap detections</div>*/}
                    {/*    <strong className="stat-value">{scrapCount}</strong><span className="stat-trend">Reviewed scraped posts</span>*/}
                    {/*</div>*/}
                </div>
                <div className="analysis-grid">
                    <article className="analysis-card analysis-card-wide">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Decisions</span><h2>Final decision distribution</h2>
                            </div>
                        </div>
                        <BarList items={data.decision_counts} label={labelForDecision} percentage/></article>
                    <article className="analysis-card">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Source</span><h2>Reviewed by source</h2></div>
                        </div>
                        <BarList items={data.source_counts} label={(key) => sourceLabels[key as keyof typeof sourceLabels] || key} percentage/></article>
                    <article className="analysis-card">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Platform</span><h2>Reviewed by platform</h2></div>
                        </div>
                        <BarList items={data.platform_counts} label={(key) => key} percentage/></article>
                    <article className="analysis-card analysis-card-wide">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Post timeline</span><h2>Reviewed posts by post date</h2><p className="chart-helper">Click a legend item to focus on one decision.</p></div>
                        </div>
                        <TrendChart series={data.post_trends}/></article>
                    {/*<article className="analysis-card analysis-card-wide">*/}
                    {/*    <div className="analysis-card-heading">*/}
                    {/*        <div><span className="card-kicker">Evidence</span><h2>Harm pathways recorded</h2></div>*/}
                    {/*    </div>*/}
                    {/*    <BarList items={data.evidence_counts.harmPathways || []}*/}
                    {/*             label={(key) => evidenceLabels[key] || key}/></article>*/}
                </div>
                <p className="analysis-note"><Info size={14}/> Only reviewed posts are included. Counts reflect recorded
                    reviewer decisions and evidence.</p>
            </>}
        </div>
    </section>;
}
