import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, TYPE_SCALE, getBeatData, getBeatProgress} from './visualUtils';
import {resolveVisualEvent} from './visualEvents';
import {TimedSentence, currentSceneProgress, narrationSentences, sceneNarrationText} from './narrationTiming';

type InflationItem = {
	name?: string;
	current?: number;
	future?: number;
};

type InflationMoment = {
	startProgress: number;
	endProgress: number;
	visualMode: 'today_anchor' | 'price_pressure' | 'basket_shrink' | 'future_loss';
};

const itemIcons = ['G', 'F', 'B', 'R', 'M'];

const asText = (value: unknown, fallback: string) =>
	typeof value === 'string' || typeof value === 'number' ? String(value) : fallback;

const buildUnits = (count: number, activeCount: number, color: string, progress: number) =>
	Array.from({length: count}).map((_, index) => {
		const active = index < activeCount;
		const delay = index * 0.035;
		const unitProgress = interpolate(progress, [delay, Math.min(delay + 0.28, 1)], [0, 1], {
			extrapolateLeft: 'clamp',
			extrapolateRight: 'clamp',
		});
		return (
			<div
				key={index}
				style={{
					width: 58,
					height: 58,
					borderRadius: 10,
					display: 'grid',
					placeItems: 'center',
					fontSize: 26,
					fontWeight: 900,
					color: active ? COLORS.text_primary : COLORS.text_tertiary,
					background: active ? `${color}33` : 'rgba(255,255,255,0.045)',
					border: active ? `1px solid ${color}AA` : `1px solid ${COLORS.stroke}`,
					transform: `scale(${active ? unitProgress : 0.86})`,
					opacity: active ? unitProgress : 0.28,
				}}
			>
				{itemIcons[index % itemIcons.length]}
			</div>
			);
		});

const semanticModeForSentence = (sentence: string): InflationMoment['visualMode'] | null => {
	if (/future|later|after\s+\d+|years?|tomorrow|long\s+term|buying\s+power\s+falls/i.test(sentence)) {
		return 'future_loss';
	}
	if (/basket|buys?|afford|items?|grocer|rent|fuel|food|shrinks?/i.test(sentence)) {
		return 'basket_shrink';
	}
	if (/inflation|prices?\s+(rise|rises|rising|increase)|rate|erosion|erodes?|silent/i.test(sentence)) {
		return 'price_pressure';
	}
	if (/today|same\s+(money|balance)|₹|rs/i.test(sentence)) {
		return 'today_anchor';
	}
	return null;
};

const momentForSentence = (sentence: TimedSentence, visualMode: InflationMoment['visualMode']): InflationMoment => ({
	startProgress: Math.max(0, sentence.startProgress - 0.004),
	endProgress: Math.min(1, sentence.endProgress + 0.01),
	visualMode,
});

const buildInflationSequence = (narration: string): InflationMoment[] =>
	narrationSentences(narration)
		.map((sentence) => {
			const visualMode = semanticModeForSentence(sentence.text);
			return visualMode ? momentForSentence(sentence, visualMode) : null;
		})
		.filter(Boolean) as InflationMoment[];

export const InflationErosionVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'erosion');
	const event = resolveVisualEvent(beat, scene, 'InflationErosionVisualizer');
	const narration = sceneNarrationText(scene);
	const sceneProgress = currentSceneProgress(scene, beat, frameWithinBeat, fps);
	const semanticMoment = buildInflationSequence(narration)
		.filter((moment) => sceneProgress >= moment.startProgress && sceneProgress <= moment.endProgress)
		.sort((a, b) => b.startProgress - a.startProgress)[0];
	const start = asText(data.start, '₹100');
	const end = asText(data.end, 'Less buying power');
	const rate = asText(data.rate, '');
	const years = asText(data.years, '');
	const rawItems = Array.isArray(data.items) ? (data.items as InflationItem[]) : [];
	const items = rawItems.length > 0 ? rawItems : [{name: 'Basket', current: 10, future: 5}];
	const rawProgress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.75)), 1);
	const progress = event.kind === 'today_anchor' ? 0 : event.kind === 'future_loss_reveal' ? 1 : rawProgress;
	const reveal = spring({frame: Math.min(frameWithinBeat, 20), fps, config: {stiffness: 190, damping: 18, mass: 0.8}, durationInFrames: 20});
	const melt = interpolate(progress, [0.18, 0.86], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const accent = COLORS.danger;
	const totalCurrent = items.reduce((sum, item) => sum + Number(item.current ?? 0), 0) || 10;
	const totalFuture = items.reduce((sum, item) => sum + Number(item.future ?? 0), 0) || Math.max(1, Math.round(totalCurrent * 0.55));
	const valueRatio = Math.max(0.12, Math.min(totalFuture / totalCurrent, 1));
	const activeFuture = Math.max(1, Math.round(totalCurrent * (1 - melt + valueRatio * melt)));
	const moneyScale = interpolate(melt, [0, 1], [1, 0.62]);
	const basketDominance = event.kind === 'basket_shrink' || event.kind === 'future_loss_reveal' ? 1.12 : 0.74;
	const moneyDominance = event.kind === 'today_anchor' ? 1.18 : event.kind === 'silent_erosion' ? 0.9 : 0.58;
	const dim = event.kind === 'future_loss_reveal' ? 0.32 : event.kind === 'silent_erosion' ? 0.14 : 0.04;
	const semanticEventProgress = semanticMoment
		? Math.max(0, Math.min((sceneProgress - semanticMoment.startProgress) / Math.max(semanticMoment.endProgress - semanticMoment.startProgress, 0.001), 1))
		: rawProgress;

	if (semanticMoment?.visualMode === 'price_pressure') {
		const pressure = interpolate(semanticEventProgress, [0.08, 0.86], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, padding: SPACING.safe, fontFamily: BODY_FONT_FAMILY, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 64% 44%, rgba(230,57,70,0.3), transparent 29%), linear-gradient(125deg, #070710, #15111c 58%, #080811)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: accent}} />
				<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 900, color: COLORS.text_secondary}}>Price pressure</div>
				<div style={{position: 'absolute', left: 220, top: 270, width: 560, zIndex: 3}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Same money</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 132, lineHeight: 0.86, transform: `scale(${1 - pressure * 0.18})`, transformOrigin: 'left center'}}>{start}</div>
				</div>
				<div style={{position: 'absolute', right: 240, top: 265, width: 560, height: 430, borderRadius: 8, border: `3px solid ${accent}`, background: 'rgba(230,57,70,0.1)', boxShadow: `0 0 ${60 + pressure * 80}px rgba(230,57,70,0.3)`, zIndex: 4}}>
					<div style={{position: 'absolute', left: 42, top: 38, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Inflation force</div>
					<div style={{position: 'absolute', left: 42, top: 112, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 116, lineHeight: 0.86, color: accent}}>{rate || 'Prices rise'}</div>
					<div style={{position: 'absolute', left: 42, right: 42, bottom: 62, height: 28, borderRadius: 999, background: 'rgba(255,255,255,0.09)', overflow: 'hidden'}}>
						<div style={{height: '100%', width: `${30 + pressure * 62}%`, background: accent}} />
					</div>
				</div>
			</AbsoluteFill>
		);
	}

	if (semanticMoment?.visualMode === 'future_loss') {
		const futureProgress = interpolate(semanticEventProgress, [0.08, 0.84], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, padding: SPACING.safe, fontFamily: BODY_FONT_FAMILY, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: 0, background: 'black', opacity: 0.34}} />
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 54% 48%, rgba(230,57,70,0.22), transparent 28%), linear-gradient(135deg, #05060b, #0c0b12 58%, #05060b)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: accent}} />
				<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 900, color: COLORS.text_secondary}}>Future buying power</div>
				<div style={{position: 'absolute', left: 0, right: 0, top: 280, textAlign: 'center'}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Later, the same money buys</div>
					<div style={{marginTop: 16, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 142, lineHeight: 0.84, color: accent, textShadow: `0 0 ${64 + futureProgress * 74}px rgba(230,57,70,0.45)`}}>{end}</div>
					<div style={{margin: '62px auto 0', display: 'grid', gridTemplateColumns: 'repeat(5, 58px)', gap: 20, width: 370, justifyContent: 'center'}}>
						{buildUnits(totalCurrent, Math.max(1, Math.round(totalFuture)), accent, futureProgress)}
					</div>
				</div>
			</AbsoluteFill>
		);
	}

	return (
		<AbsoluteFill
			style={{
				background: COLORS.bg_deep,
				color: COLORS.text_primary,
				padding: SPACING.safe,
				fontFamily: BODY_FONT_FAMILY,
				overflow: 'hidden',
			}}
		>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, background: 'black', opacity: dim}} />
			<div
				style={{
					position: 'absolute',
					inset: -140,
					background:
						'radial-gradient(circle at 72% 42%, rgba(230,57,70,0.24), transparent 30%), linear-gradient(125deg, #070710, #12121f 58%, #080811)',
				}}
			/>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: accent}} />
			<div style={{position: 'relative', zIndex: 2, fontSize: TYPE_SCALE.label.size, fontWeight: 900, color: COLORS.text_secondary}}>
				{event.kind === 'today_anchor'
					? 'Buying power today'
					: event.kind === 'future_loss_reveal'
						? 'Buying power later'
						: event.kind === 'basket_shrink'
							? 'Basket shrinks'
							: 'Silent erosion'}
			</div>

			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					top: 235,
					width: 560,
					opacity: moneyDominance,
					transform: `scale(${interpolate(reveal, [0, 1], [0.94, 1]) * moneyDominance})`,
					zIndex: 2,
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 800}}>Same balance</div>
				<div
					style={{
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: 126,
						lineHeight: 0.9,
						transform: `scale(${moneyScale}) translateY(${melt * 38}px)`,
						transformOrigin: 'left top',
						color: interpolate(melt, [0, 1], [0, 1]) > 0.55 ? COLORS.warning : COLORS.text_primary,
					}}
				>
					{start}
				</div>
				<div
					style={{
						marginTop: 26,
						width: 430,
						height: 18,
						borderRadius: 999,
						background: 'rgba(255,255,255,0.09)',
						overflow: 'hidden',
					}}
				>
					<div
						style={{
							height: '100%',
							width: `${Math.max(12, 100 - melt * (100 - valueRatio * 100))}%`,
							background: `linear-gradient(90deg, ${COLORS.warning}, ${accent})`,
							boxShadow: `0 0 26px ${accent}88`,
						}}
					/>
				</div>
				<div style={{marginTop: 18, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 800}}>
					{rate || (years ? `${years} years` : 'prices keep rising')}
				</div>
			</div>

			<div
				style={{
					position: 'absolute',
					right: SPACING.safe,
					top: 200,
					width: 840,
					height: 610,
					borderRadius: 8,
					border: `1px solid ${COLORS.stroke}`,
					background: 'rgba(255,255,255,0.055)',
					padding: 44,
					transform: `scale(${basketDominance}) translateX(${event.kind === 'future_loss_reveal' ? -70 : 0}px)`,
					transformOrigin: 'right center',
					zIndex: 2,
				}}
			>
				<div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
					<div>
						<div style={{fontSize: TYPE_SCALE.micro.size + 4, color: COLORS.text_secondary, fontWeight: 900}}>What the same money buys</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 62, lineHeight: 0.98}}>Basket shrinks</div>
					</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 70, color: accent}}>{end}</div>
				</div>
				<div style={{marginTop: 58, display: 'grid', gridTemplateColumns: 'repeat(5, 58px)', gap: 24}}>
					{buildUnits(totalCurrent, activeFuture, accent, progress)}
				</div>
				<div
					style={{
						position: 'absolute',
						left: 44,
						right: 44,
						bottom: 42,
						display: 'grid',
						gridTemplateColumns: '1fr 1fr',
						gap: 24,
					}}
				>
					<div style={{padding: 22, background: COLORS.bg_surface, border: `1px solid ${COLORS.stroke}`, borderRadius: 8}}>
						<div style={{fontSize: TYPE_SCALE.micro.size + 2, color: COLORS.text_secondary, fontWeight: 800}}>Today</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 54}}>{totalCurrent} units</div>
					</div>
					<div style={{padding: 22, background: 'rgba(230,57,70,0.12)', border: `1px solid ${accent}`, borderRadius: 8}}>
						<div style={{fontSize: TYPE_SCALE.micro.size + 2, color: COLORS.text_secondary, fontWeight: 800}}>After inflation</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 54, color: accent}}>{activeFuture} units</div>
					</div>
				</div>
			</div>

			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					bottom: SPACING.safe,
					fontFamily: DISPLAY_FONT_FAMILY,
					fontSize: 82,
					lineHeight: 0.92,
					color: accent,
					opacity: event.kind === 'today_anchor' ? 0 : interpolate(progress, [0.66, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
				}}
			>
				Same money. Less power.
			</div>
		</AbsoluteFill>
	);
};
