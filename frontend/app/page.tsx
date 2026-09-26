// import Link from "next/link";
// import { ArrowRight, BadgeCheck, ClipboardCheck, Flag, Globe2, ShieldCheck, Sparkles } from "../components/icons";
//
// export default function HomePage() {
//   return (
//     <>
//       <section className="hero">
//         <div className="page-container hero-grid">
//           <div>
//             <span className="eyebrow">A safer signal in the noise</span>
//             <h1>Help make online spaces <span>safer.</span></h1>
//             <p className="hero-copy">SignalSafe brings public reporting and expert review together to identify harmful content related to sexual violence during wars.</p>
//             <div className="hero-actions">
//               <Link className="button-primary" href="/report">Report a harmful link <ArrowRight size={17} /></Link>
//               <Link className="button-secondary" href="/login">Reviewer workspace <BadgeCheck size={16} /></Link>
//             </div>
//             <p className="hero-note"><ShieldCheck size={15} /> No account needed to submit a report.</p>
//           </div>
//           <div className="hero-card" aria-label="Review queue preview">
//             <div className="preview-header">
//               <div><div className="preview-overline">Reviewer workspace</div><div className="preview-title">Potentially harmful links</div></div>
//               <span className="preview-status">Live queue</span>
//             </div>
//             <div className="preview-row"><div><div className="preview-url">t.me/example_channel/1842</div><div className="preview-channel">Telegram · Detected today</div></div><div><div className="confidence">93%</div><div className="preview-bar"><span style={{ width: "93%" }} /></div></div></div>
//             <div className="preview-row"><div><div className="preview-url">t.me/public_updates/771</div><div className="preview-channel">Telegram · Detected today</div></div><div><div className="confidence">88%</div><div className="preview-bar"><span style={{ width: "88%" }} /></div></div></div>
//             <div className="preview-row"><div><div className="preview-url">t.me/community_watch/338</div><div className="preview-channel">Telegram · Detected yesterday</div></div><div><div className="confidence">81%</div><div className="preview-bar"><span style={{ width: "81%" }} /></div></div></div>
//             <p className="preview-caption">Model signals are reviewed by trained reviewers.</p>
//           </div>
//         </div>
//       </section>
//
//       <section className="section section-tint">
//         <div className="page-container">
//           <div className="section-heading"><span className="eyebrow">Two ways to contribute</span><h2>Every signal helps build a clearer picture.</h2><p>Whether you are reporting something you saw or validating a model signal, your contribution helps improve future detection.</p></div>
//           <div className="pathway-grid">
//             <div className="pathway-card pathway-card-accent"><span className="pathway-icon"><Flag size={19} /></span><h3>Report a harmful link</h3><p>Seen a link that may relate to sexual violence, child safety, or hate? Submit it anonymously. Your report will be stored securely for future research and model training.</p><Link className="pathway-link" href="/report">Make a report <ArrowRight size={15} /></Link></div>
//             <div className="pathway-card pathway-card-dark"><span className="pathway-icon"><ClipboardCheck size={19} /></span><h3>Review model signals</h3><p>ICRC reviewers can sign in to assess potentially harmful links detected from Telegram and add a human-validated label.</p><Link className="pathway-link" href="/login">Open reviewer login <ArrowRight size={15} /></Link></div>
//           </div>
//         </div>
//       </section>
//
//       <section className="section">
//         <div className="page-container">
//           <div className="section-heading"><span className="eyebrow">Designed with care</span><h2>Useful signals, handled responsibly.</h2></div>
//           <div className="principles">
//             <div className="principle"><Globe2 className="principle-icon" size={22} /><h3>Public participation</h3><p>Anyone can submit a link without creating an account or exposing personal information.</p></div>
//             <div className="principle"><ShieldCheck className="principle-icon" size={22} /><h3>Human validation</h3><p>Model predictions are only signals. Trained reviewers make the final label for the review queue.</p></div>
//             <div className="principle"><Sparkles className="principle-icon" size={22} /><h3>Better models over time</h3><p>Validated labels can become training data to improve future harmful-content detection.</p></div>
//           </div>
//         </div>
//       </section>
//     </>
//   );
// }
import Link from "next/link";
import {
    ArrowRight,
    BadgeCheck,
    ClipboardCheck,
    Flag,
    Globe2,
    ShieldCheck,
    Sparkles,
} from "../components/icons";

export default function HomePage() {
    return (
        <>
            <section className="hero">
                <div className="page-container hero-grid">
                    <div>
            <span className="eyebrow">
              Identifying harmful information in armed conflict
            </span>

                        <h1>
                            Help identify harmful information related to{" "}
                            <span>conflict-related sexual violence.</span>
                        </h1>

                        <p className="hero-copy" style={{fontSize: "1rem", lineHeight: 1.6}}>
                            SignalSafe brings public reporting and human review together to
                            identify potentially harmful information related to
                            sexual violence during armed conflicts.
                        </p>

                        <div className="hero-actions">
                            <Link className="button-primary" href="/report">
                                Report a harmful link <ArrowRight size={17}/>
                            </Link>

                            <Link className="button-secondary" href="/login">
                                Reviewer workspace <BadgeCheck size={16}/>
                            </Link>
                        </div>

                        <p className="hero-note">
                            <ShieldCheck size={15}/>
                            No account is required to submit a report.
                        </p>
                    </div>

                    <div className="hero-card" aria-label="Review queue preview">
                        <div className="preview-header">
                            <div>
                                <div className="preview-overline">Reviewer workspace</div>
                                <div className="preview-title">
                                    Potentially harmful links
                                </div>
                            </div>

                            <span className="preview-status">Review queue</span>
                        </div>

                        <div className="preview-row">
                            <div>
                                <div className="preview-url">
                                    t.me/example_channel/1842
                                </div>
                                <div className="preview-channel">
                                    Telegram · Detected today
                                </div>
                            </div>

                            <div>
                                <div className="confidence">93%</div>
                                <div className="preview-bar">
                                    <span style={{width: "93%"}}/>
                                </div>
                            </div>
                        </div>

                        <div className="preview-row">
                            <div>
                                <div className="preview-url">
                                    t.me/public_updates/771
                                </div>
                                <div className="preview-channel">
                                    Telegram · Detected today
                                </div>
                            </div>

                            <div>
                                <div className="confidence">88%</div>
                                <div className="preview-bar">
                                    <span style={{width: "88%"}}/>
                                </div>
                            </div>
                        </div>

                        <div className="preview-row">
                            <div>
                                <div className="preview-url">
                                    t.me/community_watch/338
                                </div>
                                <div className="preview-channel">
                                    Telegram · Detected yesterday
                                </div>
                            </div>

                            <div>
                                <div className="confidence">81%</div>
                                <div className="preview-bar">
                                    <span style={{width: "81%"}}/>
                                </div>
                            </div>
                        </div>

                        <p className="preview-caption">
                            Automated detections are signals only.
                            Reviewers provide the human-validated label.
                        </p>
                    </div>
                </div>
            </section>

            <section className="section section-tint">
                <div className="page-container">
                    <div className="section-heading">
                        <span className="eyebrow">Two ways to contribute</span>

                        <h2>
                            Human reports and expert review help build better evidence.
                        </h2>

                        <p>
                            Public reports contribute examples of potentially harmful
                            information, while authorized reviewers validate links detected
                            by the system.
                        </p>
                    </div>

                    <div className="pathway-grid">
                        <div className="pathway-card pathway-card-accent">
              <span className="pathway-icon">
                <Flag size={19}/>
              </span>

                            <h3>Report a harmful link</h3>

                            <p>
                                Seen online information that may be harmful and related to
                                conflict-related sexual violence? Submit the link without
                                creating an account. Reports are kept separately for future
                                research and model development.
                            </p>

                            <Link className="pathway-link" href="/report">
                                Make a report <ArrowRight size={15}/>
                            </Link>
                        </div>

                        <div className="pathway-card pathway-card-dark">
              <span className="pathway-icon">
                <ClipboardCheck size={19}/>
              </span>

                            <h3>Review detected links</h3>

                            <p>
                                ICRC reviewers can sign in to assess potentially harmful links
                                and assign a human-validated label.
                            </p>

                            <Link className="pathway-link" href="/login">
                                Open reviewer login <ArrowRight size={15}/>
                            </Link>
                        </div>
                    </div>
                </div>
            </section>

            <section className="section">
                <div className="page-container">
                    <div className="section-heading">
                        <span className="eyebrow">Designed with care</span>

                        <h2>
                            Human judgment remains at the center of the review process.
                        </h2>
                    </div>

                    <div className="principles">
                        <div className="principle">
                            <Globe2 className="principle-icon" size={22}/>

                            <h3>Public reporting</h3>

                            <p>
                                Anyone can submit a relevant link without creating an account.
                                Public reports are kept separate from the reviewer queue.
                            </p>
                        </div>

                        <div className="principle">
                            <ShieldCheck className="principle-icon" size={22}/>

                            <h3>Human validation</h3>

                            <p>
                                Automated predictions indicate potentially relevant content.
                                Reviewers determine the final label for detected links.
                            </p>
                        </div>

                        <div className="principle">
                            <Sparkles className="principle-icon" size={22}/>

                            <h3>Improving detection</h3>

                            <p>
                                Human-reviewed labels and public reports can support the
                                development of future systems for detecting harmful
                                information related to conflict-related sexual violence.
                            </p>
                        </div>
                    </div>
                </div>
            </section>
        </>
    );
}