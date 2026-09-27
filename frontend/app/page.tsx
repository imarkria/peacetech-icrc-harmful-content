import Link from "next/link";
import Image from "next/image";
import { ArrowRight, ShieldCheck } from "../components/icons";
import landingVisual from "../resources/pic.png";

export default function HomePage() {
  return (
    <>
      <section className="public-hero">
        <div className="page-container public-hero-grid">
          <div className="public-hero-content">
            <span className="icrc-kicker">Public reporting</span>
            <h1>Report harmful content related to sexual violence in armed conflicts.</h1>
            <p>
              If you encounter a link that may contain or promote this content, submit it for screening.
              No account is required.
            </p>
            <Link className="button-primary" href="/report">
              Report a link <ArrowRight size={17} />
            </Link>
            <p className="public-privacy-note"><ShieldCheck size={15} /> Do not include personal information.</p>
          </div>
          <div className="public-hero-visual" aria-hidden="true">
            <Image
              src={landingVisual}
              alt=""
              priority
              sizes="(max-width: 1200px) 100vw, 52vw"
            />
          </div>
        </div>
      </section>

      <section className="public-next-section">
        <div className="page-container">
          <div className="icrc-section-heading">
            <span className="icrc-section-label">What happens next</span>
            <h2>How submissions are handled.</h2>
          </div>
          <div className="public-steps">
            <article><span>01</span><h3>Submit a link</h3><p>Enter the direct URL and, if useful, add brief context.</p></article>
            <article><span>02</span><h3>It is screened</h3><p>Only reports marked as potentially harmful enter the authorised reviewer queue.</p></article>
            <article><span>03</span><h3>Support future research</h3><p>Reports may contribute to research and future model development.</p></article>
          </div>
        </div>
      </section>
    </>
  );
}
