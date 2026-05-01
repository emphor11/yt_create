import {Beat, Scene} from '../types';

export const COLORS = {
	background: '#0A0A14',
	panel: 'rgba(255,255,255,0.075)',
	panelStrong: 'rgba(255,255,255,0.12)',
	stroke: 'rgba(255,255,255,0.18)',
	text: '#FFFFFF',
	muted: 'rgba(255,255,255,0.68)',
	dim: 'rgba(255,255,255,0.42)',
	orange: '#FF9F1C',
	teal: '#2EC4B6',
	red: '#E63946',
	blue: '#4361EE',
};

export const propText = (
	source: Record<string, unknown> | undefined,
	key: string,
	fallback = ''
): string => {
	const value = source?.[key];
	return typeof value === 'string' || typeof value === 'number'
		? String(value).trim()
		: fallback;
};

export const sceneText = (scene: Scene | undefined, key: string, fallback = ''): string =>
	propText(scene?.data, key, fallback);

export const beatTitle = (beat: Beat): string =>
	propText(beat.props, 'title', beat.text || 'Core idea');

export const beatSubtitle = (beat: Beat, fallback = ''): string =>
	propText(beat.props, 'subtitle', beat.subtext || fallback);

export const compactWords = (text: string, fallback = 'Money'): string => {
	const words = text
		.replace(/\s+/g, ' ')
		.trim()
		.split(' ')
		.filter(Boolean);
	return (words.length > 4 ? words.slice(0, 4).join(' ') : words.join(' ')) || fallback;
};

export const splitComparisonText = (text: string): {left: string; right: string} => {
	const clean = text.replace(/\s+/g, ' ').trim();
	const parts = clean.split(/\s+(?:vs|versus|but|instead of|to)\s+/i);
	if (parts.length >= 2) {
		return {left: compactWords(parts[0], 'Before'), right: compactWords(parts[1], 'After')};
	}
	const words = clean.split(' ').filter(Boolean);
	const midpoint = Math.max(1, Math.ceil(words.length / 2));
	return {
		left: compactWords(words.slice(0, midpoint).join(' '), 'Before'),
		right: compactWords(words.slice(midpoint).join(' '), 'After'),
	};
};

export const stepLabels = (beat: Beat, scene?: Scene): string[] => {
	const propSteps = beat.props?.steps;
	const dataSteps = scene?.data?.steps;
	const raw = Array.isArray(propSteps) ? propSteps : Array.isArray(dataSteps) ? dataSteps : beat.steps;
	if (Array.isArray(raw) && raw.length > 0) {
		return raw
			.map((step) => {
				if (typeof step === 'string' || typeof step === 'number') {
					return String(step);
				}
				if (step && typeof step === 'object') {
					const item = step as Record<string, unknown>;
					return propText(item, 'label', propText(item, 'value', propText(item, 'text')));
				}
				return '';
			})
			.map((label) => compactWords(label))
			.filter(Boolean)
			.slice(0, 5);
	}
	const pieces = beat.text.split(/\s*(?:->|>|,|\|)\s*/).filter(Boolean);
	if (pieces.length >= 2) {
		return pieces.map((piece) => compactWords(piece)).slice(0, 5);
	}
	return [compactWords(beat.text, 'Start'), compactWords(beat.subtext || 'Result', 'Result')];
};

export const sceneValues = (scene?: Scene): string[] => {
	const values = scene?.data?.values;
	if (Array.isArray(values)) {
		return values.map((value) => String(value).trim()).filter(Boolean).slice(0, 4);
	}
	return [];
};
