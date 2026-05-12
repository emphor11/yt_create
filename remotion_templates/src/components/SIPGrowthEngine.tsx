import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';
import {ResolvedVisualEvent, resolveVisualEvent} from './visualEvents';

type VisualState = {
	state_type?: string;
	emotional_posture?: string;
	composition_density?: string;
	framing?: string;
	transition_behavior?: string;
	frame_window?: {start_frame?: number; end_frame?: number};
	derived_from_action?: string;
	overlap_group?: string;
	source_action_ids?: string[];
	source_beat_indices?: number[];
};

type Shot = {
	shot_type?: string;
	focus_target?: string;
	framing_profile?: string;
	composition_emphasis?: string;
	attention_weight?: number;
	start_frame?: number;
	end_frame?: number;
	composition_window?: {start_frame?: number; end_frame?: number};
	derived_from_action?: string;
	derived_from_state?: string;
	source_action_ids?: string[];
	source_beat_indices?: number[];
};

type GrowthLayout = {
	profile: 'default' | 'optimistic_seed' | 'growth_acceleration' | 'layered_growth' | 'awe_reveal';
	seedX: number;
	seedY: number;
	seedScale: number;
	seedOpacity: number;
	barsLeft: number;
	barsBottom: number;
	barsHeight: number;
	barGap: number;
	investedWidth: number;
	corpusWidth: number;
	investedScale: number;
	corpusScale: number;
	investedOpacity: number;
	corpusOpacity: number;
	hierarchyContrast: number;
	glowIntensity: number;
	upwardShift: number;
	corpusDominance: number;
	motionVelocity: number;
	negativeSpace: number;
	rewardIsolation: number;
	returnsX: number;
	returnsY: number;
	returnsScale: number;
	ratioX: number;
	ratioY: number;
	ratioScale: number;
	backgroundLift: number;
};

const DEFAULT_LAYOUT: GrowthLayout = {
	profile: 'default',
	seedX: SPACING.safe,
	seedY: 220,
	seedScale: 1,
	seedOpacity: 1,
	barsLeft: 780,
	barsBottom: 190,
	barsHeight: 620,
	barGap: 120,
	investedWidth: 280,
	corpusWidth: 340,
	investedScale: 1,
	corpusScale: 1,
	investedOpacity: 1,
	corpusOpacity: 1,
	hierarchyContrast: 1,
	glowIntensity: 0.18,
	upwardShift: 0,
	corpusDominance: 1,
	motionVelocity: 1,
	negativeSpace: 0,
	rewardIsolation: 0,
	returnsX: SPACING.safe,
	returnsY: 790,
	returnsScale: 1,
	ratioX: SPACING.safe,
	ratioY: 754,
	ratioScale: 1,
	backgroundLift: 0,
};

const STATE_LAYOUTS: Record<string, GrowthLayout> = {
	optimistic_seed: {
		...DEFAULT_LAYOUT,
		profile: 'optimistic_seed',
		seedX: 210,
		seedY: 300,
		seedScale: 0.92,
		barsLeft: 880,
		barsBottom: 160,
		barGap: 150,
		investedWidth: 230,
		corpusWidth: 270,
		investedScale: 0.78,
		corpusScale: 0.72,
		corpusOpacity: 0.72,
		glowIntensity: 0.08,
		motionVelocity: 0.72,
		negativeSpace: 0.28,
		ratioScale: 0.72,
		returnsScale: 0.76,
	},
	growth_acceleration: {
		...DEFAULT_LAYOUT,
		profile: 'growth_acceleration',
		seedX: 150,
		seedY: 196,
		seedScale: 0.94,
		barsLeft: 770,
		barsBottom: 230,
		barGap: 92,
		investedScale: 0.92,
		corpusScale: 1.2,
		corpusWidth: 380,
		hierarchyContrast: 1.18,
		glowIntensity: 0.34,
		upwardShift: 72,
		corpusDominance: 1.18,
		motionVelocity: 1.34,
		ratioScale: 1.08,
		returnsScale: 1.04,
		backgroundLift: 0.18,
	},
	layered_growth: {
		...DEFAULT_LAYOUT,
		profile: 'layered_growth',
		seedX: 130,
		seedY: 170,
		seedScale: 0.82,
		seedOpacity: 0.72,
		barsLeft: 650,
		barsBottom: 275,
		barsHeight: 690,
		barGap: 64,
		investedWidth: 230,
		corpusWidth: 460,
		investedScale: 0.8,
		corpusScale: 1.48,
		investedOpacity: 0.7,
		hierarchyContrast: 1.48,
		glowIntensity: 0.52,
		upwardShift: 132,
		corpusDominance: 1.55,
		motionVelocity: 1.62,
		negativeSpace: -0.08,
		ratioX: 160,
		ratioY: 670,
		ratioScale: 1.28,
		returnsX: 142,
		returnsY: 864,
		returnsScale: 1.12,
		backgroundLift: 0.28,
	},
	awe_reveal: {
		...DEFAULT_LAYOUT,
		profile: 'awe_reveal',
		seedX: 126,
		seedY: 240,
		seedScale: 0.72,
		seedOpacity: 0.28,
		barsLeft: 980,
		barsBottom: 290,
		barsHeight: 700,
		barGap: 190,
		investedWidth: 210,
		corpusWidth: 520,
		investedScale: 0.62,
		corpusScale: 1.62,
		investedOpacity: 0.22,
		hierarchyContrast: 1.7,
		glowIntensity: 0.64,
		upwardShift: 92,
		corpusDominance: 1.72,
		motionVelocity: 0.82,
		negativeSpace: 0.38,
		rewardIsolation: 1,
		returnsX: 190,
		returnsY: 790,
		returnsScale: 1.32,
		ratioX: 190,
		ratioY: 650,
		ratioScale: 1.45,
		backgroundLift: 0.2,
	},
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
	Boolean(value && typeof value === 'object' && !Array.isArray(value));

const toVisualState = (value: unknown): VisualState | null =>
	isRecord(value) ? (value as VisualState) : null;

const toShot = (value: unknown): Shot | null =>
	isRecord(value) ? (value as Shot) : null;

const overlapsBeat = (state: VisualState, beat: BeatComponentProps['beat']) => {
	const start = Number(state.frame_window?.start_frame ?? 0);
	const end = Number(state.frame_window?.end_frame ?? 0);
	const beatStart = Math.floor(Number(beat.start_time ?? 0) * 30);
	const beatEnd = Math.floor(Number(beat.end_time ?? 0) * 30);
	return start < beatEnd && end > beatStart;
};

const resolveVisualState = (
	beat: BeatComponentProps['beat'],
	scene: BeatComponentProps['scene'],
): VisualState | null => {
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const direct = toVisualState((beat as BeatComponentProps['beat'] & {visual_state?: unknown}).visual_state);
	if (direct?.state_type) {
		return direct;
	}
	const dataState = toVisualState(data.visual_state);
	if (dataState?.state_type) {
		return dataState;
	}
	const sequence = (scene as unknown as {visual_state_sequence?: {states?: unknown[]}} | undefined)?.visual_state_sequence;
	const states = Array.isArray(sequence?.states) ? sequence.states.map(toVisualState).filter(Boolean) as VisualState[] : [];
	if (!states.length) {
		return null;
	}
	const action = isRecord(data.active_action) ? data.active_action : {};
	const actionId = String(action.id ?? '');
	const actionName = String(action.action ?? '');
	const sequenceIndex = Number(action.sequence_index);
	return (
		states.find((state) => actionId && Array.isArray(state.source_action_ids) && state.source_action_ids.includes(actionId)) ??
		states.find((state) => Number.isFinite(sequenceIndex) && Array.isArray(state.source_beat_indices) && state.source_beat_indices.includes(sequenceIndex)) ??
		states.find((state) => actionName && state.derived_from_action === actionName && overlapsBeat(state, beat)) ??
		states.find((state) => overlapsBeat(state, beat)) ??
		null
	);
};

const overlapsShot = (shot: Shot, beat: BeatComponentProps['beat']) => {
	const start = Number(shot.start_frame ?? shot.composition_window?.start_frame ?? 0);
	const end = Number(shot.end_frame ?? shot.composition_window?.end_frame ?? 0);
	const beatStart = Math.floor(Number(beat.start_time ?? 0) * 30);
	const beatEnd = Math.floor(Number(beat.end_time ?? 0) * 30);
	return start < beatEnd && end > beatStart;
};

const resolveShot = (
	beat: BeatComponentProps['beat'],
	scene: BeatComponentProps['scene'],
): Shot | null => {
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const direct = toShot((beat as BeatComponentProps['beat'] & {active_shot?: unknown}).active_shot);
	if (direct?.shot_type) {
		return direct;
	}
	const dataShot = toShot(data.active_shot);
	if (dataShot?.shot_type) {
		return dataShot;
	}
	const sequence = (scene as unknown as {shot_sequence?: {shots?: unknown[]}} | undefined)?.shot_sequence;
	const shots = Array.isArray(sequence?.shots) ? sequence.shots.map(toShot).filter(Boolean) as Shot[] : [];
	if (!shots.length) {
		return null;
	}
	const action = isRecord(data.active_action) ? data.active_action : {};
	const actionId = String(action.id ?? '');
	const actionName = String(action.action ?? '');
	const sequenceIndex = Number(action.sequence_index);
	return (
		shots.find((shot) => actionId && Array.isArray(shot.source_action_ids) && shot.source_action_ids.includes(actionId)) ??
		shots.find((shot) => Number.isFinite(sequenceIndex) && Array.isArray(shot.source_beat_indices) && shot.source_beat_indices.includes(sequenceIndex)) ??
		shots.find((shot) => actionName && shot.derived_from_action === actionName && overlapsShot(shot, beat)) ??
		shots.find((shot) => overlapsShot(shot, beat)) ??
		null
	);
};

const layoutForState = (visualState: VisualState | null): GrowthLayout => {
	const stateType = String(visualState?.state_type ?? '');
	const base = STATE_LAYOUTS[stateType] ?? DEFAULT_LAYOUT;
	const density = String(visualState?.composition_density ?? '');
	const framing = String(visualState?.framing ?? '');
	const transition = String(visualState?.transition_behavior ?? '');
	return {
		...base,
		barGap: density === 'high' ? base.barGap * 0.84 : density === 'minimal' ? base.barGap * 1.18 : base.barGap,
		corpusScale: density === 'high' ? base.corpusScale * 1.08 : base.corpusScale,
		investedOpacity: density === 'minimal' ? base.investedOpacity * 0.72 : base.investedOpacity,
		glowIntensity: density === 'high' ? Math.min(0.8, base.glowIntensity + 0.08) : base.glowIntensity,
		corpusWidth: framing === 'hero' ? base.corpusWidth + 70 : framing === 'layered' ? base.corpusWidth + 36 : base.corpusWidth,
		rewardIsolation: framing === 'hero' ? Math.max(base.rewardIsolation, 0.78) : base.rewardIsolation,
		motionVelocity: transition === 'slow_reveal' ? base.motionVelocity * 0.78 : transition === 'acceleration_shift' ? base.motionVelocity * 1.12 : base.motionVelocity,
		corpusDominance: transition === 'layer_stack' ? base.corpusDominance * 1.08 : base.corpusDominance,
	};
};

const layoutForShot = (base: GrowthLayout, shot: Shot | null): GrowthLayout => {
	const shotType = String(shot?.shot_type ?? '');
	const attention = Math.max(0.4, Math.min(Number(shot?.attention_weight ?? 0.65), 1));
	if (shotType === 'wide_context') {
		return {
			...base,
			seedScale: base.seedScale * 1.05,
			barGap: base.barGap * 1.08,
			corpusScale: base.corpusScale * 0.94,
			glowIntensity: base.glowIntensity * 0.82,
			negativeSpace: base.negativeSpace + 0.08 * attention,
			motionVelocity: base.motionVelocity * 0.92,
		};
	}
	if (shotType === 'upward_momentum') {
		return {
			...base,
			barsBottom: base.barsBottom + 30 * attention,
			upwardShift: base.upwardShift + 52 * attention,
			corpusScale: base.corpusScale * (1 + 0.12 * attention),
			corpusDominance: base.corpusDominance * (1 + 0.1 * attention),
			glowIntensity: Math.min(0.82, base.glowIntensity + 0.12 * attention),
			motionVelocity: base.motionVelocity * 1.14,
			ratioScale: base.ratioScale * (1 + 0.08 * attention),
		};
	}
	if (shotType === 'focused_growth') {
		return {
			...base,
			barGap: base.barGap * 0.82,
			investedOpacity: base.investedOpacity * 0.72,
			corpusWidth: base.corpusWidth + 54 * attention,
			corpusScale: base.corpusScale * (1 + 0.16 * attention),
			hierarchyContrast: base.hierarchyContrast * (1 + 0.1 * attention),
			corpusDominance: base.corpusDominance * (1 + 0.14 * attention),
			upwardShift: base.upwardShift + 46 * attention,
			glowIntensity: Math.min(0.86, base.glowIntensity + 0.1 * attention),
		};
	}
	if (shotType === 'reward_hero' || shotType === 'emotional_pause') {
		return {
			...base,
			seedOpacity: base.seedOpacity * 0.58,
			investedOpacity: base.investedOpacity * 0.58,
			corpusWidth: base.corpusWidth + 84 * attention,
			corpusScale: base.corpusScale * (1 + 0.12 * attention),
			corpusDominance: base.corpusDominance * (1 + 0.12 * attention),
			glowIntensity: Math.min(0.9, base.glowIntensity + 0.14 * attention),
			rewardIsolation: Math.max(base.rewardIsolation, 0.86),
			negativeSpace: base.negativeSpace + 0.12 * attention,
			motionVelocity: base.motionVelocity * 0.86,
			ratioScale: base.ratioScale * (1 + 0.12 * attention),
			returnsScale: base.returnsScale * (1 + 0.1 * attention),
		};
	}
	return base;
};

const layoutForEvent = (base: GrowthLayout, event: ResolvedVisualEvent): GrowthLayout => {
	if (event.kind === 'small_seed') {
		return {
			...base,
			seedX: 265,
			seedY: 350,
			seedScale: 1.14,
			barsLeft: 1000,
			barGap: base.barGap * 1.18,
			investedOpacity: 0.42,
			corpusOpacity: 0.36,
			glowIntensity: 0.08,
			negativeSpace: Math.max(base.negativeSpace, 0.34),
			motionVelocity: 0.66,
		};
	}
	if (event.kind === 'momentum_lift') {
		return {
			...base,
			upwardShift: base.upwardShift + 110,
			corpusScale: base.corpusScale * 1.22,
			corpusDominance: base.corpusDominance * 1.18,
			glowIntensity: Math.min(0.86, base.glowIntensity + 0.24),
			motionVelocity: base.motionVelocity * 1.32,
			ratioScale: base.ratioScale * 1.16,
		};
	}
	if (event.kind === 'compounding_layer') {
		return {
			...base,
			barsLeft: 650,
			barGap: base.barGap * 0.7,
			investedOpacity: base.investedOpacity * 0.62,
			corpusWidth: base.corpusWidth + 90,
			corpusScale: base.corpusScale * 1.28,
			hierarchyContrast: base.hierarchyContrast * 1.24,
			glowIntensity: Math.min(0.9, base.glowIntensity + 0.2),
			negativeSpace: Math.min(base.negativeSpace, -0.05),
		};
	}
	if (event.kind === 'corpus_hero_reveal') {
		return {
			...base,
			seedOpacity: base.seedOpacity * 0.24,
			investedOpacity: base.investedOpacity * 0.28,
			barsLeft: 1010,
			corpusWidth: base.corpusWidth + 130,
			corpusScale: base.corpusScale * 1.22,
			corpusDominance: base.corpusDominance * 1.28,
			glowIntensity: 0.92,
			rewardIsolation: 1,
			negativeSpace: Math.max(base.negativeSpace, 0.48),
			motionVelocity: base.motionVelocity * 0.74,
			ratioX: 140,
			ratioY: 690,
			ratioScale: 0.92,
			returnsX: 130,
			returnsY: 835,
			returnsScale: 0.98,
		};
	}
	return base;
};

const mix = (from: number, to: number, amount: number) =>
	interpolate(amount, [0, 1], [from, to]);

const mixedLayout = (target: GrowthLayout, amount: number): GrowthLayout => ({
	...target,
	seedX: mix(DEFAULT_LAYOUT.seedX, target.seedX, amount),
	seedY: mix(DEFAULT_LAYOUT.seedY, target.seedY, amount),
	seedScale: mix(DEFAULT_LAYOUT.seedScale, target.seedScale, amount),
	seedOpacity: mix(DEFAULT_LAYOUT.seedOpacity, target.seedOpacity, amount),
	barsLeft: mix(DEFAULT_LAYOUT.barsLeft, target.barsLeft, amount),
	barsBottom: mix(DEFAULT_LAYOUT.barsBottom, target.barsBottom, amount),
	barsHeight: mix(DEFAULT_LAYOUT.barsHeight, target.barsHeight, amount),
	barGap: mix(DEFAULT_LAYOUT.barGap, target.barGap, amount),
	investedWidth: mix(DEFAULT_LAYOUT.investedWidth, target.investedWidth, amount),
	corpusWidth: mix(DEFAULT_LAYOUT.corpusWidth, target.corpusWidth, amount),
	investedScale: mix(DEFAULT_LAYOUT.investedScale, target.investedScale, amount),
	corpusScale: mix(DEFAULT_LAYOUT.corpusScale, target.corpusScale, amount),
	investedOpacity: mix(DEFAULT_LAYOUT.investedOpacity, target.investedOpacity, amount),
	corpusOpacity: mix(DEFAULT_LAYOUT.corpusOpacity, target.corpusOpacity, amount),
	hierarchyContrast: mix(DEFAULT_LAYOUT.hierarchyContrast, target.hierarchyContrast, amount),
	glowIntensity: mix(DEFAULT_LAYOUT.glowIntensity, target.glowIntensity, amount),
	upwardShift: mix(DEFAULT_LAYOUT.upwardShift, target.upwardShift, amount),
	corpusDominance: mix(DEFAULT_LAYOUT.corpusDominance, target.corpusDominance, amount),
	motionVelocity: mix(DEFAULT_LAYOUT.motionVelocity, target.motionVelocity, amount),
	negativeSpace: mix(DEFAULT_LAYOUT.negativeSpace, target.negativeSpace, amount),
	rewardIsolation: mix(DEFAULT_LAYOUT.rewardIsolation, target.rewardIsolation, amount),
	returnsX: mix(DEFAULT_LAYOUT.returnsX, target.returnsX, amount),
	returnsY: mix(DEFAULT_LAYOUT.returnsY, target.returnsY, amount),
	returnsScale: mix(DEFAULT_LAYOUT.returnsScale, target.returnsScale, amount),
	ratioX: mix(DEFAULT_LAYOUT.ratioX, target.ratioX, amount),
	ratioY: mix(DEFAULT_LAYOUT.ratioY, target.ratioY, amount),
	ratioScale: mix(DEFAULT_LAYOUT.ratioScale, target.ratioScale, amount),
	backgroundLift: mix(DEFAULT_LAYOUT.backgroundLift, target.backgroundLift, amount),
});

export const SIPGrowthEngine: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'growth');
	const event = resolveVisualEvent(beat, scene, 'SIPGrowthEngine');
	const visualState = resolveVisualState(beat, scene);
	const activeShot = resolveShot(beat, scene);
	const layoutTarget = layoutForEvent(layoutForShot(layoutForState(visualState), activeShot), event);
	const layoutMix = spring({frame: Math.min(frameWithinBeat, 24), fps, config: SPRINGS.entry, durationInFrames: 24});
	const layout = mixedLayout(layoutTarget, layoutMix);
	const sip = data.monthly_sip as {value?: string; amount?: number} | undefined;
	const totalInvested = Number(data.total_invested ?? 0);
	const finalCorpus = Number(data.final_corpus ?? 0);
	const returnsEarned = Number(data.returns_earned ?? Math.max(finalCorpus - totalInvested, 0));
	const durationYears = Number(data.duration_years ?? 20);
	const annualReturn = Number(data.annual_return_rate ?? 12);
	const aweRatio = Number(data.awe_ratio ?? (totalInvested ? finalCorpus / totalInvested : 0));
	const rawProgress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.75 / layout.motionVelocity)), 1);
	const motionProgress = Math.pow(rawProgress, 1 / Math.max(layout.motionVelocity, 0.1));
	const progress = phase === 'contribution' ? 0.18 : phase === 'corpus' ? 1 : motionProgress;
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const investedHeight = 230 * layout.investedScale;
	const corpusHeight = Math.min(660, Math.max(260, investedHeight * Math.max(aweRatio, 1.2) * 0.78 * layout.corpusScale * layout.corpusDominance));
	const investedFill = investedHeight * Math.min(progress * 1.35, 1);
	const rawCorpusProgress = Math.max(0, Math.min((progress - 0.25) / 0.75, 1));
	const corpusFill = corpusHeight * Math.pow(rawCorpusProgress, 0.6 / Math.max(layout.hierarchyContrast, 0.5));
	const displayedRatio = interpolate(progress, [0.42, 1], [1, Math.max(aweRatio, 1)], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const visualStateName = String(visualState?.state_type ?? 'default');
	const emotionalPosture = String(visualState?.emotional_posture ?? 'neutral');
	const compositionDensity = String(visualState?.composition_density ?? 'default');
	const framing = String(visualState?.framing ?? 'default');
	const transitionBehavior = String(visualState?.transition_behavior ?? 'default');
	const shotType = String(activeShot?.shot_type ?? 'default');
	const focusTarget = String(activeShot?.focus_target ?? 'default');
	const framingProfile = String(activeShot?.framing_profile ?? 'default');
	const investedVisualOpacity = layout.investedOpacity * (1 - layout.rewardIsolation * 0.45);
	const corpusVisualOpacity = layout.corpusOpacity;
	const backgroundGlow = `radial-gradient(circle at ${66 + layout.rewardIsolation * 10}% ${38 - layout.backgroundLift * 18}%, rgba(46,196,182,${0.10 + layout.glowIntensity * 0.42}), transparent ${26 + layout.negativeSpace * 20}%), ${COLORS.bg_deep}`;

	return (
		<AbsoluteFill
			data-visual-state={visualStateName}
			data-layout-profile={layout.profile}
			data-emotional-posture={emotionalPosture}
			data-composition-density={compositionDensity}
			data-framing={framing}
			data-transition-behavior={transitionBehavior}
			data-shot-type={shotType}
			data-focus-target={focusTarget}
			data-framing-profile={framingProfile}
			data-visual-event={event.kind}
			style={{
				background: backgroundGlow,
				color: COLORS.text_primary,
				padding: SPACING.safe,
				fontFamily: BODY_FONT_FAMILY,
				overflow: 'hidden',
			}}
		>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.positive}} />
			<div
				style={{
					position: 'absolute',
					inset: 0,
					background: 'black',
					opacity: layout.rewardIsolation * 0.18,
					pointerEvents: 'none',
				}}
			/>
			<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 800, color: COLORS.text_secondary}}>
				{event.kind === 'small_seed'
					? 'Small seed starts'
					: event.kind === 'momentum_lift'
						? 'Momentum takes over'
						: event.kind === 'compounding_layer'
							? 'Compounding stacks'
							: 'Corpus lands'}
			</div>
			<div
				style={{
					position: 'absolute',
					left: layout.seedX,
					top: layout.seedY,
					width: 560,
					opacity: layout.seedOpacity,
					transform: `translateY(${-layout.upwardShift * 0.18}px) scale(${interpolate(reveal, [0, 1], [0.96, 1]) * layout.seedScale})`,
					transformOrigin: 'left top',
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>Monthly SIP</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 104, lineHeight: 0.94}}>
					{sip?.value ?? formatIndianRupee(Number(sip?.amount ?? 0))}
				</div>
				<div style={{marginTop: SPACING.md, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>
					{durationYears} years at {annualReturn}% returns
				</div>
			</div>
			<div
				style={{
					position: 'absolute',
					left: layout.barsLeft,
					right: SPACING.safe,
					bottom: layout.barsBottom,
					height: layout.barsHeight,
					display: 'flex',
					alignItems: 'flex-end',
					gap: layout.barGap,
					transform: `translateY(${-layout.upwardShift}px)`,
				}}
			>
				<div style={{width: layout.investedWidth, opacity: investedVisualOpacity, transform: `translateY(${layout.rewardIsolation * 72}px) scale(${1 - layout.rewardIsolation * 0.1})`, transformOrigin: 'bottom center'}}>
					<div
						style={{
							height: investedHeight,
							borderRadius: 8,
							background: COLORS.bg_surface,
							border: `1px solid ${COLORS.stroke}`,
							display: 'flex',
							alignItems: 'flex-end',
							overflow: 'hidden',
						}}
					>
						<div style={{height: investedFill, width: '100%', background: COLORS.neutral}} />
					</div>
					<div style={{marginTop: SPACING.md, fontSize: TYPE_SCALE.micro.size + 4, color: COLORS.text_secondary, fontWeight: 700}}>
						You invested
					</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 52, lineHeight: 1}}>
						{formatIndianRupee(totalInvested)}
					</div>
				</div>
				<div style={{width: layout.corpusWidth, opacity: corpusVisualOpacity, transform: `translateY(${-layout.corpusDominance * 16}px) scale(${1 + layout.rewardIsolation * 0.08})`, transformOrigin: 'bottom center'}}>
					<div
						style={{
							height: corpusHeight,
							borderRadius: 8,
							background: `rgba(46,196,182,${0.08 + layout.glowIntensity * 0.08})`,
							border: `2px solid ${COLORS.positive}`,
							display: 'flex',
							alignItems: 'flex-end',
							overflow: 'hidden',
							boxShadow: `0 0 ${60 + layout.glowIntensity * 115}px rgba(46,196,182,${layout.glowIntensity})`,
						}}
					>
						<div style={{height: corpusFill, width: '100%', background: COLORS.positive}} />
					</div>
					<div style={{marginTop: SPACING.md, fontSize: TYPE_SCALE.micro.size + 4, color: COLORS.text_secondary, fontWeight: 700}}>
						Final corpus
					</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 64, lineHeight: 1, color: COLORS.positive}}>
						{formatIndianRupee(finalCorpus)}
					</div>
				</div>
			</div>
			<div
				style={{
					position: 'absolute',
					left: layout.ratioX,
					top: layout.ratioY,
					fontFamily: DISPLAY_FONT_FAMILY,
					fontSize: 78,
					lineHeight: 0.9,
					color: COLORS.positive,
					opacity: phase === 'contribution' ? 0 : interpolate(progress, [0.55, 0.86], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
					transform: `scale(${layout.ratioScale})`,
					transformOrigin: 'left center',
					textShadow: `0 0 ${24 + layout.glowIntensity * 44}px rgba(46,196,182,${layout.glowIntensity})`,
				}}
			>
				{displayedRatio.toFixed(1)}x more than invested
			</div>
			<div
				style={{
					position: 'absolute',
					left: layout.returnsX,
					top: layout.returnsY,
					padding: '24px 30px',
					borderRadius: 8,
					background: COLORS.bg_surface,
					border: `1px solid ${COLORS.stroke}`,
					opacity: event.kind === 'small_seed' ? 0 : interpolate(progress, [0.72, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
					transform: `scale(${layout.returnsScale})`,
					transformOrigin: 'left center',
					boxShadow: layout.rewardIsolation ? `0 0 82px rgba(46,196,182,${layout.glowIntensity * 0.5})` : 'none',
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>Returns earned</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 74, lineHeight: 0.95, color: COLORS.positive}}>
					{formatIndianRupee(returnsEarned)}
				</div>
			</div>
		</AbsoluteFill>
	);
};
