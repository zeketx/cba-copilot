export function HowItWorks() {
  return (
    <section id="how" className="landing-section">
      <div className="landing-section-inner">
        <h2>How it works</h2>
        <ol>
          <li>Ask a question about the 2023 NBA–NBPA Collective Bargaining Agreement.</li>
          <li>
            The copilot retrieves whole article and section passages from the official PDF — not
            snippets split across a page break.
          </li>
          <li>
            Every claim is cited to a printed page. A citation outside the retrieved set is dropped.
            If none remain, the copilot refuses instead of guessing.
          </li>
        </ol>
      </div>
    </section>
  );
}
