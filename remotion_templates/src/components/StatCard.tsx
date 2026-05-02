import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {DISPLAY_FONT_FAMILY, BODY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, propText} from './visualUtils';

export const StatCard: React.FC<BeatComponentProps> = ({
	beat,
	frameWithinBeat,
	durationFrames,
}) => {
	const {fps} = useVideoConfig();
	const animationFrame = Math.min(frameWithinBeat, 12);
	const reveal = spring({
		frame: animationFrame,
		fps,
		config: beat.emphasis === 'hero' ? SPRINGS.impact : SPRINGS.entry,
		durationInFrames: 12,
	});
	const opacity = interpolate(animationFrame, [0, 12], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const scale = interpolate(reveal, [0, 1], [0.92, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const isHero = beat.emphasis === 'hero';
	const primaryValue = propText(beat.data, 'primary_value', beat.text);
	const label = propText(beat.data, 'label', beat.subtext || (isHero ? 'Key impact' : 'Core idea'));
	const accent = propText(beat.data, 'color', '').toLowerCase();
	const accentColor = accent === 'red' ? COLORS.danger : accent === 'teal' ? COLORS.positive : accent === 'orange' ? COLORS.warning : COLORS.accent_line;

	return (
		<AbsoluteFill
			style={{
				backgroundColor: COLORS.bg_deep,
				alignItems: 'center',
				justifyContent: 'center',
				padding: SPACING.safe,
				color: COLORS.text_primary,
			}}
		>
			<style>{FONT_FACES}</style>
			<div
				style={{
					position: 'absolute',
					left: 0,
					top: 0,
					bottom: 0,
					width: 8,
					background: accentColor,
					opacity: accent ? 1 : 0.75,
				}}
			/>
			<div
				style={{
					opacity,
					transform: `scale(${scale})`,
					textAlign: 'center',
					width: '100%',
					maxWidth: 1200,
				}}
			>
				<div
					style={{
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: isHero ? TYPE_SCALE.hero_value.size + 34 : TYPE_SCALE.hero_value.size + 12,
						fontWeight: TYPE_SCALE.hero_value.weight,
						letterSpacing: 0,
						lineHeight: 0.92,
						textTransform: 'uppercase',
					}}
				>
					{primaryValue}
				</div>
				{durationFrames > 45 ? (
					<div
						style={{
							marginTop: SPACING.lg,
							fontFamily: BODY_FONT_FAMILY,
							fontSize: TYPE_SCALE.label.size,
							fontWeight: TYPE_SCALE.label.weight,
							color: COLORS.text_secondary,
						}}
					>
						{label}
					</div>
				) : null}
			</div>
		</AbsoluteFill>
	);
};
