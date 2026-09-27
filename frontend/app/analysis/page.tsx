"use client";

import {useEffect, useState} from "react";
import {Info} from "../../components/icons";
import {ApiError, AnalysisCount, AnalysisSummary, getAnalysisSummary} from "../../lib/api";
import {CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis} from "recharts";

const sourceLabels: Record<string, string> = {SCRAP: "Detection", PUBLIC: "Community", VOLUNTEER: "Trained volunteer"};
const basicTagLabels: Record<string, string> = {
    "BT-MEN": "Men",
    "BT-WOMEN": "Women",
    "BT-CHILDREN": "Children",
    "BT-SEXUAL-VIOLENCE": "Sexual Violence",
    "BT-FORCED-SEXUAL-ACTION": "Forced Sexual Action",
};

function labelForBasicTag(key: string) {
    return basicTagLabels[key] || key;
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
    "BT-MEN": "#d71920",
    "BT-WOMEN": "#b45309",
    "BT-CHILDREN": "#7c3aed",
    "BT-SEXUAL-VIOLENCE": "#0f766e",
    "BT-FORCED-SEXUAL-ACTION": "#2563eb",
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
                        <span className="chart-legend-dot" style={{background: lineColors[key] || "#334155"}} />{labelForBasicTag(key)}
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
            setError("We could not load the analysis. Please try again or contact an administrator.");
        });
    }, []);

    if (!data && !error) return <section className="inner-page">
        <div className="page-container"><p className="hero-note">Loading analysis…</p></div>
    </section>;

    return <section className="inner-page">
        <div className="page-container analysis-page">
            <div className="page-heading analysis-heading"><span className="eyebrow">Reviewer workspace</span><h1>Data
                analytics</h1><p>Overview of reviewed content related to sexual violence in armed conflicts.</p></div>
            {error ? <div className="auth-error"><Info size={15}/><span>{error}</span></div> : data && <>
                <div className="analysis-grid">
                    <article className="analysis-card analysis-card-wide">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Basic tags</span><h2>Basic tag distribution</h2>
                            </div>
                        </div>
                        <BarList items={data.evidence_counts.basicTags || []} label={labelForBasicTag} percentage/></article>
                    <article className="analysis-card">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Source</span><h2>Reviewed by source</h2></div>
                        </div>
                        <BarList items={data.source_counts} label={(key) => sourceLabels[key] || key} percentage/></article>
                    <article className="analysis-card">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Platform</span><h2>Reviewed by platform</h2></div>
                        </div>
                        <BarList items={data.platform_counts} label={(key) => key} percentage/></article>
                    <article className="analysis-card analysis-card-wide">
                        <div className="analysis-card-heading">
                            <div><span className="card-kicker">Post timeline</span><h2>Reviewed posts by Basic tag</h2><p className="chart-helper">Click a legend item to focus on one tag.</p></div>
                        </div>
                        <TrendChart series={data.post_trends}/></article>
                </div>
                <p className="analysis-note"><Info size={14}/> Only reviewed links are included. Counts reflect recorded
                    tags and evidence.</p>
            </>}
        </div>
    </section>;
}
