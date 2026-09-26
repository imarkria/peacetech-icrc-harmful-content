"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogIn, LogOut, Menu, X } from "./icons";
import { Logo } from "./logo";

const AUTH_KEY = "icrc-reviewer-auth";

export function isReviewerAuthenticated() {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(AUTH_KEY) === "true";
}

export function setReviewerAuthenticated(value: boolean) {
  if (typeof window !== "undefined") {
    if (value) window.localStorage.setItem(AUTH_KEY, "true");
    else window.localStorage.removeItem(AUTH_KEY);
  }
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [authenticated, setAuthenticated] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setAuthenticated(isReviewerAuthenticated());
  }, [pathname]);

  function signOut() {
    setReviewerAuthenticated(false);
    setAuthenticated(false);
    setMobileOpen(false);
    router.push("/");
  }

  const isReviewArea = pathname.startsWith("/review") || pathname === "/login";

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
            {authenticated ? (
              <>
                <Link className={isReviewArea ? "nav-link nav-link-active" : "nav-link"} href="/review" onClick={() => setMobileOpen(false)}>
                  Review workspace
                </Link>
                <button className="nav-button" onClick={signOut}>
                  <LogOut size={15} />
                  Sign out
                </button>
              </>
            ) : (
              <Link className="nav-button nav-button-dark" href="/login" onClick={() => setMobileOpen(false)}>
                <LogIn size={15} />
                Reviewer login
              </Link>
            )}
          </nav>
        </div>
      </header>
      <main>{children}</main>
      <footer className="site-footer">
        <div className="footer-inner">
          <Logo compact />
          <p>Built for safer humanitarian information spaces.</p>
          <span>PeaceTech ICRC challenge · MVP</span>
        </div>
      </footer>
    </div>
  );
}
