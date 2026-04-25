import {Scene} from '../types';

export const timeToFrame = (seconds: number, fps: number): number => {
	return Math.floor(seconds * fps);
};

export const sceneToFrameRange = (
	scenes: Scene[],
	index: number,
	fps: number,
): {startFrame: number; endFrame: number; durationInFrames: number} => {
	let startFrame = 0;
	for (let i = 0; i < index; i++) {
		startFrame += timeToFrame(scenes[i].duration ?? scenes[i].total_duration ?? 0, fps);
	}
	const durationInFrames = timeToFrame(
		scenes[index].duration ?? scenes[index].total_duration ?? 0,
		fps,
	);
	return {
		startFrame,
		endFrame: startFrame + durationInFrames,
		durationInFrames,
	};
};

export const calculateTotalFrames = (scenes: Scene[], fps: number): number => {
	return scenes.reduce((total, scene) => {
		return total + timeToFrame(scene.duration ?? scene.total_duration ?? 0, fps);
	}, 0);
};
