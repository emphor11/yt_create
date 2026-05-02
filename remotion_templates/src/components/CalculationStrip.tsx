import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, getBeatData} from './visualUtils';

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
	const typedData = getBeatData<{steps?: unknown[]}>(beat);
	const rawSteps = Array.isArray(typedData?.steps) ? typedData.steps : beat.steps;
	const stepRows = Array.isArray(rawSteps)
		? rawSteps
				.map((step) => {
					const item = step as Record<string, unknown>;
					const label = typeof item.label === 'string' ? item.label : '';
					const value =
						typeof item.value === 'string' || typeof item.value === 'number'
							? String(item.value)
							: '';
					const operation = typeof item.operation === 'string' ? item.operation : '';
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
				backgroundColor: COLORS.bg_deep,
				padding: `${SPACING.safe}px 140px`,
				color: COLORS.text_primary,
				justifyContent: 'center',
				gap: SPACING.md,
			}}
		>
			<style>{FONT_FACES}</style>
			{visibleRows.map((row, index) => {
				const localFrame = Math.max(0, frameWithinBeat - index * 6);
				const isFinal = index === visibleRows.length - 1;
				const reveal = spring({
					frame: Math.min(localFrame, 12),
					fps,
					config: isFinal ? SPRINGS.impact : SPRINGS.entry,
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
				return (
					<div
						key={`${row}-${index}`}
						style={{
							display: 'grid',
							gridTemplateColumns: '1fr auto 1fr',
							alignItems: 'center',
							columnGap: SPACING.md,
							padding: '22px 28px',
							borderRadius: 8,
							background: isFinal ? COLORS.panelStrong : COLORS.panel,
							border: isFinal
								? '2px solid rgba(255,255,255,0.45)'
								: `1px solid ${COLORS.stroke}`,
							opacity,
							transform: `scale(${scale})`,
						}}
					>
						<div
							style={{
								fontFamily: BODY_FONT_FAMILY,
								fontSize: TYPE_SCALE.label.size,
								fontWeight: TYPE_SCALE.label.weight,
								textTransform: 'capitalize',
							}}
						>
							{label}
						</div>
						<div
							style={{
								fontFamily: BODY_FONT_FAMILY,
								fontSize: TYPE_SCALE.subtext.size,
								color: COLORS.text_secondary,
							}}
						>
							|
						</div>
						<div
							style={{
								fontFamily: DISPLAY_FONT_FAMILY,
								fontSize: isFinal ? TYPE_SCALE.major_value.size : 70,
								fontWeight: TYPE_SCALE.major_value.weight,
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
