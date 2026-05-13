import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, getBeatData, getBeatProgress} from './visualUtils';
import {TimedSentence, currentSceneProgress, narrationSentences, sceneNarrationText} from './narrationTiming';

type PricePoint = {x: number; y: number};
type FomoMoment = {
	startProgress: number;
	endProgress: number;
	visualMode: 'hype_rise' | 'peak_buy' | 'crash_drop' | 'loss_lock';
};

const defaultPoints: PricePoint[] = [
	{x: 0.02, y: 0.68},
	{x: 0.18, y: 0.58},
	{x: 0.34, y: 0.42},
	{x: 0.52, y: 0.18},
	{x: 0.66, y: 0.28},
	{x: 0.82, y: 0.62},
	{x: 0.98, y: 0.78},
];

const pathFromPoints = (points: PricePoint[], width: number, height: number, progress: number) => {
	const visible = Math.max(2, Math.ceil(points.length * progress));
	return points
		.slice(0, visible)
		.map((point, index) => `${index === 0 ? 'M' : 'L'} ${(point.x * width).toFixed(1)} ${(point.y * height).toFixed(1)}`)
		.join(' ');
};

const semanticModeForSentence = (sentence: string): FomoMoment['visualMode'] | null => {
	if (/loss|locked|panic|after\s+entry|regret|sell/i.test(sentence)) {
		return 'loss_lock';
	}
	if (/crash|falls?|drop|red|down|breaks?/i.test(sentence)) {
		return 'crash_drop';
	}
	if (/buy|entry|peak|top|fomo|jump/i.test(sentence)) {
		return 'peak_buy';
	}
	if (/hype|rise|runs?|green|rally|loud|shoots?/i.test(sentence)) {
		return 'hype_rise';
	}
	return null;
};

const momentForSentence = (sentence: TimedSentence, visualMode: FomoMoment['visualMode']): FomoMoment => ({
	startProgress: Math.max(0, sentence.startProgress - 0.004),
	endProgress: Math.min(1, sentence.endProgress + 0.01),
	visualMode,
});

const buildFomoSequence = (narration: string): FomoMoment[] =>
	narrationSentences(narration)
		.map((sentence) => {
			const visualMode = semanticModeForSentence(sentence.text);
			return visualMode ? momentForSentence(sentence, visualMode) : null;
		})
		.filter(Boolean) as FomoMoment[];

export const FOMOPriceCrashVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'crash');
	const narration = sceneNarrationText(scene);
	const sceneProgress = currentSceneProgress(scene, beat, frameWithinBeat, fps);
	const points = Array.isArray(data.points) ? (data.points as PricePoint[]) : defaultPoints;
	const progressBase = getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.82));
	const progress = phase === 'rise' ? 0.55 : phase === 'loss' ? 1 : progressBase;
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const w = 1120;
	const h = 560;
	const buyPoint = points[Math.min(3, points.length - 1)] ?? points[0];
	const lastPoint = points[points.length - 1] ?? points[0];
	const buyOpacity = phase === 'rise' ? interpolate(progress, [0.42, 0.55], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
	const lossOpacity = phase === 'loss' ? 1 : interpolate(progress, [0.72, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const semanticMoment = buildFomoSequence(narration)
		.filter((moment) => sceneProgress >= moment.startProgress && sceneProgress <= moment.endProgress)
		.sort((a, b) => b.startProgress - a.startProgress)[0];
	const semanticEventProgress = semanticMoment
		? Math.max(0, Math.min((sceneProgress - semanticMoment.startProgress) / Math.max(semanticMoment.endProgress - semanticMoment.startProgress, 0.001), 1))
		: progressBase;

	if (semanticMoment?.visualMode === 'peak_buy') {
		const focus = interpolate(semanticEventProgress, [0.06, 0.82], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 65% 36%, rgba(255,159,28,0.34), transparent 30%), linear-gradient(125deg, #070711, #17130d 58%, #080811)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.warning}} />
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 88, lineHeight: 0.9, maxWidth: 660}}>ENTRY GETS PULLED TO THE TOP</div>
				<svg viewBox={`0 0 ${w} ${h}`} style={{position: 'absolute', left: 610, top: 220, width: w, height: h, overflow: 'visible', opacity: 0.92}}>
					<path d={pathFromPoints(points, w, h, 0.58)} fill="none" stroke={COLORS.warning} strokeWidth={14} strokeLinecap="round" strokeLinejoin="round" />
					<circle cx={buyPoint.x * w} cy={buyPoint.y * h} r={34 + focus * 14} fill={COLORS.warning} />
				</svg>
				<div style={{position: 'absolute', left: 215, top: 360, width: 520, opacity: 0.56}}>
					<div style={{fontSize: 30, color: COLORS.text_secondary, fontWeight: 900}}>The chart is already loud</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 92, lineHeight: 0.88, color: COLORS.warning}}>FOMO</div>
				</div>
				<div style={{position: 'absolute', right: 235, top: 205, padding: '34px 42px', borderRadius: 8, background: 'rgba(20,13,7,0.96)', border: `4px solid ${COLORS.warning}`, boxShadow: `0 0 ${70 + focus * 80}px rgba(255,159,28,0.38)`, transform: `scale(${0.92 + focus * 0.12})`}}>
					<div style={{fontSize: 31, color: COLORS.text_secondary, fontWeight: 950}}>Buy point</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 112, lineHeight: 0.86, color: COLORS.warning}}>PEAK</div>
				</div>
			</AbsoluteFill>
		);
	}

	if (semanticMoment?.visualMode === 'crash_drop' || semanticMoment?.visualMode === 'loss_lock') {
		const drop = interpolate(semanticEventProgress, [0.08, 0.84], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 68% 56%, rgba(230,57,70,0.34), transparent 30%), linear-gradient(125deg, #070711, #180d10 58%, #080811)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.danger}} />
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 88, lineHeight: 0.9, maxWidth: 660}}>{semanticMoment.visualMode === 'loss_lock' ? 'LOSS GETS LOCKED' : 'THE DROP OWNS THE SCREEN'}</div>
				<svg viewBox={`0 0 ${w} ${h}`} style={{position: 'absolute', left: 580, top: 205, width: w, height: h, overflow: 'visible'}}>
					<path d={pathFromPoints(points, w, h, 1)} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={14} strokeLinecap="round" strokeLinejoin="round" />
					<path d={`M ${buyPoint.x * w} ${buyPoint.y * h} L ${lastPoint.x * w} ${lastPoint.y * h}`} fill="none" stroke={COLORS.danger} strokeWidth={20} strokeLinecap="round" opacity={drop} />
					<circle cx={lastPoint.x * w} cy={lastPoint.y * h} r={32 + drop * 12} fill={COLORS.danger} opacity={drop} />
				</svg>
				<div style={{position: 'absolute', right: 235, bottom: 165, padding: '34px 42px', borderRadius: 8, background: 'rgba(230,57,70,0.16)', border: `4px solid ${COLORS.danger}`, boxShadow: `0 0 ${70 + drop * 78}px rgba(230,57,70,0.36)`, transform: `scale(${0.92 + drop * 0.12})`}}>
					<div style={{fontSize: 31, color: COLORS.text_secondary, fontWeight: 950}}>After entry</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 108, lineHeight: 0.86, color: COLORS.danger}}>PANIC</div>
				</div>
			</AbsoluteFill>
		);
	}

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe}}>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.danger}} />
			<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 88, lineHeight: 0.9, maxWidth: 640, opacity: reveal}}>
				{phase === 'rise' ? 'HYPE RUNS FIRST' : phase === 'loss' ? 'LOSS GETS LOCKED' : 'THE CRASH ARRIVES'}
			</div>
			<div style={{position: 'absolute', left: 620, top: 210, width: w, height: h}}>
				<svg viewBox={`0 0 ${w} ${h}`} style={{width: '100%', height: '100%', overflow: 'visible'}}>
					<defs>
						<linearGradient id="fomo-line" x1="0" x2="1" y1="0" y2="0">
							<stop offset="0%" stopColor={COLORS.warning} />
							<stop offset="55%" stopColor={COLORS.warning} />
							<stop offset="100%" stopColor={COLORS.danger} />
						</linearGradient>
					</defs>
					{[0.25, 0.5, 0.75].map((line) => (
						<line key={line} x1={0} x2={w} y1={h * line} y2={h * line} stroke="rgba(255,255,255,0.08)" strokeWidth={2} />
					))}
					<path d={pathFromPoints(points, w, h, progress)} fill="none" stroke="url(#fomo-line)" strokeWidth={12} strokeLinecap="round" strokeLinejoin="round" />
					<circle cx={buyPoint.x * w} cy={buyPoint.y * h} r={22} fill={COLORS.warning} opacity={buyOpacity} />
					<circle cx={lastPoint.x * w} cy={lastPoint.y * h} r={28} fill={COLORS.danger} opacity={lossOpacity} />
				</svg>
				<div
					style={{
						position: 'absolute',
						left: buyPoint.x * w - 70,
						top: buyPoint.y * h - 106,
						padding: '12px 16px',
						borderRadius: 8,
						background: 'rgba(255,159,28,0.18)',
						border: `2px solid ${COLORS.warning}`,
						fontWeight: 900,
						opacity: buyOpacity,
					}}
				>
					BUY AT PEAK
				</div>
				<div
					style={{
						position: 'absolute',
						right: 0,
						bottom: 10,
						padding: '18px 22px',
						borderRadius: 8,
						background: 'rgba(230,57,70,0.16)',
						border: `2px solid ${COLORS.danger}`,
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: 48,
						lineHeight: 0.95,
						opacity: lossOpacity,
					}}
				>
					PANIC AFTER ENTRY
				</div>
			</div>
			<div style={{position: 'absolute', left: SPACING.safe, bottom: SPACING.safe, color: COLORS.text_secondary, fontSize: 30, fontWeight: 900}}>
				Real investing starts before the price chart gets loud.
			</div>
		</AbsoluteFill>
	);
};
