import {BeatComponentProps} from '../contracts/componentTypes';

export type TimedSentence = {
	text: string;
	startProgress: number;
	endProgress: number;
};

export const sceneNarrationText = (scene: BeatComponentProps['scene']): string => {
	const direct = String(scene?.narration ?? scene?.text ?? '').trim();
	if (direct) {
		return direct;
	}
	return (scene?.beats ?? [])
		.map((item) => String(item.source_text ?? item.text ?? '').trim())
		.filter(Boolean)
		.join(' ');
};

export const sceneDurationSeconds = (scene: BeatComponentProps['scene'], beat: BeatComponentProps['beat']) => {
	const explicit = Number(scene?.duration ?? scene?.total_duration);
	if (Number.isFinite(explicit) && explicit > 0) {
		return explicit;
	}
	const beatEnd = Math.max(...(scene?.beats ?? [beat]).map((item) => Number(item.end_time ?? 0)));
	return Number.isFinite(beatEnd) && beatEnd > 0 ? beatEnd : Math.max(Number(beat.end_time ?? 0), 1);
};

const wordCount = (text: string) => text.match(/[A-Za-z0-9₹,]+/g)?.length ?? 0;

export const narrationSentences = (text: string): TimedSentence[] => {
	const sentences = text
		.split(/(?<=[.!?])\s+/)
		.map((item) => item.trim())
		.filter(Boolean);
	const totalWords = sentences.reduce((sum, sentence) => sum + wordCount(sentence), 0) || 1;
	let cursor = 0;
	return sentences.map((sentence) => {
		const duration = wordCount(sentence) / totalWords;
		const timed = {
			text: sentence,
			startProgress: cursor,
			endProgress: Math.min(1, cursor + duration),
		};
		cursor = timed.endProgress;
		return timed;
	});
};

export const firstKeywordIndex = (text: string, keywords: string[]) => {
	const lowered = text.toLowerCase();
	const hits = keywords.map((keyword) => lowered.indexOf(keyword.toLowerCase())).filter((index) => index >= 0);
	return hits.length > 0 ? Math.min(...hits) : -1;
};

export const currentSceneProgress = (
	scene: BeatComponentProps['scene'],
	beat: BeatComponentProps['beat'],
	frameWithinBeat: number,
	fps: number,
) => {
	const seconds = Number(beat.start_time ?? 0) + frameWithinBeat / fps;
	return Math.max(0, Math.min(seconds / sceneDurationSeconds(scene, beat), 1));
};
