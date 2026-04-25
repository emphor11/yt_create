import {Beat} from '../types';

export interface BeatComponentProps {
	beat: Beat;
	frameWithinBeat: number;
	durationFrames: number;
}
