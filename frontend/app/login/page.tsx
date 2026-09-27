"use client";

import Link from "next/link";
import {FormEvent, useState} from "react";
import {ArrowLeft, ArrowRight, BadgeCheck, Check, LockKeyhole} from "../../components/icons";
import {ApiError, loginRequest} from "../../lib/api";

const showDemoHint = process.env.NEXT_PUBLIC_SHOW_DEMO_LOGIN !== "false";

export default function StaffLoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    async function login(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setLoading(true);
        setError("");
        try {
            const result = await loginRequest(email, password);
            if (result.user.role !== "REVIEWER" && result.user.role !== "VOLUNTEER") {
                setError("This account does not have platform access.");
                setLoading(false);
                return;
            }
            window.location.href = result.user.role === "REVIEWER" ? "/reviewer" : "/volunteer/report";
        } catch (loginError) {
            setError(loginError instanceof ApiError && loginError.status === 401 ? "Email or password is incorrect." : "The sign-in service is unavailable.");
            setLoading(false);
        }
    }

    return <section className="inner-page">
        <div className="page-container"><Link className="breadcrumb" href="/"><ArrowLeft size={14}/> Back to home</Link>
            <div className="auth-layout">
                <div className="auth-intro"><span className="eyebrow">ICRC reviewers and trained volunteers</span><h1>Sign in to the platform.</h1><p>Your account determines whether you review links or send reports straight to the priority lane.</p>
                    <div className="auth-points"><span className="auth-point"><Check size={16}/> Reviewer accounts access the queue</span><span className="auth-point"><Check size={16}/> Trained volunteer accounts send structured reports</span><span className="auth-point"><Check size={16}/> Permissions are role-based</span></div>
                </div>
                <form className="auth-card" onSubmit={login}><BadgeCheck className="principle-icon" size={25}/>
                    <h2>Sign in</h2><p className="auth-card-intro">Use the account the ICRC gave you.</p>{error && <div className="auth-error"><LockKeyhole size={15}/> <span>{error}</span></div>}
                    <div className="form-group"><label className="form-label" htmlFor="email">Email address</label><input className="text-input" id="email" type="email" placeholder="you@icrc.org" value={email} onChange={(event) => setEmail(event.target.value)} required/></div>
                    <div className="form-group"><label className="form-label" htmlFor="password">Password</label><input className="text-input" id="password" type="password" placeholder="Enter password" value={password} onChange={(event) => setPassword(event.target.value)} required/></div>
                    <button className="button-primary auth-submit" type="submit" disabled={loading}>{loading ? "Signing in…" : "Sign in"} {!loading && <ArrowRight size={16}/>}</button>
                    {showDemoHint && <div className="demo-hint"><strong>Demo access</strong><br/>reviewer@icrc.org · reviewer<br/>volunteer@icrc.org · reviewer</div>}
                </form>
            </div>
        </div>
    </section>;
}
