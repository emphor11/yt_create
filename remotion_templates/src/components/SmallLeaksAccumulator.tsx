import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';

type Leak = {
	label?: string;
	amount?: number;
	value?: string;
};

const defaultLeaks: Leak[] = [
	{label: 'Food apps', amount: 2400},
	{label: 'Subscriptions', amount: 1200},
	{label: 'Impulse buys', amount: 3500},
	{label: 'Convenience fees', amount: 900},
];

export const SmallLeaksAccumulator: React.FC<BeatComponentProps> = ({beat, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'repeat');
	const leaks = (Array.isArray(data.leaks) ? (data.leaks as Leak[]) : defaultLeaks).slice(0, 5);
	const monthlyLoss = Number(data.monthly_loss ?? leaks.reduce((sum, leak) => sum + Number(leak.amount ?? 0), 0));
	const progress = phase === 'first_leak' ? 0.25 : phase === 'month_end' ? 1 : getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.8));
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const drainHeight = interpolate(progress, [0, 1], [80, 430], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe}}>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.warning}} />
			<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 86, lineHeight: 0.92, maxWidth: 700, opacity: reveal}}>
				{phase === 'first_leak' ? 'ONE SMALL SPEND' : phase === 'month_end' ? 'THE PATTERN GETS EXPENSIVE' : 'SMALL LEAKS REPEAT'}
			</div>
			<div style={{position: 'absolute', left: 210, bottom: 160, width: 520, height: 540}}>
				<div
					style={{
						position: 'absolute',
						left: 110,
						bottom: 0,
						width: 300,
						height: 430,
						borderRadius: 8,
						background: COLORS.bg_surface,
						border: `2px solid ${COLORS.stroke}`,
						overflow: 'hidden',
					}}
				>
					<div
						style={{
							position: 'absolute',
							left: 0,
							right: 0,
							bottom: 0,
							height: drainHeight,
							background: 'linear-gradient(180deg, rgba(255,159,28,0.25), rgba(230,57,70,0.92))',
						}}
					/>
				</div>
				<div style={{position: 'absolute', left: 0, top: 0, fontSize: 28, color: COLORS.text_secondary, fontWeight: 900}}>Monthly pressure</div>
				<div style={{position: 'absolute', left: 0, top: 44, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 86, lineHeight: 0.9, color: COLORS.warning}}>
					{formatIndianRupee(monthlyLoss)}
				</div>
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, top: 190, width: 820, height: 650}}>
				{leaks.map((leak, index) => {
					const itemProgress = interpolate(progress, [index / leaks.length, (index + 0.7) / leaks.length], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					});
					return (
						<div
							key={`${leak.label}-${index}`}
							style={{
								position: 'absolute',
								left: (index % 2) * 380,
								top: Math.floor(index / 2) * 170,
								width: 330,
								height: 120,
								borderRadius: 8,
								background: 'rgba(255,159,28,0.11)',
								border: `2px solid ${COLORS.warning}`,
								padding: '22px 24px',
								opacity: itemProgress,
								transform: `translateX(${(1 - itemProgress) * 80}px)`,
							}}
						>
							<div style={{fontSize: 25, color: COLORS.text_secondary, fontWeight: 900}}>{leak.label ?? `Leak ${index + 1}`}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 56, lineHeight: 0.94}}>
								{leak.value ?? formatIndianRupee(Number(leak.amount ?? 0))}
							</div>
						</div>
					);
				})}
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, bottom: SPACING.safe, color: COLORS.text_secondary, fontSize: 30, fontWeight: 900}}>
				The danger is repetition, not one purchase.
			</div>
		</AbsoluteFill>
	);
};
