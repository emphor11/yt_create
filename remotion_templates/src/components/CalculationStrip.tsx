import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';

const splitLabelAndValue = (text: string): {label: string; value: string} => {
	const parts = text.trim().split(/\s+/);
	if (parts.length <= 1) {
		return {label: 'Value', value: text};
	}
	const firstLooksLikeValue = /^[₹$]?\d|^\d|^\d+%|^[+-]?\d/.test(parts[0]);
	if (!firstLooksLikeValue) {
		return {
			label: parts.slice(0, -1).join(' '),
			value: parts[parts.length - 1],
		};
	}
	return {
		value: parts[0],
		label: parts.slice(1).join(' '),
	};
};

export const CalculationStrip: React.FC<BeatComponentProps> = ({
	beat,
	frameWithinBeat,
}) => {
	const {fps} = useVideoConfig();
	const stepRows = Array.isArray(beat.steps)
		? beat.steps
				.map((step) => {
					const label = typeof step.label === 'string' ? step.label : '';
					const value =
						typeof step.value === 'string' || typeof step.value === 'number'
							? String(step.value)
							: '';
					const operation = typeof step.operation === 'string' ? step.operation : '';
					return `${label} ${operation} ${value}`.replace(/\s+/g, ' ').trim();
				})
				.filter(Boolean)
		: [];
	const rows = stepRows.length > 0
		? stepRows
		: beat.text
				.split('|')
				.map((row) => row.trim())
				.filter(Boolean);
	const visibleRows = rows.length > 0 ? rows : [beat.text];

	return (
		<AbsoluteFill
			style={{
				backgroundColor: '#0A0A14',
				padding: '120px 140px',
				color: 'white',
				justifyContent: 'center',
				gap: 24,
			}}
		>
			<style>{FONT_FACES}</style>
			{visibleRows.map((row, index) => {
				const localFrame = Math.max(0, frameWithinBeat - index * 6);
				const reveal = spring({
					frame: Math.min(localFrame, 12),
					fps,
					config: {damping: 15, stiffness: 190},
					durationInFrames: 12,
				});
				const opacity = interpolate(localFrame, [0, 12], [0, 1], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
				});
				const scale = interpolate(reveal, [0, 1], [0.95, 1], {
					extrapolateLeft: 'clamp',
					extrapolateRight: 'clamp',
				});
				const {label, value} = splitLabelAndValue(row);
				const isFinal = index === visibleRows.length - 1;
				return (
					<div
						key={`${row}-${index}`}
						style={{
							display: 'grid',
							gridTemplateColumns: '1fr auto 1fr',
							alignItems: 'center',
							columnGap: 24,
							padding: '22px 28px',
							borderRadius: 24,
							background: isFinal ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.05)',
							border: isFinal
								? '2px solid rgba(255,255,255,0.45)'
								: '1px solid rgba(255,255,255,0.12)',
							opacity,
							transform: `scale(${scale})`,
						}}
					>
						<div
							style={{
								fontFamily: BODY_FONT_FAMILY,
								fontSize: 34,
								fontWeight: 700,
								textTransform: 'capitalize',
							}}
						>
							{label}
						</div>
						<div
							style={{
								fontFamily: BODY_FONT_FAMILY,
								fontSize: 28,
								color: 'rgba(255,255,255,0.6)',
							}}
						>
							|
						</div>
						<div
							style={{
								fontFamily: DISPLAY_FONT_FAMILY,
								fontSize: isFinal ? 82 : 70,
								lineHeight: 0.95,
								textAlign: 'right',
							}}
						>
							{value}
						</div>
					</div>
				);
			})}
		</AbsoluteFill>
	);
};
