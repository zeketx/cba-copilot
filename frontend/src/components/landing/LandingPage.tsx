import { Example } from "./Example";
import { Faq } from "./Faq";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import "./landing.css";
import { Sources } from "./Sources";

type LandingPageProps = {
  onRequestAccess: () => void;
  onSignIn: () => void;
};

export function LandingPage({ onRequestAccess, onSignIn }: LandingPageProps) {
  return (
    <div id="top" className="landing-page">
      <a className="landing-skip" href="#how">
        Skip to how it works
      </a>
      <Hero onRequestAccess={onRequestAccess} onSignIn={onSignIn} />
      <Example />
      <HowItWorks />
      <Sources />
      <Faq onSignIn={onSignIn} />
      <p className="landing-footer">
        Cited answers from the 2023 NBA–NBPA Collective Bargaining Agreement. Not legal advice. Not
        affiliated with the NBA or NBPA.
      </p>
    </div>
  );
}
