"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogIn, LogOut, Menu, X } from "./icons";
import { Logo } from "./logo";
import { getMeRequest, logoutRequest, UserRole } from "../lib/api";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [role, setRole] = useState<UserRole | null>(null);
  const [mounted, setMounted] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const authenticated = role !== null;

  useEffect(() => {
    // The session is an HTTP-only cookie: ask the backend who is signed in.
    let active = true;
    getMeRequest()
      .then((user) => active && setRole(user.role))
      .catch(() => active && setRole(null))
      .finally(() => active && setMounted(true));
    return () => {
      active = false;
    };
  }, [pathname]);

  async function signOut() {
    try {
      await logoutRequest();
    } catch {
      // The session may already have expired on the backend.
    }
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
            ) : mounted && authenticated && role === "VOLUNTEER" ? (
              <>
                <Link className={pathname.startsWith("/volunteer") ? "nav-link nav-link-active" : "nav-link"} href="/volunteer/report" onClick={() => setMobileOpen(false)}>
                  Volunteer report
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
                  Sign in
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
          <span>For the public, trained volunteers and authorised ICRC reviewers.</span>
        </div>
      </footer>
    </div>
  );
}
