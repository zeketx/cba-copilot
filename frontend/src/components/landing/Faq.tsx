import type { MouseEvent } from "react";
import { SIGN_IN_HREF } from "./access";

type FaqProps = {
  onSignIn: () => void;
};

export function Faq({ onSignIn }: FaqProps) {
  function goToSignIn(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onSignIn();
  }

  return (
    <section id="faq" className="landing-section">
      <div className="landing-section-inner">
        <h2>FAQ</h2>
        <div className="landing-faq">
          <h3>Is this legal advice?</h3>
          <p>No. The copilot quotes the agreement and cites the page. It does not replace a lawyer.</p>
        </div>
        <div className="landing-faq">
          <h3>What if the CBA does not cover the question?</h3>
          <p>It says so instead of guessing.</p>
        </div>
        <div className="landing-faq">
          <h3>Who can sign in?</h3>
          <p>
            Access is invite-only. Request access and we&apos;ll email you if you&apos;re approved.
            Already approved?{" "}
            <a
              href={SIGN_IN_HREF}
              className="text-landing-olive underline decoration-landing-line underline-offset-4 hover:text-landing-olive-hover"
              onClick={goToSignIn}
            >
              Sign in
            </a>{" "}
            with a magic link.
          </p>
        </div>
      </div>
    </section>
  );
}
