import Link from "next/link";
import { ArrowRight, ShieldCheck } from "../components/icons";

export default function HomePage() {
  return (
    <>
      <section className="public-hero">
        <div className="page-container public-hero-content">
          <span className="icrc-kicker">Public reporting</span>
          <h1>Report harmful information.</h1>
          <p>
            Seen online information that may be related to conflict-related sexual violence?
            Submit the link here. No account is required.
          </p>
          <Link className="button-primary" href="/report">
            Report a link <ArrowRight size={17} />
          </Link>
          <p className="public-privacy-note"><ShieldCheck size={15} /> Do not include personal information.</p>
        </div>
      </section>

      <section className="public-next-section">
        <div className="page-container">
          <div className="icrc-section-heading">
            <span className="icrc-section-label">What happens next</span>
            <h2>Your report is reviewed safely.</h2>
          </div>
          <div className="public-steps">
            <article><span>01</span><h3>Submit a link</h3><p>Enter the direct URL and, if useful, add a short reason.</p></article>
            <article><span>02</span><h3>It is reviewed</h3><p>Your report is added to the authorised reviewer queue.</p></article>
            <article><span>03</span><h3>It may support future models</h3><p>Reports may also support future research and model development.</p></article>
          </div>
        </div>
      </section>
    </>
  );
}
