import {Beat, Scene} from '../types';

export interface BeatComponentProps {
	beat: Beat;
	scene?: Scene;
	frameWithinBeat: number;
	durationFrames: number;
}
