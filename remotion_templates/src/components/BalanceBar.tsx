import React from 'react';
import {AbsoluteFill, interpolate} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, propText, splitComparisonText} from './visualUtils';

const numberFromText = (text: string, fallback: number): number => {
	const match = text.match(/(\d+(?:\.\d+)?)\s*%?/);
	if (!match) {
		return fallback;
	}
	return Math.min(100, Math.max(0, Number(match[1])));
};

const sideFromProps = (source: unknown, fallbackLabel: string, fallbackValue: number, fallbackColor: string) => {
	if (source && typeof source === 'object') {
		const item = source as Record<string, unknown>;
		return {
			label: propText(item, 'label', fallbackLabel),
			value: Number(item.value ?? fallbackValue),
			color: propText(item, 'color', fallbackColor),
		};
	}
	return {label: fallbackLabel, value: fallbackValue, color: fallbackColor};
};

export const BalanceBar: React.FC<BeatComponentProps> = ({beat, frameWithinBeat}) => {
	const labels = splitComparisonText(beat.text);
	const guessedLeft = numberFromText(beat.text, 60);
	const left = sideFromProps(beat.props?.left, labels.left, guessedLeft, COLORS.red);
	const right = sideFromProps(beat.props?.right, labels.right, Math.max(0, 100 - left.value), COLORS.teal);
	const total = Math.max(left.value + right.value, 1);
	const leftValue = Math.max(0, Math.min(100, (left.value / total) * 100));
	const rightValue = Math.max(0, Math.min(100, (right.value / total) * 100));
	const progress = interpolate(frameWithinBeat, [0, 34], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const title = propText(beat.props, 'title', beat.subtext || 'Balance check');

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, padding: 120, justifyContent: 'center'}}>
			<style>{FONT_FACES}</style>
			<div style={{fontFamily: BODY_FONT_FAMILY, color: COLORS.muted, fontSize: 34, fontWeight: 900, marginBottom: 42}}>
				{title.toUpperCase()}
			</div>
			<div style={{height: 96, border: `2px solid ${COLORS.stroke}`, background: COLORS.panel, display: 'flex', overflow: 'hidden'}}>
				<div style={{width: `${leftValue * progress}%`, background: left.color}} />
				<div style={{width: `${rightValue * progress}%`, background: right.color}} />
			</div>
			<div style={{display: 'flex', justifyContent: 'space-between', marginTop: 34}}>
				<Label label={left.label} value={`${Math.round(leftValue)}%`} color={left.color} />
				<Label label={right.label} value={`${Math.round(rightValue)}%`} color={right.color} align="right" />
			</div>
		</AbsoluteFill>
	);
};

const Label: React.FC<{label: string; value: string; color: string; align?: 'left' | 'right'}> = ({label, value, color, align = 'left'}) => (
	<div style={{textAlign: align}}>
		<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 74, color}}>{value}</div>
		<div style={{fontFamily: BODY_FONT_FAMILY, fontSize: 32, fontWeight: 900, color: COLORS.muted}}>{label.toUpperCase()}</div>
	</div>
);
