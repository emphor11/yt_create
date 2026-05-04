import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';

type BalancePoint = {month: number; balance: number; interest: number; principal_paid: number};

const spiralPoints = (count: number, progress: number) => {
	const points: string[] = [];
	const visible = Math.max(2, Math.floor(count * progress));
	for (let index = 0; index < visible; index++) {
		const t = index / Math.max(count - 1, 1);
		const angle = t * Math.PI * 5.4 - Math.PI / 2;
		const radius = 36 + t * 260;
		const x = 760 + Math.cos(angle) * radius;
		const y = 540 + Math.sin(angle) * radius;
		points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
	}
	return points.join(' ');
};

export const DebtSpiralVisualizer: React.FC<BeatComponentProps> = ({beat, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const principal = data.principal as {value?: string; amount?: number} | undefined;
	const balances = Array.isArray(data.balances) ? (data.balances as BalancePoint[]) : [];
	const monthlyInterest = Number(data.monthly_interest ?? 0);
	const minimumPayment = Number(data.minimum_payment ?? 0);
	const month12Balance = Number(data.month_12_balance ?? balances[balances.length - 1]?.balance ?? principal?.amount ?? 0);
	const isTrap = Boolean(data.is_trap);
	const progress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.75)), 1);
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.impact, durationInFrames: 18});
	const pulse = spring({frame: frameWithinBeat % 30, fps, config: {stiffness: 220, damping: 11, mass: 0.6}, durationInFrames: 18});
	const trapScale = isTrap ? 1 + pulse * 0.05 : 1;
	const accent = isTrap ? COLORS.danger : COLORS.warning;
	const path = spiralPoints(Math.max(balances.length, 12), progress);
	const monthlyGap = Math.max(monthlyInterest - minimumPayment, 0);

	return (
		<AbsoluteFill
			style={{
				background: COLORS.bg_deep,
				color: COLORS.text_primary,
				padding: SPACING.safe,
				fontFamily: BODY_FONT_FAMILY,
			}}
		>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: accent}} />
			<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 800, color: COLORS.text_secondary}}>
				Minimum payment trap
			</div>
			<svg viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
				<circle cx="760" cy="540" r="328" fill="rgba(230,57,70,0.035)" stroke="rgba(255,255,255,0.08)" />
				<polyline points={path} fill="none" stroke={accent} strokeWidth="26" strokeLinecap="round" strokeLinejoin="round" />
				<polyline points={path} fill="none" stroke="rgba(255,255,255,0.36)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
				<circle
					cx="760"
					cy="540"
					r={interpolate(reveal, [0, 1], [24, 48]) * trapScale}
					fill={COLORS.bg_surface}
					stroke={accent}
					strokeWidth={isTrap ? 8 : 5}
				/>
				{isTrap ? (
					<text
						x="760"
						y="565"
						textAnchor="middle"
						fontSize="72"
						fill={COLORS.danger}
						fontFamily={DISPLAY_FONT_FAMILY}
						opacity={interpolate(progress, [0.58, 0.88], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
					>
						STILL GROWING
					</text>
				) : null}
			</svg>
			<div
				style={{
					position: 'absolute',
					left: 300,
					top: 442,
					width: 920,
					textAlign: 'center',
					transform: `scale(${interpolate(reveal, [0, 1], [0.96, 1])})`,
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>Starting balance</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 92, lineHeight: 0.92}}>
					{principal?.value ?? formatIndianRupee(Number(principal?.amount ?? 0))}
				</div>
			</div>
			{isTrap && monthlyGap > 0 ? (
				<div
					style={{
						position: 'absolute',
						right: SPACING.safe,
						bottom: 222,
						width: 470,
						padding: '18px 24px',
						borderRadius: 8,
						background: 'rgba(230,57,70,0.16)',
						border: `2px solid ${COLORS.danger}`,
						opacity: interpolate(progress, [0.52, 0.78], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
						boxShadow: '0 0 46px rgba(230,57,70,0.18)',
					}}
				>
					<div style={{fontSize: TYPE_SCALE.micro.size + 4, color: COLORS.text_secondary, fontWeight: 800}}>
						Gap every month
					</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 52, lineHeight: 1, color: COLORS.danger}}>
						{formatIndianRupee(monthlyGap)} still unpaid
					</div>
				</div>
			) : null}
			<div
				style={{
					position: 'absolute',
					right: SPACING.safe,
					top: 260,
					width: 470,
					display: 'grid',
					gap: SPACING.md,
				}}
			>
				{[
					['Monthly interest', formatIndianRupee(monthlyInterest), COLORS.danger],
					['Minimum payment', minimumPayment ? formatIndianRupee(minimumPayment) : 'not enough', COLORS.warning],
					['Month 12 balance', formatIndianRupee(month12Balance), accent],
				].map(([label, value, color], index) => (
					<div
						key={label}
						style={{
							padding: '22px 26px',
							borderRadius: 8,
							background: COLORS.bg_surface,
							border: `1px solid ${COLORS.stroke}`,
							opacity: interpolate(progress, [index * 0.18, index * 0.18 + 0.18], [0, 1], {
								extrapolateLeft: 'clamp',
								extrapolateRight: 'clamp',
							}),
						}}
					>
						<div style={{fontSize: TYPE_SCALE.micro.size + 4, color: COLORS.text_secondary, fontWeight: 700}}>
							{label}
						</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 56, lineHeight: 1, color}}>{value}</div>
					</div>
				))}
			</div>
			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					bottom: SPACING.safe,
					fontFamily: DISPLAY_FONT_FAMILY,
					fontSize: 76,
					lineHeight: 0.95,
					color: accent,
					opacity: interpolate(progress, [0.78, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
				}}
			>
				{isTrap ? 'You owe more.' : 'Interest is still heavy.'}
			</div>
		</AbsoluteFill>
	);
};
