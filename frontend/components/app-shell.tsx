"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogIn, LogOut, Menu, X } from "./icons";
import { Logo } from "./logo";
import { logoutRequest } from "../lib/api";

const AUTH_KEY = "icrc-reviewer-auth";
const ROLE_KEY = "icrc-auth-role";
export type AuthRole = "REVIEWER" | "SPECIALIST";

export function getAuthenticatedRole(): AuthRole | null {
  if (typeof window === "undefined") return null;
  const role = window.localStorage.getItem(ROLE_KEY);
  if (role === "REVIEWER" || role === "SPECIALIST") return role;
  return window.localStorage.getItem(AUTH_KEY) === "true" ? "REVIEWER" : null;
}

export function isReviewerAuthenticated() {
  return getAuthenticatedRole() === "REVIEWER";
}

export function isSpecialistAuthenticated() {
  return getAuthenticatedRole() === "SPECIALIST";
}

export function setAuthenticatedRole(role: AuthRole | null) {
  if (typeof window !== "undefined") {
    if (role) {
      window.localStorage.setItem(AUTH_KEY, "true");
      window.localStorage.setItem(ROLE_KEY, role);
    } else {
      window.localStorage.removeItem(AUTH_KEY);
      window.localStorage.removeItem(ROLE_KEY);
    }
  }
}

export function setReviewerAuthenticated(value: boolean) {
  setAuthenticatedRole(value ? "REVIEWER" : null);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);
  const [role, setRole] = useState<AuthRole | null>(null);
  const [mounted, setMounted] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMounted(true);
    const currentRole = getAuthenticatedRole();
    setRole(currentRole);
    setAuthenticated(Boolean(currentRole));
  }, [pathname]);

  async function signOut() {
    try {
      await logoutRequest();
    } catch {
      // Clear the local marker even when the backend session has already expired.
    }
    setReviewerAuthenticated(false);
    setAuthenticated(false);
    setRole(null);
    setMobileOpen(false);
    router.push("/");
  }

  const isReviewArea = pathname.startsWith("/reviewer") || pathname.startsWith("/review") || pathname === "/login";
  const isAnalysisArea = pathname.startsWith("/analysis");

  return (
    <div className="site-frame">
      <header className="topbar">
        <div className="topbar-inner">
          <Link className="brand-link" href="/" onClick={() => setMobileOpen(false)}>
            <Logo />
          </Link>
          <button className="mobile-menu-button" onClick={() => setMobileOpen((open) => !open)} aria-label="Toggle menu">
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <nav className={`main-nav ${mobileOpen ? "main-nav-open" : ""}`}>
            <Link className={pathname === "/" ? "nav-link nav-link-active" : "nav-link"} href="/" onClick={() => setMobileOpen(false)}>
              Home
            </Link>
            <Link className={pathname.startsWith("/report") ? "nav-link nav-link-active" : "nav-link"} href="/report" onClick={() => setMobileOpen(false)}>
              Report a link
            </Link>
            {mounted && authenticated && role === "REVIEWER" ? (
              <>
                <Link className={isReviewArea && !isAnalysisArea ? "nav-link nav-link-active" : "nav-link"} href="/reviewer" onClick={() => setMobileOpen(false)}>
                  Reviewer workspace
                </Link>
                <Link className={isAnalysisArea ? "nav-link nav-link-active" : "nav-link"} href="/analysis" onClick={() => setMobileOpen(false)}>
                  Data analysis
                </Link>
                <button className="nav-button" onClick={signOut}>
                  <LogOut size={15} />
                  Sign out
                </button>
              </>
            ) : mounted && authenticated && role === "SPECIALIST" ? (
              <>
                <Link className={pathname.startsWith("/specialist") ? "nav-link nav-link-active" : "nav-link"} href="/specialist/report" onClick={() => setMobileOpen(false)}>
                  Submit for review
                </Link>
                <button className="nav-button" onClick={signOut}>
                  <LogOut size={15} />
                  Sign out
                </button>
              </>
            ) : (
              <>
                <Link className="nav-button nav-button-dark" href="/login" onClick={() => setMobileOpen(false)}>
                  <LogIn size={15} />
                  Staff sign in
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main>{children}</main>
      <footer className="site-footer">
        <div className="footer-inner">
          <Logo compact />
          <p>Humanitarian content reporting and review.</p>
          <span>For authorised ICRC staff and public reporting.</span>
        </div>
      </footer>
    </div>
  );
}
