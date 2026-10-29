# Corpus

The only source of truth is the official 2023 NBA-NBPA Collective Bargaining Agreement linked from [nbpa.com/cba](https://nbpa.com/cba). It is 676 pages. It took effect on 1 July 2023 and runs through the 2029-30 season.

`data/download_cba.py` reads that page and saves the PDF under `data/downloads/`. The PDF is gitignored. The license on the agreement is not a license to commit the file.

## Optional markdown aid

[atlhawksfanatic/NBA-CBA-2023](https://github.com/atlhawksfanatic/NBA-CBA-2023) splits the agreement into one markdown file per article. The repository license is GPL-3.0. The author says the conversion is unofficial and disclaims accuracy.

This repo does not vendor those files. `data/download_markdown_aid.py` writes them into gitignored `data/markdown-aid/` only when you pass `--i-accept-the-unofficial-aid`. The chunker can read that markdown. Every chunk still needs the official PDF url and page. The aid has no page numbers.

## Out of scope

Do not ingest Larry Coon's Salary Cap FAQ. It was retired in June 2025 and its reproduction terms do not allow this use.

Do not scrape Hoops Rumors or RealGM.

## Page numbers

Printed page 1 of the July 2023 PDF is viewer page 25. `data/corpus.json` records that offset as 24. Citation links use `#page=` on the PDF url, which is the viewer page.
