import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {BalanceBar} from './components/BalanceBar';
import {CalculationStrip} from './components/CalculationStrip';
import {CinematicScene} from './components/CinematicScene';
import {ConceptCard} from './components/ConceptCard';
import {DebtSpiralVisualizer} from './components/DebtSpiralVisualizer';
import {EMIStackVisualizer} from './components/EMIStackVisualizer';
import {FlowDiagram} from './components/FlowDiagram';
import {FOMOPriceCrashVisualizer} from './components/FOMOPriceCrashVisualizer';
import {GrowthChart} from './components/GrowthChart';
import {InflationErosionVisualizer} from './components/InflationErosionVisualizer';
import {LifestyleCreepVisualizer} from './components/LifestyleCreepVisualizer';
import {MoneyFlowDiagram} from './components/MoneyFlowDiagram';
import {PortfolioDiversificationVisualizer} from './components/PortfolioDiversificationVisualizer';
import {RiskCard} from './components/RiskCard';
import {SIPGrowthEngine} from './components/SIPGrowthEngine';
import {SmallLeaksAccumulator} from './components/SmallLeaksAccumulator';
import {SplitComparison} from './components/SplitComparison';
import {StatCard} from './components/StatCard';
import {StepFlow} from './components/StepFlow';
import {StoryWorldOverlay} from './components/StoryWorldOverlay';
import {Beat, Scene} from './types';
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
	CinematicScene,
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
	const shouldOverlayStoryWorld =
		hasStoryState &&
		!cinematicTextBeat &&
		shouldShowStoryOverlay(activeBeat, activeBeatIndex, scene.beats.length);

	return (
		<>
			<Component
				beat={activeBeat}
				scene={scene}
				frameWithinBeat={frameWithinBeat}
				durationFrames={durationFrames}
			/>
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
