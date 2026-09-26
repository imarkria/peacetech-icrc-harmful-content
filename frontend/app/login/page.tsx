"use client";

import Link from "next/link";
import {FormEvent, useState} from "react";
import {ArrowLeft, ArrowRight, BadgeCheck, Check, LockKeyhole} from "../../components/icons";
import {setReviewerAuthenticated} from "../../components/app-shell";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    function login(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setLoading(true);
        setError("");
        window.setTimeout(() => {
            if (email.toLowerCase() === "reviewer@icrc.org" && password === "reviewer") {
                setReviewerAuthenticated(true);
                window.location.href = "/review";
            } else {
                setError("The email or password is not recognised. Use the demo account shown below.");
                setLoading(false);
            }
        }, 350);
    }

    return <section className="inner-page">
        <div className="page-container"><Link className="breadcrumb" href="/"><ArrowLeft size={14}/> Back to home</Link>
            <div className="auth-layout">
                <div className="auth-intro"><span className="eyebrow">Restricted workspace</span><h1>Review with care.
                    Label with confidence.</h1><p>The reviewer workspace turns model signals into human-validated
                    labels. Sign in with your ICRC reviewer account to access the queue.</p>
                    <div className="auth-points"><span className="auth-point"><Check size={16}/> Work through a focused review queue</span><span
                        className="auth-point"><Check
                        size={16}/> See model confidence without exposing media</span><span
                        className="auth-point"><Check size={16}/> Record a clear, auditable decision</span></div>
                </div>
                <form className="auth-card" onSubmit={login}><BadgeCheck className="principle-icon" size={25}/>
                    <h2>Reviewer sign in</h2><p className="auth-card-intro">Use your authorised reviewer credentials to
                        continue.</p>{error &&
                        <div className="auth-error"><LockKeyhole size={15}/> <span>{error}</span></div>}
                    <div className="form-group"><label className="form-label" htmlFor="email">Email
                        address</label><input className="text-input" id="email" type="email" placeholder="you@icrc.org"
                                              value={email} onChange={(event) => setEmail(event.target.value)}
                                              required/></div>
                    <div className="form-group">
                        <div className="password-row"><label className="form-label" htmlFor="password">Password</label>
                            <button className="fake-link" type="button">Need help?</button>
                        </div>
                        <input className="text-input" id="password" type="password" placeholder="Enter password"
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
