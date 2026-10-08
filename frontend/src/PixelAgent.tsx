// Pixel-art staff, drawn as SVG rects on a 16x16 grid.
//
// Two frames per figure. Which one shows, and how fast they alternate, is
// driven by the agent's real status - so the movement on screen is a readout
// of what the backend reported, not decoration running on a timer.
//
//   working    hands type, figure bobs, desk lamp warm
//   delegated  still, with a token drifting away to the right
//   waiting    slow restless typing
//   done       still, eyes open, small tick
//   idle       still, occasional blink

import type { StaffStatus } from "./desk";

/** 16 rows of 16. Legend: H hair · S skin · E eye · C shirt · D desk · K chair */
const FRAME_A = [
  "................",
  ".....HHHHH......",
  "....HHHHHHH.....",
  "....HSSSSSH.....",
  "....HSESESH.....",
  ".....SSSSS......",
  "......SSS.......",
  "...CCCCCCCCC....",
  "..CCCCCCCCCCC...",
  "..SCCCCCCCCCS...",
  "..SCCCCCCCCCS...",
  "..SS.......SS...",
  "DDDDDDDDDDDDDDDD",
  "DDDDDDDDDDDDDDDD",
  "..K..........K..",
  "..K..........K..",
];

/** Hands lifted off the desk - the other half of the typing cycle. */
const FRAME_B = [
  "................",
  "................",
  ".....HHHHH......",
  "....HHHHHHH.....",
  "....HSSSSSH.....",
  "....HSESESH.....",
  ".....SSSSS......",
  "......SSS.......",
  "...CCCCCCCCC....",
  "..CCCCCCCCCCC...",
  "..SSCCCCCCCSS...",
  "...C.......C....",
  "DDDDDDDDDDDDDDDD",
  "DDDDDDDDDDDDDDDD",
  "..K..........K..",
  "..K..........K..",
];

export interface PixelPalette {
  hair: string;
  skin: string;
  shirt: string;
}

const DESK = "#8a6f52";
const DESK_EDGE = "#6d573f";
const CHAIR = "#4a4035";
const EYE = "#2a2d2f";

function colorFor(ch: string, p: PixelPalette): string | null {
  switch (ch) {
    case "H":
      return p.hair;
    case "S":
      return p.skin;
    case "C":
      return p.shirt;
    case "D":
      return DESK;
    case "K":
      return CHAIR;
    default:
      return null;
  }
}

/** One frame as a group of 1x1 rects. Eyes are kept separate so they can blink. */
function Frame({
  grid,
  palette,
  className,
}: {
  grid: string[];
  palette: PixelPalette;
  className?: string;
}) {
  const body: React.ReactElement[] = [];
  const eyes: React.ReactElement[] = [];

  grid.forEach((row, y) => {
    [...row].forEach((ch, x) => {
      if (ch === "E") {
        // draw skin underneath so a blink has something to close onto
        body.push(
          <rect key={`b${x}-${y}`} x={x} y={y} width="1" height="1" fill={palette.skin} />,
        );
        eyes.push(
          <rect key={`e${x}-${y}`} x={x} y={y} width="1" height="1" fill={EYE} />,
        );
        return;
      }
      const fill = colorFor(ch, palette);
      if (!fill) return;
      body.push(
        <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill={fill} />,
      );
    });
  });

  // a darker lip along the desk front, so it reads as a surface not a block
  body.push(
    <rect key="edge" x={0} y={13} width={16} height={1} fill={DESK_EDGE} opacity={0.55} />,
  );

  return (
    <g className={className}>
      {body}
      <g className="px-eyes">{eyes}</g>
    </g>
  );
}

interface Props {
  palette: PixelPalette;
  status: StaffStatus;
  size?: number;
  title?: string;
}

export function PixelAgent({ palette, status, size = 46, title }: Props) {
  return (
    <svg
      className={`px px--${status}`}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      shapeRendering="crispEdges"
      role="img"
      aria-label={title ?? `agent, ${status}`}
    >
      {title && <title>{title}</title>}

      {/* desk lamp pool — warms only while actually working */}
      <rect className="px-lamp" x={1} y={11} width={14} height={1} fill="#f2c877" />

      <Frame grid={FRAME_A} palette={palette} className="px-a" />
      <Frame grid={FRAME_B} palette={palette} className="px-b" />

      {/* handoff token, drifting right while this agent is waiting on another */}
      <g className="px-token">
        <rect x={12} y={2} width={2} height={2} fill={palette.shirt} />
      </g>

      {/* a small tick once the agent is finished */}
      <g className="px-tick">
        <rect x={12} y={3} width={1} height={1} fill="#426a4a" />
        <rect x={13} y={4} width={1} height={1} fill="#426a4a" />
        <rect x={14} y={2} width={1} height={1} fill="#426a4a" />
        <rect x={15} y={1} width={1} height={1} fill="#426a4a" />
      </g>
    </svg>
  );
}
