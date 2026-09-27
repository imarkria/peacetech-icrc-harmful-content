"use client";

import Link from "next/link";
import {FormEvent, useState} from "react";
import {ArrowLeft, ArrowRight, BadgeCheck, Check, LockKeyhole} from "../../../components/icons";
import {ApiError, loginRequest} from "../../../lib/api";

const showDemoHint = process.env.NEXT_PUBLIC_SHOW_DEMO_LOGIN !== "false";

export default function ReviewerLoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    async function login(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setLoading(true);
        setError("");
        try {
            const {user} = await loginRequest(email, password);
            window.location.href = user.role === "VOLUNTEER" ? "/volunteer/report" : "/reviewer";
        } catch (loginError) {
            if (loginError instanceof ApiError && loginError.status === 401) {
                setError("Email or password is incorrect.");
            } else {
                setError("The reviewer service is unavailable.");
            }
            setLoading(false);
        }
    }

    return <section className="inner-page">
        <div className="page-container"><Link className="breadcrumb" href="/"><ArrowLeft size={14}/> Back to home</Link>
            <div className="auth-layout">
                <div className="auth-intro"><span className="eyebrow">ICRC reviewers and trained volunteers</span><h1>Sign in.</h1><p>Reviewers label the links collected from every lane. Trained volunteers send reports
                    straight to the priority lane.</p>
                    <div className="auth-points"><span className="auth-point"><Check
                        size={16}/> Reviewers: review pending links and record one final label</span><span className="auth-point"><Check size={16}/> Copies of the same content appear once</span><span
                        className="auth-point"><Check size={16}/> Trained volunteers: report a link with context and urgency</span></div>
                </div>
                <form className="auth-card" onSubmit={login}><BadgeCheck className="principle-icon" size={25}/>
                    <h2>Sign in</h2><p className="auth-card-intro">Use the account the ICRC gave you.</p>{error &&
                        <div className="auth-error"><LockKeyhole size={15}/> <span>{error}</span></div>}
                    <div className="form-group"><label className="form-label" htmlFor="email">Email
                        address</label><input className="text-input" id="email" type="email" placeholder="you@icrc.org"
                                              value={email} onChange={(event) => setEmail(event.target.value)}
                                              required/></div>
                    <div className="form-group"><label className="form-label" htmlFor="password">Password</label><input
                        className="text-input" id="password" type="password" placeholder="Enter password"
                        value={password} onChange={(event) => setPassword(event.target.value)} required/></div>
                    <button className="button-primary auth-submit" type="submit"
                            disabled={loading}>{loading ? "Signing in…" : "Sign in"} {!loading &&
                        <ArrowRight size={16}/>}</button>
                    {showDemoHint &&
                        <div className="demo-hint"><strong>Demo access</strong><br/>reviewer@icrc.org · reviewer<br/>volunteer@icrc.org · reviewer</div>}
                </form>
            </div>
        </div>
    </section>;
}
