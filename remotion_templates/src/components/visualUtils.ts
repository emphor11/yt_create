import {Beat, Scene} from '../types';

export const COLORS = {
	bg_deep: '#0A0A14',
	bg_surface: '#12121F',
	bg_elevated: '#1A1A2E',
	positive: '#2EC4B6',
	warning: '#FF9F1C',
	danger: '#E63946',
	neutral: '#4361EE',
	text_primary: '#FFFFFF',
	text_secondary: 'rgba(255,255,255,0.6)',
	text_tertiary: 'rgba(255,255,255,0.35)',
	accent_line: '#FF9F1C',
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

export type ColorPalette = typeof COLORS;

export const TYPE_SCALE = {
	hero_value: {size: 120, weight: 900, font: 'Anton'},
	major_value: {size: 88, weight: 900, font: 'Anton'},
	label: {size: 36, weight: 700, font: 'Nunito'},
	subtext: {size: 28, weight: 600, font: 'Nunito'},
	micro: {size: 20, weight: 400, font: 'Nunito'},
};

export type TypeScale = typeof TYPE_SCALE;

export const SPRINGS = {
	entry: {damping: 18, stiffness: 200, mass: 0.8},
	counter: {damping: 25, stiffness: 150, mass: 1},
	impact: {damping: 12, stiffness: 300, mass: 0.6},
	exit: {damping: 22, stiffness: 180, mass: 1},
};

export type SpringConfigs = typeof SPRINGS;

export const SPACING = {
	unit: 8,
	safe: 120,
	xs: 8,
	sm: 16,
	md: 24,
	lg: 32,
	xl: 48,
	xxl: 64,
};

export type SpacingSystem = typeof SPACING;

export const getAccentColor = (color = '', sentiment = ''): string => {
	const key = `${color} ${sentiment}`.toLowerCase();
	if (key.includes('red') || key.includes('danger') || key.includes('negative')) {
		return COLORS.danger;
	}
	if (key.includes('teal') || key.includes('positive') || key.includes('growth')) {
		return COLORS.positive;
	}
	if (key.includes('blue') || key.includes('neutral')) {
		return COLORS.neutral;
	}
	return COLORS.warning;
};

export const formatIndianRupee = (amount: number): string => {
	if (!Number.isFinite(amount)) {
		return '₹0';
	}
	const rounded = Math.round(amount);
	const sign = rounded < 0 ? '-' : '';
	let digits = String(Math.abs(rounded));
	if (digits.length <= 3) {
		return `${sign}₹${digits}`;
	}
	const lastThree = digits.slice(-3);
	digits = digits.slice(0, -3);
	const head = digits.replace(/\B(?=(\d{2})+(?!\d))/g, ',');
	return `${sign}₹${head},${lastThree}`;
};

export const getBeatProgress = (frame: number, durationFrames: number): number => {
	if (durationFrames <= 0) {
		return 1;
	}
	return Math.max(0, Math.min(frame / durationFrames, 1));
};

export const getEntryProgress = (frame: number, entryDurationFrames = 15): number => {
	if (entryDurationFrames <= 0) {
		return 1;
	}
	return Math.max(0, Math.min(frame / entryDurationFrames, 1));
};

export function getBeatData<T>(beat: Beat, fallbackKey?: string): T | null {
	if (beat.data) {
		return beat.data as T;
	}
	if (fallbackKey && beat.props?.[fallbackKey]) {
		return beat.props[fallbackKey] as T;
	}
	return null;
}

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

export type VisualNode = {
	label: string;
	value?: string;
	subtext?: string;
	color?: string;
};

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

export const visualNodes = (beat: Beat, scene?: Scene): VisualNode[] => {
	const propNodes = beat.props?.nodes;
	const dataNodes = scene?.data?.nodes;
	const raw = Array.isArray(propNodes) ? propNodes : Array.isArray(dataNodes) ? dataNodes : undefined;
	if (raw && raw.length > 0) {
		return raw
			.map((node) => {
				if (typeof node === 'string' || typeof node === 'number') {
					return {label: String(node)};
				}
				if (node && typeof node === 'object') {
					const item = node as Record<string, unknown>;
					return {
						label: propText(item, 'label', propText(item, 'text', propText(item, 'value', 'Money'))),
						value: propText(item, 'value'),
						subtext: propText(item, 'subtext'),
						color: propText(item, 'color'),
					};
				}
				return {label: ''};
			})
			.filter((node) => node.label || node.value)
			.slice(0, 5);
	}
	return stepLabels(beat, scene).map((label) => ({label}));
};

export const sceneValues = (scene?: Scene): string[] => {
	const values = scene?.data?.values;
	if (Array.isArray(values)) {
		return values.map((value) => String(value).trim()).filter(Boolean).slice(0, 4);
	}
	return [];
};
