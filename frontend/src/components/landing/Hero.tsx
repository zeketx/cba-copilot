import type { MouseEvent } from "react";
import { GET_ACCESS_HREF } from "./access";
import { CourtScene } from "./CourtScene";

const NAV = [
  { href: "#how", label: "How it works" },
  { href: "#sources", label: "Sources" },
  { href: "#faq", label: "FAQ" },
] as const;

type HeroProps = {
  onGetAccess: () => void;
};

export function Hero({ onGetAccess }: HeroProps) {
  function goToSignIn(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onGetAccess();
  }

  return (
    <section className="landing-hero">
      <header className="relative z-20 flex items-center justify-between px-[clamp(1.15rem,4.2vw,3.75rem)] py-[1.35rem]">
        <a
          href="#top"
          className="landing-serif text-[1.28rem] font-semibold tracking-[-0.03em] text-landing-ink no-underline"
        >
          CBA Copilot
        </a>
        <nav
          className="absolute left-1/2 hidden -translate-x-1/2 gap-[2.15rem] min-[720px]:flex"
          aria-label="Primary"
        >
          {NAV.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="text-[0.95rem] text-landing-muted no-underline hover:text-landing-ink"
            >
              {item.label}
            </a>
          ))}
        </nav>
        <a href={GET_ACCESS_HREF} className="landing-btn" onClick={goToSignIn}>
          Get access
        </a>
      </header>

      <div className="landing-copy">
        <h1 className="landing-headline">The CBA, answered.</h1>
        <p className="landing-sub">Every answer cited to the page.</p>
        <div className="landing-actions">
          <a href={GET_ACCESS_HREF} className="landing-btn" onClick={goToSignIn}>
            Get access
          </a>
          <a href="#example" className="landing-btn-ghost">
            See an example
          </a>
        </div>
      </div>

      <CourtScene />
    </section>
  );
}
