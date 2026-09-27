import { ShieldCheck } from "./icons";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand-lockup">
      <span className="brand-mark" aria-hidden="true">
        <ShieldCheck size={18} strokeWidth={2.2} />
      </span>
      {!compact && (
        <span className="brand-name">
          <span>signal</span>
          <span className="brand-name-muted">safe</span>
        </span>
      )}
    </span>
  );
}
