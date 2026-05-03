import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, TYPE_SCALE} from './visualUtils';

type Intent = {
	visual_mode?: string;
	human_action?: string;
	metaphor?: string;
	overlay_text?: string;
	motion_treatment?: string;
	asset_query?: string;
	texture?: string;
};

const intentFromScene = (scene: BeatComponentProps['scene']): Intent =>
	(scene?.cinematic_intent ?? {}) as Intent;

const accentForIntent = (intent: Intent): string => {
	const joined = `${intent.motion_treatment ?? ''} ${intent.metaphor ?? ''}`.toLowerCase();
	if (joined.includes('erosion') || joined.includes('debt') || joined.includes('panic') || joined.includes('leak')) {
		return COLORS.danger;
	}
	if (joined.includes('compound') || joined.includes('growth') || joined.includes('calm')) {
		return COLORS.positive;
	}
	return COLORS.warning;
};

export const CinematicScene: React.FC<BeatComponentProps> = ({
	beat,
	scene,
	frameWithinBeat,
	durationFrames,
}) => {
	const {fps} = useVideoConfig();
	const intent = intentFromScene(scene);
	const treatment = String(intent.motion_treatment ?? 'slow_push');
	const accent = accentForIntent(intent);
	const reveal = spring({
		frame: Math.min(frameWithinBeat, 18),
		fps,
		config: {damping: 18, stiffness: 170, mass: 0.9},
		durationInFrames: 18,
	});
	const progress = interpolate(frameWithinBeat, [0, Math.max(durationFrames - 1, 1)], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const title = String(
		beat.emphasis === 'hero' ? intent.overlay_text || beat.text : beat.text || intent.overlay_text || ''
	).toUpperCase();
	const subtitle = String(
		beat.emphasis === 'hero' ? intent.metaphor || '' : intent.metaphor || ''
	).toUpperCase();

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.bg_deep, color: COLORS.text_primary, overflow: 'hidden'}}>
			<style>{FONT_FACES}</style>
			<CinematicBackground progress={progress} accent={accent} treatment={treatment} />
			<CinematicObject progress={progress} accent={accent} treatment={treatment} intent={intent} />
			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					right: SPACING.safe,
					bottom: 116,
					borderLeft: `8px solid ${accent}`,
					paddingLeft: SPACING.xl,
					opacity: interpolate(frameWithinBeat, [0, 12], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					}),
					transform: `translateY(${(1 - reveal) * 26}px)`,
				}}
			>
				<div
					style={{
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: beat.emphasis === 'hero' ? TYPE_SCALE.hero_value.size : TYPE_SCALE.major_value.size,
						lineHeight: 0.9,
						maxWidth: 1180,
						textTransform: 'uppercase',
					}}
				>
					{title}
				</div>
				{subtitle ? (
					<div
						style={{
							marginTop: SPACING.lg,
							fontFamily: BODY_FONT_FAMILY,
							fontSize: TYPE_SCALE.subtext.size,
							fontWeight: 800,
							color: COLORS.text_secondary,
							maxWidth: 980,
						}}
					>
						{subtitle}
					</div>
				) : null}
			</div>
			<FilmGrain />
		</AbsoluteFill>
	);
};

const CinematicBackground: React.FC<{progress: number; accent: string; treatment: string}> = ({
	progress,
	accent,
	treatment,
}) => {
	const push = treatment === 'dolly_zoom' ? progress * 48 : progress * 24;
	return (
		<AbsoluteFill>
			<div
				style={{
					position: 'absolute',
					inset: -80,
					background: `radial-gradient(circle at ${30 + progress * 18}% 35%, ${accent}33, transparent 28%), linear-gradient(120deg, #090912, #111422 55%, #07070d)`,
					transform: `scale(${1.03 + progress * 0.04}) translateX(${-push}px)`,
				}}
			/>
			<div
				style={{
					position: 'absolute',
					inset: 0,
					background: 'linear-gradient(90deg, rgba(0,0,0,0.72), rgba(0,0,0,0.18) 52%, rgba(0,0,0,0.72))',
				}}
			/>
		</AbsoluteFill>
	);
};

const CinematicObject: React.FC<{progress: number; accent: string; treatment: string; intent: Intent}> = ({
	progress,
	accent,
	treatment,
	intent,
}) => {
	if (treatment === 'notification_stack') {
		return <NotificationStack progress={progress} accent={accent} />;
	}
	if (treatment === 'value_erosion') {
		return <ValueErosion progress={progress} accent={accent} />;
	}
	if (String(intent.metaphor ?? '').toLowerCase().includes('portfolio')) {
		return <PortfolioGrid progress={progress} accent={accent} />;
	}
	return <PhoneSilhouette progress={progress} accent={accent} />;
};

const PhoneSilhouette: React.FC<{progress: number; accent: string}> = ({progress, accent}) => (
	<div
		style={{
			position: 'absolute',
			right: 190,
			top: 120,
			width: 390,
			height: 700,
			borderRadius: 52,
			border: `3px solid ${accent}88`,
			background: 'rgba(255,255,255,0.045)',
			boxShadow: `0 0 80px ${accent}33`,
			transform: `rotate(-7deg) translateY(${progress * -28}px)`,
		}}
	>
		<div style={{position: 'absolute', left: 50, right: 50, top: 80, height: 28, borderRadius: 99, background: `${accent}99`}} />
		{[0, 1, 2].map((index) => (
			<div
				key={index}
				style={{
					position: 'absolute',
					left: 44,
					right: 44,
					top: 170 + index * 120,
					height: 72,
					borderRadius: 18,
					background: 'rgba(255,255,255,0.08)',
					border: '1px solid rgba(255,255,255,0.16)',
				}}
			/>
		))}
	</div>
);

const NotificationStack: React.FC<{progress: number; accent: string}> = ({progress, accent}) => (
	<div style={{position: 'absolute', right: 160, top: 170, width: 620}}>
		{['SALARY CREDIT', 'EMI AUTO-DEBIT', 'RENT PAID', 'BALANCE LOW'].map((label, index) => {
			const local = Math.max(0, Math.min((progress * 5 - index) / 1.2, 1));
			return (
				<div
					key={label}
					style={{
						marginBottom: 24,
						height: 92,
						borderRadius: 18,
						padding: '22px 30px',
						background: index === 0 ? 'rgba(46,196,182,0.18)' : 'rgba(255,255,255,0.08)',
						border: `2px solid ${index === 0 ? COLORS.positive : accent}`,
						fontFamily: BODY_FONT_FAMILY,
						fontSize: 28,
						fontWeight: 900,
						letterSpacing: 0,
						opacity: local,
						transform: `translateX(${(1 - local) * 130}px)`,
					}}
				>
					{label}
				</div>
			);
		})}
	</div>
);

const ValueErosion: React.FC<{progress: number; accent: string}> = ({progress, accent}) => (
	<div style={{position: 'absolute', right: 130, top: 180, width: 680, height: 440}}>
		<div style={{position: 'absolute', left: 0, bottom: 60, width: 620, height: 4, background: COLORS.stroke}} />
		<div
			style={{
				position: 'absolute',
				left: 0,
				top: 70 + progress * 210,
				width: 560 * progress,
				height: 14,
				background: accent,
				transform: 'rotate(18deg)',
				transformOrigin: 'left center',
				boxShadow: `0 0 50px ${accent}`,
			}}
		/>
		<div
			style={{
				position: 'absolute',
				right: 40,
				bottom: 86,
				width: 210,
				height: 210 - progress * 90,
				border: `3px solid ${accent}`,
				background: 'rgba(255,255,255,0.055)',
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'center',
				fontFamily: DISPLAY_FONT_FAMILY,
				fontSize: 46,
			}}
		>
			BASKET
		</div>
	</div>
);

const PortfolioGrid: React.FC<{progress: number; accent: string}> = ({progress, accent}) => (
	<div style={{position: 'absolute', right: 160, top: 170, width: 560, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 22}}>
		{Array.from({length: 9}).map((_, index) => {
			const local = Math.max(0.18, Math.min((progress * 10 - index) / 2, 1));
			return (
				<div
					key={index}
					style={{
						height: 130,
						borderRadius: 16,
						background: `rgba(255,255,255,${0.04 + local * 0.08})`,
						border: `2px solid ${index === 4 ? accent : COLORS.stroke}`,
						opacity: local,
					}}
				/>
			);
		})}
	</div>
);

const FilmGrain: React.FC = () => (
	<AbsoluteFill
		style={{
			pointerEvents: 'none',
			opacity: 0.13,
			backgroundImage:
				'radial-gradient(rgba(255,255,255,0.18) 0.8px, transparent 0.8px), radial-gradient(rgba(255,255,255,0.10) 0.8px, transparent 0.8px)',
			backgroundPosition: '0 0, 13px 17px',
			backgroundSize: '28px 28px',
			mixBlendMode: 'screen',
		}}
	/>
);
