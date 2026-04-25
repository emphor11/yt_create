import React from 'react';
import {Audio, Sequence, staticFile, useVideoConfig} from 'remotion';
import {SceneRenderer} from './SceneRenderer';
import {VideoSpec} from './types';
import {sceneToFrameRange} from './utils/timing';

type Props = VideoSpec;

const toAudioSrc = (audioFile: string): string => {
	if (audioFile.startsWith('http://') || audioFile.startsWith('https://')) {
		return audioFile;
	}
	if (audioFile.startsWith('/')) {
		return `file://${audioFile}`;
	}
	return staticFile(audioFile);
};

export const VideoRenderer: React.FC<Props> = ({scenes}) => {
	const {fps} = useVideoConfig();

	return (
		<>
			{scenes.map((scene, index) => {
				const range = sceneToFrameRange(scenes, index, fps);
				return (
					<Sequence
						key={scene.id ?? scene.scene_id ?? `${scene.pattern}-${index}`}
						from={range.startFrame}
						durationInFrames={range.durationInFrames}
					>
						<Audio src={toAudioSrc(scene.audio_file)} />
						<SceneRenderer scene={scene} />
					</Sequence>
				);
			})}
		</>
	);
};
