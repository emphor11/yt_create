import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY} from '../fonts';
import {Beat, Scene} from '../types';
import {COLORS, SPACING} from './visualUtils';

type StoryState = {
	scene_role?: string;
	protagonist_state?: string;
	active_objects?: string[];
	state_change?: {
		money?: {from?: string; to?: string; change_label?: string};
		emotion?: {from?: string; to?: string};
		risk?: {from?: string; to?: string};
	};
	callback_from?: string | null;
	callback_to?: string | null;
	visual_question?: string;
	visual_answer?: string;
};

type Props = {
	scene: Scene;
	beat: Beat;
	frameWithinBeat: number;
	durationFrames: number;
};

const storyStateFrom = (scene: Scene): StoryState => (scene.story_state ?? {}) as StoryState;

const activeObjects = (storyState: StoryState): string[] =>
	Array.isArray(storyState.active_objects)
		? storyState.active_objects.map((item) => String(item))
		: [];

const objectLabel = (object: string): string =>
	(
		{
			phone_account: 'Account',
			salary_balance: 'Salary',
			emi_stack: 'Fixed payments',
			debt_pressure: 'Debt',
			inflation_basket: 'Buying power',
			sip_jar: 'SIP growth',
			portfolio_grid: 'Portfolio',
			emergency_buffer: 'Safety buffer',
		} as Record<string, string>
	)[object] ?? object.replace(/_/g, ' ');

const accentFor = (storyState: StoryState): string => {
	const joined = `${storyState.protagonist_state ?? ''} ${storyState.scene_role ?? ''} ${activeObjects(storyState).join(' ')}`.toLowerCase();
	if (joined.includes('emi') || joined.includes('debt') || joined.includes('stressed')) {
		return COLORS.danger;
	}
	if (joined.includes('sip') || joined.includes('portfolio') || joined.includes('buffer') || joined.includes('disciplined')) {
		return COLORS.positive;
	}
	if (joined.includes('inflation')) {
		return COLORS.warning;
	}
	return COLORS.neutral;
};

const objectGlyph = (object: string, accent: string, progress: number): React.ReactNode => {
	if (object === 'sip_jar') {
		return (
			<div style={styles.jar(accent)}>
				<div style={{...styles.jarFill(accent), height: `${28 + progress * 58}%`}} />
			</div>
		);
	}
	if (object === 'emergency_buffer') {
		return <div style={styles.shield(accent)}>BUFFER</div>;
	}
	if (object === 'portfolio_grid') {
		return (
			<div style={styles.grid}>
				{Array.from({length: 9}).map((_, index) => (
					<div key={index} style={{...styles.gridCell, borderColor: index === 4 ? accent : COLORS.stroke}} />
				))}
			</div>
		);
	}
	if (object === 'emi_stack') {
		return (
			<div style={styles.stack}>
				{['EMI', 'RENT', 'LOW'].map((label, index) => (
					<div key={label} style={{...styles.stackItem(accent), transform: `translateX(${index * 18}px)`}}>
						{label}
					</div>
				))}
			</div>
		);
	}
	if (object === 'inflation_basket') {
		return <div style={styles.basket(accent)}>BASKET</div>;
	}
	if (object === 'debt_pressure') {
		return <div style={styles.pressure(accent)}>DEBT</div>;
	}
	return <div style={styles.account(accent)}>₹</div>;
};

export const StoryWorldOverlay: React.FC<Props> = ({scene, beat, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const storyState = storyStateFrom(scene);
	const objects = activeObjects(storyState);
	if (objects.length === 0) {
		return null;
	}

	const accent = accentFor(storyState);
	const progress = interpolate(frameWithinBeat, [0, Math.max(durationFrames - 1, 1)], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const entry = spring({
		frame: Math.min(frameWithinBeat, 16),
		fps,
		config: {damping: 18, stiffness: 190, mass: 0.8},
		durationInFrames: 16,
	});
	const primaryObject = objects[0];
	const money = storyState.state_change?.money ?? {};
	const risk = storyState.state_change?.risk ?? {};
	const title = storyState.visual_answer || beat.text || objectLabel(primaryObject);
	const subtitle = money.change_label || storyState.visual_question || risk.to || storyState.scene_role || '';

	return (
		<AbsoluteFill style={{pointerEvents: 'none'}}>
			<div
				style={{
					...styles.panel,
					borderColor: `${accent}99`,
					boxShadow: `0 0 58px ${accent}24`,
					opacity: entry,
					transform: `translateY(${(1 - entry) * 24}px)`,
				}}
			>
				<div style={styles.objectRow}>
					{objectGlyph(primaryObject, accent, progress)}
					<div>
						<div style={styles.objectName}>{objectLabel(primaryObject).toUpperCase()}</div>
						<div style={{...styles.role, color: accent}}>{String(storyState.protagonist_state || storyState.scene_role || 'state').toUpperCase()}</div>
					</div>
				</div>
				<div style={styles.answer}>{String(title).toUpperCase()}</div>
				{subtitle ? <div style={styles.subtitle}>{String(subtitle).toUpperCase()}</div> : null}
				{money.from || money.to ? (
					<div style={styles.moneyRow}>
						<div>{money.from || 'START'}</div>
						<div style={{color: accent}}>→</div>
						<div>{money.to || 'END'}</div>
					</div>
				) : null}
			</div>
		</AbsoluteFill>
	);
};

const styles = {
	panel: {
		position: 'absolute' as const,
		right: SPACING.safe,
		bottom: 72,
		width: 430,
		minHeight: 210,
		borderRadius: 26,
		border: '2px solid rgba(255,255,255,0.18)',
		background: 'linear-gradient(150deg, rgba(18,18,31,0.78), rgba(10,10,20,0.64))',
		backdropFilter: 'blur(8px)',
		padding: 28,
		color: COLORS.text_primary,
	},
	objectRow: {
		display: 'flex',
		gap: 18,
		alignItems: 'center',
	},
	objectName: {
		fontFamily: BODY_FONT_FAMILY,
		fontSize: 22,
		fontWeight: 900,
		color: COLORS.text_secondary,
	},
	role: {
		marginTop: 5,
		fontFamily: BODY_FONT_FAMILY,
		fontSize: 20,
		fontWeight: 900,
	},
	answer: {
		marginTop: 20,
		fontFamily: DISPLAY_FONT_FAMILY,
		fontSize: 36,
		lineHeight: 0.92,
		maxWidth: 370,
	},
	subtitle: {
		marginTop: 14,
		fontFamily: BODY_FONT_FAMILY,
		fontSize: 20,
		fontWeight: 900,
		lineHeight: 1.15,
		color: COLORS.text_secondary,
	},
	moneyRow: {
		marginTop: 20,
		display: 'flex',
		gap: 14,
		alignItems: 'center',
		fontFamily: BODY_FONT_FAMILY,
		fontSize: 24,
		fontWeight: 900,
	},
	account: (accent: string) => ({
		width: 72,
		height: 72,
		borderRadius: 18,
		border: `3px solid ${accent}`,
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'center',
		fontFamily: DISPLAY_FONT_FAMILY,
		fontSize: 48,
		color: accent,
	}),
	jar: (accent: string) => ({
		position: 'relative' as const,
		width: 72,
		height: 84,
		borderRadius: '14px 14px 26px 26px',
		border: `3px solid ${accent}`,
		overflow: 'hidden',
	}),
	jarFill: (accent: string) => ({
		position: 'absolute' as const,
		left: 0,
		right: 0,
		bottom: 0,
		background: `${accent}cc`,
	}),
	shield: (accent: string) => ({
		width: 82,
		height: 82,
		borderRadius: '42px 42px 18px 18px',
		border: `3px solid ${accent}`,
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'center',
		fontFamily: BODY_FONT_FAMILY,
		fontSize: 15,
		fontWeight: 900,
		color: accent,
	}),
	grid: {
		width: 82,
		display: 'grid',
		gridTemplateColumns: 'repeat(3, 1fr)',
		gap: 5,
	},
	gridCell: {
		width: 22,
		height: 22,
		border: '2px solid rgba(255,255,255,0.18)',
		background: 'rgba(255,255,255,0.06)',
	},
	stack: {
		width: 96,
		height: 78,
		position: 'relative' as const,
	},
	stackItem: (accent: string) => ({
		height: 28,
		width: 72,
		marginBottom: 5,
		borderRadius: 8,
		border: `2px solid ${accent}`,
		background: 'rgba(255,255,255,0.08)',
		fontFamily: BODY_FONT_FAMILY,
		fontSize: 13,
		fontWeight: 900,
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'center',
	}),
	basket: (accent: string) => ({
		width: 86,
		height: 64,
		border: `3px solid ${accent}`,
		borderTop: 'none',
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'center',
		fontFamily: BODY_FONT_FAMILY,
		fontSize: 13,
		fontWeight: 900,
		color: accent,
	}),
	pressure: (accent: string) => ({
		width: 84,
		height: 68,
		borderRadius: 16,
		border: `3px solid ${accent}`,
		display: 'flex',
		alignItems: 'center',
		justifyContent: 'center',
		fontFamily: DISPLAY_FONT_FAMILY,
		fontSize: 26,
		color: accent,
	}),
};
