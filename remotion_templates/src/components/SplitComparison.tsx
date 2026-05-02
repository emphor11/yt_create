import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, getBeatData, propText, sceneText, splitComparisonText} from './visualUtils';

export const SplitComparison: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const reveal = spring({
		frame: Math.min(frameWithinBeat, 16),
		fps,
		config: {damping: 16, stiffness: 150},
		durationInFrames: 16,
	});
	const fallback = splitComparisonText(beat.text);
	const typedData = getBeatData<{left?: unknown; right?: unknown}>(beat);
	const dataLeft = typedData?.left ?? beat.props?.left ?? scene?.data?.left;
	const dataRight = typedData?.right ?? beat.props?.right ?? scene?.data?.right;
	const left =
		typeof dataLeft === 'object' && dataLeft
			? propText(dataLeft as Record<string, unknown>, 'label', fallback.left)
			: sceneText(scene, 'start', fallback.left);
	const right =
		typeof dataRight === 'object' && dataRight
			? propText(dataRight as Record<string, unknown>, 'label', fallback.right)
			: sceneText(scene, 'end', fallback.right);
	const connector = propText(beat.props, 'connector', sceneText(scene, 'connector', 'VS'));

	const sideStyle = (accent: string, delay: number): React.CSSProperties => {
		const opacity = interpolate(frameWithinBeat - delay, [0, 10], [0, 1], {
			extrapolateLeft: 'clamp',
			extrapolateRight: 'clamp',
		});
		return {
			opacity,
			transform: `translateY(${(1 - reveal) * 24}px)`,
			background: COLORS.panel,
			border: `2px solid ${accent}`,
			padding: '64px 58px',
			minHeight: 380,
			display: 'flex',
			flexDirection: 'column',
			justifyContent: 'center',
		};
	};

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, padding: 100}}>
			<style>{FONT_FACES}</style>
			<div style={{display: 'grid', gridTemplateColumns: '1fr 180px 1fr', alignItems: 'center', gap: 34, height: '100%'}}>
				<div style={sideStyle(COLORS.red, 0)}>
					<div style={{fontFamily: BODY_FONT_FAMILY, color: COLORS.dim, fontSize: 30, fontWeight: 900}}>OPTION A</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 92, lineHeight: 0.95, marginTop: 22}}>{left.toUpperCase()}</div>
				</div>
				<div
					style={{
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: 64,
						color: COLORS.orange,
						textAlign: 'center',
						opacity: interpolate(frameWithinBeat, [8, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
					}}
				>
					{connector.toUpperCase()}
				</div>
				<div style={sideStyle(COLORS.teal, 6)}>
					<div style={{fontFamily: BODY_FONT_FAMILY, color: COLORS.dim, fontSize: 30, fontWeight: 900}}>OPTION B</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 92, lineHeight: 0.95, marginTop: 22}}>{right.toUpperCase()}</div>
				</div>
			</div>
		</AbsoluteFill>
	);
};
