import corpus from "../../../../data/corpus.json";

export function Sources() {
  return (
    <section id="sources" className="landing-section">
      <div className="landing-section-inner">
        <h2>Sources</h2>
        <p>
          One corpus: the official 2023 NBA–NBPA Collective Bargaining Agreement PDF. Each citation
          names the article, the section, and the printed page, and opens that page in the file.
          Only the official agreement is a source.
        </p>
        <p className="mt-4">
          <a
            href={corpus.pdf_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-landing-olive underline decoration-landing-line underline-offset-4 hover:text-landing-olive-hover"
          >
            Official 2023 NBA–NBPA CBA PDF
          </a>
        </p>
      </div>
    </section>
  );
}
