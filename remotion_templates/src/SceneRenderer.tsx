import React from 'react';
import {
	AbsoluteFill,
	interpolate,
	spring,
	useCurrentFrame,
	useVideoConfig,
} from 'remotion';
import {BalanceBar} from './components/BalanceBar';
import {CalculationStrip} from './components/CalculationStrip';
import {CinematicScene} from './components/CinematicScene';
import {ConceptCard} from './components/ConceptCard';
import {DebtSpiralVisualizer} from './components/DebtSpiralVisualizer';
import {EMIStackVisualizer} from './components/EMIStackVisualizer';
import {EmergencyFundVisualizer} from './components/EmergencyFundVisualizer';
import {FlowDiagram} from './components/FlowDiagram';
import {FOMOPriceCrashVisualizer} from './components/FOMOPriceCrashVisualizer';
import {GrowthChart} from './components/GrowthChart';
import {InflationErosionVisualizer} from './components/InflationErosionVisualizer';
import {LifestyleCreepVisualizer} from './components/LifestyleCreepVisualizer';
import {MoneyFlowDiagram} from './components/MoneyFlowDiagram';
import {OutroRecapVisualizer} from './components/OutroRecapVisualizer';
import {PortfolioDiversificationVisualizer} from './components/PortfolioDiversificationVisualizer';
import {RiskCard} from './components/RiskCard';
import {RiskReturnVisualizer} from './components/RiskReturnVisualizer';
import {SIPGrowthEngine} from './components/SIPGrowthEngine';
import {SmallLeaksAccumulator} from './components/SmallLeaksAccumulator';
import {SplitComparison} from './components/SplitComparison';
import {StatCard} from './components/StatCard';
import {StepFlow} from './components/StepFlow';
import {StoryWorldOverlay} from './components/StoryWorldOverlay';
import {UniversalMechanismRenderer} from './components/UniversalMechanismRenderer';
import {Beat, Scene, Shot} from './types';
import {timeToFrame} from './utils/timing';

export const COMPONENT_MAP = {
	StatCard,
	CalculationStrip,
	ConceptCard,
	ConceptCardScene: ConceptCard,
	HighlightText: ConceptCard,
	FlowBar: FlowDiagram,
	FlowDiagram,
	SplitComparison,
	SplitComparisonScene: SplitComparison,
	StepFlow,
	StepFlowScene: StepFlow,
	GrowthChart,
	GrowthChartScene: GrowthChart,
	InflationErosionVisualizer,
	LifestyleCreepVisualizer,
	RiskCard,
	RiskCardScene: RiskCard,
	BalanceBar,
	MoneyFlowDiagram,
	DebtSpiralVisualizer,
	SIPGrowthEngine,
	EMIStackVisualizer,
	FOMOPriceCrashVisualizer,
	PortfolioDiversificationVisualizer,
	SmallLeaksAccumulator,
	RiskReturnVisualizer,
	EmergencyFundVisualizer,
	OutroRecapVisualizer,
	CinematicScene,
	UniversalMechanismRenderer,
} as const;

type Props = {
	scene: Scene;
};

export const beatFrameRange = (beat: Beat, fps: number) => ({
	startFrame: timeToFrame(beat.start_time, fps),
	endFrame: timeToFrame(beat.end_time, fps),
});

export const resolveActiveBeat = (scene: Scene, frame: number, fps: number) => {
	const activeBeatIndex = scene.beats.findIndex((beat) => {
		const range = beatFrameRange(beat, fps);
		return range.startFrame <= frame && frame < range.endFrame;
	});
	const activeBeat = activeBeatIndex >= 0 ? scene.beats[activeBeatIndex] : undefined;
	return {activeBeatIndex, activeBeat};
};

export const resolveSceneComponent = (component: string) => {
	const Component = COMPONENT_MAP[component as keyof typeof COMPONENT_MAP] ?? ConceptCard;
	return {
		Component,
		resolvedComponent: COMPONENT_MAP[component as keyof typeof COMPONENT_MAP] ? component : 'ConceptCard',
		fallbackUsed: !COMPONENT_MAP[component as keyof typeof COMPONENT_MAP],
	};
};

const SHOT_FRAME_PROFILES: Record<
	string,
	{
		scale: number;
		x: number;
		y: number;
		opacity: number;
		origin: string;
	}
> = {
	wide_context: {scale: 0.99, x: 0, y: 0, opacity: 1, origin: '50% 50%'},
	focused_growth: {scale: 1.035, x: 0, y: -18, opacity: 1, origin: '50% 42%'},
	pressure_closeup: {scale: 1.045, x: -18, y: -4, opacity: 1, origin: '44% 52%'},
	survivor_isolation: {scale: 0.985, x: 0, y: 12, opacity: 0.98, origin: '50% 56%'},
	reward_hero: {scale: 1.055, x: 0, y: -28, opacity: 1, origin: '50% 34%'},
	comparison_focus: {scale: 1.015, x: 0, y: 0, opacity: 1, origin: '50% 50%'},
	upward_momentum: {scale: 1.03, x: 0, y: -30, opacity: 1, origin: '50% 38%'},
	emotional_pause: {scale: 0.995, x: 0, y: 8, opacity: 1, origin: '50% 54%'},
};

const asShot = (value: unknown): Shot | null => {
	if (!value || typeof value !== 'object') {
		return null;
	}
	return value as Shot;
};

export const resolveActiveShot = (
	beat: Beat,
	scene: Scene,
	fps: number,
): Shot | null => {
	const direct = asShot(beat.active_shot);
	if (direct) {
		return direct;
	}
	const dataShot = asShot(beat.data?.active_shot);
	if (dataShot) {
		return dataShot;
	}
	const shots = scene.shot_sequence?.shots ?? [];
	if (shots.length === 0) {
		return null;
	}
	const {startFrame, endFrame} = beatFrameRange(beat, fps);
	return (
		shots.find((shot) => {
			const shotStart = Number(shot.start_frame ?? shot.composition_window?.start_frame ?? 0);
			const shotEnd = Number(shot.end_frame ?? shot.composition_window?.end_frame ?? 0);
			return startFrame < shotEnd && endFrame > shotStart;
		}) ?? null
	);
};

const clampAttention = (value: unknown) => {
	const numeric = Number(value);
	if (!Number.isFinite(numeric)) {
		return 0.7;
	}
	return Math.min(1, Math.max(0.45, numeric));
};

const ShotFrame: React.FC<{
	shot: Shot | null;
	frameWithinBeat: number;
	durationFrames: number;
	fps: number;
	children: React.ReactNode;
}> = ({shot, frameWithinBeat, durationFrames, fps, children}) => {
	if (!shot) {
		return <>{children}</>;
	}
	const shotType = shot.shot_type ?? 'wide_context';
	const profile = SHOT_FRAME_PROFILES[shotType] ?? SHOT_FRAME_PROFILES.wide_context;
	const attention = clampAttention(shot.attention_weight);
	const enter = spring({
		frame: Math.max(0, frameWithinBeat),
		fps,
		config: {damping: 22, stiffness: 110, mass: 0.9},
	});
	const drift = interpolate(
		Math.max(0, frameWithinBeat),
		[0, Math.max(1, durationFrames - 1)],
		[0, 1],
		{extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
	);
	const momentumY = shotType === 'upward_momentum' ? profile.y * drift * attention : profile.y * enter * attention;
	const scale = interpolate(enter, [0, 1], [1, 1 + (profile.scale - 1) * attention]);
	const transform = [
		`translate3d(${profile.x * enter * attention}px, ${momentumY}px, 0)`,
		`scale(${scale})`,
	].join(' ');

	return (
		<AbsoluteFill
			data-shot-type={shotType}
			data-focus-target={shot.focus_target ?? ''}
			data-framing-profile={shot.framing_profile ?? ''}
			style={{overflow: 'hidden'}}
		>
			<AbsoluteFill
				style={{
					opacity: interpolate(enter, [0, 1], [0.98, profile.opacity]),
					transform,
					transformOrigin: profile.origin,
				}}
			>
				{children}
			</AbsoluteFill>
		</AbsoluteFill>
	);
};

const DATA_HEAVY_COMPONENTS = new Set([
	'MoneyFlowDiagram',
	'DebtSpiralVisualizer',
	'SIPGrowthEngine',
	'CalculationStrip',
	'GrowthChart',
	'GrowthChartScene',
	'InflationErosionVisualizer',
	'LifestyleCreepVisualizer',
	'EMIStackVisualizer',
	'FOMOPriceCrashVisualizer',
	'PortfolioDiversificationVisualizer',
	'SmallLeaksAccumulator',
	'RiskReturnVisualizer',
	'EmergencyFundVisualizer',
	'OutroRecapVisualizer',
	'UniversalMechanismRenderer',
	'FlowDiagram',
	'FlowBar',
	'SplitComparison',
	'SplitComparisonScene',
]);

const OVERLAY_FRIENDLY_COMPONENTS = new Set([
	'StatCard',
	'ConceptCard',
	'ConceptCardScene',
	'HighlightText',
]);

const shouldShowStoryOverlay = (beat: Beat, beatIndex: number, totalBeats: number): boolean => {
	const overlayRequested = Boolean(beat.props?.show_story_overlay ?? beat.data?.show_story_overlay);
	if (!overlayRequested) {
		return false;
	}
	const role = String(beat.beat_role ?? beat.props?.beat_role ?? beat.data?.beat_role ?? '').toLowerCase();
	if (role === 'process' || role === 'change') {
		return false;
	}
	if (role === 'introduce' || role === 'result' || role === 'punch') {
		return OVERLAY_FRIENDLY_COMPONENTS.has(beat.component);
	}
	if (DATA_HEAVY_COMPONENTS.has(beat.component)) {
		return false;
	}
	return (beatIndex === 0 || beatIndex === totalBeats - 1) && OVERLAY_FRIENDLY_COMPONENTS.has(beat.component);
};

export const SceneRenderer: React.FC<Props> = ({scene}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	const {activeBeatIndex, activeBeat} = resolveActiveBeat(scene, frame, fps);

	if (!activeBeat) {
		return null;
	}

	const {startFrame, endFrame} = beatFrameRange(activeBeat, fps);
	const frameWithinBeat = frame - startFrame;
	const durationFrames = endFrame - startFrame;
	const hasStoryState =
		scene.story_state && Object.keys(scene.story_state).length > 0;
	const cinematicTextBeat = activeBeat.component === 'CinematicScene';
	const {Component} = resolveSceneComponent(activeBeat.component);
	const activeShot = resolveActiveShot(activeBeat, scene, fps);
	const shouldOverlayStoryWorld =
		hasStoryState &&
		!cinematicTextBeat &&
		shouldShowStoryOverlay(activeBeat, activeBeatIndex, scene.beats.length);

	return (
		<>
			<ShotFrame
				shot={activeShot}
				frameWithinBeat={frameWithinBeat}
				durationFrames={durationFrames}
				fps={fps}
			>
				<Component
					beat={activeBeat}
					scene={scene}
					frameWithinBeat={frameWithinBeat}
					durationFrames={durationFrames}
				/>
			</ShotFrame>
			{shouldOverlayStoryWorld ? (
				<StoryWorldOverlay
					beat={activeBeat}
					scene={scene}
					frameWithinBeat={frameWithinBeat}
					durationFrames={durationFrames}
				/>
			) : null}
		</>
	);
};
