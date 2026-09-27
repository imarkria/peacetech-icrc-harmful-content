"use client";

import Link from "next/link";
import {FormEvent, useState} from "react";
import {ArrowLeft, ArrowRight, BadgeCheck, Check, LockKeyhole} from "../../../components/icons";
import {setReviewerAuthenticated} from "../../../components/app-shell";
import {ApiError, loginRequest} from "../../../lib/api";

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
            await loginRequest(email, password);
            setReviewerAuthenticated(true);
            window.location.href = "/reviewer";
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
                <div className="auth-intro"><span className="eyebrow">ICRC reviewer access</span><h1>Review detected
                    links.</h1><p>Sign in to review links detected by the system and record a final label.</p>
                    <div className="auth-points"><span className="auth-point"><Check
                        size={16}/> Review pending links</span><span className="auth-point"><Check size={16}/> See the model category and confidence</span><span
                        className="auth-point"><Check size={16}/> Record one final label</span></div>
                </div>
                <form className="auth-card" onSubmit={login}><BadgeCheck className="principle-icon" size={25}/>
                    <h2>Reviewer sign in</h2><p className="auth-card-intro">Use your reviewer credentials.</p>{error &&
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
                    <div className="demo-hint"><strong>Demo access</strong><br/>reviewer@icrc.org · reviewer</div>
                </form>
            </div>
        </div>
    </section>;
}
