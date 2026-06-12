import { useEffect, useRef, useState } from "react";
import { cn } from "./components/ui";
import { HistoryPage } from "./pages/HistoryPage";
import { RunPage } from "./pages/RunPage";

const TEAM_MEMBERS = [
  {
    name: "Kuanpin Chen",
    role: "IP Software Engineer",
    contribution: "Built the AI backend prototype and database foundation for SkillForge.",
  },
  {
    name: "Chin-Lun Fu",
    role: "CDAO ML Scientist",
    contribution: "Built the evaluation framework, especially the Agentic AI methodology behind the system.",
  },
  {
    name: "Prajwal Manjunath",
    role: "IP Software Engineer",
    contribution: "Provided key technical support and system integration across the prototype.",
  },
  {
    name: "Luciana Ma",
    role: "CIB Product Manager",
    contribution: "Built the frontend, refined the problem framing, and created the demo material.",
  },
];

function SkillPruneAnimation() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const rawCtx = cv.getContext("2d");
    if (!rawCtx) return;
    const ctx: CanvasRenderingContext2D = rawCtx;

    const S = 600;
    cv.width = S;
    cv.height = S;

    const CREAM = "#F7F3E9";
    const GRID_C = "#D8D0C0";
    const INK = "#1A1208";
    const PINK_BG = "#FFD6DA";
    const BLUE_BG = "#C8DEFF";
    const PINK_SH = "#E8A0A8";
    const BLUE_SH = "#7AAADA";
    const BRICK_N = "#C8B88A";
    const BRICK_S = "#A89870";
    const GREEN_A = "#4CAF72";
    const RED_A = "#E05050";

    const WX = 88;
    const WY = 78;
    const WW = S - 146;
    const WH = S - 186;
    const CW = 112;
    const CH = 160;
    const SPREAD1 = { x: WX + 36, y: WY + 52 };
    const SPREAD2 = { x: WX + WW - 36 - CW, y: WY + 52 };
    const CMP1 = { x: WX + WW / 2 - CW - 9, y: WY + 52 };
    const CMP2 = { x: WX + WW / 2 + 9, y: WY + 52 };
    const CONTACT_BLUE = CMP1.x + CW;
    const PUSH_DIST = 44;
    const FINAL2 = { x: WX + WW / 2 - CW / 2, y: WY + 52 };

    const BW = 70;
    const BH = 16;
    const BGAP = 3;
    const ROW_H = 19;
    const WALL_L = WX + 20;
    const WALL_BOT = WY + WH - 14;
    const rows = [
      { off: false, n: 5 },
      { off: true, n: 4 },
      { off: false, n: 5 },
      { off: true, n: 4 },
    ];
    const bricks: Array<{ x: number; y: number; ri: number; ci: number; pink: boolean; blue: boolean }> = [];
    rows.forEach((row, ri) => {
      const offX = row.off ? (BW + BGAP) / 2 : 0;
      const by = WALL_BOT - ri * ROW_H - BH;
      for (let ci = 0; ci < row.n; ci += 1) {
        bricks.push({
          x: WALL_L + offX + ci * (BW + BGAP),
          y: by,
          ri,
          ci,
          pink: ri === 3 && ci === 2,
          blue: ri === 3 && ci === 3,
        });
      }
    });
    const pinkBrick = bricks.find((b) => b.pink)!;
    const blueBrick = bricks.find((b) => b.blue)!;

    let t = 0;
    let phase = 0;
    let phaseStart = 0;
    let frame = 0;
    const PHASE_DUR = [110, 150, 110, 150, 120, 130];

    const ease = (x: number) => (x < 0.5 ? 2 * x * x : 1 - (-2 * x + 2) ** 2 / 2);
    const easeOut3 = (x: number) => 1 - (1 - x) ** 3;
    const easeIn3 = (x: number) => x * x * x;
    const lerp = (a: number, b: number, u: number) => a + (b - a) * u;
    const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));
    const phaseT = () => (phase < PHASE_DUR.length ? clamp((t - phaseStart) / PHASE_DUR[phase], 0, 1) : 1);
    const handFont = "'Marker Felt','Bradley Hand','Comic Sans MS','Segoe Print',cursive";

    function rr(x: number, y: number, w: number, h: number, r: number) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }

    function drawGrid() {
      ctx.strokeStyle = GRID_C;
      ctx.lineWidth = 0.7;
      for (let x = 0; x <= S; x += 28) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, S);
        ctx.stroke();
      }
      for (let y = 0; y <= S; y += 28) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(S, y);
        ctx.stroke();
      }
    }

    function drawCard(
      cx: number,
      cy: number,
      w: number,
      h: number,
      r: number,
      bg: string,
      sh: string,
      small: string,
      main: string,
      s1: string,
      s2: string,
      alpha: number,
      rot: number,
      textA: number,
      strike: boolean,
    ) {
      if (alpha <= 0.01) return;
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.translate(cx, cy);
      ctx.rotate(rot);
      const shA = clamp((w - BW) / (CW - BW), 0, 1) * 0.7;
      ctx.globalAlpha = alpha * shA;
      rr(-w / 2 + 4, -h / 2 + 5, w, h, r);
      ctx.fillStyle = sh;
      ctx.fill();
      ctx.globalAlpha = alpha;
      ctx.fillStyle = bg;
      ctx.strokeStyle = INK;
      ctx.lineWidth = clamp(lerp(1.5, 2.5, (w - BW) / (CW - BW)), 1.5, 2.5);
      rr(-w / 2, -h / 2, w, h, r);
      ctx.fill();
      ctx.stroke();
      if (textA > 0) {
        ctx.globalAlpha = alpha * textA;
        ctx.fillStyle = INK;
        ctx.textAlign = "center";
        ctx.font = `500 11px ${handFont}`;
        ctx.fillText(small, 0, -h / 2 + 18);
        ctx.font = `700 19px ${handFont}`;
        ctx.fillText(main, 0, -h / 2 + 50);
        ctx.fillStyle = "#666";
        ctx.font = `400 12px ${handFont}`;
        ctx.fillText(s1, 0, -h / 2 + 68);
        if (s2) ctx.fillText(s2, 0, -h / 2 + 84);
        if (strike) {
          ctx.strokeStyle = RED_A;
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.moveTo(-w / 2 + 14, -h / 2 + 50);
          ctx.lineTo(w / 2 - 14, -h / 2 + 50);
          ctx.stroke();
        }
      }
      ctx.restore();
    }

    function drawCheckOrX(x: number, y: number, type: "check" | "x", alpha: number) {
      if (alpha <= 0.01) return;
      ctx.save();
      ctx.globalAlpha = alpha;
      const col = type === "check" ? GREEN_A : RED_A;
      ctx.fillStyle = `${col}33`;
      ctx.beginPath();
      ctx.arc(x, y, 18, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = col;
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      if (type === "check") {
        ctx.beginPath();
        ctx.moveTo(x - 13, y);
        ctx.lineTo(x - 4, y + 11);
        ctx.lineTo(x + 13, y - 11);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.moveTo(x - 11, y - 11);
        ctx.lineTo(x + 11, y + 11);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x + 11, y - 11);
        ctx.lineTo(x - 11, y + 11);
        ctx.stroke();
      }
      ctx.restore();
    }

    function drawWall(showPink: boolean, showBlue: boolean, bumpPt: number) {
      ctx.save();
      ctx.beginPath();
      rr(WX + 2, WY + 2, WW - 4, WH - 4, 16);
      ctx.clip();
      bricks.forEach((b) => {
        if (b.pink || b.blue) return;
        ctx.fillStyle = BRICK_N;
        ctx.strokeStyle = BRICK_S;
        ctx.lineWidth = 1.5;
        rr(b.x, b.y, BW, BH, 3);
        ctx.fill();
        ctx.stroke();
      });
      if (showPink) {
        const pe = ease(clamp((bumpPt - 0.5) / 0.5, 0, 1));
        const px = pinkBrick.x - pe * (WW + 60);
        const py = pinkBrick.y + pe * 20;
        if (1 - pe > 0.01) {
          ctx.save();
          ctx.globalAlpha = 1 - pe;
          ctx.translate(px + BW / 2, py + BH / 2);
          ctx.rotate(-pe * 0.28);
          ctx.fillStyle = PINK_BG;
          ctx.strokeStyle = INK;
          ctx.lineWidth = 1.5;
          rr(-BW / 2, -BH / 2, BW, BH, 3);
          ctx.fill();
          ctx.stroke();
          ctx.restore();
        }
      }
      if (showBlue) {
        let bx = blueBrick.x;
        if (bumpPt > 0) {
          const closeGap = ease(clamp(bumpPt / 0.3, 0, 1));
          const push = ease(clamp((bumpPt - 0.3) / 0.3, 0, 1));
          const settle = ease(clamp((bumpPt - 0.6) / 0.4, 0, 1));
          const contactBlueBrick = pinkBrick.x + BW + BGAP;
          const bxContact = lerp(blueBrick.x, contactBlueBrick, closeGap);
          const bxPush = lerp(contactBlueBrick, contactBlueBrick - PUSH_DIST * (BW / CW), push);
          const bxFinal = lerp(contactBlueBrick - PUSH_DIST * (BW / CW), pinkBrick.x, settle);
          bx = bumpPt <= 0.3 ? bxContact : bumpPt <= 0.6 ? bxPush : bxFinal;
        }
        const imp = clamp((bumpPt - 0.26) / 0.06, 0, 1) * (1 - clamp((bumpPt - 0.34) / 0.06, 0, 1));
        ctx.save();
        ctx.translate(bx + BW / 2, blueBrick.y + BH / 2);
        ctx.scale(lerp(1, 0.8, imp), lerp(1, 1.25, imp));
        ctx.fillStyle = BLUE_BG;
        ctx.strokeStyle = INK;
        ctx.lineWidth = 1.5;
        rr(-BW / 2, -BH / 2, BW, BH, 3);
        ctx.fill();
        ctx.stroke();
        ctx.restore();
      }
      ctx.restore();
    }

    function drawCompareBar(fillPt: number) {
      const barW = 220;
      const barH = 18;
      const bx = WX + WW / 2 - barW / 2;
      const by = CMP1.y + CH + 32;
      ctx.fillStyle = "#E0D8C8";
      ctx.strokeStyle = "#B8A888";
      ctx.lineWidth = 1.5;
      rr(bx, by, barW, barH, 6);
      ctx.fill();
      ctx.stroke();
      if (fillPt > 0) {
        ctx.save();
        ctx.beginPath();
        rr(bx, by, barW, barH, 6);
        ctx.clip();
        ctx.fillStyle = "#7BBFA0";
        ctx.fillRect(bx, by, barW * fillPt, barH);
        ctx.restore();
      }
      ctx.fillStyle = "#8A7A60";
      ctx.font = `600 12px ${handFont}`;
      ctx.textAlign = "center";
      ctx.fillText("evaluating...", WX + WW / 2, by - 6);
    }

    function drawVerticalLabel() {
      ctx.save();
      ctx.translate(24, S / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillStyle = "#8A7A60";
      ctx.font = `600 14px ${handFont}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("observe / compare / prune", 0, 0);
      ctx.restore();
    }

    function draw() {
      ctx.clearRect(0, 0, S, S);
      ctx.fillStyle = CREAM;
      ctx.fillRect(0, 0, S, S);
      drawGrid();
      const pt = phaseT();

      const boxA = clamp(phase === 0 ? ease(pt) : 1, 0, 1);
      ctx.save();
      ctx.globalAlpha = boxA;
      ctx.strokeStyle = "#B8A888";
      ctx.lineWidth = 2;
      ctx.setLineDash([8, 5]);
      rr(WX, WY, WW, WH, 18);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#B8A888";
      ctx.font = `600 13px ${handFont}`;
      ctx.textAlign = "right";
      ctx.fillText("SkillForge working", WX + WW - 14, WY + 15);
      ctx.restore();

      if (phase === 0) {
        drawWall(true, true, 0);
      } else if (phase === 1) {
        drawWall(true, true, 0);
        const u = ease(pt);
        ctx.save();
        ctx.beginPath();
        rr(WX + 2, WY + 2, WW - 4, WH - 4, 16);
        ctx.clip();
        const startY = WY - CH - 10;
        const c1y = lerp(startY, SPREAD1.y, u);
        const c2y = lerp(startY, SPREAD2.y, u);
        const textA = clamp((u - 0.6) / 0.4, 0, 1);
        drawCard(SPREAD1.x + CW / 2, c1y + CH / 2, CW, CH, 10, PINK_BG, PINK_SH, "skill 1", "fast guesser", "assumes policy", "", 1, 0, textA, false);
        drawCard(SPREAD2.x + CW / 2, c2y + CH / 2, CW, CH, 10, BLUE_BG, BLUE_SH, "skill 2", "asks first", "unlocks hidden", "rules", 1, 0, textA, false);
        ctx.restore();
      } else if (phase === 2) {
        drawWall(true, true, 0);
        const u = ease(pt);
        const p1x = lerp(SPREAD1.x, CMP1.x, u);
        const p2x = lerp(SPREAD2.x, CMP2.x, u);
        const vsA = clamp((pt - 0.6) / 0.4, 0, 1);
        if (vsA > 0) {
          ctx.save();
          ctx.globalAlpha = vsA;
          ctx.fillStyle = "#8A7A60";
          ctx.font = `700 20px ${handFont}`;
          ctx.textAlign = "center";
          ctx.fillText("vs", WX + WW / 2, CMP1.y + CH / 2 + 6);
          ctx.restore();
        }
        drawCard(p1x + CW / 2, CMP1.y + CH / 2, CW, CH, 10, PINK_BG, PINK_SH, "skill 1", "fast guesser", "assumes policy", "", 1, 0, 1, false);
        drawCard(p2x + CW / 2, CMP2.y + CH / 2, CW, CH, 10, BLUE_BG, BLUE_SH, "skill 2", "asks first", "unlocks hidden", "rules", 1, 0, 1, false);
      } else if (phase === 3) {
        drawWall(true, true, 0);
        ctx.fillStyle = "#8A7A60";
        ctx.font = `700 20px ${handFont}`;
        ctx.textAlign = "center";
        ctx.fillText("vs", WX + WW / 2, CMP1.y + CH / 2 + 6);
        const markA = ease(clamp(pt / 0.3, 0, 1));
        drawCard(CMP1.x + CW / 2, CMP1.y + CH / 2, CW, CH, 10, PINK_BG, PINK_SH, "skill 1", "fast guesser", "assumes policy", "", 1, 0, 1, markA > 0.5);
        drawCard(CMP2.x + CW / 2, CMP2.y + CH / 2, CW, CH, 10, BLUE_BG, BLUE_SH, "skill 2", "asks first", "unlocks hidden", "rules", 1, 0, 1, false);
        drawCheckOrX(CMP1.x + CW / 2, CMP1.y + CH / 2, "x", markA);
        drawCheckOrX(CMP2.x + CW / 2, CMP2.y + CH / 2, "check", markA);
        drawCompareBar(pt);
      } else if (phase === 4) {
        const WINDUP = 14;
        const PUSH_DIST2 = 38;
        const windU = ease(clamp(pt / 0.12, 0, 1));
        const chargeU = easeOut3(clamp((pt - 0.12) / 0.28, 0, 1));
        const pushU = ease(clamp((pt - 0.4) / 0.14, 0, 1));
        const pinkFlyU = easeIn3(clamp((pt - 0.54) / 0.46, 0, 1));
        const blueSetU = ease(clamp((pt - 0.54) / 0.46, 0, 1));
        const impRaw = clamp((pt - 0.38) / 0.05, 0, 1) * (1 - clamp((pt - 0.48) / 0.07, 0, 1));
        const imp = impRaw ** 0.55;

        let blueX;
        let blueRot = 0;
        if (pt <= 0.12) {
          blueX = CMP2.x + lerp(0, WINDUP, windU);
          blueRot = lerp(0, 0.06, windU);
        } else if (pt <= 0.4) {
          blueX = lerp(CMP2.x + WINDUP, CONTACT_BLUE, chargeU);
          blueRot = lerp(0.06, -0.04, chargeU);
        } else if (pt <= 0.54) {
          blueX = lerp(CONTACT_BLUE, CONTACT_BLUE - PUSH_DIST2, pushU);
          blueRot = lerp(-0.04, 0, pushU);
        } else {
          blueX = lerp(CONTACT_BLUE - PUSH_DIST2, FINAL2.x, blueSetU);
        }

        let pinkX;
        let pinkA = 1;
        let pinkRot = 0;
        if (pt <= 0.4) {
          pinkX = CMP1.x;
        } else if (pt <= 0.54) {
          pinkX = blueX - CW;
        } else {
          const pinkStart = CONTACT_BLUE - PUSH_DIST2 - CW;
          pinkX = lerp(pinkStart, pinkStart - 380, pinkFlyU);
          pinkA = clamp(1 - pinkFlyU * 1.6, 0, 1);
          pinkRot = lerp(0, -0.42, pinkFlyU);
        }

        const shakeAmt = imp * 7;
        const shakeX = shakeAmt * Math.sin(t * 3.1);
        const shakeY = shakeAmt * 0.4 * Math.sin(t * 3.7 + 1);

        drawWall(pinkA > 0.01, true, pt);
        ctx.save();
        ctx.translate(shakeX, shakeY);
        drawCard(pinkX + CW / 2, CMP1.y + CH / 2, CW, CH, 10, PINK_BG, PINK_SH, "skill 1", "fast guesser", "assumes policy", "", pinkA, pinkRot, 1, true);
        drawCheckOrX(pinkX + CW / 2, CMP1.y + CH / 2, "x", pinkA);
        const bSX = lerp(1, 0.6, imp);
        const bSY = lerp(1, 1.4, imp);
        drawCard(blueX + CW / 2, CMP2.y + CH / 2, CW * bSX, CH * bSY, 10, BLUE_BG, BLUE_SH, "skill 2", "asks first", "unlocks hidden", "rules", 1, blueRot, 1, false);
        drawCheckOrX(blueX + CW / 2, CMP2.y + CH / 2, "check", 1);
        ctx.restore();
      } else {
        drawWall(false, true, 1);
        const a = ease(pt);
        drawCard(FINAL2.x + CW / 2, FINAL2.y + CH / 2, CW, CH, 10, BLUE_BG, BLUE_SH, "skill 2", "asks first", "unlocks hidden", "rules", 1, 0, 1, false);
        drawCheckOrX(FINAL2.x + CW / 2, FINAL2.y + CH / 2, "check", 1);
        ctx.save();
        ctx.globalAlpha = a;
        ctx.fillStyle = GREEN_A;
        ctx.font = `700 15px ${handFont}`;
        ctx.textAlign = "center";
        ctx.fillText("retained ✓", FINAL2.x + CW / 2, FINAL2.y + CH + 22);
        ctx.restore();
      }

      drawVerticalLabel();

      t += 1;
      if (phase < PHASE_DUR.length) {
        if (t - phaseStart >= PHASE_DUR[phase]) {
          phase += 1;
          phaseStart = t;
        }
      } else if (t - phaseStart > 200) {
        t = 0;
        phase = 0;
        phaseStart = 0;
      }
    }

    function loop() {
      draw();
      frame = window.requestAnimationFrame(loop);
    }
    frame = window.requestAnimationFrame(loop);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  return (
    <div className="skill-prune-canvas-wrap" aria-label="Animated skill comparison">
      <canvas ref={canvasRef} className="skill-prune-canvas" />
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<"run" | "history">("run");
  const [heroTab, setHeroTab] = useState<"problem" | "team" | "product">("problem");

  useEffect(() => {
    let locked = false;

    // Demo scroll controller: each screen is a presentation beat. A wheel or
    // trackpad gesture snaps to the next/previous `.demo-screen`, while form
    // fields keep normal editing behavior.
    const onWheel = (event: WheelEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        locked ||
        Math.abs(event.deltaY) < 35 ||
        event.metaKey ||
        event.ctrlKey ||
        target?.closest("input, textarea, select, [data-scroll-free]")
      ) {
        return;
      }

      const screens = Array.from(document.querySelectorAll<HTMLElement>(".demo-screen"));
      if (screens.length < 2) return;

      const currentY = window.scrollY;
      const currentIndex = screens.reduce((bestIndex, screen, index) => {
        const bestDistance = Math.abs(screens[bestIndex].offsetTop - currentY);
        const distance = Math.abs(screen.offsetTop - currentY);
        return distance < bestDistance ? index : bestIndex;
      }, 0);
      const nextIndex =
        event.deltaY > 0
          ? Math.min(currentIndex + 1, screens.length - 1)
          : Math.max(currentIndex - 1, 0);

      if (nextIndex === currentIndex) return;
      event.preventDefault();
      locked = true;
      screens[nextIndex].scrollIntoView({ behavior: "smooth", block: "start" });
      window.setTimeout(() => {
        locked = false;
      }, 720);
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, []);

  const demoNav = (
    <nav className="mb-4 flex gap-2 border-b-2 border-dashed border-sketch-ink">
      {(
        [
          ["run", "Eval Lab"],
          ["history", "Run History"],
        ] as const
      ).map(([id, label]) => (
        <button
          key={id}
          onClick={() => setTab(id)}
          data-testid={`tab-${id}`}
          className={cn(
            "font-hand rounded-t-[15px] border-2 border-b-0 border-sketch-ink px-4 py-2 text-sm font-bold shadow-[3px_0_0_rgba(48,42,37,0.12)] transition-transform hover:-rotate-1",
            tab === id
              ? "bg-sketch-yellow text-sketch-ink"
              : "bg-sketch-paper text-sketch-ink hover:bg-sketch-blue",
          )}
        >
          {label}
        </button>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-sketch-paper text-sketch-ink">
      <div className="mx-auto max-w-[1600px] px-4 py-6">
        {/* SCREEN 1: Demo opening hero. Keep this exact story beat together:
            its local tabs only affect Screen 1 and never change downstream screens. */}
        <header className="demo-screen sketch-card mb-6 min-h-[calc(100vh-3rem)] overflow-hidden bg-sketch-paper">
          <nav className="screen-one-tabs">
            {(
              [
                ["problem", "The Problem"],
                ["team", "Our Team"],
                ["product", "Our Product"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={cn(
                  "font-hand rounded-t-[15px] border-2 border-b-0 border-sketch-ink px-4 py-2 text-sm font-bold shadow-[3px_0_0_rgba(48,42,37,0.12)] transition-transform hover:-rotate-1",
                  heroTab === id
                    ? "bg-sketch-yellow text-sketch-ink"
                    : "bg-sketch-paper text-sketch-ink hover:bg-sketch-blue",
                )}
                onClick={() => setHeroTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>

          {heroTab === "product" ? (
            <div className="sketch-hero-grid">
              <div className="flex flex-col justify-center p-6 md:p-10 lg:p-14">
                <div className="font-hand sticky-note mb-4 inline-block rotate-[-1deg] bg-sketch-yellow px-3 py-1 text-sm font-bold">
                  Evidence-based skill decisions
                </div>
                <h1 className="font-hand max-w-5xl text-4xl font-bold leading-[0.95] tracking-normal md:text-7xl xl:text-8xl">
                  SkillForge
                  <span className="mt-3 block text-2xl leading-tight text-sketch-muted md:text-4xl xl:text-5xl">
                    Evidence-Based Agent Skill Observatory
                  </span>
                </h1>
                <p className="mt-6 max-w-3xl text-base font-semibold leading-7 md:text-lg">
                  Your team keeps adding skills, rules, and workflows. This lab tests which
                  instructions actually change agent behavior, which ones create risk, and
                  which ones deserve to stay.
                </p>
                <p className="font-hand mt-5 text-base font-bold text-sketch-muted md:text-lg">
                  Controlled evals · live behavior replay · evidence-backed decisions
                </p>
              </div>
              <div className="relative min-h-[430px] border-t-2 border-dashed border-sketch-ink p-5 md:min-h-0 md:border-l-2 md:border-t-0">
                <SkillPruneAnimation />
              </div>
            </div>
          ) : null}

          {heroTab === "problem" ? (
            <div className="screen-one-panel problem-slide">
              <h2 className="problem-title font-hand">
                More skills make agents dumber — and we only ever add more
              </h2>

              <div className="problem-grid mt-6">
                <section className="problem-block">
                  <div>
                    <h3 className="font-hand text-xl font-bold">What the research proves — the mechanism</h3>
                    <ul className="mt-3 space-y-2 text-sm font-semibold leading-6">
                      <li>
                        Big skill pile → agents pick the right skill just <strong>13%</strong> of the time;
                        filtering lifts it to <strong>43%</strong> <span className="text-sketch-muted">(RAG-MCP, 2025)</span>.
                      </li>
                      <li>
                        Every added skill drags accuracy down — losses up to <strong>85%</strong> as catalogues grow
                        <span className="text-sketch-muted"> (Kate et al., LongFuncEval)</span>.
                      </li>
                      <li>
                        Prompt & skill config is the <strong>#1 source</strong> of LLM technical debt
                        <span className="text-sketch-muted"> (PromptDebt, EASE 2025 — 93K files)</span>.
                      </li>
                    </ul>
                  </div>
                </section>

                <div className="problem-reasoning-arrow font-hand" aria-hidden="true">
                  →
                </div>

                <section className="problem-block">
                  <div>
                    <h3 className="font-hand text-xl font-bold">What that means in production — every mis-selection becomes a bill</h3>
                    <ul className="mt-3 space-y-2 text-sm font-semibold leading-6">
                      <li>Every skill rides in context on every call → token carrying cost. <span className="problem-cost-pill">tokens ~$7K</span></li>
                      <li>Wrong skill picked → engineers dig through transcripts to find which rule misfired → debugging hours. <span className="problem-cost-pill">debugging ~$22K</span></li>
                      <li>Wrong skill ships → rework & incidents. <span className="problem-cost-pill">incidents ~$12K</span></li>
                    </ul>
                  </div>
                </section>
              </div>

              <div className="problem-conclusion font-hand mt-5">
                <span className="problem-conclusion-text">
                  300,000 developers · If 500 teams use AI agents → <span className="problem-money-box">~$20M/year</span>
                </span>
              </div>
            </div>
          ) : null}

          {heroTab === "team" ? (
            <div className="screen-one-panel">
              <div className="team-member-grid">
                {TEAM_MEMBERS.map((member) => (
                  <div key={member.name} className="team-member-card sticky-note bg-sketch-paper p-5">
                    <div className="flex items-start gap-4">
                      <div className="team-avatar font-hand">{member.name.split(" ").map((part) => part[0]).join("")}</div>
                      <div>
                        <h3 className="font-hand text-xl font-bold">{member.name}</h3>
                        <p className="mt-1 text-sm font-bold text-sketch-muted">{member.role}</p>
                      </div>
                    </div>
                    <p className="mt-5 text-base font-semibold leading-7">{member.contribution}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </header>

        {/* SCREEN 2 begins here with the demo tabs, then continues in RunPage
            through the eval setup form and Run eval button. Do not move this
            nav below the setup form; the demo sequence depends on it. */}
        {tab === "run" ? (
          <RunPage navSlot={demoNav} />
        ) : (
          <section className="demo-screen demo-screen-panel">
            {demoNav}
            <HistoryPage />
          </section>
        )}
      </div>
    </div>
  );
}
