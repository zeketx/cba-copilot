export const COURT_BREAKPOINT_PX = 720;
export const COURT_WIDE_PX = 1100;

export type LayerBox = {
  left?: string;
  right?: string;
  bottom?: string;
  width?: string;
  height?: string;
  "margin-left"?: string;
};

export type CourtLayer = {
  id: "stands" | "court" | "hoop-back" | "hoop-front";
  file: `${CourtLayer["id"]}.webp`;
  width: number;
  height: number;
  zIndex: number;
  /** The court is in normal flow and sizes the ground; the rest sit on it. */
  inFlow: boolean;
  mobile: LayerBox;
  desktop: LayerBox;
  wide?: LayerBox;
};

export const COURT_LAYERS: readonly CourtLayer[] = [
  {
    id: "stands",
    file: "stands.webp",
    width: 1230,
    height: 288,
    zIndex: 1,
    inFlow: false,
    mobile: { left: "2%", width: "96%", bottom: "78%", height: "auto" },
    desktop: { left: "13%", width: "68%", bottom: "78%", height: "auto" },
  },
  {
    id: "court",
    file: "court.webp",
    width: 1280,
    height: 321,
    zIndex: 2,
    inFlow: true,
    mobile: { width: "155%", "margin-left": "-27.5%", height: "auto" },
    desktop: { width: "100%", "margin-left": "0", height: "auto" },
  },
  {
    id: "hoop-back",
    file: "hoop-back.webp",
    width: 488,
    height: 855,
    zIndex: 3,
    inFlow: false,
    mobile: { right: "-2%", bottom: "14%", height: "min(400px, 42vh)", width: "auto" },
    desktop: {
      right: "6%",
      bottom: "20%",
      height: "clamp(340px, 52vh, 470px)",
      width: "auto",
    },
    wide: { right: "7%", bottom: "18%", height: "min(58vh, 480px)", width: "auto" },
  },
  {
    id: "hoop-front",
    file: "hoop-front.webp",
    width: 488,
    height: 855,
    zIndex: 5,
    inFlow: false,
    mobile: { right: "-2%", bottom: "14%", height: "min(400px, 42vh)", width: "auto" },
    desktop: {
      right: "6%",
      bottom: "20%",
      height: "clamp(340px, 52vh, 470px)",
      width: "auto",
    },
    wide: { right: "7%", bottom: "18%", height: "min(58vh, 480px)", width: "auto" },
  },
];

export const BALL_LAYER = {
  file: "ball-sheet.webp",
  zIndex: 4,
  frameCount: 4,
  nativeFrame: 288,
  sizePx: { mobile: 78, desktop: 80, wide: 84 },
  reducedMotion: { left: "58%", bottom: "96%", scale: "0.9" },
} as const;

function declarations(box: LayerBox): string {
  return Object.entries(box)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string")
    .map(([property, value]) => `${property}: ${value};`)
    .join(" ");
}

function pieceRule(layer: CourtLayer, box: LayerBox, includeBase: boolean): string {
  const base = includeBase
    ? `position: ${layer.inFlow ? "relative" : "absolute"}; z-index: ${String(layer.zIndex)}; `
    : "";
  return `.court-piece-${layer.id} { ${base}${declarations(box)} }`;
}

/** Layout CSS derived from COURT_LAYERS / BALL_LAYER so positions stay in one place. */
export const COURT_LAYER_CSS = [
  `.court-scene { --ball: ${String(BALL_LAYER.sizePx.mobile)}px; }`,
  ...COURT_LAYERS.map((layer) => pieceRule(layer, layer.mobile, true)),
  `@media (min-width: ${String(COURT_BREAKPOINT_PX)}px) {`,
  `  .court-scene { --ball: ${String(BALL_LAYER.sizePx.desktop)}px; }`,
  ...COURT_LAYERS.map((layer) => `  ${pieceRule(layer, layer.desktop, false)}`),
  `}`,
  `@media (min-width: ${String(COURT_WIDE_PX)}px) {`,
  `  .court-scene { --ball: ${String(BALL_LAYER.sizePx.wide)}px; }`,
  ...COURT_LAYERS.filter((layer) => layer.wide !== undefined).map(
    (layer) => `  ${pieceRule(layer, layer.wide ?? {}, false)}`,
  ),
  `}`,
  `@media (prefers-reduced-motion: reduce) {`,
  `  .court-ball {`,
  `    animation: none !important;`,
  `    opacity: 1;`,
  `    left: ${BALL_LAYER.reducedMotion.left};`,
  `    bottom: ${BALL_LAYER.reducedMotion.bottom};`,
  `    transform: scale(${BALL_LAYER.reducedMotion.scale});`,
  `  }`,
  `}`,
].join("\n");
