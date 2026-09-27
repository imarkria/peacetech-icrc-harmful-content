import { redirect } from "next/navigation";

// Specialist accounts became the trained volunteer lane.
export default function SpecialistReportRedirect() {
  redirect("/volunteer/report");
}
