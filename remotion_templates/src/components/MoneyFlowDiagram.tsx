import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';

type Flow = {
	label: string;
	value: string;
	amount: number;
	color: 'red' | 'orange' | 'teal';
	order: number;
};

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

type LayoutProfile = {
	profile: 'default' | 'centered_focus' | 'pressure_cluster' | 'isolate_survivor';
	sourceX: number;
	sourceY: number;
	sourceScale: number;
	sourceOpacity: number;
	pipeStartX: number;
	pipeEndX: number;
	rowStartY: number;
	rowGap: number;
	rowOverlap: number;
	labelOffsetX: number;
	labelScale: number;
	labelOpacity: number;
	ghostOpacity: number;
	flowOpacity: number;
	flowWidthScale: number;
	progressPower: number;
	motionWindowShare: number;
	remainderX: number;
	remainderY: number;
	remainderScale: number;
	remainderOpacityBoost: number;
	backgroundDim: number;
};

const DEFAULT_LAYOUT: LayoutProfile = {
	profile: 'default',
	sourceX: 240,
	sourceY: 540,
	sourceScale: 1,
	sourceOpacity: 1,
	pipeStartX: 500,
	pipeEndX: 1380,
	rowStartY: 290,
	rowGap: 118,
	rowOverlap: 0,
	labelOffsetX: 40,
	labelScale: 1,
	labelOpacity: 1,
	ghostOpacity: 0.1,
	flowOpacity: 0.92,
	flowWidthScale: 1,
	progressPower: 1,
	motionWindowShare: 0.75,
	remainderX: 1566,
	remainderY: 850,
	remainderScale: 1,
	remainderOpacityBoost: 0,
	backgroundDim: 0,
};

const STATE_LAYOUTS: Record<string, LayoutProfile> = {
	centered_focus: {
		...DEFAULT_LAYOUT,
		profile: 'centered_focus',
		sourceX: 960,
		sourceY: 500,
		sourceScale: 1.18,
		pipeStartX: 720,
		pipeEndX: 1540,
		rowStartY: 245,
		rowGap: 154,
		labelOffsetX: 54,
		labelScale: 0.96,
		ghostOpacity: 0.07,
		flowOpacity: 0.82,
		flowWidthScale: 0.9,
		progressPower: 1.35,
		motionWindowShare: 0.9,
		remainderX: 960,
		remainderY: 820,
		remainderScale: 0.95,
	},
	pressure_cluster: {
		...DEFAULT_LAYOUT,
		profile: 'pressure_cluster',
		sourceX: 220,
		sourceY: 540,
		sourceScale: 0.96,
		pipeStartX: 430,
		pipeEndX: 1090,
		rowStartY: 310,
		rowGap: 92,
		rowOverlap: 8,
		labelOffsetX: 12,
		labelScale: 0.94,
		labelOpacity: 1,
		ghostOpacity: 0.2,
		flowOpacity: 1,
		flowWidthScale: 1.28,
		progressPower: 0.58,
		motionWindowShare: 0.56,
		remainderX: 1548,
		remainderY: 844,
		remainderScale: 0.92,
		backgroundDim: 0.1,
	},
	isolate_survivor: {
		...DEFAULT_LAYOUT,
		profile: 'isolate_survivor',
		sourceX: 210,
		sourceY: 540,
		sourceScale: 0.82,
		sourceOpacity: 0.35,
		pipeStartX: 450,
		pipeEndX: 930,
		rowStartY: 300,
		rowGap: 112,
		labelOffsetX: 16,
		labelScale: 0.8,
		labelOpacity: 0.16,
		ghostOpacity: 0.04,
		flowOpacity: 0.18,
		flowWidthScale: 0.65,
		progressPower: 1.55,
		motionWindowShare: 1,
		remainderX: 960,
		remainderY: 560,
		remainderScale: 1.46,
		remainderOpacityBoost: 0.42,
		backgroundDim: 0.24,
	},
};

const moneyFlowData = (beat: BeatComponentProps['beat']) => {
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const source = data.source as {label?: string; value?: string; amount?: number} | undefined;
	const flows = Array.isArray(data.flows) ? (data.flows as Flow[]) : [];
	const remainder = data.remainder as {value?: string; amount?: number; is_dangerous?: boolean} | undefined;
	return {
		source: {
			label: source?.label ?? 'Salary',
			value: source?.value ?? formatIndianRupee(Number(source?.amount ?? 0)),
			amount: Number(source?.amount ?? 0),
		},
		flows: flows
			.map((flow, index) => ({
				label: String(flow.label ?? `Expense ${index + 1}`),
				value: String(flow.value ?? formatIndianRupee(Number(flow.amount ?? 0))),
				amount: Number(flow.amount ?? 0),
				color: flow.color ?? 'orange',
				order: Number(flow.order ?? index + 1),
			}))
			.sort((a, b) => a.order - b.order)
			.slice(0, 5),
		remainder: {
			value: remainder?.value ?? formatIndianRupee(Number(remainder?.amount ?? 0)),
			amount: Number(remainder?.amount ?? 0),
			is_dangerous: Boolean(remainder?.is_dangerous),
		},
	};
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

const layoutForState = (visualState: VisualState | null): LayoutProfile => {
	const stateType = String(visualState?.state_type ?? '');
	const base = STATE_LAYOUTS[stateType] ?? DEFAULT_LAYOUT;
	const density = String(visualState?.composition_density ?? '');
	const framing = String(visualState?.framing ?? '');
	const transition = String(visualState?.transition_behavior ?? '');
	return {
		...base,
		rowGap: density === 'high' ? base.rowGap * 0.92 : density === 'minimal' ? base.rowGap * 1.12 : base.rowGap,
		labelOpacity: density === 'minimal' ? base.labelOpacity * 0.74 : base.labelOpacity,
		flowOpacity: density === 'minimal' ? base.flowOpacity * 0.82 : density === 'high' ? Math.min(1, base.flowOpacity * 1.08) : base.flowOpacity,
		flowWidthScale: density === 'high' ? base.flowWidthScale * 1.06 : density === 'minimal' ? base.flowWidthScale * 0.86 : base.flowWidthScale,
		pipeEndX: framing === 'tight' ? base.pipeEndX - 36 : framing === 'wide' ? base.pipeEndX + 34 : base.pipeEndX,
		remainderScale: framing === 'isolated' ? base.remainderScale * 1.08 : base.remainderScale,
		progressPower: transition === 'compression_shift' ? base.progressPower * 0.9 : transition === 'slow_hold' ? base.progressPower * 1.14 : base.progressPower,
		motionWindowShare: transition === 'soft_enter' ? Math.min(1, base.motionWindowShare * 1.08) : base.motionWindowShare,
		backgroundDim: density === 'minimal' ? Math.min(0.35, base.backgroundDim + 0.04) : base.backgroundDim,
	};
};

const layoutForShot = (base: LayoutProfile, shot: Shot | null): LayoutProfile => {
	const shotType = String(shot?.shot_type ?? '');
	const attention = Math.max(0.4, Math.min(Number(shot?.attention_weight ?? 0.65), 1));
	if (shotType === 'pressure_closeup') {
		return {
			...base,
			pipeEndX: base.pipeEndX - 52 * attention,
			rowGap: base.rowGap * 0.98,
			rowOverlap: base.rowOverlap + 3 * attention,
			labelOffsetX: Math.max(6, base.labelOffsetX - 10 * attention),
			flowWidthScale: base.flowWidthScale * (1 + 0.16 * attention),
			progressPower: base.progressPower * 0.86,
			backgroundDim: Math.min(0.28, base.backgroundDim + 0.06 * attention),
		};
	}
	if (shotType === 'survivor_isolation' || shotType === 'emotional_pause') {
		return {
			...base,
			sourceOpacity: base.sourceOpacity * 0.72,
			pipeEndX: base.pipeEndX - 120 * attention,
			labelOpacity: base.labelOpacity * 0.48,
			flowOpacity: base.flowOpacity * 0.46,
			ghostOpacity: base.ghostOpacity * 0.5,
			remainderX: 960,
			remainderY: 560,
			remainderScale: base.remainderScale * (1 + 0.22 * attention),
			remainderOpacityBoost: Math.max(base.remainderOpacityBoost, 0.38),
			progressPower: base.progressPower * 1.12,
			backgroundDim: Math.min(0.34, base.backgroundDim + 0.08 * attention),
		};
	}
	if (shotType === 'wide_context') {
		return {
			...base,
			rowGap: base.rowGap * 1.08,
			pipeEndX: base.pipeEndX + 36 * attention,
			flowOpacity: base.flowOpacity * 0.92,
			progressPower: base.progressPower * 1.08,
		};
	}
	return base;
};

const mix = (from: number, to: number, amount: number) =>
	interpolate(amount, [0, 1], [from, to]);

const mixedLayout = (target: LayoutProfile, amount: number): LayoutProfile => ({
	...target,
	sourceX: mix(DEFAULT_LAYOUT.sourceX, target.sourceX, amount),
	sourceY: mix(DEFAULT_LAYOUT.sourceY, target.sourceY, amount),
	sourceScale: mix(DEFAULT_LAYOUT.sourceScale, target.sourceScale, amount),
	sourceOpacity: mix(DEFAULT_LAYOUT.sourceOpacity, target.sourceOpacity, amount),
	pipeStartX: mix(DEFAULT_LAYOUT.pipeStartX, target.pipeStartX, amount),
	pipeEndX: mix(DEFAULT_LAYOUT.pipeEndX, target.pipeEndX, amount),
	rowStartY: mix(DEFAULT_LAYOUT.rowStartY, target.rowStartY, amount),
	rowGap: mix(DEFAULT_LAYOUT.rowGap, target.rowGap, amount),
	rowOverlap: mix(DEFAULT_LAYOUT.rowOverlap, target.rowOverlap, amount),
	labelOffsetX: mix(DEFAULT_LAYOUT.labelOffsetX, target.labelOffsetX, amount),
	labelScale: mix(DEFAULT_LAYOUT.labelScale, target.labelScale, amount),
	labelOpacity: mix(DEFAULT_LAYOUT.labelOpacity, target.labelOpacity, amount),
	ghostOpacity: mix(DEFAULT_LAYOUT.ghostOpacity, target.ghostOpacity, amount),
	flowOpacity: mix(DEFAULT_LAYOUT.flowOpacity, target.flowOpacity, amount),
	flowWidthScale: mix(DEFAULT_LAYOUT.flowWidthScale, target.flowWidthScale, amount),
	progressPower: mix(DEFAULT_LAYOUT.progressPower, target.progressPower, amount),
	motionWindowShare: mix(DEFAULT_LAYOUT.motionWindowShare, target.motionWindowShare, amount),
	remainderX: mix(DEFAULT_LAYOUT.remainderX, target.remainderX, amount),
	remainderY: mix(DEFAULT_LAYOUT.remainderY, target.remainderY, amount),
	remainderScale: mix(DEFAULT_LAYOUT.remainderScale, target.remainderScale, amount),
	remainderOpacityBoost: mix(DEFAULT_LAYOUT.remainderOpacityBoost, target.remainderOpacityBoost, amount),
	backgroundDim: mix(DEFAULT_LAYOUT.backgroundDim, target.backgroundDim, amount),
});

const roundDebug = (value: number) => Math.round(value * 1000) / 1000;

const moneyLayoutDebug = (layout: LayoutProfile) => ({
	profile: layout.profile,
	sourceX: roundDebug(layout.sourceX),
	pipeEndX: roundDebug(layout.pipeEndX),
	rowGap: roundDebug(layout.rowGap),
	rowOverlap: roundDebug(layout.rowOverlap),
	labelOpacity: roundDebug(layout.labelOpacity),
	flowOpacity: roundDebug(layout.flowOpacity),
	flowWidthScale: roundDebug(layout.flowWidthScale),
	remainderX: roundDebug(layout.remainderX),
	remainderY: roundDebug(layout.remainderY),
	remainderScale: roundDebug(layout.remainderScale),
	backgroundDim: roundDebug(layout.backgroundDim),
	progressPower: roundDebug(layout.progressPower),
});

let lastMoneyFlowDebugKey = '';

const MoneyFlowDebugOverlay: React.FC<{
	currentFrame: number;
	beatLabel: string;
	shot: Shot | null;
	visualState: VisualState | null;
	layoutValues: ReturnType<typeof moneyLayoutDebug>;
}> = ({currentFrame, beatLabel, shot, visualState, layoutValues}) => (
	<div
		style={{
			position: 'absolute',
			left: 24,
			bottom: 24,
			zIndex: 9998,
			width: 650,
			padding: '18px 20px',
			borderRadius: 8,
			background: 'rgba(2, 6, 23, 0.82)',
			border: '1px solid rgba(255,159,28,0.55)',
			color: 'white',
			fontFamily: 'monospace',
			fontSize: 21,
			lineHeight: 1.35,
			pointerEvents: 'none',
		}}
	>
		<div>MoneyFlowDiagram debug</div>
		<div>frame: {currentFrame}</div>
		<div>beat: {beatLabel}</div>
		<div>shot: {shot?.shot_type ?? 'none'}</div>
		<div>focus: {shot?.focus_target ?? 'none'}</div>
		<div>visual_state: {visualState?.state_type ?? 'none'}</div>
		<div>layout: {JSON.stringify(layoutValues)}</div>
	</div>
);

export const MoneyFlowDiagram: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const rawData = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? rawData.active_phase ?? 'drain');
	const visualState = resolveVisualState(beat, scene);
	const activeShot = resolveShot(beat, scene);
	const layoutTarget = layoutForShot(layoutForState(visualState), activeShot);
	const layoutMix = spring({frame: Math.min(frameWithinBeat, 22), fps, config: SPRINGS.entry, durationInFrames: 22});
	const layout = mixedLayout(layoutTarget, layoutMix);
	const currentFrame = Math.floor(Number(beat.start_time ?? 0) * fps + frameWithinBeat);
	const layoutDebug = moneyLayoutDebug(layout);
	const targetLayoutDebug = moneyLayoutDebug(layoutTarget);
	const debugKey = [
		beat.text,
		activeShot?.shot_type ?? 'none',
		activeShot?.focus_target ?? 'none',
		visualState?.state_type ?? 'none',
		layoutTarget.profile,
	].join('|');
	if (debugKey !== lastMoneyFlowDebugKey) {
		lastMoneyFlowDebugKey = debugKey;
		console.info('[ShotDebug:MoneyFlowDiagram] metadata change', {
			frame: currentFrame,
			beatLabel: beat.text,
			activeShot: activeShot ?? null,
			visualState: visualState ?? null,
			layoutTarget: targetLayoutDebug,
			layoutCurrent: layoutDebug,
		});
	}
	const {source, flows, remainder} = moneyFlowData(beat);
	const total = Math.max(source.amount, 1);
	const rawProgress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * layout.motionWindowShare)) / 1, 1);
	const actionProgress = Math.pow(rawProgress, layout.progressPower);
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const opacity = interpolate(reveal, [0, 1], [0, 1]);
	const accentColor = remainder.is_dangerous ? COLORS.danger : COLORS.warning;
	const flowProgress = phase === 'intro' ? 0 : phase === 'remainder' ? 1 : actionProgress;
	const labelProgress = phase === 'intro' ? 0 : interpolate(flowProgress, [0.12, 0.72], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const remainderOpacity = phase === 'intro' ? 0 : Math.min(1, interpolate(flowProgress, [0.58, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) + layout.remainderOpacityBoost);
	const visualStateName = String(visualState?.state_type ?? 'default');
	const emotionalPosture = String(visualState?.emotional_posture ?? 'neutral');
	const compositionDensity = String(visualState?.composition_density ?? 'default');
	const framing = String(visualState?.framing ?? 'default');
	const transitionBehavior = String(visualState?.transition_behavior ?? 'default');
	const shotType = String(activeShot?.shot_type ?? 'default');
	const focusTarget = String(activeShot?.focus_target ?? 'default');
	const framingProfile = String(activeShot?.framing_profile ?? 'default');

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
			style={{
				background: COLORS.bg_deep,
				color: COLORS.text_primary,
				padding: SPACING.safe,
				fontFamily: BODY_FONT_FAMILY,
			}}
		>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: accentColor}} />
			<div
				style={{
					position: 'absolute',
					inset: 0,
					background: 'black',
					opacity: layout.backgroundDim,
					pointerEvents: 'none',
				}}
			/>
			<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 800, color: COLORS.text_secondary}}>
				{phase === 'intro' ? 'Money enters' : phase === 'remainder' ? 'What survives' : 'Where the money goes'}
			</div>
			<div
				style={{
					position: 'absolute',
					left: layout.sourceX - 110,
					top: layout.sourceY - 100,
					width: 220,
					height: 200,
					borderRadius: 8,
					background: COLORS.bg_surface,
					border: `2px solid ${COLORS.stroke}`,
					display: 'flex',
					flexDirection: 'column',
					alignItems: 'center',
					justifyContent: 'center',
					opacity: opacity * layout.sourceOpacity,
					transform: `scale(${interpolate(reveal, [0, 1], [0.94, 1]) * layout.sourceScale})`,
					boxShadow: layout.profile === 'centered_focus' ? '0 0 80px rgba(255,159,28,0.12)' : 'none',
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>
					{source.label}
				</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58, lineHeight: 1}}>
					{source.value}
				</div>
			</div>
			<svg viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
				{phase !== 'intro' ? flows.map((flow, index) => {
					const y = layout.rowStartY + index * layout.rowGap - (index % 2) * layout.rowOverlap;
					const width = Math.max(10, Math.min(86, (flow.amount / total) * 120 * layout.flowWidthScale));
					const color = flow.color === 'red' ? COLORS.danger : flow.color === 'teal' ? COLORS.positive : COLORS.warning;
					const drawX = layout.pipeStartX + (layout.pipeEndX - layout.pipeStartX) * flowProgress;
					return (
						<g key={`${flow.label}-${index}`}>
							<path
								d={`M ${layout.pipeStartX} ${layout.sourceY} C 680 ${layout.sourceY}, 680 ${y}, ${layout.pipeEndX} ${y}`}
								stroke={`rgba(255,255,255,${layout.ghostOpacity})`}
								strokeWidth={width + 10}
								fill="none"
								strokeLinecap="round"
							/>
							<path
								d={`M ${layout.pipeStartX} ${layout.sourceY} C 680 ${layout.sourceY}, 680 ${y}, ${drawX} ${y}`}
								stroke={color}
								strokeWidth={width}
								fill="none"
								strokeLinecap="round"
								opacity={layout.flowOpacity}
							/>
							<circle cx={drawX} cy={y} r={Math.max(8, width / 3)} fill={color} opacity={flowProgress > 0.04 ? layout.flowOpacity : 0} />
						</g>
					);
				}) : null}
			</svg>
			{phase !== 'intro' ? flows.map((flow, index) => {
				const y = layout.rowStartY + index * layout.rowGap - (index % 2) * layout.rowOverlap;
				return (
					<div
						key={flow.label}
						style={{
							position: 'absolute',
							left: layout.pipeEndX + layout.labelOffsetX,
							top: y - 38,
							opacity: labelProgress * layout.labelOpacity,
							transform: `scale(${layout.labelScale}) translateX(${layout.profile === 'pressure_cluster' ? -18 * layoutMix : 0}px)`,
							transformOrigin: 'left center',
						}}
					>
						<div style={{fontSize: TYPE_SCALE.subtext.size, fontWeight: 800}}>{flow.label}</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 48, lineHeight: 1}}>{flow.value}</div>
					</div>
				);
			}) : null}
			<div
				style={{
					position: 'absolute',
					left: layout.remainderX,
					top: layout.remainderY,
					padding: '26px 34px',
					borderRadius: 8,
					background: remainder.is_dangerous ? 'rgba(230,57,70,0.16)' : COLORS.bg_surface,
					border: `2px solid ${accentColor}`,
					textAlign: 'right',
					opacity: remainderOpacity,
					transform: `translate(-50%, -50%) scale(${layout.remainderScale})`,
					boxShadow: layout.profile === 'isolate_survivor' ? `0 0 120px ${accentColor}33` : 'none',
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>Left over</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 82, lineHeight: 0.95, color: accentColor}}>
					{remainder.value}
				</div>
			</div>
			<MoneyFlowDebugOverlay
				currentFrame={currentFrame}
				beatLabel={String(beat.text ?? '')}
				shot={activeShot}
				visualState={visualState}
				layoutValues={layoutDebug}
			/>
		</AbsoluteFill>
	);
};
