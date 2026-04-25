import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {DISPLAY_FONT_FAMILY, BODY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';

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
		config: {damping: 14, stiffness: 180},
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

	return (
		<AbsoluteFill
			style={{
				backgroundColor: '#0A0A14',
				alignItems: 'center',
				justifyContent: 'center',
				padding: 96,
				color: 'white',
			}}
		>
			<style>{FONT_FACES}</style>
			<div
				style={{
					opacity,
					transform: `scale(${scale})`,
					textAlign: 'center',
					width: '100%',
				}}
			>
				<div
					style={{
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: isHero ? 154 : 132,
						letterSpacing: '-0.04em',
						lineHeight: 0.92,
						textTransform: 'uppercase',
					}}
				>
					{beat.text}
				</div>
				{durationFrames > 45 ? (
					<div
						style={{
							marginTop: 28,
							fontFamily: BODY_FONT_FAMILY,
							fontSize: 36,
							fontWeight: 700,
							color: 'rgba(255,255,255,0.72)',
						}}
					>
						{isHero ? 'Key impact' : 'Core idea'}
					</div>
				) : null}
			</div>
		</AbsoluteFill>
	);
};
