const ITEMS = [
  {
    q: "Is this legal advice?",
    a: "No. The copilot quotes the agreement and cites the page. It does not replace a lawyer.",
  },
  {
    q: "What if the CBA does not cover the question?",
    a: "The copilot refuses. It will not invent a rule to fill the gap.",
  },
  {
    q: "Who can sign in?",
    a: "Access is invite-only. Get access sends a magic-link to your email. Only approved addresses can use the copilot.",
  },
] as const;

export function Faq() {
  return (
    <section id="faq" className="landing-section">
      <div className="landing-section-inner">
        <h2>FAQ</h2>
        {ITEMS.map((item) => (
          <div key={item.q} className="landing-faq">
            <h3>{item.q}</h3>
            <p>{item.a}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
