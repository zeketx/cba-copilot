import { compactCitationLabel } from "@/lib/citation";

/** Question and expected cites from `backend/evals/corpus_cases.yaml` (`minimum-salary`). */
const QUESTION = "What is the minimum salary for a player with 0 years of service?";
const EXHIBIT_C = compactCitationLabel({
  articleNumber: null,
  section: "Exhibit C",
  pageStart: null,
});
const SECTION_1JJ = compactCitationLabel({
  articleNumber: 1,
  section: "1(jj)",
  pageStart: 5,
});

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
          <p className="landing-example-kicker">Illustrative example</p>
          <p className="landing-example-label">0 YOS · Exhibit C baseline</p>
          <p className="landing-example-q">Q. {QUESTION}</p>
          <p className="landing-example-a">
            Exhibit C Baseline Minimum Annual Salary Scale. 0 years of service, Year 1 is $1,017,781.
            That cell is the baseline, not the 2023-24 amount. 2023-24 is Exhibit C adjusted by the
            percentage increase in the Salary Cap from 2022-23 to 2023-24. Later Salary Cap Years
            chain-adjust. The PDF states no adjusted dollar figure.
          </p>
          <p className="mt-3 flex flex-wrap gap-1.5">
            <span className="landing-chip">{EXHIBIT_C}</span>
            <span className="landing-chip">{SECTION_1JJ}</span>
          </p>
        </div>
      </div>
    </section>
  );
}
