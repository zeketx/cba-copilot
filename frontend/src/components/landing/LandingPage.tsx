import { Example } from "./Example";
import { Faq } from "./Faq";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import "./landing.css";
import { Sources } from "./Sources";

type LandingPageProps = {
  onGetAccess: () => void;
};

export function LandingPage({ onGetAccess }: LandingPageProps) {
  return (
    <div id="top" className="landing-page">
      <a className="landing-skip" href="#how">
        Skip to how it works
      </a>
      <Hero onGetAccess={onGetAccess} />
      <HowItWorks />
      <Example />
      <Sources />
      <Faq />
      <p className="landing-footer">Cited answers from the 2023 CBA. Not legal advice.</p>
    </div>
  );
}
