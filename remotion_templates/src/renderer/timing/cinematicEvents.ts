import {Beat, CinematicEvent, Scene} from '../../types';
import {currentSceneProgress} from './narrationTiming';

const isEvent = (value: unknown): value is CinematicEvent =>
	Boolean(value && typeof value === 'object' && !Array.isArray(value));

export const sceneCinematicEvents = (scene?: Scene, beat?: Beat): CinematicEvent[] => {
	const fromScene = Array.isArray(scene?.cinematic_events) ? scene?.cinematic_events ?? [] : [];
	if (fromScene.length > 0) {
		return fromScene.filter(isEvent);
	}
	const beatEvents = beat?.data?.cinematic_events;
	if (Array.isArray(beatEvents)) {
		return beatEvents.filter(isEvent);
	}
	const sceneData = scene?.data?.cinematic_events;
	if (Array.isArray(sceneData)) {
		return sceneData.filter(isEvent);
	}
	return [];
};

export const activeCinematicEvent = (
	scene: Scene | undefined,
	beat: Beat,
	frameWithinBeat: number,
	fps: number,
): CinematicEvent | null => {
	const events = sceneCinematicEvents(scene, beat);
	if (events.length === 0) {
		return null;
	}
	const progress = currentSceneProgress(scene, beat, frameWithinBeat, fps);
	const active = events
		.filter((event) => progress >= Number(event.start_progress ?? 0) && progress <= Number(event.end_progress ?? 0))
		.sort((a, b) => Number(b.start_progress ?? 0) - Number(a.start_progress ?? 0))[0];
	if (active) {
		return active;
	}
	const previous = events
		.filter((event) => Number(event.start_progress ?? 0) <= progress)
		.sort((a, b) => Number(b.start_progress ?? 0) - Number(a.start_progress ?? 0))[0];
	return previous ?? events[0] ?? null;
};

export const eventPresence = (progress: number, event: CinematicEvent | null) => {
	if (!event) {
		return 0;
	}
	const start = Number(event.start_progress ?? 0);
	const end = Number(event.end_progress ?? 1);
	if (progress < start || progress > end) {
		return 0;
	}
	const span = Math.max(0.001, end - start);
	const enterEnd = start + span * 0.28;
	const exitStart = start + span * 0.76;
	const enter = progress <= enterEnd ? (progress - start) / Math.max(0.001, enterEnd - start) : 1;
	const exit = progress >= exitStart ? 1 - (progress - exitStart) / Math.max(0.001, end - exitStart) * 0.28 : 1;
	return Math.max(0, Math.min(1, enter * exit));
};

export const eventColor = (event: CinematicEvent | null, fallback: string) => {
	const mode = String(event?.visual_mode ?? '');
	if (/expense|debt|shock|spiral|erosion|survivor/.test(mode)) {
		return '#E63946';
	}
	if (/single_bet/.test(mode)) {
		return '#E63946';
	}
	if (/growth|hero|protect|buffer|risk_spread|protection/.test(mode)) {
		return '#2EC4B6';
	}
	if (/salary|arrival|generic/.test(mode)) {
		return '#FF9F1C';
	}
	return fallback;
};
