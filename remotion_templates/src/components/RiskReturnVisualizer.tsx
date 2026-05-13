import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, getBeatData, getBeatProgress} from './visualUtils';
import {currentSceneProgress, firstKeywordIndex, narrationSentences, sceneNarrationText} from './narrationTiming';

type RiskMoment = {
	mode: 'fd_anchor' | 'equity_growth' | 'volatility_price' | 'chosen_risk';
	startProgress: number;
	endProgress: number;
};

const modeKeywords: Record<RiskMoment['mode'], string[]> = {
	fd_anchor: ['fd', 'fixed deposit', 'safe', 'safety', 'low risk', 'calm', 'guaranteed'],
	equity_growth: ['equity', 'stock', 'market', 'growth', 'higher return', 'upside', 'long term'],
	volatility_price: ['risk', 'volatile', 'volatility', 'fall', 'down', 'drop', 'panic', 'uncomfortable'],
	chosen_risk: ['choose', 'understand', 'stay', 'right risk', 'hold', 'plan', 'balance'],
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const buildRiskSequence = (narration: string): RiskMoment[] => {
	const sentences = narrationSentences(narration);
	const moments: RiskMoment[] = [];
	for (const sentence of sentences) {
		const hits = (Object.keys(modeKeywords) as RiskMoment['mode'][]).map((mode) => ({
			mode,
			hit: firstKeywordIndex(sentence.text, modeKeywords[mode]),
		})).filter((item) => item.hit >= 0).sort((a, b) => a.hit - b.hit);
		if (hits.length === 0) {
			continue;
		}
		const span = sentence.endProgress - sentence.startProgress;
		hits.forEach((hit, index) => {
			moments.push({
				mode: hit.mode,
				startProgress: clamp(sentence.startProgress + (span * index) / hits.length - 0.006, 0, 1),
				endProgress: clamp(sentence.startProgress + (span * (index + 1)) / hits.length + 0.014, 0, 1),
			});
		});
	}
	if (moments.length > 0) {
		return moments;
	}
	return [
		{mode: 'fd_anchor', startProgress: 0, endProgress: 0.26},
		{mode: 'equity_growth', startProgress: 0.23, endProgress: 0.52},
		{mode: 'volatility_price', startProgress: 0.49, endProgress: 0.76},
		{mode: 'chosen_risk', startProgress: 0.73, endProgress: 1},
	];
};

const activeMode = (progress: number, narration: string, fallback: RiskMoment['mode']): RiskMoment['mode'] => {
	const sequence = buildRiskSequence(narration);
	const active = sequence.find((moment) => progress >= moment.startProgress && progress <= moment.endProgress);
	if (active) {
		return active.mode;
	}
	const previousMoments = sequence.filter((moment) => moment.startProgress <= progress);
	const previous = previousMoments[previousMoments.length - 1];
	return previous?.mode ?? fallback;
};

const useEntrance = (frameWithinBeat: number, fps: number) => spring({
	frame: frameWithinBeat,
	fps,
	config: {damping: 22, stiffness: 140, mass: 0.9},
});

const Pill: React.FC<{label: string; value: string; color: string; active?: boolean}> = ({label, value, color, active}) => (
	<div
		style={{
			border: `2px solid ${active ? color : 'rgba(255,255,255,0.14)'}`,
			background: active ? `${color}22` : 'rgba(255,255,255,0.05)',
			borderRadius: 999,
			padding: '16px 24px',
			color: COLORS.text_primary,
			fontFamily: BODY_FONT_FAMILY,
			fontSize: 28,
			fontWeight: 800,
			opacity: active ? 1 : 0.42,
			boxShadow: active ? `0 0 36px ${color}44` : 'none',
		}}
	>
		<span style={{color, marginRight: 14}}>{value}</span>{label}
	</div>
);

export const RiskReturnVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const narration = sceneNarrationText(scene);
	const sceneProgress = scene ? currentSceneProgress(scene, beat, frameWithinBeat, fps) : getBeatProgress(frameWithinBeat, durationFrames);
	const fallback = String(beat.beat_phase ?? data.active_phase ?? 'fd_anchor') as RiskMoment['mode'];
	const mode = activeMode(sceneProgress, narration, fallback);
	const enter = useEntrance(frameWithinBeat, fps);
	const safeRate = String(data.safe_rate ?? '6%');
	const growthRate = String(data.growth_rate ?? '12%');
	const safeAsset = String(data.safe_asset ?? 'FD');
	const growthAsset = String(data.growth_asset ?? 'Equity');

	const fdActive = mode === 'fd_anchor';
	const equityActive = mode === 'equity_growth';
	const volatilityActive = mode === 'volatility_price';
	const decisionActive = mode === 'chosen_risk';
	const pulse = interpolate(Math.sin(frameWithinBeat / 6), [-1, 1], [0.92, 1.08]);
	const shake = volatilityActive ? Math.sin(frameWithinBeat * 0.9) * 13 : 0;

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, overflow: 'hidden'}}>
			<style>{FONT_FACES}</style>
			<AbsoluteFill
				style={{
					background: fdActive
						? 'radial-gradient(circle at 50% 48%, rgba(46,196,182,0.22), rgba(10,10,20,0.96) 58%)'
						: equityActive
							? 'radial-gradient(circle at 70% 34%, rgba(46,196,182,0.28), rgba(10,10,20,0.96) 62%)'
							: volatilityActive
								? 'radial-gradient(circle at 38% 42%, rgba(230,57,70,0.24), rgba(10,10,20,0.98) 60%)'
								: 'radial-gradient(circle at 50% 46%, rgba(67,97,238,0.28), rgba(10,10,20,0.96) 64%)',
					transition: 'background 300ms ease',
				}}
			/>
			<div style={{position: 'absolute', inset: 94, fontFamily: BODY_FONT_FAMILY, color: COLORS.text_primary}}>
				<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start'}}>
					<Pill label={safeAsset} value={safeRate} color={COLORS.teal} active={fdActive} />
					<Pill label={growthAsset} value={growthRate} color={COLORS.orange} active={equityActive || volatilityActive} />
				</div>

				{fdActive && (
					<div style={{position: 'absolute', left: 360, top: 210, width: 560, textAlign: 'center', transform: `scale(${0.92 + enter * 0.08})`}}>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 132, lineHeight: 0.9, color: COLORS.teal}}>CALM</div>
						<div style={{marginTop: 26, fontSize: 34, color: COLORS.muted}}>low risk also means limited upside</div>
						<div style={{margin: '46px auto 0', width: 380, height: 24, borderRadius: 999, background: 'rgba(46,196,182,0.22)', overflow: 'hidden'}}>
							<div style={{width: '42%', height: '100%', background: COLORS.teal, borderRadius: 999}} />
						</div>
					</div>
				)}

				{equityActive && (
					<div style={{position: 'absolute', left: 210, top: 170, width: 850, height: 430, transform: `translateY(${(1 - enter) * 34}px)`}}>
						<div style={{position: 'absolute', left: 0, bottom: 80, width: 760, height: 5, background: 'rgba(255,255,255,0.16)'}} />
						{[0, 1, 2, 3, 4].map((index) => (
							<div
								key={index}
								style={{
									position: 'absolute',
									left: 64 + index * 142,
									bottom: 84,
									width: 78,
									height: 80 + index * 42,
									borderRadius: 16,
									background: index === 4 ? COLORS.orange : 'rgba(46,196,182,0.56)',
									boxShadow: index === 4 ? `0 0 44px ${COLORS.orange}66` : 'none',
									transform: `scaleY(${enter})`,
									transformOrigin: 'bottom',
								}}
							/>
						))}
						<div style={{position: 'absolute', right: 0, top: 20, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 116, lineHeight: 0.88}}>
							UPSIDE
						</div>
						<div style={{position: 'absolute', right: 0, top: 244, fontSize: 32, color: COLORS.muted, width: 340}}>
							growth demands time and emotional capacity
						</div>
					</div>
				)}

				{volatilityActive && (
					<div style={{position: 'absolute', left: 185 + shake, top: 135, width: 900, height: 520}}>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 102, color: COLORS.red, transform: `scale(${pulse})`}}>VOLATILITY</div>
						<svg width="900" height="340" style={{position: 'absolute', top: 132, left: 0, overflow: 'visible'}}>
							<polyline
								points="20,120 150,64 250,158 360,82 470,220 610,118 735,252 880,178"
								fill="none"
								stroke={COLORS.red}
								strokeWidth="12"
								strokeLinecap="round"
								strokeLinejoin="round"
							/>
							<polyline
								points="20,120 150,64 250,158 360,82 470,220 610,118 735,252 880,178"
								fill="none"
								stroke="rgba(255,255,255,0.18)"
								strokeWidth="28"
								strokeLinecap="round"
								strokeLinejoin="round"
							/>
						</svg>
						<div style={{position: 'absolute', right: 24, bottom: 20, fontSize: 34, color: COLORS.text_primary}}>this is the price of higher returns</div>
					</div>
				)}

				{decisionActive && (
					<div style={{position: 'absolute', inset: '110px 150px', display: 'grid', placeItems: 'center', textAlign: 'center'}}>
						<div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 118, lineHeight: 0.92, color: COLORS.text_primary}}>CHOOSE THE RISK</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 92, lineHeight: 0.92, color: COLORS.blue}}>YOU CAN STAY WITH</div>
							<div style={{margin: '42px auto 0', width: 620, height: 18, borderRadius: 999, background: 'rgba(255,255,255,0.16)', overflow: 'hidden'}}>
								<div style={{width: `${58 + enter * 28}%`, height: '100%', borderRadius: 999, background: `linear-gradient(90deg, ${COLORS.teal}, ${COLORS.orange})`}} />
							</div>
						</div>
					</div>
				)}
			</div>
		</AbsoluteFill>
	);
};
