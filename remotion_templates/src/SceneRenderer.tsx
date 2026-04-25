import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {CalculationStrip} from './components/CalculationStrip';
import {StatCard} from './components/StatCard';
import {Beat, Scene} from './types';
import {timeToFrame} from './utils/timing';

const COMPONENT_MAP = {
	StatCard,
	CalculationStrip,
	ConceptCardScene: StatCard,
	SplitComparisonScene: StatCard,
	StepFlowScene: StatCard,
	GrowthChartScene: StatCard,
	RiskCardScene: StatCard,
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
	const Component =
		COMPONENT_MAP[activeBeat.component as keyof typeof COMPONENT_MAP] ?? StatCard;

	return (
		<Component
			beat={activeBeat}
			frameWithinBeat={frameWithinBeat}
			durationFrames={durationFrames}
		/>
	);
};
