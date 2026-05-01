import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {beatSubtitle, beatTitle, COLORS} from './visualUtils';

export const RiskCard: React.FC<BeatComponentProps> = ({beat, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const pulse = Math.sin(frameWithinBeat / 7) * 0.5 + 0.5;
	const reveal = spring({
		frame: Math.min(frameWithinBeat, 14),
		fps,
		config: {damping: 13, stiffness: 170},
		durationInFrames: 14,
	});
	const opacity = interpolate(frameWithinBeat, [0, 10], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const title = beatTitle(beat).toUpperCase();
	const subtitle = beatSubtitle(beat, 'Risk rising');

	return (
		<AbsoluteFill
			style={{
				background: `radial-gradient(circle at center, rgba(230,57,70,${0.18 + pulse * 0.06}), ${COLORS.background} 58%)`,
				color: COLORS.text,
				alignItems: 'center',
				justifyContent: 'center',
				padding: 110,
			}}
		>
			<style>{FONT_FACES}</style>
			<div
				style={{
					opacity,
					transform: `scale(${0.9 + reveal * 0.1})`,
					width: '86%',
					border: `3px solid rgba(230,57,70,${0.5 + pulse * 0.25})`,
					background: 'rgba(230,57,70,0.08)',
					padding: '72px 86px',
					textAlign: 'center',
				}}
			>
				<div style={{fontFamily: BODY_FONT_FAMILY, fontSize: 34, fontWeight: 900, color: COLORS.red}}>
					RISK SIGNAL
				</div>
				<div
					style={{
						marginTop: 18,
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: beat.emphasis === 'hero' ? 146 : 124,
						lineHeight: 0.9,
						textTransform: 'uppercase',
					}}
				>
					{title}
				</div>
				<div
					style={{
						marginTop: 30,
						fontFamily: BODY_FONT_FAMILY,
						fontSize: 38,
						fontWeight: 800,
						color: COLORS.muted,
					}}
				>
					{subtitle}
				</div>
			</div>
		</AbsoluteFill>
	);
};

