import type { CSSProperties } from "react";
import ballSheet from "@/assets/landing/ball-sheet.webp";
import court from "@/assets/landing/court.webp";
import hoopBack from "@/assets/landing/hoop-back.webp";
import hoopFront from "@/assets/landing/hoop-front.webp";
import stands from "@/assets/landing/stands.webp";
import { COURT_LAYER_CSS, COURT_LAYERS, type CourtLayer } from "./layers";

const SRC: Record<CourtLayer["file"], string> = {
  "stands.webp": stands,
  "court.webp": court,
  "hoop-back.webp": hoopBack,
  "hoop-front.webp": hoopFront,
};

export function CourtScene() {
  return (
    <div
      className="court-scene"
      style={{ "--ball-src": `url(${ballSheet})` } as CSSProperties}
      aria-hidden="true"
    >
      <style>{COURT_LAYER_CSS}</style>
      <div className="court-ground">
        {COURT_LAYERS.map((layer) => (
          <img
            key={layer.id}
            className={`court-piece-${layer.id}`}
            src={SRC[layer.file]}
            alt=""
            width={layer.width}
            height={layer.height}
            decoding="async"
            fetchPriority={layer.id === "court" ? "high" : "low"}
          />
        ))}
        <div className="court-ball" />
      </div>
    </div>
  );
}
