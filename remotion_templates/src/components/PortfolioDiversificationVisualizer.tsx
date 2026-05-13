import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, getBeatData, getBeatProgress} from './visualUtils';
import {TimedSentence, currentSceneProgress, firstKeywordIndex, narrationSentences, sceneNarrationText} from './narrationTiming';
import {activeCinematicEvent, eventPresence} from './cinematicEvents';
import {CinematicEvent} from '../types';

type Asset = {
	label?: string;
	allocation?: number;
	color?: string;
};

type PortfolioMoment = {
	assetIndex?: number;
	startProgress: number;
	endProgress: number;
	visualMode: 'single_bet' | 'asset_focus' | 'spread_world' | 'impact_absorption';
};

const defaultAssets: Asset[] = [
	{label: 'Equity', allocation: 45, color: COLORS.positive},
	{label: 'Debt', allocation: 25, color: COLORS.neutral},
	{label: 'FD', allocation: 15, color: COLORS.warning},
	{label: 'Gold', allocation: 10, color: '#B8A44C'},
	{label: 'Cash', allocation: 5, color: COLORS.text_secondary},
];

const keywordsForAsset = (label: string) => {
	const lowered = label.toLowerCase();
	const parts = lowered.split(/[^a-z0-9]+/).filter((item) => item.length > 1);
	const extra =
		lowered.includes('equity') ? ['stock', 'stocks', 'share', 'shares', 'market'] :
		lowered.includes('debt') ? ['bond', 'bonds', 'debt'] :
		lowered.includes('fd') ? ['fixed deposit', 'deposit', 'fd'] :
		lowered.includes('gold') ? ['gold'] :
		lowered.includes('cash') ? ['cash', 'liquid'] :
		[];
	return Array.from(new Set([lowered, ...parts, ...extra]));
};

const semanticModeForSentence = (sentence: string): PortfolioMoment['visualMode'] | null => {
	if (/fall|crash|impact|does\s+not\s+break|absorbs?|shock|drops?/i.test(sentence)) {
		return 'impact_absorption';
	}
	if (/spread|diversif|allocation|mix|across|basket/i.test(sentence)) {
		return 'spread_world';
	}
	if (/one\s+(stock|bet|asset)|concentrated|everything|single/i.test(sentence)) {
		return 'single_bet';
	}
	return null;
};

const buildPortfolioSequence = (narration: string, assets: Asset[]): PortfolioMoment[] => {
	const moments: PortfolioMoment[] = [];
	for (const sentence of narrationSentences(narration)) {
		const lowered = sentence.text.toLowerCase();
		const mentioned = assets
			.map((asset, index) => ({index, hit: firstKeywordIndex(lowered, keywordsForAsset(String(asset.label ?? `Asset ${index + 1}`)))}))
			.filter((item) => item.hit >= 0)
			.sort((a, b) => a.hit - b.hit);
		if (mentioned.length > 0) {
			const span = sentence.endProgress - sentence.startProgress;
			const slot = span / mentioned.length;
			mentioned.forEach((item, order) => {
				moments.push({
					assetIndex: item.index,
					startProgress: Math.max(0, sentence.startProgress + slot * order - 0.004),
					endProgress: Math.min(1, sentence.startProgress + slot * (order + 1) + 0.008),
					visualMode: 'asset_focus',
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

const momentFromCinematicEvent = (
	event: CinematicEvent | null,
	progress: number,
	assets: Asset[],
): PortfolioMoment | null => {
	if (!event) {
		return null;
	}
	const start = Number(event.start_progress ?? 0);
	const end = Number(event.end_progress ?? 0);
	if (progress < start || progress > end) {
		return null;
	}
	const mode = String(event.visual_mode ?? '');
	const label = String(event.label ?? event.entity_id ?? '').toLowerCase();
	const text = String(event.text ?? '').toLowerCase();
	const assetIndex = assets.findIndex((asset) => {
		const terms = keywordsForAsset(String(asset.label ?? ''));
		return terms.some((term) => term.length > 1 && (label.includes(term) || text.includes(term)));
	});
	if (/single_bet/.test(mode) || /one stock|one asset|single|concentrat/.test(label + text)) {
		return {startProgress: start, endProgress: end, visualMode: 'single_bet'};
	}
	if (/risk_spread/.test(mode) || /spread|diversif|portfolio/.test(label + text)) {
		return {startProgress: start, endProgress: end, visualMode: 'spread_world'};
	}
	if (/erosion|shock|fall|impact/.test(mode + label + text)) {
		return {startProgress: start, endProgress: end, visualMode: 'impact_absorption'};
	}
	if (assetIndex >= 0) {
		return {assetIndex, startProgress: start, endProgress: end, visualMode: 'asset_focus'};
	}
	return null;
};

export const PortfolioDiversificationVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'spread');
	const assets = (Array.isArray(data.assets) ? (data.assets as Asset[]) : defaultAssets).slice(0, 6);
	const narration = sceneNarrationText(scene);
	const sceneProgress = currentSceneProgress(scene, beat, frameWithinBeat, fps);
	const cinematicEvent = activeCinematicEvent(scene, beat, frameWithinBeat, fps);
	const progress = phase === 'concentrated' ? 0.2 : phase === 'impact' ? 1 : getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.8));
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const gridOpacity = phase === 'concentrated' ? 0 : interpolate(progress, [0.18, 0.62], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const shock = phase === 'impact' ? interpolate(frameWithinBeat % 30, [0, 15, 30], [0, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;
	const cinematicMoment = eventPresence(sceneProgress, cinematicEvent) > 0 ? momentFromCinematicEvent(cinematicEvent, sceneProgress, assets) : null;
	const semanticMoment = cinematicMoment ?? buildPortfolioSequence(narration, assets)
		.filter((moment) => sceneProgress >= moment.startProgress && sceneProgress <= moment.endProgress)
		.sort((a, b) => b.startProgress - a.startProgress)[0];
	const semanticEventProgress = semanticMoment
		? Math.max(0, Math.min((sceneProgress - semanticMoment.startProgress) / Math.max(semanticMoment.endProgress - semanticMoment.startProgress, 0.001), 1))
		: progress;
	const activeAsset = typeof semanticMoment?.assetIndex === 'number' ? assets[semanticMoment.assetIndex] : undefined;

	if (semanticMoment?.visualMode === 'single_bet') {
		const focus = interpolate(semanticEventProgress, [0.06, 0.82], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 50% 48%, rgba(230,57,70,0.3), transparent 30%), linear-gradient(135deg, #05070d, #170a10 58%, #05070d)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.danger}} />
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 92, lineHeight: 0.9, maxWidth: 760}}>ONE STOCK DECIDES EVERYTHING</div>
				<div style={{position: 'absolute', left: 675, top: 245, width: 570, height: 410, borderRadius: 8, border: `5px solid ${COLORS.danger}`, background: 'rgba(230,57,70,0.16)', boxShadow: `0 0 ${70 + focus * 86}px rgba(230,57,70,0.42)`, transform: `scale(${0.86 + focus * 0.16}) rotate(${-2 + focus * 2}deg)`, display: 'grid', placeItems: 'center', textAlign: 'center'}}>
					<div>
						<div style={{fontSize: 30, color: COLORS.text_secondary, fontWeight: 950}}>Concentration risk</div>
						<div style={{marginTop: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 124, lineHeight: 0.82, color: COLORS.danger}}>100%</div>
						<div style={{marginTop: 14, fontSize: 36, fontWeight: 950}}>one asset</div>
					</div>
				</div>
				<div style={{position: 'absolute', left: 200, bottom: 135, right: 200, height: 80, display: 'flex', gap: 18, justifyContent: 'center', opacity: 0.16}}>
					{assets.map((asset, index) => (
						<div key={`${asset.label}-${index}`} style={{width: 150, height: 62, borderRadius: 8, border: `1px solid ${asset.color ?? COLORS.stroke}`, background: 'rgba(255,255,255,0.045)'}} />
					))}
				</div>
			</AbsoluteFill>
		);
	}

	if (semanticMoment?.visualMode === 'asset_focus' && activeAsset) {
		const focus = interpolate(semanticEventProgress, [0.06, 0.82], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const color = activeAsset.color ?? COLORS.positive;

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -140, background: `radial-gradient(circle at 68% 42%, ${color}33, transparent 30%), linear-gradient(125deg, #05070d, #0d1117 58%, #05070d)`}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: color}} />
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 84, lineHeight: 0.92, maxWidth: 700}}>ONE ALLOCATION GETS THE FRAME</div>
				<div style={{position: 'absolute', left: 225, top: 330, width: 460, opacity: 0.5}}>
					<div style={{fontSize: 30, color: COLORS.text_secondary, fontWeight: 900}}>Portfolio context</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 84, lineHeight: 0.9}}>Diversified mix</div>
				</div>
				<div style={{position: 'absolute', right: 265, top: 250, width: 580, padding: '44px 52px', borderRadius: 8, border: `4px solid ${color}`, background: 'rgba(7,12,18,0.95)', boxShadow: `0 0 ${70 + focus * 82}px ${color}55`, transform: `scale(${0.9 + focus * 0.13})`}}>
					<div style={{fontSize: 31, color: COLORS.text_secondary, fontWeight: 950}}>Active asset</div>
					<div style={{marginTop: 12, fontSize: 56, fontWeight: 950}}>{activeAsset.label ?? 'Asset'}</div>
					<div style={{marginTop: 20, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 126, lineHeight: 0.84, color}}>{Math.round(Number(activeAsset.allocation ?? 0))}%</div>
				</div>
				<div style={{position: 'absolute', left: 340, bottom: 128, right: 340, display: 'flex', gap: 14, justifyContent: 'center'}}>
					{assets.map((asset, index) => (
						<div key={`${asset.label}-${index}`} style={{width: 165, height: 68, borderRadius: 8, border: `1px solid ${index === semanticMoment.assetIndex ? color : COLORS.stroke}`, background: index === semanticMoment.assetIndex ? `${color}20` : 'rgba(255,255,255,0.045)', opacity: index === semanticMoment.assetIndex ? 1 : 0.28, padding: '10px 13px'}}>
							<div style={{fontSize: 18, color: COLORS.text_secondary, fontWeight: 900}}>{asset.label ?? `Asset ${index + 1}`}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 26, color: index === semanticMoment.assetIndex ? color : COLORS.text_secondary}}>{Math.round(Number(asset.allocation ?? 0))}%</div>
						</div>
					))}
				</div>
			</AbsoluteFill>
		);
	}

	if (semanticMoment?.visualMode === 'impact_absorption') {
		const impact = interpolate(semanticEventProgress, [0.08, 0.84], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 34% 52%, rgba(230,57,70,0.28), transparent 28%), radial-gradient(circle at 72% 42%, rgba(46,196,182,0.18), transparent 29%), #05070d'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.positive}} />
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 84, lineHeight: 0.92, maxWidth: 720}}>ONE FALL DOES NOT BREAK ALL</div>
				<div style={{position: 'absolute', left: 230, top: 330, width: 430, height: 270, borderRadius: 8, border: `4px solid ${COLORS.danger}`, background: 'rgba(230,57,70,0.16)', boxShadow: `0 0 ${50 + impact * 70}px rgba(230,57,70,0.36)`, transform: `translateY(${impact * 70}px) rotate(${-impact * 5}deg)`}}>
					<div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', fontFamily: DISPLAY_FONT_FAMILY, fontSize: 72, lineHeight: 0.9, textAlign: 'center', color: COLORS.danger}}>ONE ASSET FALLS</div>
				</div>
				<div style={{position: 'absolute', right: 220, top: 230, width: 870, height: 560}}>
					{assets.slice(1).map((asset, index) => (
						<div key={`${asset.label}-${index}`} style={{position: 'absolute', left: (index % 3) * 285, top: Math.floor(index / 3) * 220, width: 230, height: 160, borderRadius: 8, border: `2px solid ${asset.color ?? COLORS.positive}`, background: COLORS.bg_surface, boxShadow: `0 0 36px ${(asset.color ?? COLORS.positive)}33`, opacity: interpolate(impact, [index * 0.08, index * 0.08 + 0.24], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}), padding: 22}}>
							<div style={{fontSize: 24, color: COLORS.text_secondary, fontWeight: 900}}>{asset.label ?? `Asset ${index + 2}`}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58, lineHeight: 0.92}}>{Math.round(Number(asset.allocation ?? 0))}%</div>
							<div style={{fontSize: 21, color: COLORS.positive, fontWeight: 900}}>holds</div>
						</div>
					))}
				</div>
			</AbsoluteFill>
		);
	}

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe}}>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.positive}} />
			<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 84, lineHeight: 0.92, maxWidth: 700, opacity: reveal}}>
				{phase === 'concentrated' ? 'ONE BET DECIDES EVERYTHING' : phase === 'impact' ? 'ONE FALL DOES NOT BREAK ALL' : 'RISK GETS SPREAD'}
			</div>
			<div style={{position: 'absolute', left: 190, bottom: 170, width: 500, height: 500}}>
				<div
					style={{
						position: 'absolute',
						left: 115,
						top: 115,
						width: 270,
						height: 270,
						borderRadius: 8,
						background: 'rgba(230,57,70,0.14)',
						border: `3px solid ${COLORS.danger}`,
						transform: `scale(${phase === 'concentrated' ? 1 : interpolate(progress, [0, 0.5], [1, 0.48], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}) rotate(${shock * -4}deg)`,
						opacity: phase === 'spread' ? 0.35 : 1,
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: 68,
						lineHeight: 0.9,
						textAlign: 'center',
					}}
				>
					ONE STOCK
				</div>
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, top: 230, width: 920, height: 650, opacity: gridOpacity}}>
				{assets.map((asset, index) => {
					const row = Math.floor(index / 3);
					const col = index % 3;
					const drop = phase === 'impact' && index === 0;
					return (
						<div
							key={`${asset.label}-${index}`}
							style={{
								position: 'absolute',
								left: col * 300,
								top: row * 260 + (drop ? 70 : 0),
								width: 240,
								height: 190,
								borderRadius: 8,
								background: drop ? 'rgba(230,57,70,0.16)' : COLORS.bg_surface,
								border: `2px solid ${drop ? COLORS.danger : asset.color ?? COLORS.positive}`,
								boxShadow: `0 0 42px ${drop ? COLORS.danger : asset.color ?? COLORS.positive}22`,
								padding: 24,
								transform: `translateY(${(1 - reveal) * 34}px)`,
							}}
						>
							<div style={{fontSize: 26, color: COLORS.text_secondary, fontWeight: 900}}>{asset.label ?? `Asset ${index + 1}`}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 70, lineHeight: 0.95}}>
								{Math.round(Number(asset.allocation ?? 0))}%
							</div>
							<div style={{fontSize: 22, color: drop ? COLORS.danger : COLORS.text_secondary, fontWeight: 900}}>
								{drop ? 'falls' : 'holds'}
							</div>
						</div>
					);
				})}
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, bottom: SPACING.safe, fontSize: 32, color: COLORS.text_secondary, fontWeight: 900}}>
				No single basket should decide the future.
			</div>
		</AbsoluteFill>
	);
};
