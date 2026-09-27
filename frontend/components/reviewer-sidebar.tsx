"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ClipboardCheck, FileWarning } from "./icons";

export function ReviewerSidebar({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const onQueue = pathname === "/reviewer" || pathname.startsWith("/reviewer/");

  return <div className="reviewer-app">
    <aside className="reviewer-sidebar">
      <div className="reviewer-sidebar-label">Reviewer workspace</div>
      <nav className="reviewer-sidebar-nav" aria-label="Reviewer navigation">
        <Link className={onQueue ? "reviewer-sidebar-link reviewer-sidebar-link-active" : "reviewer-sidebar-link"} href="/reviewer"><FileWarning size={16} /> Queue</Link>
        <Link className="reviewer-sidebar-link" href="/reviewer?status=reviewed"><ClipboardCheck size={16} /> Reviewed</Link>
      </nav>
    </aside>
    <div className="reviewer-main">{children}</div>
  </div>;
}
