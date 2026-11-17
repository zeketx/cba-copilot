export function Example() {
  return (
    <section id="example" className="landing-section">
      <div className="landing-section-inner">
        <h2>See an example</h2>
        <p>
          A reply names the rule in plain language, then pins it to the page. Open the chip to read
          that passage in the official PDF.
        </p>
        <div className="landing-example">
          <p className="landing-example-q">
            Q. What can a second-apron team not do in a trade?
          </p>
          <p className="landing-example-a">
            The copilot answers from the retrieved passage and cites the printed page, not a
            rumor site.
          </p>
          <p className="mt-3">
            <span className="landing-chip">Art. VII §2(e) p.187</span>
          </p>
        </div>
      </div>
    </section>
  );
}
