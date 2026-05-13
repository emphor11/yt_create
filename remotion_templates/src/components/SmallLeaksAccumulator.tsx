import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';
import {TimedSentence, currentSceneProgress, firstKeywordIndex, narrationSentences, sceneNarrationText} from './narrationTiming';

type Leak = {
	label?: string;
	amount?: number;
	value?: string;
};

type LeakMoment = {
	leakIndex?: number;
	startProgress: number;
	endProgress: number;
	visualMode: 'single_leak_focus' | 'repeat_pattern' | 'month_end_loss';
};

const defaultLeaks: Leak[] = [
	{label: 'Food apps', amount: 2400},
	{label: 'Subscriptions', amount: 1200},
	{label: 'Impulse buys', amount: 3500},
	{label: 'Convenience fees', amount: 900},
];

const keywordsForLeak = (label: string) => {
	const lowered = label.toLowerCase();
	const parts = lowered.split(/[^a-z0-9]+/).filter((item) => item.length > 2);
	const extra =
		lowered.includes('food') ? ['delivery', 'zomato', 'swiggy', 'apps'] :
		lowered.includes('subscription') ? ['subscription', 'subscriptions', 'netflix', 'ott'] :
		lowered.includes('impulse') || lowered.includes('shopping') ? ['shopping', 'impulse', 'buy', 'buys'] :
		lowered.includes('convenience') ? ['fee', 'fees', 'convenience'] :
		[];
	return Array.from(new Set([lowered, ...parts, ...extra]));
};

const semanticModeForSentence = (sentence: string): LeakMoment['visualMode'] | null => {
	if (/month\s+end|monthly|total|adds?\s+up|expensive|loss|gone/i.test(sentence)) {
		return 'month_end_loss';
	}
	if (/repeat|again|every\s+day|habit|pattern|keeps?/i.test(sentence)) {
		return 'repeat_pattern';
	}
	return null;
};

const buildLeakSequence = (narration: string, leaks: Leak[]): LeakMoment[] => {
	const moments: LeakMoment[] = [];
	for (const sentence of narrationSentences(narration)) {
		const lowered = sentence.text.toLowerCase();
		const mentioned = leaks
			.map((leak, index) => ({index, hit: firstKeywordIndex(lowered, keywordsForLeak(String(leak.label ?? `Leak ${index + 1}`)))}))
			.filter((item) => item.hit >= 0)
			.sort((a, b) => a.hit - b.hit);
		if (mentioned.length > 0) {
			const span = sentence.endProgress - sentence.startProgress;
			const slot = span / mentioned.length;
			mentioned.forEach((item, order) => {
				moments.push({
					leakIndex: item.index,
					startProgress: Math.max(0, sentence.startProgress + slot * order - 0.004),
					endProgress: Math.min(1, sentence.startProgress + slot * (order + 1) + 0.008),
					visualMode: 'single_leak_focus',
				});
			});
			continue;
		}
		const mode = semanticModeForSentence(sentence.text);
		if (mode) {
			moments.push({
				startProgress: Math.max(0, sentence.startProgress - 0.004),
				endProgress: Math.min(1, sentence.endProgress + 0.008),
				visualMode: mode,
			});
		}
	}
	return moments.sort((a, b) => a.startProgress - b.startProgress);
};

export const SmallLeaksAccumulator: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'repeat');
	const leaks = (Array.isArray(data.leaks) ? (data.leaks as Leak[]) : defaultLeaks).slice(0, 5);
	const narration = sceneNarrationText(scene);
	const sceneProgress = currentSceneProgress(scene, beat, frameWithinBeat, fps);
	const monthlyLoss = Number(data.monthly_loss ?? leaks.reduce((sum, leak) => sum + Number(leak.amount ?? 0), 0));
	const progress = phase === 'first_leak' ? 0.25 : phase === 'month_end' ? 1 : getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.8));
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const drainHeight = interpolate(progress, [0, 1], [80, 430], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const semanticMoment = buildLeakSequence(narration, leaks)
		.filter((moment) => sceneProgress >= moment.startProgress && sceneProgress <= moment.endProgress)
		.sort((a, b) => b.startProgress - a.startProgress)[0];
	const semanticEventProgress = semanticMoment
		? Math.max(0, Math.min((sceneProgress - semanticMoment.startProgress) / Math.max(semanticMoment.endProgress - semanticMoment.startProgress, 0.001), 1))
		: progress;
	const activeLeak = typeof semanticMoment?.leakIndex === 'number' ? leaks[semanticMoment.leakIndex] : undefined;

	if (semanticMoment?.visualMode === 'single_leak_focus' && activeLeak) {
		const focus = interpolate(semanticEventProgress, [0.06, 0.82], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 68% 42%, rgba(255,159,28,0.3), transparent 30%), linear-gradient(125deg, #070711, #161116 58%, #080811)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.warning}} />
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 82, lineHeight: 0.9, maxWidth: 640}}>ONE LEAK GETS ATTENTION</div>
				<div style={{position: 'absolute', left: 230, top: 330, width: 460, opacity: 0.48}}>
					<div style={{fontSize: 30, color: COLORS.text_secondary, fontWeight: 900}}>Monthly pressure context</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 92, lineHeight: 0.88, color: COLORS.warning}}>{formatIndianRupee(monthlyLoss)}</div>
				</div>
				<div style={{position: 'absolute', right: 260, top: 250, width: 610, padding: '44px 52px', borderRadius: 8, border: `4px solid ${COLORS.warning}`, background: 'rgba(20,13,7,0.95)', boxShadow: `0 0 ${70 + focus * 82}px rgba(255,159,28,0.38)`, transform: `scale(${0.9 + focus * 0.13})`}}>
					<div style={{fontSize: 31, color: COLORS.text_secondary, fontWeight: 950}}>This small spend</div>
					<div style={{marginTop: 12, fontSize: 48, fontWeight: 950}}>{activeLeak.label ?? 'Small leak'}</div>
					<div style={{marginTop: 20, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 126, lineHeight: 0.84, color: COLORS.warning}}>{activeLeak.value ?? formatIndianRupee(Number(activeLeak.amount ?? 0))}</div>
				</div>
				<div style={{position: 'absolute', left: 330, bottom: 132, right: 330, display: 'flex', gap: 16, justifyContent: 'center'}}>
					{leaks.map((leak, index) => (
						<div key={`${leak.label}-${index}`} style={{width: 195, height: 64, borderRadius: 8, border: `1px solid ${index === semanticMoment.leakIndex ? COLORS.warning : COLORS.stroke}`, background: index === semanticMoment.leakIndex ? 'rgba(255,159,28,0.16)' : 'rgba(255,255,255,0.045)', opacity: index === semanticMoment.leakIndex ? 1 : 0.3, padding: '10px 13px'}}>
							<div style={{fontSize: 18, color: COLORS.text_secondary, fontWeight: 900}}>{leak.label ?? `Leak ${index + 1}`}</div>
						</div>
					))}
				</div>
			</AbsoluteFill>
		);
	}

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe}}>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.warning}} />
			<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 86, lineHeight: 0.92, maxWidth: 700, opacity: reveal}}>
				{phase === 'first_leak' ? 'ONE SMALL SPEND' : phase === 'month_end' ? 'THE PATTERN GETS EXPENSIVE' : 'SMALL LEAKS REPEAT'}
			</div>
			<div style={{position: 'absolute', left: 210, bottom: 160, width: 520, height: 540}}>
				<div
					style={{
						position: 'absolute',
						left: 110,
						bottom: 0,
						width: 300,
						height: 430,
						borderRadius: 8,
						background: COLORS.bg_surface,
						border: `2px solid ${COLORS.stroke}`,
						overflow: 'hidden',
					}}
				>
					<div
						style={{
							position: 'absolute',
							left: 0,
							right: 0,
							bottom: 0,
							height: drainHeight,
							background: 'linear-gradient(180deg, rgba(255,159,28,0.25), rgba(230,57,70,0.92))',
						}}
					/>
				</div>
				<div style={{position: 'absolute', left: 0, top: 0, fontSize: 28, color: COLORS.text_secondary, fontWeight: 900}}>Monthly pressure</div>
				<div style={{position: 'absolute', left: 0, top: 44, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 86, lineHeight: 0.9, color: COLORS.warning}}>
					{formatIndianRupee(monthlyLoss)}
				</div>
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, top: 190, width: 820, height: 650}}>
				{leaks.map((leak, index) => {
					const itemProgress = interpolate(progress, [index / leaks.length, (index + 0.7) / leaks.length], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					});
					return (
						<div
							key={`${leak.label}-${index}`}
							style={{
								position: 'absolute',
								left: (index % 2) * 380,
								top: Math.floor(index / 2) * 170,
								width: 330,
								height: 120,
								borderRadius: 8,
								background: 'rgba(255,159,28,0.11)',
								border: `2px solid ${COLORS.warning}`,
								padding: '22px 24px',
								opacity: itemProgress,
								transform: `translateX(${(1 - itemProgress) * 80}px)`,
							}}
						>
							<div style={{fontSize: 25, color: COLORS.text_secondary, fontWeight: 900}}>{leak.label ?? `Leak ${index + 1}`}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 56, lineHeight: 0.94}}>
								{leak.value ?? formatIndianRupee(Number(leak.amount ?? 0))}
							</div>
						</div>
					);
				})}
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, bottom: SPACING.safe, color: COLORS.text_secondary, fontSize: 30, fontWeight: 900}}>
				The danger is repetition, not one purchase.
			</div>
		</AbsoluteFill>
	);
};
