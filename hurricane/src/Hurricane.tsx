import React from 'react';
import {AbsoluteFill, Audio, Img, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {SPR} from './sprites';

// ---------------------------------------------------------------------------------------------------------------
// Timing (seconds). Voice placed at VO_AT; beats measured from the voice's loudness pauses.
export const FPS = 60;
export const DURATION = 14.8;
const VO_AT = 0.1;
const MASTER_DB = -3.5; // keeps the mix peak around -4 dBFS
const T = {
  windup: 1.42, // "nuke"
  release: 2.15, // end of "hurricane"
  arrive: 3.35, // bomb reaches the storm and gets caught in the spin
  eyesOpen: 3.05, // "the storm"
  stronger: 4.25, // "way stronger"
  clockIn: 4.75, // "NOAA says"
  booms: [6.0, 6.85, 7.55], // "ten-megaton bomb every twenty minutes"
  clockOut: 7.8,
  blast: 7.92, // in the pause before "The blast"
  smug: 9.35, // "the storm keeps spinning"
  inhale: 10.55,
  blow: 11.15, // "And the wind carries"
  scared: 12.55, // "fallout"
  landWord: 13.85, // "land"
};

// ---------------------------------------------------------------------------------------------------------------
// Helpers
const clamp = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a: number, b: number, u: number) => a + (b - a) * u;
const seg = (t: number, a: number, b: number) => clamp((t - a) / (b - a));
const eio = (u: number) => (u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2);
const eout = (u: number) => 1 - Math.pow(1 - u, 3);
const eback = (u: number) => {
  const c1 = 1.9;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(u - 1, 3) + c1 * Math.pow(u - 1, 2);
};
// damped spring kick: 0 before t0
const ring = (t: number, t0: number, amp: number, f = 3, decay = 6) =>
  t < t0 ? 0 : amp * Math.exp(-decay * (t - t0)) * Math.cos(2 * Math.PI * f * (t - t0));
// pop-in / pop-out scale with overshoot
const popScale = (t: number, tin: number, tout: number, dur = 0.22) => {
  if (t < tin || t > tout + dur) return 0;
  if (t < tin + dur) return eback(seg(t, tin, tin + dur));
  if (t > tout) return 1 - eio(seg(t, tout, tout + dur));
  return 1;
};
const hash = (n: number) => {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
};

// ---------------------------------------------------------------------------------------------------------------
// World layout
const INK = '#141414';
const LINE = 9; // outline width in world px at the character plane
const FEET = {x: 455, y: 1700};
const HEAD_R = 200; // every pose is scaled so its head has this radius
const STORM = {x: 1080, y: -240, z: 3000, W: 1680, squash: 0.55};
const HORIZON_Y = 540;
const ORBIT_R = 640;
const SAND_Y = 1385;
const BOMB = {w: SPR.bomb.w, h: SPR.bomb.h, cx: 213, cy: 316, diam: 374, fuse: {x: 305, y: 25}};
const BOMB_W = (SPR.hold.bomb![2] * (HEAD_R / SPR.hold.head[2]) * SPR.bomb.w) / BOMB.diam; // world width of the bomb sprite
const BOMB_S = BOMB_W / SPR.bomb.w;

type Cam = {x: number; y: number; z: number};

const camLerp = (a: Cam, b: Cam, ux: number, uy: number, uz: number, zRef = STORM.z): Cam => {
  const kA = 1000 / (zRef - a.z);
  const kB = 1000 / (zRef - b.z);
  const k = Math.exp(lerp(Math.log(kA), Math.log(kB), uz));
  return {x: lerp(a.x, b.x, ux), y: lerp(a.y, b.y, uy), z: zRef - 1000 / k};
};

const C0: Cam = {x: 505, y: 960, z: 0};
const C0b: Cam = {x: 515, y: 948, z: 80};
const C1: Cam = {x: 1080, y: -150, z: 1330};
const C1b: Cam = {x: 1074, y: -150, z: 1420};

const camAt = (t: number): Cam => {
  if (t < 2.2) return camLerp(C0, C0b, eio(t / 2.2), eio(t / 2.2), eio(t / 2.2));
  if (t < 3.8)
    return camLerp(C0b, C1, eio(seg(t, 2.25, 3.75)), eio(seg(t, 2.2, 3.4)), eio(seg(t, 2.3, 3.8)));
  if (t < 11.2) {
    const u = eio(seg(t, 3.8, 11.2));
    return camLerp(C1, C1b, u, u, u);
  }
  return camLerp(C1b, C0, eio(seg(t, 11.25, 12.9)), eio(seg(t, 11.5, 13.05)), eio(seg(t, 11.2, 12.85)));
};

// screen shake: sums of sines under an amplitude envelope
const shakeAt = (t: number) => {
  let amp = 0;
  if (t >= T.blast) amp += 30 * Math.exp(-5 * (t - T.blast));
  for (const b of T.booms) if (t >= b) amp += 7 * Math.exp(-9 * (t - b));
  if (t >= T.blow && t < 13.9) amp += 3 * Math.sin(Math.PI * seg(t, T.blow, 13.9));
  return {
    x: amp * (Math.sin(2 * Math.PI * 13.3 * t) * 0.6 + Math.sin(2 * Math.PI * 7.1 * t + 1.3) * 0.4),
    y: amp * (Math.sin(2 * Math.PI * 11.7 * t + 0.5) * 0.6 + Math.sin(2 * Math.PI * 5.3 * t + 2.1) * 0.4),
  };
};

// ---------------------------------------------------------------------------------------------------------------
// Multiplane layer
const Layer: React.FC<{cam: Cam; z: number; blur?: number; minDepth?: number; children: React.ReactNode}> = ({
  cam,
  z,
  blur = 0,
  minDepth = 300,
  children,
}) => {
  const d = z - cam.z;
  if (d < minDepth) return null;
  const k = 1000 / d;
  return (
    <AbsoluteFill style={{filter: blur > 0.05 ? `blur(${blur}px)` : undefined}}>
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 0,
          transformOrigin: '0 0',
          transform: `translate(540px, 960px) scale(${k}) translate(${-cam.x}px, ${-cam.y}px)`,
        }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
};

// an svg canvas in world coordinates (origin at world 0,0)
const W: React.FC<{children: React.ReactNode}> = ({children}) => (
  <svg width={1} height={1} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
    {children}
  </svg>
);

// ---------------------------------------------------------------------------------------------------------------
// Character
type PoseName = 'hold' | 'windup' | 'throw' | 'smug' | 'confused' | 'scared';

const poseAt = (t: number): PoseName => {
  if (t < T.windup) return 'hold';
  if (t < T.release) return 'windup';
  if (t < 4.0) return 'throw';
  if (t < T.scared) return 'confused';
  return 'scared';
};

const poseScale = (p: PoseName) => HEAD_R / SPR[p].head[2];

// world position of a point given in a pose sprite's pixels (before squash / lean)
const posePoint = (p: PoseName, px: number, py: number) => {
  const s = poseScale(p);
  return {x: FEET.x + (px - SPR[p].feet[0]) * s, y: FEET.y + (py - SPR[p].feet[1]) * s};
};

const guyMotion = (t: number) => {
  let sx = 1;
  let sy = 1;
  let rot = 0;
  let dx = 0;
  // breathing
  const br = 0.009 * Math.sin(2 * Math.PI * 0.6 * t);
  sy += br;
  sx -= br * 0.5;
  // anticipation before the wind-up, stretch after
  if (t > T.windup - 0.14 && t < T.windup) {
    const u = seg(t, T.windup - 0.14, T.windup);
    sy -= 0.06 * u;
    sx += 0.04 * u;
  }
  sy += ring(t, T.windup, 0.035, 2.6, 7);
  sx -= ring(t, T.windup, 0.02, 2.6, 7);
  // wind-up lean back, throw lean forward
  if (t >= T.windup && t < T.release) rot = -3 * eout(seg(t, T.windup, T.windup + 0.2));
  if (t >= T.release) rot = 5 * Math.exp(-3 * (t - T.release)) * Math.cos(2 * Math.PI * 1.6 * (t - T.release));
  // squash into the scared pose
  if (t > T.scared - 0.1 && t < T.scared) {
    const u = seg(t, T.scared - 0.1, T.scared);
    sy -= 0.07 * u;
    sx += 0.05 * u;
  }
  sy += ring(t, T.scared, 0.05, 3, 6);
  sx -= ring(t, T.scared, 0.03, 3, 6);
  // small bounce on "land"
  sy += ring(t, T.landWord, 0.025, 3, 7);
  // tremble while scared
  if (t > T.scared) dx = 2.2 * Math.sin(2 * Math.PI * 23 * t) + 1.4 * Math.sin(2 * Math.PI * 31 * t + 1);
  return {sx, sy, rot, dx};
};

const Guy: React.FC<{t: number}> = ({t}) => {
  const p = poseAt(t);
  const s = poseScale(p);
  const S = SPR[p];
  const m = guyMotion(t);
  const fx = S.feet[0] * s;
  const fy = S.feet[1] * s;
  return (
    <>
      {/* contact shadow */}
      <div
        style={{
          position: 'absolute',
          left: FEET.x - 170,
          top: FEET.y - 26,
          width: 340,
          height: 52,
          borderRadius: '50%',
          background: 'rgba(72, 54, 42, 0.26)',
          filter: 'blur(3px)',
        }}
      />
      <Img
        src={staticFile(`hurricane/${p}.png`)}
        style={{
          position: 'absolute',
          left: FEET.x - fx + m.dx,
          top: FEET.y - fy,
          width: S.w * s,
          height: S.h * s,
          transformOrigin: `${fx}px ${fy}px`,
          transform: `rotate(${m.rot}deg) scale(${m.sx}, ${m.sy})`,
        }}
      />
      <SweatDrop t={t} />
    </>
  );
};

const SweatDrop: React.FC<{t: number}> = ({t}) => {
  const t0 = T.scared + 0.15;
  const t1 = 14.4;
  const sc = popScale(t, t0, t1, 0.2);
  if (sc <= 0) return null;
  const h = posePoint('scared', SPR.scared.head[0], SPR.scared.head[1]);
  const slide = 60 * eio(seg(t, t0, t1));
  const x = h.x + HEAD_R * 0.86;
  const y = h.y - HEAD_R * 0.45 + slide;
  return (
    <W>
      <g transform={`translate(${x}, ${y}) scale(${sc})`}>
        <path d="M0,-58 C20,-24 34,-2 34,18 A34,34 0 0 1 -34,18 C-34,-2 -20,-24 0,-58 Z" fill="#8FD3FF" stroke={INK} strokeWidth={LINE * 0.8} strokeLinejoin="round" />
        <ellipse cx={-12} cy={14} rx={7} ry={12} fill="#FFFFFF" />
      </g>
    </W>
  );
};

// ---------------------------------------------------------------------------------------------------------------
// Bomb
const bombSprite = (cx: number, cy: number, rot: number, spark: boolean, t: number, scale = 1) => {
  const w = BOMB.w * BOMB_S * scale;
  const h = BOMB.h * BOMB_S * scale;
  const ox = BOMB.cx * BOMB_S * scale;
  const oy = BOMB.cy * BOMB_S * scale;
  const fl = 0.75 + 0.25 * Math.sin(t * 90) + 0.15 * Math.sin(t * 57);
  return (
    <div
      style={{
        position: 'absolute',
        left: cx - ox,
        top: cy - oy,
        width: w,
        height: h,
        transformOrigin: `${ox}px ${oy}px`,
        transform: `rotate(${rot}deg)`,
      }}
    >
      <Img src={staticFile('hurricane/bomb.png')} style={{position: 'absolute', left: 0, top: 0, width: w, height: h}} />
      {spark ? (
        <svg width={w} height={h} style={{position: 'absolute', left: 0, top: 0, overflow: 'visible'}}>
          <g transform={`translate(${BOMB.fuse.x * BOMB_S * scale}, ${BOMB.fuse.y * BOMB_S * scale}) scale(${fl * scale})`}>
            <path d="M0,-38 L9,-10 L36,-12 L13,5 L22,32 L0,15 L-22,32 L-13,5 L-36,-12 L-9,-10 Z" fill="#FFD447" stroke={INK} strokeWidth={6} strokeLinejoin="round" />
            <circle r={8} fill="#FFFFFF" />
          </g>
        </svg>
      ) : null}
    </div>
  );
};

// bomb state: where it is in the world, which layer it belongs to
const ORBIT_TURNS = 1;
const orbitAngle = (t: number) => Math.PI / 2 - (2 * Math.PI * ORBIT_TURNS * (t - T.arrive)) / (T.blast - T.arrive);
const orbitPos = (t: number) => {
  const a = orbitAngle(t);
  return {x: STORM.x + ORBIT_R * Math.cos(a), y: STORM.y + ORBIT_R * STORM.squash * Math.sin(a), behind: Math.sin(a) < 0};
};

const windupBomb = posePoint('windup', SPR.windup.bomb![0], SPR.windup.bomb![1]);
const throwHand = posePoint('throw', 560, 365);

const flight = (t: number) => {
  // a short swing from behind the head to the hand, then a 3D projectile into the storm's spin
  const swing = 0.07;
  if (t < T.release + swing) {
    const u = eio(seg(t, T.release, T.release + swing));
    const midX = (windupBomb.x + throwHand.x) / 2;
    const midY = Math.min(windupBomb.y, throwHand.y) - 120;
    const x = (1 - u) * (1 - u) * windupBomb.x + 2 * (1 - u) * u * midX + u * u * throwHand.x;
    const y = (1 - u) * (1 - u) * windupBomb.y + 2 * (1 - u) * u * midY + u * u * throwHand.y;
    return {x, y, z: 1000, rot: -60 * (1 - u)};
  }
  const T0 = T.release + swing;
  const Tf = T.arrive - T0;
  const tau = clamp(t - T0, 0, Tf);
  const end = orbitPos(T.arrive);
  const y0 = throwHand.y;
  const y1 = end.y;
  const ta = 0.78 * Tf; // late apex keeps the arc low
  const g = (2 * (y0 - y1)) / (ta * ta - (Tf - ta) * (Tf - ta));
  const ya = y0 - 0.5 * g * ta * ta;
  const u = tau / Tf;
  return {
    x: lerp(throwHand.x, end.x, u),
    y: ya + 0.5 * g * (tau - ta) * (tau - ta),
    z: lerp(1000, STORM.z - 10, u),
    rot: 360 * u,
  };
};

// ---------------------------------------------------------------------------------------------------------------
// Storm (sprite spun in its own plane, squashed into perspective), face, booms
const stormSpin = (t: number) => -(42 * t + (t > T.smug ? 18 * (t - T.smug) : 0)); // counter-clockwise

const stormBody = (t: number) => {
  let s = 1;
  // flex on "stronger"
  s += 0.07 * eio(seg(t, T.stronger - 0.3, T.stronger)) * (1 - eio(seg(t, T.stronger + 0.5, T.stronger + 1.2)));
  s += ring(t, T.stronger, 0.03, 2.5, 5);
  for (const b of T.booms) s += ring(t, b, 0.03, 3, 7);
  // squash on the blast
  s += ring(t, T.blast, -0.07, 2.2, 4.5);
  // inhale before blowing the fallout, then deflate
  s += 0.06 * eio(seg(t, T.inhale, T.blow)) * (1 - eio(seg(t, T.blow, T.blow + 0.6)));
  return s;
};

const Storm: React.FC<{t: number}> = ({t}) => {
  const sc = STORM.W / SPR.storm.w;
  const w = SPR.storm.w * sc;
  const h = SPR.storm.h * sc;
  const ex = SPR.storm.eye![0] * sc;
  const ey = SPR.storm.eye![1] * sc;
  const b = stormBody(t);
  return (
    <div
      style={{
        position: 'absolute',
        left: STORM.x,
        top: STORM.y,
        width: 0,
        height: 0,
        transform: `scale(${b}, ${STORM.squash * b * (1 + (b - 1) * 0.6)})`,
      }}
    >
      <Img
        src={staticFile('hurricane/storm.png')}
        style={{
          position: 'absolute',
          left: -ex,
          top: -ey,
          width: w,
          height: h,
          transformOrigin: `${ex}px ${ey}px`,
          transform: `rotate(${stormSpin(t)}deg)`,
        }}
      />
    </div>
  );
};

const StormBackdrop: React.FC<{t: number}> = ({t}) => {
  const cx = STORM.x;
  const top = STORM.y + 120;
  const off = (t * 900) % 120;
  const lines = [];
  for (let i = -9; i <= 9; i++) {
    const x = cx + i * 85 + ((i * 37) % 30);
    const o = (off * 2 + i * 53) % 240;
    lines.push(<line key={i} x1={x + 90} y1={top - 240 + o} x2={x - 90} y2={HORIZON_Y + 240 + o} stroke="rgba(225,238,252,0.32)" strokeWidth={10} strokeDasharray="110 130" strokeLinecap="round" />);
  }
  return (
    <W>
      <defs>
        <radialGradient id="stormGlow">
          <stop offset="0%" stopColor="rgba(38,52,74,0.42)" />
          <stop offset="100%" stopColor="rgba(38,52,74,0)" />
        </radialGradient>
        <clipPath id="rainClip">
          <polygon points={`${cx - 620},${top} ${cx + 620},${top} ${cx + 760},${HORIZON_Y} ${cx - 760},${HORIZON_Y}`} />
        </clipPath>
      </defs>
      <ellipse cx={cx} cy={STORM.y + 150} rx={2100} ry={1500} fill="url(#stormGlow)" />
      <polygon points={`${cx - 620},${top} ${cx + 620},${top} ${cx + 760},${HORIZON_Y} ${cx - 760},${HORIZON_Y}`} fill="rgba(80,98,128,0.42)" />
      <g clipPath="url(#rainClip)">{lines}</g>
    </W>
  );
};

// cartoon face in the eye of the storm
const Face: React.FC<{t: number; look: {x: number; y: number}}> = ({t, look}) => {
  const open = eback(seg(t, T.eyesOpen, T.eyesOpen + 0.25));
  if (t < T.eyesOpen) return null;
  const b = stormBody(t);
  const cx = STORM.x;
  const cy = STORM.y - 20;
  const ex = 150;
  const rx = 95;
  const ry = 120 * open;
  // blink
  const blink = [5.3, 9.9, 13.2].some((bt) => t > bt && t < bt + 0.12);
  // squeezed shut on the blast
  const squeeze = t > T.blast && t < T.blast + 0.75;
  // lids: 0 open .. 1 closed (smug = half)
  let lid = 0;
  if (t > T.smug - 0.2) lid = 0.42 * eio(seg(t, T.smug - 0.2, T.smug + 0.1));
  if (t > T.inhale) lid = lerp(0.42, 0.12, eio(seg(t, T.inhale, T.inhale + 0.2)));
  if (blink) lid = 1;
  // brows: lift on "stronger", angry tilt while booming, relaxed when smug
  const browLift = 20 * eout(seg(t, T.stronger - 0.2, T.stronger)) * (1 - eio(seg(t, T.stronger + 0.6, T.stronger + 1.0))) + ring(t, T.stronger, 8, 4, 6);
  const browTilt = t > T.clockIn && t < T.blast ? 14 : t > T.smug ? -4 : 6;
  // pupils look toward the action
  const lx = clamp((look.x - cx) / 900, -1, 1) * 22;
  const ly = clamp((look.y - cy) / 700, -1, 1) * 26;
  const mouthO = t > T.blow - 0.1 && t < 12.7;
  const mouthOpen = mouthO ? eback(seg(t, T.blow - 0.1, T.blow + 0.15)) * (1 - eio(seg(t, 12.4, 12.7))) : 0;
  const smile = t > T.smug - 0.1 && !mouthO ? eout(seg(t, T.smug - 0.1, T.smug + 0.25)) : 0;
  return (
    <W>
      <g transform={`translate(${cx}, ${cy}) scale(${b})`}>
        {[-1, 1].map((side) => (
          <g key={side} transform={`translate(${side * ex}, 0)`}>
            {squeeze ? (
              <path d={side < 0 ? 'M-64,-56 L50,0 L-64,56' : 'M64,-56 L-50,0 L64,56'} fill="none" stroke={INK} strokeWidth={LINE * 1.6} strokeLinecap="round" strokeLinejoin="round" />
            ) : (
              <>
                <clipPath id={`eye${side}`}>
                  <ellipse rx={rx} ry={Math.max(1, ry)} />
                </clipPath>
                <ellipse rx={rx} ry={Math.max(1, ry)} fill="#FFFFFF" stroke={INK} strokeWidth={LINE} />
                <g clipPath={`url(#eye${side})`}>
                  <circle cx={lx * 1.4} cy={ly * 1.4 + 8} r={42} fill={INK} />
                  <circle cx={lx * 1.4 + 14} cy={ly * 1.4 - 8} r={14} fill="#FFFFFF" />
                  {lid > 0 ? (
                    <>
                      <rect x={-rx - 10} y={-ry - 10} width={2 * rx + 20} height={(2 * ry + 10) * lid + 10} fill="#B8C4CF" />
                      <line x1={-rx - 10} x2={rx + 10} y1={-ry + (2 * ry + 10) * lid} y2={-ry + (2 * ry + 10) * lid} stroke={INK} strokeWidth={LINE} />
                    </>
                  ) : null}
                </g>
                <ellipse rx={rx} ry={Math.max(1, ry)} fill="none" stroke={INK} strokeWidth={LINE} />
              </>
            )}
            <path
              d={(() => {
                const outer = -120 - 34 - browLift;
                const inner = outer + browTilt;
                const top = -120 - 68 - browLift;
                return side < 0 ? `M-80,${outer} Q0,${top} 80,${inner}` : `M-80,${inner} Q0,${top} 80,${outer}`;
              })()}
              fill="none"
              stroke={INK}
              strokeWidth={LINE * 2}
              strokeLinecap="round"
              opacity={open > 0.3 ? 1 : 0}
            />
          </g>
        ))}
        {mouthOpen > 0 ? <ellipse cx={0} cy={190} rx={48 * mouthOpen} ry={60 * mouthOpen} fill="#3B1F22" stroke={INK} strokeWidth={LINE} /> : null}
        {smile > 0 ? (
          <path d={`M-95,${175} Q0,${175 + 64 * smile} 95,${175}`} fill="none" stroke={INK} strokeWidth={LINE * 1.3} strokeLinecap="round" />
        ) : null}
      </g>
    </W>
  );
};

// outlined cluster of circles: draw all ink circles first, then all fills (one merged outline)
type Puff = {x: number; y: number; r: number};
const Cluster: React.FC<{puffs: Puff[]; fill: string; shade?: string; ink?: number}> = ({puffs, fill, shade, ink = LINE}) => (
  <>
    {puffs.map((p, i) => (p.r > 0 ? <circle key={`o${i}`} cx={p.x} cy={p.y} r={p.r + ink} fill={INK} /> : null))}
    {puffs.map((p, i) => (p.r > 0 ? <circle key={`f${i}`} cx={p.x} cy={p.y} r={p.r} fill={fill} /> : null))}
    {shade
      ? puffs.map((p, i) => (p.r > 0 ? <circle key={`s${i}`} cx={p.x + p.r * 0.18} cy={p.y + p.r * 0.22} r={p.r * 0.62} fill={shade} /> : null))
      : null}
  </>
);

const starPath = (R: number, r: number, n = 10, phase = 0) => {
  let d = '';
  for (let i = 0; i < n * 2; i++) {
    const a = phase + (Math.PI * i) / n;
    const rr = i % 2 === 0 ? R : r;
    d += `${i === 0 ? 'M' : 'L'}${(rr * Math.cos(a)).toFixed(1)},${(rr * Math.sin(a)).toFixed(1)}`;
  }
  return d + 'Z';
};

// small booms inside the storm on the clock beats
const BOOM_SPOTS = [
  {x: -330, y: -60},
  {x: 290, y: 80},
  {x: -40, y: 170},
];
const StormBooms: React.FC<{t: number}> = ({t}) => (
  <W>
    {T.booms.map((bt, i) => {
      const u = t - bt;
      if (u < 0 || u > 0.9) return null;
      const s = u < 0.12 ? eout(u / 0.12) : 1 - eio(seg(u, 0.25, 0.55));
      const p = BOOM_SPOTS[i];
      const x = STORM.x + p.x;
      const y = STORM.y + p.y * STORM.squash;
      const smoke: Puff[] = [0, 1, 2, 3, 4].map((j) => {
        const a = (j / 5) * Math.PI * 2 + i;
        const g = eout(seg(u, 0.1, 0.5));
        const sh = 1 - eio(seg(u, 0.5, 0.9));
        return {x: x + Math.cos(a) * 120 * g, y: y + Math.sin(a) * 70 * g - 40 * g, r: 70 * g * sh};
      });
      return (
        <g key={i}>
          <Cluster puffs={smoke} fill="#8E949C" shade="#7A8089" />
          {s > 0 ? (
            <g transform={`translate(${x}, ${y}) scale(${s})`}>
              <path d={starPath(230, 120, 9, i)} fill="#FF8A2B" stroke={INK} strokeWidth={LINE} strokeLinejoin="round" />
              <path d={starPath(140, 70, 9, i + 0.3)} fill="#FFD447" />
              <circle r={50} fill="#FFF6C8" />
            </g>
          ) : null}
        </g>
      );
    })}
  </W>
);

// the big blast at the bomb's position: flash star, fire cluster turning to smoke, and a shock ring that passes
const Blast: React.FC<{t: number; at: {x: number; y: number}}> = ({t, at}) => {
  const u = t - T.blast;
  if (u < 0 || u > 2.2) return null;
  const fire = u < 0.1 ? eout(u / 0.1) : 1 - eio(seg(u, 0.35, 0.8));
  const puffs: Puff[] = Array.from({length: 9}, (_, j) => {
    const a = (j / 9) * Math.PI * 2 + 0.4;
    const d = 170 * eout(seg(u, 0, 0.45)) + 60 * hash(j);
    const g = eout(seg(u, 0, 0.3));
    const sh = 1 - eio(seg(u, 0.75, 1.35 + 0.15 * hash(j + 9)));
    return {x: at.x + Math.cos(a) * d * (1 + 0.5 * seg(u, 0.5, 1.4)), y: at.y + Math.sin(a) * d * 0.75 - 160 * eout(seg(u, 0, 1.5)), r: (120 + 50 * hash(j + 5)) * g * sh};
  });
  const smokeCol = u < 0.5 ? '#FFB347' : '#8E949C';
  const shadeCol = u < 0.5 ? '#FF8A2B' : '#7A8089';
  const ringU = seg(u, 0.03, 1.1);
  const rr = lerp(120, 4200, eout(ringU));
  return (
    <W>
      {ringU > 0 && ringU < 1 ? (
        <>
          <ellipse cx={at.x} cy={at.y} rx={rr} ry={rr * STORM.squash} fill="none" stroke={INK} strokeWidth={46} />
          <ellipse cx={at.x} cy={at.y} rx={rr} ry={rr * STORM.squash} fill="none" stroke="#FFFFFF" strokeWidth={30} />
        </>
      ) : null}
      <Cluster puffs={puffs} fill={smokeCol} shade={shadeCol} />
      {fire > 0 ? (
        <g transform={`translate(${at.x}, ${at.y}) scale(${fire})`}>
          <path d={starPath(400, 210, 11)} fill="#FF8A2B" stroke={INK} strokeWidth={LINE * 1.2} strokeLinejoin="round" />
          <path d={starPath(260, 130, 11, 0.25)} fill="#FFD447" />
          <circle r={95} fill="#FFF6C8" />
        </g>
      ) : null}
    </W>
  );
};

// radioactive fallout cloud: born at the storm's mouth, blown toward the beach
const FALL0 = {x: STORM.x, y: STORM.y + 400, z: STORM.z - 60};
const FALL1 = {x: 600, y: 800, z: 1350};
const falloutAt = (t: number) => {
  const u = eio(seg(t, T.blow + 0.1, T.landWord));
  return {x: lerp(FALL0.x, FALL1.x, u), y: lerp(FALL0.y, FALL1.y, u) - 260 * Math.sin(Math.PI * u), z: lerp(FALL0.z, FALL1.z, u), u};
};

const Trefoil: React.FC<{r: number}> = ({r}) => (
  <g>
    <circle r={r} fill="#FFD447" stroke={INK} strokeWidth={r * 0.12} />
    {[0, 1, 2].map((i) => {
      const a0 = (-90 + i * 120 - 30) * (Math.PI / 180);
      const a1 = (-90 + i * 120 + 30) * (Math.PI / 180);
      const R = r * 0.82;
      const r0 = r * 0.24;
      return (
        <path
          key={i}
          d={`M${r0 * Math.cos(a0)},${r0 * Math.sin(a0)} L${R * Math.cos(a0)},${R * Math.sin(a0)} A${R},${R} 0 0 1 ${R * Math.cos(a1)},${R * Math.sin(a1)} L${r0 * Math.cos(a1)},${r0 * Math.sin(a1)} A${r0},${r0} 0 0 0 ${r0 * Math.cos(a0)},${r0 * Math.sin(a0)} Z`}
          fill={INK}
        />
      );
    })}
    <circle r={r * 0.16} fill={INK} />
  </g>
);

const Fallout: React.FC<{t: number}> = ({t}) => {
  if (t < T.blow) return null;
  const f = falloutAt(t);
  const grow = eback(seg(t, T.blow + 0.15, T.blow + 0.5));
  const s = grow * lerp(0.35, 1, eout(f.u));
  const offs = [
    [0, 0, 150],
    [-170, 30, 115],
    [170, 25, 120],
    [-90, -90, 110],
    [95, -95, 115],
    [-280, 70, 80],
    [280, 70, 85],
    [0, 95, 110],
  ];
  const puffs: Puff[] = offs.map(([x, y, r], i) => ({
    x: f.x + x * s,
    y: f.y + y * s,
    r: r * s * (1 + 0.06 * Math.sin(2 * Math.PI * 1.3 * t + i * 1.7)),
  }));
  return (
    <W>
      <defs>
        <radialGradient id="falloutGlow">
          <stop offset="0%" stopColor="rgba(170,255,90,0.45)" />
          <stop offset="100%" stopColor="rgba(170,255,90,0)" />
        </radialGradient>
      </defs>
      <circle cx={f.x} cy={f.y} r={520 * s} fill="url(#falloutGlow)" />
      <Cluster puffs={puffs} fill="#A6E35A" shade="#86C83E" />
      <g transform={`translate(${f.x}, ${f.y + 10 * s}) scale(${s}) rotate(${8 * Math.sin(2 * Math.PI * 0.8 * t)})`}>
        <Trefoil r={62} />
      </g>
    </W>
  );
};

// wind streaks in screen space while the fallout is blown toward land
const WindStreaks: React.FC<{t: number}> = ({t}) => {
  if (t < T.blow || t > 14.2) return null;
  const items = [];
  for (let i = 0; i < 10; i++) {
    const start = T.blow + 0.1 + i * 0.26;
    const u = (t - start) / 0.85;
    if (u < 0 || u > 1) continue;
    const y0 = 330 + 55 * ((i * 7) % 10) + 160 * eio(u);
    const x0 = 1300 - 1700 * eio(u);
    const len = 320 * Math.sin(Math.PI * u);
    const c = 34 * Math.sin(Math.PI * u);
    // a gust line that ends in a little curl
    const d = `M${x0 + len},${y0 - len * 0.18} Q${x0 + len / 2},${y0 - len * 0.05} ${x0},${y0} a${c},${c} 0 1 1 ${c * 0.9},${-c * 1.3}`;
    items.push(<path key={`k${i}`} d={d} fill="none" stroke={INK} strokeWidth={17} strokeLinecap="round" opacity={0.85} />);
    items.push(<path key={i} d={d} fill="none" stroke="#FFFFFF" strokeWidth={9} strokeLinecap="round" />);
  }
  return (
    <AbsoluteFill>
      <svg width={1080} height={1920}>{items}</svg>
    </AbsoluteFill>
  );
};

// "every twenty minutes": a pop-up clock whose 20-minute wedge fills once per storm boom
const Clock: React.FC<{t: number}> = ({t}) => {
  const sc = popScale(t, T.clockIn, T.clockOut, 0.22);
  if (sc <= 0) return null;
  const starts = [T.clockIn + 0.2, T.booms[0], T.booms[1]];
  let frac = 0;
  for (let i = 0; i < 3; i++) if (t >= starts[i] && t < T.booms[i]) frac = seg(t, starts[i], T.booms[i]);
  for (let i = 0; i < 3; i++) if (t >= T.booms[i] && t < T.booms[i] + 0.12) frac = 1;
  const a = (-90 + 120 * frac) * (Math.PI / 180);
  const R = 118;
  const wedge = `M0,0 L0,${-R + 14} A${R - 14},${R - 14} 0 0 1 ${(R - 14) * Math.cos(a)},${(R - 14) * Math.sin(a)} Z`;
  const bump = 1 + T.booms.reduce((acc, b) => acc + ring(t, b, 0.08, 4, 9), 0);
  return (
    <AbsoluteFill>
      <svg width={1080} height={1920}>
        <g transform={`translate(230, 330) scale(${sc * bump}) rotate(${-6 + 3 * Math.sin(t * 3)})`}>
          <rect x={-22} y={-R - 38} width={44} height={30} rx={8} fill="#E2E7EC" stroke={INK} strokeWidth={8} />
          <circle r={R} fill="#FFFFFF" stroke={INK} strokeWidth={10} />
          {frac > 0 ? <path d={wedge} fill="#FF8A2B" /> : null}
          {Array.from({length: 12}, (_, i) => {
            const aa = (i / 12) * Math.PI * 2;
            return <line key={i} x1={Math.cos(aa) * (R - 26)} y1={Math.sin(aa) * (R - 26)} x2={Math.cos(aa) * (R - 12)} y2={Math.sin(aa) * (R - 12)} stroke={INK} strokeWidth={i % 3 === 0 ? 8 : 4} strokeLinecap="round" />;
          })}
          <line x1={0} y1={0} x2={(R - 34) * Math.cos(a)} y2={(R - 34) * Math.sin(a)} stroke={INK} strokeWidth={10} strokeLinecap="round" />
          <line x1={0} y1={0} x2={0} y2={-(R - 60)} stroke={INK} strokeWidth={12} strokeLinecap="round" />
          <circle r={12} fill={INK} />
        </g>
      </svg>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------------------------------------------
// Set pieces
const Sea: React.FC = () => (
  <W>
    <rect x={-9000} y={HORIZON_Y} width={20000} height={30000} fill="#3E8DD0" />
    <rect x={-9000} y={HORIZON_Y} width={20000} height={160} fill="#5AA6E0" />
    <line x1={-9000} x2={11000} y1={HORIZON_Y} y2={HORIZON_Y} stroke={INK} strokeWidth={16} />
  </W>
);

const Waves: React.FC<{t: number; pts: [number, number][]; w: number}> = ({t, pts, w}) => (
  <W>
    {pts.map(([x, y], i) => {
      const bob = 10 * Math.sin(2 * Math.PI * 0.5 * t + i * 1.9);
      return (
        <path key={i} d={`M${x - w},${y + bob} q${w / 2},${-w * 0.35} ${w},0 q${w / 2},${-w * 0.35} ${w},0`} fill="none" stroke="#FFFFFF" strokeWidth={w * 0.13} strokeLinecap="round" opacity={0.9} />
      );
    })}
  </W>
);

const Sand: React.FC<{t: number}> = ({t}) => {
  let d = `M-6000,${SAND_Y + 40}`;
  for (let x = -6000; x <= 7000; x += 200) {
    const y = SAND_Y + 18 * Math.sin(x / 180 + t * 1.6);
    d += ` L${x},${y.toFixed(1)}`;
  }
  return (
    <W>
      <rect x={-6000} y={SAND_Y} width={13000} height={9000} fill="#F2D59B" />
      <path d={d} fill="none" stroke={INK} strokeWidth={46} strokeLinecap="round" />
      <path d={d} fill="none" stroke="#FFFFFF" strokeWidth={30} strokeLinecap="round" />
      <ellipse cx={-120} cy={SAND_Y + 330} rx={160} ry={26} fill="#E5C47F" />
      <ellipse cx={900} cy={SAND_Y + 520} rx={220} ry={30} fill="#E5C47F" />
    </W>
  );
};

const Palm: React.FC = () => {
  const s = 0.9;
  const fx = 1116;
  const fy = 1600;
  return (
    <Img
      src={staticFile('hurricane/palm.png')}
      style={{position: 'absolute', left: fx - SPR.palm.feet[0] * s, top: fy - SPR.palm.feet[1] * s, width: SPR.palm.w * s, height: SPR.palm.h * s}}
    />
  );
};

// ---------------------------------------------------------------------------------------------------------------
// Sound
type Cue = {f: string; at: number; db: number; keys?: [number, number][]};
const CUES: Cue[] = [
  {f: 'wind', at: 0, db: -30, keys: [[0, -32], [2.4, -32], [3.6, -25], [10.8, -25], [11.4, -21], [13.0, -27], [14.8, -30]]},
  {f: 'whoosh', at: T.release - 0.2, db: -24},
  {f: 'whoosh', at: 2.55, db: -30},
  {f: 'pop', at: T.eyesOpen, db: -20},
  {f: 'pop', at: T.clockIn, db: -24},
  ...Array.from({length: 12}, (_, i) => ({f: 'tick', at: T.clockIn + 0.3 + i * 0.24, db: -27})),
  ...T.booms.map((b) => ({f: 'boom_small', at: b, db: -21})),
  {f: 'boom', at: T.blast, db: -9},
  {f: 'shock', at: T.blast + 0.05, db: -26},
  {f: 'gust', at: T.blow, db: -19},
  {f: 'boing', at: T.scared, db: -21},
];

const dbAt = (c: Cue, t: number) => {
  if (!c.keys) return c.db;
  const k = c.keys;
  if (t <= k[0][0]) return k[0][1];
  for (let i = 1; i < k.length; i++) if (t <= k[i][0]) return lerp(k[i - 1][1], k[i][1], seg(t, k[i - 1][0], k[i][0]));
  return k[k.length - 1][1];
};

const Sounds: React.FC = () => (
  <>
    <Sequence from={Math.round(VO_AT * FPS)} layout="none">
      <Audio src={staticFile('hurricane/vo/take1.mp3')} volume={10 ** (MASTER_DB / 20)} />
    </Sequence>
    {CUES.map((c, i) => {
      const from = Math.round(c.at * FPS);
      return (
        <Sequence key={i} from={from} layout="none">
          <Audio src={staticFile(`hurricane/sfx/${c.f}.wav`)} volume={(f) => 10 ** ((dbAt(c, (from + f) / FPS) + MASTER_DB) / 20)} />
        </Sequence>
      );
    })}
  </>
);

// ---------------------------------------------------------------------------------------------------------------
export const Hurricane: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const cam = camAt(t);
  const sh = shakeAt(t);

  // bomb
  let bomb: {x: number; y: number; z: number; rot: number; behind: boolean} | null = null;
  if (t >= T.release && t < T.arrive) bomb = {...flight(t), behind: false};
  else if (t >= T.arrive && t < T.blast) {
    const o = orbitPos(t);
    bomb = {x: o.x, y: o.y, z: STORM.z - 10, rot: 360 + 25 * Math.sin(t * 4), behind: o.behind};
  }
  const blastAt = orbitPos(T.blast);
  const look = t < T.blast ? (bomb ? {x: bomb.x, y: bomb.y} : blastAt) : t < T.blow ? {x: STORM.x, y: STORM.y + 600} : {x: STORM.x - 300, y: STORM.y + 900};

  // depth of field: blur the far plane a little only while the camera is close to the character
  const farBlur = t < 2.3 ? 0 : 0;
  const fall = falloutAt(t);
  const flash = t >= T.blast ? 0.6 * Math.exp(-14 * (t - T.blast)) : 0;
  const skyDark = 0.25 * eio(seg(t, 2.4, 3.8)) * (1 - eio(seg(t, 11.3, 12.9)));

  return (
    <AbsoluteFill style={{background: '#9EC3E0', overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `translate(${sh.x}px, ${sh.y}px) scale(1.04)`}}>
        {/* sky */}
        <AbsoluteFill style={{background: 'linear-gradient(180deg, #6F93B8 0%, #9EC3E0 45%, #CFE3F0 100%)'}} />
        <AbsoluteFill style={{background: `rgba(30, 44, 66, ${skyDark})`}} />

        <Layer cam={cam} z={STORM.z} blur={farBlur}>
          <Sea />
          <StormBackdrop t={t} />
        </Layer>
        {bomb && bomb.behind ? <Layer cam={cam} z={bomb.z}>{bombSprite(bomb.x, bomb.y, bomb.rot, true, t)}</Layer> : null}
        <Layer cam={cam} z={STORM.z} blur={farBlur}>
          <Storm t={t} />
          <StormBooms t={t} />
          <Face t={t} look={look} />
        </Layer>
        {bomb && !bomb.behind && t >= T.arrive ? <Layer cam={cam} z={bomb.z}>{bombSprite(bomb.x, bomb.y, bomb.rot, true, t)}</Layer> : null}
        <Layer cam={cam} z={STORM.z - 20}>
          <Blast t={t} at={blastAt} />
        </Layer>
        {fall.z >= 2200 ? <Layer cam={cam} z={fall.z}><Fallout t={t} /></Layer> : null}
        <Layer cam={cam} z={2200}>
          <Waves t={t} pts={[[-260, 1040], [520, 1110], [1350, 1010], [1900, 1180], [-800, 1200]]} w={90} />
        </Layer>
        {fall.z < 2200 && fall.z >= 1700 ? <Layer cam={cam} z={fall.z}><Fallout t={t} /></Layer> : null}
        <Layer cam={cam} z={1700}>
          <Waves t={t} pts={[[-150, 1330], [700, 1290], [1500, 1380], [250, 1470]]} w={80} />
        </Layer>
        {fall.z < 1700 && fall.z >= 1600 ? <Layer cam={cam} z={fall.z}><Fallout t={t} /></Layer> : null}
        <Layer cam={cam} z={1600}>
          <Palm />
        </Layer>
        {fall.z < 1600 ? <Layer cam={cam} z={fall.z}><Fallout t={t} /></Layer> : null}
        <Layer cam={cam} z={1250}>
          <Sand t={t} />
        </Layer>
        <Layer cam={cam} z={1000}>
          <Guy t={t} />
        </Layer>
        {bomb && t < T.arrive ? <Layer cam={cam} z={bomb.z} minDepth={150}>{bombSprite(bomb.x, bomb.y, bomb.rot, true, t)}</Layer> : null}
        <WindStreaks t={t} />
      </AbsoluteFill>
      <Clock t={t} />
      <AbsoluteFill style={{background: `rgba(255, 252, 235, ${flash})`}} />
      <Sounds />
    </AbsoluteFill>
  );
};
