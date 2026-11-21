export type CbaCitation = {
  id: string;
  chip: string;
  article: string;
  section: string;
  printedPages: string;
  pdfPage: number;
  quote: string;
  passage: string;
};

export type CbaThreadExample = {
  id: string;
  sidebarTitle: string;
  sidebarMeta: string;
  question: string;
  claims: readonly {
    text: string;
    citationId: string;
  }[];
  citations: readonly CbaCitation[];
};

export const CBA_THREAD_EXAMPLES: readonly CbaThreadExample[] = [
  {
    id: "second-apron",
    sidebarTitle: "Second apron trade limits",
    sidebarMeta: "Art. VII · pp. 190–191",
    question: "Can a second-apron team aggregate salaries or send cash in a trade?",
    claims: [
      {
        text: "A team cannot acquire a player using an Aggregated Standard Traded Player Exception if the trade puts Apron Team Salary over the Second Apron Level.",
        citationId: "art7-2e4",
      },
      {
        text: "A team also cannot pay cash to another team in a trade, or take back a player from a sign-and-trade under Section 8(e)(1), if that transaction pushes Apron Team Salary over the Second Apron Level.",
        citationId: "art7-2e4",
      },
    ],
    citations: [
      {
        id: "art7-2e4",
        chip: "Art. VII, § 2(e)(4) · p. 190",
        article: "Article VII — Basketball Related Income, Salary Cap, and Apron Levels",
        section: "Section 2(e)(4) Transaction Restrictions Table",
        printedPages: "pp. 190–191",
        pdfPage: 214,
        quote:
          "A team may not acquire a player using an Aggregated Standard Traded Player Exception if that trade would put Apron Team Salary over the Second Apron Level.",
        passage:
          "A team may not acquire a player using an Aggregated Standard Traded Player Exception if that trade would put Apron Team Salary over the Second Apron Level. A team may not pay cash to another team in a trade if that payment would put it over the Second Apron Level. A team may not take a player back in a Traded Player Exception that came from a contract signed and traded under Section 8(e)(1) if that trade would put it over the Second Apron Level.",
      },
    ],
  },
  {
    id: "awards-65",
    sidebarTitle: "65-game award threshold",
    sidebarMeta: "Art. XXIX · pp. 432–433",
    question: "What are the games-played rules for MVP and All-NBA eligibility?",
    claims: [
      {
        text: "A player must appear in at least 65 Regular Season games to qualify for MVP, Defensive Player of the Year, Most Improved Player, All-NBA, or All-Defensive honors.",
        citationId: "art29-6",
      },
      {
        text: "A game counts at 20 minutes played, with up to two games per season allowed at 15 minutes; a player with a season-ending injury can still qualify at 62 games if he played at least 85% of team games beforehand.",
        citationId: "art29-6",
      },
    ],
    citations: [
      {
        id: "art29-6",
        chip: "Art. XXIX, § 6 · p. 432",
        article: "Article XXIX — Miscellaneous",
        section: "Section 6 Games Played Requirement for Certain League Honors",
        printedPages: "pp. 432–433",
        pdfPage: 456,
        quote:
          "A player is not eligible for NBA Most Valuable Player, NBA Defensive Player of the Year, NBA Most Improved Player, All-NBA Team, or NBA All-Defensive Team honors unless he played in at least sixty-five (65) Regular Season games.",
        passage:
          "A player is not eligible for NBA Most Valuable Player, NBA Defensive Player of the Year, NBA Most Improved Player, All-NBA Team, or NBA All-Defensive Team honors unless he played in at least sixty-five (65) Regular Season games, or played at least sixty-two games, suffered a season-ending injury, and played in at least 85 percent of his team's games before that injury. A game counts at 20 minutes, with two games a season allowed at 15 minutes.",
      },
    ],
  },
  {
    id: "taxpayer-mle",
    sidebarTitle: "Taxpayer MLE above second apron",
    sidebarMeta: "Art. VII · pp. 237–238",
    question: "Does the Taxpayer Mid-Level Exception shrink above the second apron?",
    claims: [
      {
        text: "The Taxpayer Mid-Level Salary Exception covers contracts of up to two seasons ($5 million in 2023–24, scaling with the Salary Cap) once Apron Team Salary is above the First Apron Level.",
        citationId: "art7-6f",
      },
      {
        text: "The dollar formula does not shrink above the second apron — availability disappears, because Row K treats its use as a Second Apron Level transaction.",
        citationId: "art7-6f",
      },
    ],
    citations: [
      {
        id: "art7-6f",
        chip: "Art. VII, § 6(f) · p. 237",
        article: "Article VII — Basketball Related Income, Salary Cap, and Apron Levels",
        section: "Section 6(f) Taxpayer Mid-Level Salary Exception",
        printedPages: "pp. 237–238",
        pdfPage: 261,
        quote:
          "Row K of the Transaction Restrictions Table treats use of this exception as a Second Apron Level transaction, so a team cannot use it when the signing would put Apron Team Salary over the Second Apron Level.",
        passage:
          "A team may use the Taxpayer Mid-Level Salary Exception to sign one or more contracts of up to two seasons once its Apron Team Salary is above the First Apron Level. For 2023-24 the amount is 5 million dollars, and later years scale that amount with the Salary Cap. Row K of the Transaction Restrictions Table treats use of this exception as a Second Apron Level transaction, so a team cannot use it when the signing would put Apron Team Salary over the Second Apron Level. The dollar formula itself does not shrink above the second apron. Availability does.",
      },
    ],
  },
];
