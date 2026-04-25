import React from 'react';
import {Composition} from 'remotion';
import {VideoRenderer} from './VideoRenderer';
import {calculateTotalFrames} from './utils/timing';

const FPS = 30;

export const Root: React.FC = () => {
	return (
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
	);
};
