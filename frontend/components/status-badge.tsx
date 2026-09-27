import { categoryLabels, ViolationCategory } from "../lib/review-data";

const categoryClass: Record<ViolationCategory, string> = {
  sexual_violence: "badge badge-red",
  child_related_harm: "badge badge-amber",
  hate_related: "badge badge-violet",
  other: "badge badge-slate",
};

export function CategoryBadge({ category }: { category: ViolationCategory }) {
  return <span className={categoryClass[category]}>{categoryLabels[category]}</span>;
}

export function StatusBadge({ status }: { status: "PENDING" | "REVIEWED" }) {
  return (
    <span className={`status-badge ${status === "PENDING" ? "status-pending" : "status-reviewed"}`}>
      <span className="status-dot" />
      {status === "PENDING" ? "Pending review" : "Reviewed"}
    </span>
  );
}
