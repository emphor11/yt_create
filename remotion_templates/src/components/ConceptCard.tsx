import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {beatSubtitle, beatTitle, COLORS} from './visualUtils';

export const ConceptCard: React.FC<BeatComponentProps> = ({beat, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const reveal = spring({
		frame: Math.min(frameWithinBeat, 16),
		fps,
		config: {damping: 16, stiffness: 160},
		durationInFrames: 16,
	});
	const opacity = interpolate(frameWithinBeat, [0, 12], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const title = beatTitle(beat).toUpperCase();
	const subtitle = beatSubtitle(beat);
	const accent = beat.emphasis === 'hero' ? COLORS.orange : COLORS.blue;

	return (
		<AbsoluteFill
			style={{
				backgroundColor: COLORS.background,
				color: COLORS.text,
				justifyContent: 'center',
				padding: 120,
			}}
		>
			<style>{FONT_FACES}</style>
			<div
				style={{
					opacity,
					transform: `translateY(${(1 - reveal) * 34}px) scale(${0.96 + reveal * 0.04})`,
					borderLeft: `10px solid ${accent}`,
					padding: '28px 0 28px 46px',
					maxWidth: 1320,
				}}
			>
				<div
					style={{
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: beat.emphasis === 'hero' ? 136 : 116,
						lineHeight: 0.92,
						textTransform: 'uppercase',
					}}
				>
					{title}
				</div>
				{subtitle ? (
					<div
						style={{
							marginTop: 28,
							fontFamily: BODY_FONT_FAMILY,
							fontSize: 40,
							fontWeight: 800,
							color: COLORS.muted,
							maxWidth: 960,
						}}
					>
						{subtitle}
					</div>
				) : null}
			</div>
		</AbsoluteFill>
	);
};

