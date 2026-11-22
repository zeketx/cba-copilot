import { useEffect, useState, type CSSProperties, type MouseEvent } from "react";
import bustCutout from "@/assets/landing/bust-cutout.webp";
import bustThinkingCutout from "@/assets/landing/bust-thinking-cutout.webp";
import corpus from "../../../../data/corpus.json";
import { REQUEST_ACCESS_HREF, SIGN_IN_HREF } from "./access";
import { CBA_THREAD_EXAMPLES } from "./cba-examples";
import "./landing.css";

type LandingPageProps = {
  onRequestAccess: () => void;
  onSignIn: () => void;
};

const ARROW_ICON = (
  <svg className="m-arrow" viewBox="0 0 12 12" aria-hidden="true">
    <path className="m-arrow__stem" d="M1 6h8" />
    <path className="m-arrow__head" d="M4.5 2.5 8 6l-3.5 3.5" />
  </svg>
);

const SHORT_TAB_LABEL: Record<string, string> = {
  "second-apron": "Second apron",
  "awards-65": "65-game rule",
  "taxpayer-mle": "Taxpayer MLE",
};

const FAQ_ITEMS = [
  {
    q: "Is CBA Copilot legal advice?",
    a: "No. CBA Copilot quotes the 2023 NBA-NBPA agreement and cites the printed page.",
  },
  {
    q: "When does CBA Copilot refuse a question?",
    a: "Unsupported claims are dropped. If no cited claim remains, CBA Copilot refuses.",
  },
  {
    q: "Which CBA document is indexed?",
    a: "Only the official 676-page 2023 NBA-NBPA Collective Bargaining Agreement PDF.",
  },
  {
    q: "Who can sign in to CBA Copilot?",
    a: "Access is invite-only. Approved emails sign in with a magic link.",
  },
] as const;

let kitLoaded = false;

export function LandingPage({ onRequestAccess, onSignIn }: LandingPageProps) {
  const [selectedId, setSelectedId] = useState(CBA_THREAD_EXAMPLES[0].id);
  const selectedThread =
    CBA_THREAD_EXAMPLES.find((item) => item.id === selectedId) ?? CBA_THREAD_EXAMPLES[0];
  const activeCitation = selectedThread.citations[0];

  useEffect(() => {
    if (kitLoaded) {
      return;
    }
    kitLoaded = true;
    const modules = [
      "/assets/system.js",
      "/assets/motion/motion.js",
      "/assets/layout/layout.js",
    ];
    for (const src of modules) {
      const script = document.createElement("script");
      script.type = "module";
      script.src = src;
      document.body.appendChild(script);
    }
  }, []);

  function handleRequestAccess(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onRequestAccess();
  }

  function handleSignIn(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onSignIn();
  }

  return (
    <div className="cba-landing">
      {/* type: software
          deal: hero collage, nav nav-centre (re-dealt from nav-cards: no photographs), close close-type, footer footer-dark, rhythm space, buttons pill, mark stack, ground sage, effect fluted-glass */}
      <header className="nav nav--centre">
        <div className="wrap nav__bar">
          <a className="skip-link" href="#top">
            Skip to content
          </a>
          <a className="nav__logo" href="#top" aria-label="CBA Copilot">
            <span className="mark" data-mark="stack" aria-hidden="true" />
            <span className="nav__wordmark">CBA Copilot</span>
          </a>
          <nav className="nav__links" aria-label="Main">
            <div className="nav__item">
              <a className="nav__link" href="#workspace">
                Workspace
              </a>
            </div>
            <div className="nav__item">
              <a className="nav__link" href="#checks">
                Citations
              </a>
            </div>
            <div className="nav__item">
              <a className="nav__link" href="#corpus">
                Corpus
              </a>
            </div>
            <div className="nav__item">
              <a className="nav__link" href="#faq">
                FAQ
              </a>
            </div>
          </nav>
          <div className="nav__actions">
            <a className="nav__link" href={SIGN_IN_HREF} onClick={handleSignIn}>
              Sign in
            </a>
            <a
              className="btn btn--primary"
              href={REQUEST_ACCESS_HREF}
              onClick={handleRequestAccess}
            >
              Request access
            </a>
          </div>
          <button className="nav__toggle" type="button" aria-expanded="false" aria-label="Menu">
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <path
                d="M2 5h14M2 13h14"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </header>

      <main id="top">
        <section className="hero hero--collage" data-enter aria-labelledby="hero-h">
          <div className="wrap">
            <div className="hero-text grid hero__grid">
              <div className="hero__text span-5">
                <h1 id="hero-h">
                  2023 NBA CBA research for <em>front offices</em>
                </h1>
                <p className="hero__lead">
                  Ask plain-language questions across all 676 pages of the 2023 NBA-NBPA agreement.
                  Every claim cites its article, section, and printed page.
                </p>
                <div className="btn-row">
                  <a
                    className="btn btn--primary"
                    href={REQUEST_ACCESS_HREF}
                    onClick={handleRequestAccess}
                  >
                    Request access
                    {ARROW_ICON}
                  </a>
                  <a className="btn btn--secondary" href="#workspace">
                    See the workspace
                  </a>
                </div>
                <p className="hero__proof">
                  Grounded in the{" "}
                  <a href={corpus.pdf_url} target="_blank" rel="noopener noreferrer">
                    official 2023 NBA-NBPA CBA
                  </a>{" "}
                  (676 pages).
                </p>
              </div>

              <div
                className="hero__art span-6 start-7"
                data-fx="fluted-glass"
                data-fx-seed="2023"
                role="img"
                aria-label="CBA Copilot answering a second-apron trade question with inline citations to Article VII, Section 2(e)(4), printed page 190, and a grounding verification card"
              >
                <div className="ly-piece ly-piece--main cba-win" aria-hidden="true">
                  <div className="cba-win__bar">
                    <span className="cba-win__dots">
                      <i />
                      <i />
                      <i />
                    </span>
                    <span>CBA Copilot · 2023 CBA</span>
                  </div>
                  <div className="cba-win__body">
                    <div className="cba-win__side">
                      <span className="cba-win__side-label">Threads</span>
                      <span className="cba-win__side-item is-on">Second apron</span>
                      <span className="cba-win__side-item">65-game rule</span>
                      <span className="cba-win__side-item">Taxpayer MLE</span>
                      <span className="cba-win__side-item">Bird rights</span>
                      <span className="cba-win__side-label">Reference</span>
                      <span className="cba-win__side-item">Glossary</span>
                    </div>
                    <div className="cba-win__main">
                      <div className="cba-win__q">
                        Can a second-apron team aggregate salaries or send cash in a trade?
                      </div>
                      <div className="cba-win__ans">
                        <p>
                          No. A team may not acquire a player using an Aggregated Standard Traded
                          Player Exception if that trade puts Apron Team Salary over the Second
                          Apron Level. <span className="cba-chip">Art. VII, § 2(e)(4) · p. 190</span>
                        </p>
                        <p>
                          Cash payments and Section 8(e)(1) sign-and-trade acquisitions are barred
                          under the same limit.{" "}
                          <span className="cba-chip">Art. VII, § 2(e)(4) · p. 191</span>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                <img
                  className="cba-hero-bust-front"
                  src={bustThinkingCutout}
                  alt=""
                  aria-hidden="true"
                  width={520}
                  height={694}
                  decoding="async"
                />

                <div
                  className="ly-piece ly-piece--note cba-note"
                  aria-hidden="true"
                  data-ly-steps="700"
                >
                  <div className="cba-note__head">
                    <h3>Grounding check</h3>
                    <span className="cba-note__badge" data-step="" data-step-at="4">
                      Verified
                    </span>
                  </div>
                  <div className="cba-note__line" data-step="">
                    <i>✓</i>
                    <span>
                      <b>Art. VII, § 2(e)(4)</b> retrieved whole
                    </span>
                  </div>
                  <div className="cba-note__line" data-step="">
                    <i>✓</i>
                    <span>
                      Quote matched on <b>printed p. 190</b>
                    </span>
                  </div>
                  <div className="cba-note__line" data-step="">
                    <i>✓</i>
                    <span>
                      <b>0 uncited claims</b> dropped
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="section" id="workspace" aria-labelledby="workspace-h">
          <div className="wrap">
            <div className="section-head">
              <h2 id="workspace-h">
                CBA Copilot workspace.{" "}
                <span className="muted">Inspect every cited clause beside the answer.</span>
              </h2>
            </div>

            <div className="cba-app frame ui ui-panel" data-visual="">
              <div className="cba-app__rail" role="tablist" aria-label="CBA questions">
                <p className="cba-app__rail-title">Questions</p>
                {CBA_THREAD_EXAMPLES.map((thread) => {
                  const isActive = thread.id === selectedThread.id;
                  return (
                    <button
                      key={thread.id}
                      type="button"
                      role="tab"
                      aria-selected={isActive}
                      className={`cba-app__thread${isActive ? " is-active" : ""}`}
                      onClick={() => setSelectedId(thread.id)}
                    >
                      <span className="cba-app__thread-name">
                        {SHORT_TAB_LABEL[thread.id] ?? thread.sidebarTitle}
                      </span>
                      <span className="cba-app__thread-meta">{thread.sidebarMeta}</span>
                    </button>
                  );
                })}
              </div>

              <div className="cba-app__chat" role="tabpanel">
                <p className="cba-app__q">{selectedThread.question}</p>
                <div className="cba-app__claims">
                  {selectedThread.claims.map((claim, index) => (
                    <p key={index} className="cba-app__claim">
                      {claim.text}
                      <span className="cba-app__cite-btn">{activeCitation.chip}</span>
                    </p>
                  ))}
                </div>
              </div>

              <aside className="cba-app__source" aria-label="Source passage">
                <div className="cba-app__source-head">
                  <span className="cba-app__source-tag">
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                      <path
                        d="M4 2h5l3 3v9H4V2zm5 0v3h3"
                        stroke="currentColor"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    Official PDF passage
                  </span>
                  <span className="cba-app__source-pages">
                    {activeCitation.printedPages} · PDF p. {activeCitation.pdfPage}
                  </span>
                </div>
                <p className="cba-app__source-sec">{activeCitation.section}</p>
                <p className="cba-app__source-art">{activeCitation.article}</p>
                <blockquote className="cba-app__source-body">{activeCitation.quote}</blockquote>
                <a
                  className="link"
                  href={`${corpus.pdf_url}#page=${activeCitation.pdfPage}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open printed page in PDF
                </a>
              </aside>
            </div>
          </div>
        </section>

        <section className="section" id="checks" aria-labelledby="checks-h">
          <div className="wrap">
            <div className="section-head">
              <h2 id="checks-h">
                Citation checks.{" "}
                <span className="muted">Unsupported claims are dropped.</span>
              </h2>
            </div>

            <div className="grid">
              <article className="card card--row card--open m-nolift span-6">
                <h3>CBA Copilot quote checks</h3>
                <p>
                  Each claim carries a passage ID and quote verified against the retrieved CBA text
                  before it reaches the screen.
                </p>
                <div
                  className="panel"
                  role="img"
                  aria-label="Article XXIX Section 6 text with the 65-game and 20-minute clauses highlighted and verified"
                >
                  <div className="stage stage--fade-b">
                    <div
                      className="at-corner fit to-edge"
                      style={
                        {
                          "--fit-max": "440px",
                          "--ax": "28px",
                          "--ay": "28px",
                        } as CSSProperties
                      }
                      data-ui-loop=""
                    >
                      <div className="ui ui-doc" data-ui="doc" aria-hidden="true">
                        <article className="ui-doc__page">
                          <div className="ui-doc__label">Article XXIX · Printed pp. 432–433</div>
                          <div className="ui-doc__title">Section 6. Games Played Requirement</div>
                          <div className="ui-doc__text">
                            A player is not eligible for MVP or All-NBA honors unless he played in
                            at least{" "}
                            <mark className="ui-doc__mark is-on">65 Regular Season games</mark>.
                          </div>
                          <div className="ui-doc__text">
                            A game counts at{" "}
                            <mark
                              className="ui-doc__mark"
                              data-kind="Verified"
                              data-msg="Two games per season are allowed at 15 minutes."
                              data-where="Article XXIX, Section 6 · p. 433"
                            >
                              20 minutes played
                            </mark>
                            , or 62 games after a season-ending injury with 85% of team games played.
                          </div>
                        </article>
                        <aside className="ui-doc__note ui-panel is-on">
                          <div className="ui-doc__kind">
                            <span className="ui-doc__dot" />
                            <span data-doc-kind="">Verified</span>
                          </div>
                          <div className="ui-doc__msg" data-doc-msg="">
                            Quote matched in retrieved set; claim kept.
                          </div>
                          <div className="ui-doc__where" data-doc-where="">
                            Article XXIX, Section 6 · p. 432
                          </div>
                        </aside>
                      </div>
                    </div>
                  </div>
                </div>
              </article>

              <article className="card card--row card--open m-nolift span-6">
                <h3>CBA section search and refusal</h3>
                <p>
                  Hybrid vector and full-text search keeps article boundaries intact. When no cited
                  claim survives verification, the answer refuses.
                </p>
                <div
                  className="panel"
                  role="img"
                  aria-label="CBA Copilot retrieval pipeline showing whole-section indexing, hybrid search, quote verification, and the refusal gate"
                >
                  <div className="stage">
                    <div
                      className="at-rise fit"
                      style={
                        {
                          "--fit-max": "420px",
                          "--ax": "max(20px, 50% - 210px)",
                          "--ay": "28px",
                          "--ay-sm": "16px",
                        } as CSSProperties
                      }
                    >
                      <div className="cba-trace" aria-hidden="true">
                        <div className="cba-trace__head">
                          <span className="cba-trace__title">Retrieval &amp; refusal gate</span>
                          <span className="cba-note__badge">Active</span>
                        </div>
                        <div className="cba-trace__row">
                          <span className="cba-trace__step">01</span>
                          <div>
                            <b>Article &amp; section index</b>
                            <small>Art. I–XLII + exhibits, whole sections</small>
                          </div>
                          <span className="cba-trace__tag">676 pp</span>
                        </div>
                        <div className="cba-trace__row">
                          <span className="cba-trace__step">02</span>
                          <div>
                            <b>Hybrid retrieval</b>
                            <small>Vector + Postgres full-text search</small>
                          </div>
                          <span className="cba-trace__tag">Top-K</span>
                        </div>
                        <div className="cba-trace__row">
                          <span className="cba-trace__step">03</span>
                          <div>
                            <b>Claim &amp; refusal check</b>
                            <small>Drops uncited claims; refuses if empty</small>
                          </div>
                          <span className="cba-trace__tag">Strict</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            </div>
            <p className="cba-checks-foot">
              <a className="link" href="#corpus">
                See corpus details
              </a>
            </p>
          </div>
        </section>

        <section className="section" id="corpus" aria-labelledby="corpus-h">
          <div className="wrap cba-corpus-wrap">
            <div className="cba-corpus-head">
              <h2 id="corpus-h" className="mo-la__type">
                One CBA corpus
              </h2>
              <p className="mo-la__sub cba-manifesto">
                <span className="cba-manifesto__strong">
                  Plain-language answers from the 2023 NBA-NBPA Collective Bargaining Agreement,
                  cited to the printed page.
                </span>{" "}
                <span className="cba-manifesto__mid">
                  Uncited claims are dropped before an answer prints,
                </span>{" "}
                <span className="cba-manifesto__soft">
                  and when the agreement does not cover a question, CBA Copilot refuses instead of
                  guessing.
                </span>
              </p>
            </div>
            <ul className="rows cba-corpus-rows">
              <li>
                <span className="rows__name">Official source</span>
                <span className="rows__value">2023 NBA-NBPA CBA PDF (676 pages)</span>
              </li>
              <li>
                <span className="rows__name">Effective term</span>
                <span className="rows__value">July 1, 2023 through 2029–30</span>
              </li>
              <li>
                <span className="rows__name">Page offset</span>
                <span className="rows__value">24-page front-matter offset mapped</span>
              </li>
            </ul>
            <p className="cba-corpus-link">
              <a
                className="link"
                href={corpus.pdf_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Open the official 2023 CBA PDF
              </a>
            </p>
          </div>
        </section>

        <section className="section" id="faq" aria-labelledby="faq-h">
          <div className="wrap">
            <div className="section-head">
              <h2 id="faq-h">FAQ and access</h2>
            </div>
            <div className="grid">
              <div className="faq span-6">
                {FAQ_ITEMS.map((item) => (
                  <div key={item.q} className="faq__item">
                    <h3>{item.q}</h3>
                    <p>{item.a}</p>
                  </div>
                ))}
              </div>
              <aside
                id="sign-in"
                className="cba-faq-panel frame span-6 start-7"
                data-visual=""
                aria-label="Invite-only access"
              >
                <img
                  className="cba-cutout-bust"
                  src={bustCutout}
                  alt=""
                  aria-hidden="true"
                  width={341}
                  height={480}
                  loading="lazy"
                  decoding="async"
                />
                <div className="cba-faq-panel__body">
                  <span className="cba-folio-dot" aria-hidden="true" />
                  <h3>Invite-only CBA Copilot access</h3>
                  <a className="link" href={SIGN_IN_HREF} onClick={handleSignIn}>
                    Sign in with a magic link
                  </a>
                </div>
              </aside>
            </div>
          </div>
        </section>
      </main>

      <footer
        className="footer closing footer--dark ground-inverse"
        id="contact"
        aria-labelledby="close-h"
      >
        <div className="wrap">
          <div id="request-access" className="closing__cta close--type">
            <div className="section-head">
              <h2 id="close-h">
                Request access to <em>CBA Copilot</em>
              </h2>
              <p>Invite-only access for front offices, cap analysts, agents, and reporters.</p>
            </div>
            <a
              className="btn btn--primary btn--xl btn--wide"
              href={REQUEST_ACCESS_HREF}
              onClick={handleRequestAccess}
            >
              Request access
              {ARROW_ICON}
            </a>
          </div>
          <div className="closing__links">
            <div className="grid">
              <div className="span-6 stack-4">
                <a className="nav__logo" href="#top">
                  <span className="mark" data-mark="stack" aria-hidden="true" />
                  CBA Copilot
                </a>
                <p className="footer__lede">
                  Cited answers from the 2023 NBA-NBPA Collective Bargaining Agreement.
                </p>
              </div>
              <div className="span-3 start-7 footer__col">
                <h3>Product</h3>
                <ul>
                  <li>
                    <a href="#workspace">Workspace</a>
                  </li>
                  <li>
                    <a href="#checks">Citations</a>
                  </li>
                  <li>
                    <a href="#corpus">Corpus</a>
                  </li>
                </ul>
              </div>
              <div className="span-3 footer__col">
                <h3>Access</h3>
                <ul>
                  <li>
                    <a href={SIGN_IN_HREF} onClick={handleSignIn}>
                      Sign in
                    </a>
                  </li>
                  <li>
                    <a href="#faq">FAQ</a>
                  </li>
                  <li>
                    <a href={corpus.pdf_url} target="_blank" rel="noopener noreferrer">
                      Official 2023 PDF
                    </a>
                  </li>
                </ul>
              </div>
            </div>
            <div className="footer__legal">
              <span>
                &copy; 2026 CBA Copilot &nbsp;·&nbsp; Not legal advice &nbsp;·&nbsp; Not affiliated
                with the NBA or NBPA.
              </span>
              <div className="socials" />
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
