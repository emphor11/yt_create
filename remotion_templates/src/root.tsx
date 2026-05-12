import React from 'react';
import {Composition} from 'remotion';
import {EndCard, IntroCard, SceneTransition, ThumbnailFrame} from './templates';
import {VideoRenderer} from './VideoRenderer';
import {calculateTotalFrames} from './utils/timing';
import {visualEventFixtureScenes} from './visualEventFixtures';

const FPS = 30;

export const Root: React.FC = () => {
	return (
		<>
			<Composition
				id="VideoRenderer"
				component={VideoRenderer}
				width={1920}
				height={1080}
				fps={FPS}
				durationInFrames={FPS}
				defaultProps={{scenes: []}}
				calculateMetadata={({props}) => ({
					durationInFrames: Math.max(calculateTotalFrames(props.scenes, FPS), 1),
				})}
			/>
			<Composition
				id="VisualEventFixtures"
				component={VideoRenderer}
				width={1920}
				height={1080}
				fps={FPS}
				durationInFrames={FPS}
				defaultProps={{scenes: visualEventFixtureScenes}}
				calculateMetadata={({props}) => ({
					durationInFrames: Math.max(calculateTotalFrames(props.scenes, FPS), 1),
				})}
			/>
			<Composition
				id="IntroCard"
				component={IntroCard}
				width={1920}
				height={1080}
				fps={FPS}
				durationInFrames={FPS * 3}
				defaultProps={{title: 'YTCreate'}}
			/>
			<Composition
				id="SceneTransition"
				component={SceneTransition}
				width={1920}
				height={1080}
				fps={FPS}
				durationInFrames={Math.round(FPS * 0.5)}
				defaultProps={{label: 'Next'}}
			/>
			<Composition
				id="EndCard"
				component={EndCard}
				width={1920}
				height={1080}
				fps={FPS}
				durationInFrames={FPS * 5}
				defaultProps={{message: 'Subscribe for more finance insights'}}
			/>
			<Composition
				id="ThumbnailFrame"
				component={ThumbnailFrame}
				width={1280}
				height={720}
				fps={FPS}
				durationInFrames={1}
				defaultProps={{dominantText: 'YTCreate', supportingText: 'Finance explained', brand: 'YTCreate', variant: 1}}
			/>
		</>
	);
};
