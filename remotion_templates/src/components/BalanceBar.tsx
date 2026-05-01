import React from 'react';
import {AbsoluteFill, interpolate} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, splitComparisonText} from './visualUtils';

const numberFromText = (text: string, fallback: number): number => {
	const match = text.match(/(\d+(?:\.\d+)?)\s*%?/);
	if (!match) {
		return fallback;
	}
	return Math.min(100, Math.max(0, Number(match[1])));
};

export const BalanceBar: React.FC<BeatComponentProps> = ({beat, frameWithinBeat}) => {
	const labels = splitComparisonText(beat.text);
	const leftValue = numberFromText(beat.text, 60);
	const rightValue = Math.max(0, 100 - leftValue);
	const progress = interpolate(frameWithinBeat, [0, 34], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, padding: 120, justifyContent: 'center'}}>
			<style>{FONT_FACES}</style>
			<div style={{fontFamily: BODY_FONT_FAMILY, color: COLORS.muted, fontSize: 34, fontWeight: 900, marginBottom: 42}}>
				{(beat.subtext || 'Balance check').toUpperCase()}
			</div>
			<div style={{height: 96, border: `2px solid ${COLORS.stroke}`, background: COLORS.panel, display: 'flex', overflow: 'hidden'}}>
				<div style={{width: `${leftValue * progress}%`, background: COLORS.red}} />
				<div style={{width: `${rightValue * progress}%`, background: COLORS.teal}} />
			</div>
			<div style={{display: 'flex', justifyContent: 'space-between', marginTop: 34}}>
				<Label label={labels.left} value={`${Math.round(leftValue)}%`} color={COLORS.red} />
				<Label label={labels.right} value={`${Math.round(rightValue)}%`} color={COLORS.teal} align="right" />
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

