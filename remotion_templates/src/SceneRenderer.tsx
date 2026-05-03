import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {BalanceBar} from './components/BalanceBar';
import {CalculationStrip} from './components/CalculationStrip';
import {CinematicScene} from './components/CinematicScene';
import {ConceptCard} from './components/ConceptCard';
import {DebtSpiralVisualizer} from './components/DebtSpiralVisualizer';
import {FlowDiagram} from './components/FlowDiagram';
import {GrowthChart} from './components/GrowthChart';
import {MoneyFlowDiagram} from './components/MoneyFlowDiagram';
import {RiskCard} from './components/RiskCard';
import {SIPGrowthEngine} from './components/SIPGrowthEngine';
import {SplitComparison} from './components/SplitComparison';
import {StatCard} from './components/StatCard';
import {StepFlow} from './components/StepFlow';
import {StoryWorldOverlay} from './components/StoryWorldOverlay';
import {Beat, Scene} from './types';
import {timeToFrame} from './utils/timing';

const COMPONENT_MAP = {
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
	RiskCard,
	RiskCardScene: RiskCard,
	BalanceBar,
	MoneyFlowDiagram,
	DebtSpiralVisualizer,
	SIPGrowthEngine,
	CinematicScene,
} as const;

type Props = {
	scene: Scene;
};

const beatFrameRange = (beat: Beat, fps: number) => ({
	startFrame: timeToFrame(beat.start_time, fps),
	endFrame: timeToFrame(beat.end_time, fps),
});

export const SceneRenderer: React.FC<Props> = ({scene}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();

	const activeBeat = scene.beats.find((beat) => {
		const range = beatFrameRange(beat, fps);
		return range.startFrame <= frame && frame < range.endFrame;
	});

	if (!activeBeat) {
		return null;
	}

	const {startFrame, endFrame} = beatFrameRange(activeBeat, fps);
	const frameWithinBeat = frame - startFrame;
	const durationFrames = endFrame - startFrame;
	const hasCinematicIntent =
		scene.cinematic_intent && Object.keys(scene.cinematic_intent).length > 0;
	const hasStoryState =
		scene.story_state && Object.keys(scene.story_state).length > 0;
	const cinematicTextBeat =
		(hasCinematicIntent || hasStoryState) &&
		['StatCard', 'ConceptCard', 'ConceptCardScene', 'HighlightText'].includes(activeBeat.component);
	const Component = cinematicTextBeat
		? CinematicScene
		: COMPONENT_MAP[activeBeat.component as keyof typeof COMPONENT_MAP] ?? StatCard;
	const shouldOverlayStoryWorld = hasStoryState && !cinematicTextBeat;

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
