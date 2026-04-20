import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Video,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

type DataPoint = {label: string; value: number};
type FlowNode = {
  id: string;
  label: string;
  role?: 'source' | 'process' | 'modifier' | 'result' | 'actor' | 'sink';
  children?: string[];
};
type FlowConnection = {from: string; to: string};

const palette: Record<string, string> = {
  negative: '#E63946',
  positive: '#2EC4B6',
  neutral: '#FF9F1C',
  red: '#E63946',
  teal: '#2EC4B6',
  orange: '#FF9F1C',
  navy: '#4361EE',
  white: '#FFFFFF',
};

const bg: React.CSSProperties = {
  background:
    'radial-gradient(circle at 20% 15%, rgba(46,196,182,0.18), transparent 28%), linear-gradient(135deg, #080812 0%, #101827 55%, #07070d 100%)',
  color: 'white',
  fontFamily: 'Avenir Next, Helvetica Neue, sans-serif',
};

const formatValue = (value: number, unit = '') => {
  if (unit === '%') {
    return `${Math.round(value)}%`;
  }
  if (unit === '₹') {
    return `₹${Math.round(value).toLocaleString('en-IN')}`;
  }
  return Math.round(value).toLocaleString('en-IN');
};

const FinanceGrid: React.FC<{accent: string}> = ({accent}) => (
  <>
    <div
      style={{
        position: 'absolute',
        inset: 0,
        backgroundImage:
          'linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)',
        backgroundSize: '72px 72px',
        maskImage: 'linear-gradient(90deg, transparent, black 12%, black 88%, transparent)',
      }}
    />
    <div
      style={{
        position: 'absolute',
        top: -180,
        right: -120,
        width: 620,
        height: 620,
        borderRadius: 999,
        background: `radial-gradient(circle, ${accent}44, transparent 62%)`,
      }}
    />
  </>
);

export const StatReveal: React.FC<{
  headline?: string;
  subtext?: string;
  kicker?: string;
  sentiment?: 'negative' | 'positive' | 'neutral';
}> = ({headline = 'KEY STAT', subtext = '', kicker = 'Finance insight', sentiment = 'neutral'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const lift = spring({frame, fps, config: {damping: 16, stiffness: 95}});
  const accent = palette[sentiment] ?? palette.neutral;
  return (
    <AbsoluteFill style={{...bg, overflow: 'hidden'}}>
      <FinanceGrid accent={accent} />
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(transparent 55%, rgba(0,0,0,0.5))'}} />
      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 12, background: accent}} />
      <div style={{position: 'absolute', top: 70, left: 84, color: accent, fontSize: 26, letterSpacing: 6, textTransform: 'uppercase', fontWeight: 900}}>
        {kicker}
      </div>
      <div
        style={{
          margin: 'auto',
          textAlign: 'center',
          transform: `translateY(${interpolate(lift, [0, 1], [80, 0])}px)`,
          opacity: lift,
          width: '82%',
        }}
      >
        <div style={{fontSize: 154, fontWeight: 950, letterSpacing: -7, lineHeight: 0.95, textShadow: `0 0 42px ${accent}55`}}>{headline}</div>
        <div
          style={{
            height: 10,
            width: interpolate(frame, [8, 34], [0, 620], {extrapolateRight: 'clamp'}),
            background: accent,
            borderRadius: 99,
            margin: '34px auto',
          }}
        />
        <div style={{fontSize: 50, fontWeight: 650, opacity: interpolate(frame, [18, 36], [0, 0.84], {extrapolateRight: 'clamp'})}}>
          {subtext}
        </div>
      </div>
      <div style={{position: 'absolute', right: 72, bottom: 58, color: '#8D99AE', fontSize: 24, letterSpacing: 3}}>YTCREATE FINANCE</div>
    </AbsoluteFill>
  );
};

export const StatExplosion: React.FC<{
  headline?: string;
  subtext?: string;
  color?: 'red' | 'orange' | 'teal' | 'navy' | 'white';
}> = ({headline = '₹0', subtext = 'that is the problem', color = 'orange'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = palette[color] ?? palette.orange;
  const pop = spring({frame, fps, config: {damping: 9, stiffness: 180}});
  const y = interpolate(pop, [0, 1], [260, 0]);
  const scale = interpolate(pop, [0, 0.75, 1], [0.3, 1.2, 1]);
  const subIn = interpolate(frame, [12, 20], [70, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: '#0A0A14', color: 'white', overflow: 'hidden', fontFamily: 'Impact, Anton, Avenir Next, sans-serif'}}>
      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: 8, background: accent}} />
      <div style={{margin: 'auto', textAlign: 'center', width: '86%', transform: `translateY(${y}px) scale(${scale})`}}>
        <div style={{fontSize: 166, fontWeight: 950, lineHeight: 0.9, color: accent, textTransform: 'uppercase'}}>{headline}</div>
        <div style={{marginTop: 34, fontFamily: 'Nunito, Avenir Next, sans-serif', fontSize: 42, color: 'rgba(255,255,255,0.72)', transform: `translateY(${subIn}px)`, opacity: interpolate(frame, [12, 20], [0, 1], {extrapolateRight: 'clamp'})}}>
          {subtext}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const TextBurst: React.FC<{
  content?: string;
  color?: 'red' | 'orange' | 'teal' | 'navy' | 'white';
}> = ({content = 'WAIT WHAT', color = 'orange'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = content.split(/\s+/).filter(Boolean);
  const accent = palette[color] ?? palette.orange;
  const lines = words.length > 4 ? [words.slice(0, Math.ceil(words.length / 2)), words.slice(Math.ceil(words.length / 2))] : [words];
  return (
    <AbsoluteFill style={{background: accent, color: 'white', alignItems: 'center', justifyContent: 'center', fontFamily: 'Nunito, Avenir Next, sans-serif'}}>
      {lines.map((line, lineIndex) => (
        <div key={lineIndex} style={{display: 'flex', gap: 24, justifyContent: 'center', margin: '8px 0'}}>
          {line.map((word, wordIndex) => {
            const globalIndex = lineIndex * Math.ceil(words.length / 2) + wordIndex;
            const local = Math.max(0, frame - globalIndex * 3);
            const pop = spring({frame: local, fps, config: {damping: 12, stiffness: 220}});
            return (
              <span key={`${word}-${wordIndex}`} style={{fontSize: 96, fontWeight: 950, transform: `scale(${interpolate(pop, [0, 1], [1.4, 1])})`, opacity: pop, textTransform: 'uppercase'}}>
                {word}
              </span>
            );
          })}
        </div>
      ))}
    </AbsoluteFill>
  );
};

export const ReactionCard: React.FC<{
  content?: string;
  subtext?: string;
  color?: 'red' | 'orange' | 'teal' | 'navy' | 'white';
}> = ({content = 'bruh', subtext = '', color = 'red'}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const accent = palette[color] ?? palette.red;
  const bounce = spring({frame, fps, config: {damping: 7, stiffness: 170}});
  const exitOpacity = interpolate(frame, [durationInFrames - 4, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: accent, color: 'white', alignItems: 'center', justifyContent: 'center', textAlign: 'center', fontFamily: 'Avenir Next, Helvetica Neue, sans-serif', opacity: exitOpacity}}>
      <div style={{fontSize: 120, fontWeight: 950, transform: `translateY(${interpolate(bounce, [0, 1], [70, 0])}px)`, textTransform: 'lowercase'}}>{content}</div>
      {subtext ? <div style={{marginTop: 24, fontSize: 40, fontWeight: 750, color: 'rgba(255,255,255,0.72)'}}>{subtext}</div> : null}
    </AbsoluteFill>
  );
};

export const SplitComparison: React.FC<{
  leftLabel?: string;
  leftContent?: string;
  rightLabel?: string;
  rightContent?: string;
}> = ({leftLabel = 'WHAT YOU THINK', leftContent = '6.5% FD return', rightLabel = 'REALITY', rightContent = '-0.2% after inflation'}) => {
  const frame = useCurrentFrame();
  const line = interpolate(frame, [0, 15], [0, 1080], {extrapolateRight: 'clamp'});
  const leftX = interpolate(frame, [8, 20], [-120, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const rightX = interpolate(frame, [8, 20], [120, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: '#0A0A14', color: 'white', fontFamily: 'Avenir Next, Helvetica Neue, sans-serif'}}>
      <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: '50%', background: '#1A0A0A'}} />
      <div style={{position: 'absolute', right: 0, top: 0, bottom: 0, width: '50%', background: '#0A1A14'}} />
      <div style={{position: 'absolute', left: 960, top: 0, width: 5, height: line, background: 'rgba(255,255,255,0.75)'}} />
      <div style={{position: 'absolute', left: 110, right: 1030, top: 300, transform: `translateX(${leftX}px)`}}>
        <div style={{fontSize: 22, fontWeight: 950, color: '#E63946', letterSpacing: 2}}>{leftLabel}</div>
        <div style={{marginTop: 24, fontSize: 56, lineHeight: 1.05, fontWeight: 900}}>{leftContent}</div>
      </div>
      <div style={{position: 'absolute', left: 1030, right: 110, top: 300, transform: `translateX(${rightX}px)`}}>
        <div style={{fontSize: 22, fontWeight: 950, color: '#2EC4B6', letterSpacing: 2}}>{rightLabel}</div>
        <div style={{marginTop: 24, fontSize: 56, lineHeight: 1.05, fontWeight: 900}}>{rightContent}</div>
      </div>
    </AbsoluteFill>
  );
};

export const FlowDiagram: React.FC<{
  mode?: 'linear' | 'branch' | 'loop' | 'decay' | 'growth';
  layout?: 'horizontal' | 'vertical' | 'radial';
  spacing?: 'equal' | 'weighted';
  direction?: 'forward' | 'reverse';
  nodes?: FlowNode[];
  connections?: FlowConnection[];
  caption?: string;
  color?: 'red' | 'orange' | 'teal' | 'navy' | 'white';
  animationIntent?: 'reveal' | 'progress' | 'highlight' | 'transform';
  animationSpec?: {type?: 'fade_sequence' | 'line_draw' | 'pulse_node' | 'scale_change'};
  contextRef?: string;
}> = ({
  mode = 'linear',
  layout = 'horizontal',
  direction = 'forward',
  nodes = [
    {id: 'income', label: 'Income', role: 'source'},
    {id: 'expenses', label: 'Expenses', role: 'process'},
    {id: 'savings', label: 'Savings', role: 'result'},
  ],
  connections,
  caption = 'Follow the money',
  color = 'orange',
  animationIntent = 'reveal',
  animationSpec = {type: 'fade_sequence'},
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const accent = palette[color] ?? palette.orange;
  const safeNodes = nodes.slice(0, 5);
  const positions = safeNodes.map((node, index) => {
    if (layout === 'radial' || mode === 'loop') {
      const angle = -Math.PI / 2 + (index / Math.max(safeNodes.length, 1)) * Math.PI * 2;
      return {node, x: 960 + Math.cos(angle) * 460, y: 510 + Math.sin(angle) * 250};
    }
    if (layout === 'vertical' || mode === 'branch') {
      const x = mode === 'branch' && index > 0 ? 720 + (index % 2) * 480 : 960;
      return {node, x, y: 210 + index * (620 / Math.max(safeNodes.length - 1, 1))};
    }
    const orderedIndex = direction === 'reverse' ? safeNodes.length - 1 - index : index;
    return {node, x: 260 + orderedIndex * (1400 / Math.max(safeNodes.length - 1, 1)), y: 520};
  });
  const byId = Object.fromEntries(positions.map((position) => [position.node.id, position]));
  const safeConnections =
    connections && connections.length
      ? connections.filter((connection) => byId[connection.from] && byId[connection.to]).slice(0, 6)
      : safeNodes.slice(0, -1).map((node, index) => ({from: node.id, to: safeNodes[index + 1].id}));
  const draw = interpolate(frame, [5, 42], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const pulse = spring({frame, fps, config: {damping: 10, stiffness: 130}});
  const transformScale = mode === 'decay' ? interpolate(frame, [15, 55], [1, 0.72], {extrapolateRight: 'clamp'}) : mode === 'growth' ? interpolate(frame, [15, 55], [0.78, 1.15], {extrapolateRight: 'clamp'}) : 1;
  const specType = animationSpec?.type ?? (animationIntent === 'progress' ? 'line_draw' : 'fade_sequence');
  return (
    <AbsoluteFill style={{...bg, overflow: 'hidden'}}>
      <FinanceGrid accent={accent} />
      <svg width="1920" height="1080" style={{position: 'absolute', inset: 0}}>
        {safeConnections.map((connection, index) => {
          const start = byId[connection.from];
          const end = byId[connection.to];
          if (!start || !end) {
            return null;
          }
          const visible = specType === 'line_draw' ? interpolate(frame, [8 + index * 4, 30 + index * 4], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : draw;
          return (
            <line
              key={`${connection.from}-${connection.to}-${index}`}
              x1={start.x}
              y1={start.y}
              x2={start.x + (end.x - start.x) * visible}
              y2={start.y + (end.y - start.y) * visible}
              stroke={accent}
              strokeWidth={7}
              strokeLinecap="round"
              opacity={0.75}
            />
          );
        })}
      </svg>
      {positions.map(({node, x, y}, index) => {
        const reveal = interpolate(frame, [index * 5, index * 5 + 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        const isResult = node.role === 'result';
        const scale = isResult && specType === 'scale_change' ? transformScale : specType === 'pulse_node' && isResult ? interpolate(pulse, [0, 1], [0.92, 1.06]) : 1;
        const childReveal = interpolate(frame, [28 + index * 3, 44 + index * 3], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
        return (
          <div
            key={node.id}
            style={{
              position: 'absolute',
              left: x - 150,
              top: y - 72,
              width: 300,
              minHeight: 144,
              borderRadius: 24,
              border: `3px solid ${accent}`,
              background: node.role === 'modifier' ? 'rgba(230,57,70,0.18)' : 'rgba(6,10,22,0.86)',
              boxShadow: `0 18px 44px ${accent}22`,
              opacity: reveal,
              transform: `scale(${scale}) translateY(${interpolate(reveal, [0, 1], [30, 0])}px)`,
              color: 'white',
              textAlign: 'center',
              padding: '24px 20px',
              fontFamily: 'Avenir Next, Helvetica Neue, sans-serif',
            }}
          >
            <div style={{fontSize: 18, color: accent, fontWeight: 900, textTransform: 'uppercase'}}>{node.role ?? 'step'}</div>
            <div style={{marginTop: 12, fontSize: 38, lineHeight: 1.05, fontWeight: 900}}>{node.label}</div>
            {node.children && node.children.length ? (
              <div style={{marginTop: 14, display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap', opacity: childReveal}}>
                {node.children.slice(0, 4).map((child) => (
                  <span key={child} style={{padding: '5px 10px', borderRadius: 12, background: 'rgba(255,255,255,0.12)', color: '#D6DEEA', fontSize: 18, fontWeight: 700}}>
                    {child}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        );
      })}
      <div style={{position: 'absolute', left: 160, right: 160, bottom: 78, padding: '22px 34px', borderLeft: `8px solid ${accent}`, background: 'rgba(5,8,15,0.76)', color: 'white', fontSize: 42, fontWeight: 850, textAlign: 'center'}}>
        {caption}
      </div>
    </AbsoluteFill>
  );
};

export const BarChart: React.FC<{title?: string; data?: DataPoint[]; color?: 'red' | 'teal' | 'orange'; unit?: string; animationSpeed?: 'normal' | 'fast'}> = ({
  title = 'Financial Overview',
  data = [],
  color = 'orange',
  unit = '',
  animationSpeed = 'normal',
}) => {
  const frame = useCurrentFrame();
  const safeData = data.filter((point) => Number.isFinite(Number(point.value)));
  if (!safeData.length) {
    return (
      <AbsoluteFill style={bg}>
        <FinanceGrid accent={palette[color] ?? palette.orange} />
        <h1 style={{position: 'absolute', top: 72, left: 160, right: 160, fontSize: 68}}>{title}</h1>
        <div style={{position: 'absolute', left: 180, right: 180, top: 430, color: '#fff', fontSize: 74, fontWeight: 900, textAlign: 'center'}}>
          Real data required
        </div>
      </AbsoluteFill>
    );
  }
  const max = Math.max(...safeData.map((d) => Number(d.value) || 0), 1);
  const growFrames = animationSpeed === 'fast' ? 60 : 90;
  const grow = interpolate(frame, [0, growFrames], [0, 1], {easing: Easing.out(Easing.cubic), extrapolateRight: 'clamp'});
  const chartLeft = 220;
  const chartBottom = 880;
  const chartHeight = 610;
  const step = 1450 / safeData.length;
  return (
    <AbsoluteFill style={bg}>
      <FinanceGrid accent={palette[color] ?? palette.orange} />
      <h1 style={{position: 'absolute', top: 72, left: 160, right: 160, fontSize: 68, letterSpacing: -2}}>{title}</h1>
      <div style={{position: 'absolute', top: 158, left: 164, color: '#AAB4C5', fontSize: 26}}>Animated data snapshot</div>
      <div style={{position: 'absolute', left: 128, top: 210, right: 128, bottom: 104, border: '1px solid rgba(255,255,255,0.1)', borderRadius: 34, background: 'rgba(3,7,18,0.44)'}} />
      <svg width="1920" height="1080" style={{position: 'absolute', inset: 0}}>
        {[0, 1, 2, 3, 4].map((i) => (
          <line key={i} x1={chartLeft} x2={1700} y1={chartBottom - i * 135} y2={chartBottom - i * 135} stroke="rgba(255,255,255,0.08)" />
        ))}
        {safeData.map((point, i) => {
          const h = ((Number(point.value) || 0) / max) * chartHeight * grow;
          const x = chartLeft + i * step + step * 0.2;
          const y = chartBottom - h;
          return (
            <g key={point.label}>
              <rect x={x} y={y} width={step * 0.56} height={h} rx={16} fill={palette[color] ?? palette.orange} />
              <text x={x + step * 0.28} y={chartBottom + 54} fill="#AAB4C5" textAnchor="middle" fontSize={28}>
                {point.label}
              </text>
              <text x={x + step * 0.28} y={y - 24} fill="#fff" textAnchor="middle" fontSize={34} fontWeight={800}>
                {formatValue(Number(point.value) || 0, unit)}
              </text>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};

export const LineChart: React.FC<{title?: string; data?: DataPoint[]; color?: 'red' | 'teal' | 'orange'; unit?: string; animationSpeed?: 'normal' | 'fast'}> = ({
  title = 'Financial Trend',
  data = [],
  color = 'teal',
  unit = '',
  animationSpeed = 'normal',
}) => {
  const frame = useCurrentFrame();
  const safeData = data.filter((point) => Number.isFinite(Number(point.value)));
  if (safeData.length < 2) {
    return (
      <AbsoluteFill style={bg}>
        <FinanceGrid accent={palette[color] ?? palette.teal} />
        <h1 style={{position: 'absolute', top: 72, left: 160, right: 160, fontSize: 68}}>{title}</h1>
        <div style={{position: 'absolute', left: 180, right: 180, top: 430, color: '#fff', fontSize: 74, fontWeight: 900, textAlign: 'center'}}>
          Real trend data required
        </div>
      </AbsoluteFill>
    );
  }
  const max = Math.max(...safeData.map((d) => Number(d.value) || 0), 1);
  const drawFrames = animationSpeed === 'fast' ? 60 : 100;
  const draw = interpolate(frame, [0, drawFrames], [0, 1], {easing: Easing.out(Easing.cubic), extrapolateRight: 'clamp'});
  const points = safeData.map((point, i) => {
    const x = 240 + i * (1420 / Math.max(safeData.length - 1, 1));
    const y = 870 - ((Number(point.value) || 0) / max) * 610;
    return {x, y, point};
  });
  const visible = Math.max(2, Math.ceil(points.length * draw));
  const line = points.slice(0, visible).map((p) => `${p.x},${p.y}`).join(' ');
  return (
    <AbsoluteFill style={bg}>
      <FinanceGrid accent={palette[color] ?? palette.teal} />
      <h1 style={{position: 'absolute', top: 72, left: 160, right: 160, fontSize: 68, letterSpacing: -2}}>{title}</h1>
      <div style={{position: 'absolute', top: 158, left: 164, color: '#AAB4C5', fontSize: 26}}>Trend line with highlighted data points</div>
      <div style={{position: 'absolute', left: 128, top: 210, right: 128, bottom: 104, border: '1px solid rgba(255,255,255,0.1)', borderRadius: 34, background: 'rgba(3,7,18,0.44)'}} />
      <svg width="1920" height="1080" style={{position: 'absolute', inset: 0}}>
        {[0, 1, 2, 3, 4].map((i) => (
          <line key={i} x1={220} x2={1700} y1={870 - i * 135} y2={870 - i * 135} stroke="rgba(255,255,255,0.08)" />
        ))}
        <polyline points={line} fill="none" stroke={palette[color] ?? palette.teal} strokeWidth={8} strokeLinecap="round" strokeLinejoin="round" />
        {points.slice(0, visible).map(({x, y, point}) => (
          <g key={point.label}>
            <circle cx={x} cy={y} r={11} fill={palette[color] ?? palette.teal} />
            <text x={x} y={930} fill="#AAB4C5" textAnchor="middle" fontSize={28}>
              {point.label}
            </text>
            <text x={x} y={y - 28} fill="#fff" textAnchor="middle" fontSize={32} fontWeight={800}>
              {formatValue(Number(point.value) || 0, unit)}
            </text>
          </g>
        ))}
      </svg>
    </AbsoluteFill>
  );
};

export const BrollOverlay: React.FC<{videoPath?: string; overlayText?: string; brand?: string; sentiment?: 'negative' | 'positive' | 'neutral'}> = ({
  videoPath = '',
  overlayText = 'Finance insight',
  brand = 'YTCreate Finance',
  sentiment = 'neutral',
}) => {
  const frame = useCurrentFrame();
  const accent = palette[sentiment] ?? palette.neutral;
  const src = videoPath.startsWith('http://') || videoPath.startsWith('https://') ? videoPath : staticFile(videoPath);
  return (
    <AbsoluteFill style={{background: '#080812'}}>
      {videoPath ? (
        <Video src={src} style={{width: '100%', height: '100%', objectFit: 'cover', filter: 'contrast(1.08) saturate(0.82) brightness(0.78)'}} />
      ) : (
        <>
          <div style={{...bg, position: 'absolute', inset: 0}} />
          <FinanceGrid accent={accent} />
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: 260 + i * 260,
                bottom: 240,
                width: 130,
                height: interpolate(frame, [0, 42], [90, 250 + i * 72], {extrapolateRight: 'clamp'}),
                borderRadius: 20,
                background: `linear-gradient(180deg, ${accent}, rgba(255,255,255,0.08))`,
                opacity: 0.82,
              }}
            />
          ))}
        </>
      )}
      <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(0,0,0,0.72), rgba(0,0,0,0.2) 55%, rgba(0,0,0,0.5))'}} />
      <div style={{position: 'absolute', top: 54, left: 64, fontSize: 24, letterSpacing: 4, color: accent, fontWeight: 900}}>{brand}</div>
      <div style={{position: 'absolute', left: 64, bottom: 72, width: 1120, padding: '36px 44px', borderLeft: `10px solid ${accent}`, background: 'rgba(5,8,15,0.78)', borderRadius: 24}}>
        <div style={{fontSize: 64, fontWeight: 900, color: 'white', lineHeight: 1.04}}>{overlayText}</div>
        <div style={{marginTop: 18, fontSize: 24, color: '#AAB4C5', letterSpacing: 2}}>CONTEXT VISUAL</div>
      </div>
    </AbsoluteFill>
  );
};

export const SceneTransition: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 7, 15], [0, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: '#05050A', opacity}} />;
};

export const IntroCard: React.FC<{title?: string; channelName?: string}> = ({title = 'Finance Breakdown', channelName = 'YTCreate Finance'}) => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [5, 35], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={bg}>
      <div style={{margin: 'auto', width: '78%', transform: `translateY(${(1 - reveal) * 40}px)`, opacity: reveal}}>
        <div style={{fontSize: 28, color: '#2EC4B6', fontWeight: 800, letterSpacing: 6}}>{channelName}</div>
        <div style={{fontSize: 84, fontWeight: 900, letterSpacing: -3, lineHeight: 1.04, marginTop: 24}}>{title}</div>
      </div>
    </AbsoluteFill>
  );
};

export const EndCard: React.FC<{message?: string; nextTitle?: string}> = ({
  message = 'Subscribe for more finance insights',
  nextTitle = '',
}) => (
  <AbsoluteFill style={{...bg, alignItems: 'center', justifyContent: 'center', textAlign: 'center'}}>
    <div style={{fontSize: 70, fontWeight: 900}}>{message}</div>
    <div style={{marginTop: 34, padding: '18px 34px', borderRadius: 999, background: '#E63946', fontSize: 34, fontWeight: 850}}>SUBSCRIBE</div>
    {nextTitle ? <div style={{marginTop: 46, fontSize: 32, color: '#AAB4C5'}}>Next: {nextTitle}</div> : null}
  </AbsoluteFill>
);

export const ThumbnailFrame: React.FC<{
  dominantText?: string;
  supportingText?: string;
  brand?: string;
  variant?: number;
}> = ({dominantText = '₹5,000', supportingText = 'THAT IS ALL', brand = 'YTCreate', variant = 1}) => {
  const accent = variant % 2 === 0 ? '#2EC4B6' : '#E63946';
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 18% 20%, ${accent}55, transparent 30%), linear-gradient(135deg, #080812, #172033)`,
        color: 'white',
        fontFamily: 'Avenir Next, Helvetica Neue, sans-serif',
      }}
    >
      <div style={{position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(45deg, rgba(255,255,255,0.05) 25%, transparent 25%)', backgroundSize: '42px 42px'}} />
      <div style={{position: 'absolute', top: 44, left: 52, color: accent, fontSize: 30, fontWeight: 900, letterSpacing: 2}}>{brand}</div>
      <div style={{position: 'absolute', left: 66, top: 210, height: 118, width: 680, background: accent, transform: 'skewX(-8deg)'}} />
      <div style={{position: 'absolute', left: 84, top: 170, fontSize: 128, fontWeight: 950, letterSpacing: -7, textShadow: '0 10px 28px rgba(0,0,0,0.45)'}}>{dominantText}</div>
      <div style={{position: 'absolute', left: 88, top: 360, width: 760, fontSize: 58, fontWeight: 900, lineHeight: 1.02}}>{supportingText}</div>
      <div style={{position: 'absolute', right: 74, bottom: 58, width: 250, height: 250, borderRadius: 999, border: `18px solid ${accent}`, opacity: 0.8}} />
    </AbsoluteFill>
  );
};
