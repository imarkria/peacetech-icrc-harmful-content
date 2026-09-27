"use client";

import Link from "next/link";
import {useParams, useRouter} from "next/navigation";
import {FormEvent, useEffect, useState} from "react";
import {
    ArrowLeft,
    ArrowRight,
    Check,
    CheckCircle2,
    ChevronDown,
    ExternalLink,
    Info,
    Link2,
    ShieldCheck,
    TriangleAlert
} from "../../../components/icons";
import {CategoryBadge} from "../../../components/status-badge";
import {ApiError, getReviewRequest, submitReviewRequest} from "../../../lib/api";
import {decisionLabels, DetectedLink, formatDate, priorityLabels, ReviewDecision, ReviewEvidence, sourceLabels} from "../../../lib/review-data";

const decisions: ReviewDecision[] = ["SEXUAL_VIOLENCE", "CHILD_RELATED_HARM", "HATE_RELATED", "OTHER", "NOT_A_VIOLATION", "UNCLEAR"];

const decisionDescriptions: Record<ReviewDecision, string> = {
    SEXUAL_VIOLENCE: "A sexual act committed under coercive circumstances.",
    CHILD_RELATED_HARM: "Content that harms, exploits or puts a child at risk.",
    HATE_RELATED: "Content that targets a group or person with identity-based hatred.",
    OTHER: "Harmful content that does not fit the categories above.",
    NOT_A_VIOLATION: "No policy violation is supported by the available context.",
    UNCLEAR: "The evidence is insufficient or needs specialist escalation.",
};

const coerciveCircumstances = [
    ["SV-CO-1", "Force or threat of force"],
    ["SV-CO-2", "Fear of violence, duress or psychological oppression"],
    ["SV-CO-3", "Detention or captivity"],
    ["SV-CO-4", "Abuse of power"],
    ["SV-CO-5", "Coercive environment", "checkpoint, occupation, displacement camp or armed-group control"],
    ["SV-CO-6", "Incapacity to give genuine consent"],
] as const;

const sexualForms = [
    ["SV-FORM-01", "Rape", "Sexual penetration of any kind without genuine consent"],
    ["SV-FORM-02", "Sexual slavery", "Exercising ownership over a person, including sexual access"],
    ["SV-FORM-03", "Enforced prostitution", "Forcing sexual acts in exchange for money, goods or survival"],
    ["SV-FORM-04", "Forced pregnancy", "Confinement after a person is made pregnant by force"],
    ["SV-FORM-05", "Forced abortion", "Terminating a pregnancy without consent"],
    ["SV-FORM-06", "Enforced sterilization", "Removing reproductive capacity without consent"],
    ["SV-FORM-07", "Forced marriage", "Forcing a person into marriage or a marriage-like union"],
    ["SV-FORM-08", "Trafficking for sexual exploitation", "Moving or holding a person for sexual violence or exploitation"],
    ["SV-FORM-09", "Sexualised torture or ill-treatment", "Sexual acts or forced nudity used to punish, humiliate or extract information"],
    ["SV-FORM-10", "Other sexual violence of comparable gravity", "Another coercive sexual act of similar seriousness"],
] as const;

const harmfulTypes = [
    ["HI-TYPE-01", "Misinformation", "False information spread by someone who believes it is true"],
    ["HI-TYPE-02", "Disinformation", "False information spread intentionally for some gain"],
    ["HI-TYPE-03", "Malinformation", "True information spread with intent to cause harm, including exposing identities"],
    ["HI-TYPE-04", "Hate speech", "Expression that spreads, incites, promotes or justifies identity-based hatred or violence"],
    ["HI-TYPE-05", "Undermines respect for IHL", "Encourages or normalises violations, or erodes restraint among weapon bearers"],
    ["HI-TYPE-06", "Spread in violation of IHL", "Publication itself violates IHL, such as humiliating images of detainees"],
] as const;

const harmPathways = [
    ["HP-01", "Could trigger violence", "Including retaliatory sexual violence"],
    ["HP-02", "Stigmatises or exposes survivors", "Could expose victims or survivors to reprisals"],
    ["HP-03", "Reveals a person at risk", "Identity, location or affiliation"],
    ["HP-04", "Dehumanises a group or side", "Makes harm against them seem acceptable"],
    ["HP-05", "Spreads fear", "Could cause displacement or stop people seeking care"],
    ["HP-06", "Normalises sexual violence", "Among weapon bearers or supporters"],
    ["HP-07", "Undermines humanitarian safety", "Access, trust or operational security"],
] as const;

function toggleValue(values: string[], value: string) {
    return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function Checkmark({checked}: { checked: boolean }) {
    return <span className={`checkmark ${checked ? "checkmark-checked" : ""}`}>{checked && <Check size={12}/>}</span>;
}

export default function ReviewDetailPage() {
    const params = useParams<{ id: string }>();
    const router = useRouter();
    const [link, setLink] = useState<DetectedLink | null>(null);
    const [decision, setDecision] = useState<ReviewDecision | "">("");
    const [sexualElements, setSexualElements] = useState<string[]>([]);
    const [coerciveSelected, setCoerciveSelected] = useState<string[]>([]);
    const [sexualFormsSelected, setSexualFormsSelected] = useState<string[]>([]);
    const [harmfulTypesSelected, setHarmfulTypesSelected] = useState<string[]>([]);
    const [harmPathwaysSelected, setHarmPathwaysSelected] = useState<string[]>([]);
    const [error, setError] = useState("");
    const [ready, setReady] = useState(false);

    useEffect(() => {
        let cancelled = false;
        setReady(false);
        setError("");
        getReviewRequest(params.id).then((found) => {
            if (cancelled) return;
            setLink(found);
            if (found.review) {
                setDecision(found.review.decision);
                const evidence = found.review.evidence;
                setSexualElements(evidence?.sexualElements || []);
                setCoerciveSelected(evidence?.coerciveCircumstances || []);
                setSexualFormsSelected(evidence?.sexualForms || []);
                setHarmfulTypesSelected(evidence?.harmfulTypes || []);
                setHarmPathwaysSelected(evidence?.harmPathways || []);
            }
            setReady(true);
        }).catch((requestError) => {
            if (cancelled) return;
            if (requestError instanceof ApiError && requestError.status === 401) {
                window.location.href = "/reviewer/login";
                return;
            }
            setError("Unable to load this review item. Make sure the backend is running on http://localhost:8000.");
            setReady(true);
        });

        return () => {
            cancelled = true;
        };
    }, [params.id]);

    function chooseDecision(value: ReviewDecision) {
        setDecision(value);
        setError("");
    }

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!link || link.status === "REVIEWED") return;
        if (!decision) {
            setError("Choose the outcome that best fits the available evidence.");
            return;
        }

        const evidence: ReviewEvidence = {
            sexualElements,
            coerciveCircumstances: coerciveSelected,
            sexualForms: sexualFormsSelected,
            harmfulTypes: harmfulTypesSelected,
            harmPathways: harmPathwaysSelected
        };
        try {
            await submitReviewRequest(link.id, decision, evidence);
            router.push("/reviewer");
        } catch (requestError) {
            if (requestError instanceof ApiError && requestError.status === 409) {
                setError("This link has already been reviewed by another reviewer.");
            } else {
                setError("Could not save the review. Make sure the backend is running on http://localhost:8000.");
            }
        }
    }

    if (!ready) return <section className="inner-page">
        <div className="page-container"><p className="hero-note">Loading review…</p></div>
    </section>;
    if (error && !link) return <section className="inner-page">
        <div className="page-container">
            <div className="auth-error"><Info size={15}/><span>{error}</span></div>
            <Link className="button-secondary" href="/reviewer">Back to queue</Link></div>
    </section>;
    if (!link) return <section className="not-found">
        <div><h1>Link not found</h1><p>This review item may have been removed or reset.</p><Link
            className="button-primary" href="/reviewer">Back to queue</Link></div>
    </section>;

    const reviewed = link.status === "REVIEWED";
    // The policy cores are the first review step for every item. The model label
    // must not decide which guidance a reviewer is allowed to see.
    const showSexualGuidance = true;
    const showHarmfulGuidance = true;
    const isPublicReport = link.source === "PUBLIC" || link.source === "VOLUNTEER";
    const otherCopies = link.occurrences.filter((o) => o.url !== link.url);

    return <section className="inner-page">
        <div className="page-container">
            <Link className="detail-back" href="/reviewer"><ArrowLeft size={14}/> Back to review queue</Link>
            <div className="review-detail-heading">
                <div className="page-heading"><span className="eyebrow">Review item · {link.id}</span>
                    <h1>{reviewed ? "Review completed" : "Make a careful decision"}</h1>
                    <p>{reviewed ? "This item has already been reviewed. The decision is read-only." : "Check the policy cores and record one final label."}</p>
                </div>
                <div className="review-stepper" aria-label="Review progress"><span
                    className="stepper-active">1</span><span className="stepper-line"/><span
                    className="stepper-muted">2</span>
                    <div><strong>Human
                        review</strong><small>{reviewed ? "Decision recorded" : "Policy cores + final outcome"}</small>
                    </div>
                </div>
            </div>
            <div className="review-detail-grid">
                <div>
                    <div className="detail-card source-detail-card">
                        <div className="card-kicker">Source</div>
                        <h2>{sourceLabels[link.source || "SCRAP"]}</h2>
                        <div className="source-box"><h3>Source link</h3>
                            <div className="source-url">{link.url}</div>
                            <div className="source-meta"><span><Link2
                                size={13}/> {link.platform}</span><span>{priorityLabels[link.priority]} priority</span><span>Detected {formatDate(link.detectedAt)}</span><a
                                href={link.url} target="_blank" rel="noreferrer" style={{
                                color: "var(--teal-dark)",
                                display: "inline-flex",
                                gap: 5,
                                alignItems: "center"
                            }}>Open link <ExternalLink size={12}/></a></div>
                        </div>
                        <div className="guidance-callout"><TriangleAlert size={16}/>
                            <div>
                                <p style={{whiteSpace: "pre-line"}}>{link.context}</p></div>
                        </div>
                        {link.occurrenceCount > 1 && <div className="source-box" style={{marginTop: 14}}>
                            <h3>Seen {link.occurrenceCount} times</h3>
                            <p className="micro-note">Copies of the same content (reposts, other platforms, other
                                reports). Your decision applies to all of them.</p>
                            {otherCopies.map((o, index) => <div className="source-meta" key={`${o.url}-${index}`}>
                                <span><Link2 size={13}/> {o.platform}</span><span>{sourceLabels[o.source]}</span>
                                <span>{formatDate(o.seenAt)}</span>
                                <span className="source-url" style={{fontSize: 12}}>{o.url}</span>
                            </div>)}
                        </div>}
                        <p className="micro-note"><ShieldCheck size={14}/> Do not download, copy or share sensitive
                            content.</p></div>

                    {!reviewed ? <form onSubmit={submit}>

                        {showSexualGuidance && <div className="detail-card rubric-card">
                            <div className="rubric-heading">
                                <div>
                                    <div className="card-kicker">Step 1 · Core: sexual violence</div>
                                    <h2>Sexual violence</h2></div>
                                <span className="policy-pill">SV</span></div>
                            <p className="definition-lead"><strong>SV-DEF.</strong> Sexual violence is an act of a
                                sexual nature committed against any person under coercive circumstances. <span
                                    className="source-note">Source: ICRC policy brief, February 2026.</span></p>
                            <details open>
                                <summary><span><b>01</b> Check the two required elements</span><ChevronDown size={16}/>
                                </summary>
                                <div className="details-body">
                                    <div className="element-grid"><label
                                        className={`element-card ${sexualElements.includes("SV-EL-A") ? "element-selected" : ""}`}><input
                                        type="checkbox" checked={sexualElements.includes("SV-EL-A")}
                                        onChange={() => setSexualElements(toggleValue(sexualElements, "SV-EL-A"))}/><Checkmark
                                        checked={sexualElements.includes("SV-EL-A")}/><span><strong>SV-EL-A · Sexual nature</strong><small>The act is sexual in nature. It can target any person of any age, sex, gender identity or sexual orientation. Never assume the victim is a woman or girl.</small></span></label><label
                                        className={`element-card ${sexualElements.includes("SV-EL-B") ? "element-selected" : ""}`}><input
                                        type="checkbox" checked={sexualElements.includes("SV-EL-B")}
                                        onChange={() => setSexualElements(toggleValue(sexualElements, "SV-EL-B"))}/><Checkmark
                                        checked={sexualElements.includes("SV-EL-B")}/><span><strong>SV-EL-B · Coercive circumstances</strong><small>At least one coercive circumstance is present or indicated below.</small></span></label>
                                    </div>
                                </div>
                            </details>
                            <details>
                                <summary><span><b>02</b> Which coercive circumstances are present?</span><ChevronDown
                                    size={16}/></summary>
                                <div
                                    className="details-body checklist-grid">{coerciveCircumstances.map(([id, title, hint]) =>
                                    <label className="check-row" key={id}><input type="checkbox"
                                                                                 checked={coerciveSelected.includes(id)}
                                                                                 onChange={() => setCoerciveSelected(toggleValue(coerciveSelected, id))}/><Checkmark
                                        checked={coerciveSelected.includes(id)}/><span><strong>{id} · {title}</strong>{hint &&
                                        <small>{hint}</small>}</span></label>)}</div>
                            </details>
                            <details>
                                <summary><span><b>03</b> Named forms <em>select all that apply</em></span><ChevronDown
                                    size={16}/></summary>
                                <div className="details-body form-grid">{sexualForms.map(([id, title, definition]) =>
                                    <label className="form-chip" key={id}><input type="checkbox"
                                                                                 checked={sexualFormsSelected.includes(id)}
                                                                                 onChange={() => setSexualFormsSelected(toggleValue(sexualFormsSelected, id))}/><Checkmark
                                        checked={sexualFormsSelected.includes(id)}/><span><strong>{title}</strong><small>{id} · {definition}</small></span></label>)}</div>
                                <p className="rubric-note">Forced nudity, sexual humiliation and threats of sexual
                                    violence can themselves be sexual violence. Treat them under SV-FORM-09 or
                                    SV-FORM-10.</p></details>
                        </div>}

                        {showHarmfulGuidance && <div className="detail-card rubric-card harmful-rubric">
                            <div className="rubric-heading">
                                <div>
                                    <div className="card-kicker">Step 2 · Core: harmful information</div>
                                    <h2>Harmful information</h2></div>
                                <span className="policy-pill policy-pill-amber">HI</span></div>
                            <p className="definition-lead"><strong>HI-DEF.</strong> Harmful information is any
                                information that, when spread, could trigger or cause harm to people affected by armed
                                conflict or other violence. Truth is not the test: judge the potential effect on
                                people's life, safety and dignity. <span className="source-note">Source: ICRC, Harmful information: Questions and answers.</span>
                            </p>
                            <details open>
                                <summary>
                                    <span><b>01</b> What type(s) apply? <em>select all that apply</em></span><ChevronDown
                                    size={16}/></summary>
                                <div className="details-body form-grid">{harmfulTypes.map(([id, title, definition]) =>
                                    <label className="form-chip" key={id}><input type="checkbox"
                                                                                 checked={harmfulTypesSelected.includes(id)}
                                                                                 onChange={() => setHarmfulTypesSelected(toggleValue(harmfulTypesSelected, id))}/><Checkmark
                                        checked={harmfulTypesSelected.includes(id)}/><span><strong>{title}</strong><small>{id} · {definition}</small></span></label>)}</div>
                                <p className="rubric-note">You do not need to prove falsity. If truth is unknown, use
                                    possible misinformation or disinformation and let the reviewer decide.</p></details>
                            <details open>
                                <summary><span><b>02</b> What is the harm pathway? <em>at least one required for every harmful item</em></span><ChevronDown
                                    size={16}/></summary>
                                <div className="details-body checklist-grid">{harmPathways.map(([id, title, hint]) =>
                                    <label className="check-row" key={id}><input type="checkbox"
                                                                                 checked={harmPathwaysSelected.includes(id)}
                                                                                 onChange={() => setHarmPathwaysSelected(toggleValue(harmPathwaysSelected, id))}/><Checkmark
                                        checked={harmPathwaysSelected.includes(id)}/><span><strong>{id} · {title}</strong><small>{hint}</small></span></label>)}</div>
                                <p className="rubric-note">No pathway, no Axis 2.</p></details>
                        </div>}

                        <div className="detail-card decision-card">
                            <div className="card-kicker">Step 3 · Final label</div>
                            <h2>Final label</h2><p className="card-intro">Select the label supported by the available
                            context. The model output is not the final label.</p>
                            <div className="decision-card-grid">{decisions.map((item) => <div
                                className="decision-option" key={item}><input id={item} type="radio" name="decision"
                                                                              checked={decision === item}
                                                                              onChange={() => chooseDecision(item)}/><label
                                className={`decision-option-card decision-${item.toLowerCase()}`} htmlFor={item}><span
                                className="decision-radio"><Check
                                size={12}/></span><span><strong>{decisionLabels[item]}</strong><small>{decisionDescriptions[item]}</small></span></label>
                            </div>)}</div>
                            {error && <p className="decision-error">{error}</p>}</div>
                        {!reviewed && <div className="detail-actions detail-actions-sticky">
                            <button className="button-primary" type="submit">Save decision <ArrowRight size={16}/>
                            </button>
                            <Link className="button-secondary" href="/reviewer">Cancel</Link><span
                            className="save-hint">You can review the item again before saving.</span>
                        </div>}
                    </form> : <div className="detail-card reviewed-card">
                        <div className="reviewed-callout"><CheckCircle2
                            size={17}/><span>Decision recorded as <strong>{link.review ? decisionLabels[link.review.decision] : "completed"}</strong>.</span>
                        </div>
                        <p className="reviewed-summary">This review is read-only.</p></div>}
                </div>
                <aside>
                    <div className="detail-card model-card">
                        <div className="card-kicker">{isPublicReport ? sourceLabels[link.source || "PUBLIC"] : "Model signal"}</div>
                        <h2>{isPublicReport ? "Reported category" : "Model prediction"}</h2>
                        <div className="prediction-row"><span
                            className="prediction-label">{isPublicReport ? "Reporter selected" : "Predicted category"}</span><span
                            className="prediction-value"><CategoryBadge category={link.predictedCategory}/></span></div>
                        {link.confidence > 0 && <>
                            <div className="prediction-row"><span className="prediction-label">Confidence</span><span
                                className="prediction-value prediction-confidence">{Math.round(link.confidence * 100)}%</span>
                            </div>
                            <div className="confidence-track confidence-track-wide"><span
                                style={{width: `${link.confidence * 100}%`}}/></div>
                        </>}
                        {link.confidence === 0 && <div className="prediction-row"><span className="prediction-label">Model confidence</span><span
                            className="prediction-value">Not available</span></div>}
                        <div className="prediction-row"><span className="prediction-label">Queue status</span><span
                            className="prediction-value">{reviewed ? "Reviewed" : "Pending review"}</span></div>
                    </div>
                    {reviewed && <div className="detail-card reviewed-card">
                        <div className="reviewed-callout"><CheckCircle2
                            size={17}/><span>Reviewed on {link.review ? formatDate(link.review.reviewedAt) : "a previous date"} as <strong>{link.review ? decisionLabels[link.review.decision] : "completed"}</strong>.</span>
                        </div>
                        <p className="reviewed-summary">{link.review?.evidence?.harmPathways?.length ? `${link.review.evidence.harmPathways.length} harm pathway(s) recorded.` : link.review?.evidence?.sexualForms?.length ? `${link.review.evidence.sexualForms.length} sexual violence form(s) recorded.` : "No additional policy signals recorded."}</p>
                    </div>}
                    <div className="detail-card safety-card"><h2>Safety</h2><p className="privacy-note">
                        <ShieldCheck size={15}/> Do not copy or share sensitive content.</p><p className="privacy-note">
                        <Info size={15}/> Select Unclear when evidence is insufficient.</p></div>
                </aside>
            </div>
        </div>
    </section>;
}
