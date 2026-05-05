import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';

type MoneyPoint = {
	value?: string;
	amount?: number;
};

type LifestyleCreepData = {
	start_income?: MoneyPoint;
	end_income?: MoneyPoint;
	old_spending?: MoneyPoint;
	new_spending?: MoneyPoint;
	old_savings?: MoneyPoint;
	new_savings?: MoneyPoint;
	raise?: MoneyPoint;
	active_phase?: string;
	title?: string;
};

const moneyPoint = (point: unknown, fallbackAmount: number): Required<MoneyPoint> => {
	const item = point && typeof point === 'object' ? (point as MoneyPoint) : {};
	const amount = Number.isFinite(Number(item.amount)) ? Number(item.amount) : fallbackAmount;
	return {
		amount,
		value: item.value || formatIndianRupee(amount),
	};
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const barHeight = (amount: number, maxAmount: number, min = 88, max = 510) =>
	interpolate(clamp(amount / Math.max(maxAmount, 1), 0, 1), [0, 1], [min, max]);

export const LifestyleCreepVisualizer: React.FC<BeatComponentProps> = ({beat, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const rawData = getBeatData<LifestyleCreepData>(beat) ?? {};
	const phase = String(beat.beat_phase ?? rawData.active_phase ?? 'expenses_follow');
	const startIncome = moneyPoint(rawData.start_income, 50000);
	const endIncome = moneyPoint(rawData.end_income, 80000);
	const oldSpending = moneyPoint(rawData.old_spending, Math.round(startIncome.amount * 0.78));
	const newSpending = moneyPoint(rawData.new_spending, Math.round(endIncome.amount * 0.88));
	const oldSavings = moneyPoint(rawData.old_savings, Math.max(0, startIncome.amount - oldSpending.amount));
	const newSavings = moneyPoint(rawData.new_savings, Math.max(0, endIncome.amount - newSpending.amount));
	const raise = moneyPoint(rawData.raise, Math.max(0, endIncome.amount - startIncome.amount));
	const maxAmount = Math.max(endIncome.amount, newSpending.amount, startIncome.amount, 1);
	const rawProgress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.78)), 1);
	const reveal = spring({frame: Math.min(frameWithinBeat, 20), fps, config: SPRINGS.entry, durationInFrames: 20});
	const raiseProgress = phase === 'income_base' ? 0 : phase === 'raise_arrives' ? rawProgress : 1;
	const creepProgress = phase === 'income_base' || phase === 'raise_arrives' ? 0 : phase === 'expenses_follow' ? rawProgress : 1;
	const gapProgress = phase === 'gap_revealed' ? rawProgress : 0;
	const incomeAmount = startIncome.amount + (endIncome.amount - startIncome.amount) * raiseProgress;
	const spendingAmount = oldSpending.amount + (newSpending.amount - oldSpending.amount) * creepProgress;
	const savingsAmount = Math.max(0, incomeAmount - spendingAmount);
	const incomeHeight = barHeight(incomeAmount, maxAmount);
	const spendingHeight = barHeight(spendingAmount, maxAmount);
	const savingsHeight = barHeight(savingsAmount, maxAmount, 46, 240);
	const gapShrank = newSavings.amount <= oldSavings.amount * 1.15;
	const title =
		phase === 'income_base'
			? 'Before the raise'
			: phase === 'raise_arrives'
				? 'Income moves up'
				: phase === 'expenses_follow'
					? 'Lifestyle catches up'
					: 'Savings gap exposed';

	return (
		<AbsoluteFill
			style={{
				background: COLORS.bg_deep,
				color: COLORS.text_primary,
				padding: SPACING.safe,
				fontFamily: BODY_FONT_FAMILY,
				overflow: 'hidden',
			}}
		>
			<style>{FONT_FACES}</style>
			<div
				style={{
					position: 'absolute',
					inset: -120,
					background:
						'radial-gradient(circle at 76% 36%, rgba(255,159,28,0.20), transparent 31%), radial-gradient(circle at 18% 78%, rgba(230,57,70,0.16), transparent 28%), linear-gradient(120deg, #080811, #12121f 56%, #090914)',
				}}
			/>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.warning}} />
			<div style={{position: 'relative', zIndex: 2, fontSize: TYPE_SCALE.label.size, fontWeight: 900, color: COLORS.text_secondary}}>
				{title}
			</div>

			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					top: 215,
					width: 530,
					opacity: reveal,
					transform: `translateY(${interpolate(reveal, [0, 1], [24, 0])}px)`,
					zIndex: 3,
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>Raise received</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 120, lineHeight: 0.88}}>
					{formatIndianRupee(incomeAmount)}
				</div>
				<div
					style={{
						marginTop: 28,
						width: 440,
						height: 16,
						borderRadius: 999,
						background: 'rgba(255,255,255,0.08)',
						overflow: 'hidden',
					}}
				>
					<div
						style={{
							height: '100%',
							width: `${18 + raiseProgress * 82}%`,
							background: `linear-gradient(90deg, ${COLORS.positive}, ${COLORS.warning})`,
							boxShadow: `0 0 28px ${COLORS.warning}88`,
						}}
					/>
				</div>
				<div style={{marginTop: 18, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 800}}>
					{raise.value} extra income
				</div>
			</div>

			<div
				style={{
					position: 'absolute',
					right: 150,
					bottom: 190,
					width: 900,
					height: 600,
					borderRadius: 8,
					border: `1px solid ${COLORS.stroke}`,
					background: 'rgba(255,255,255,0.045)',
					zIndex: 2,
				}}
			>
				<div style={{position: 'absolute', left: 70, right: 70, bottom: 95, height: 2, background: COLORS.stroke}} />
				{[
					{label: 'Income', amount: incomeAmount, value: formatIndianRupee(incomeAmount), color: COLORS.positive, height: incomeHeight, left: 150},
					{label: 'Lifestyle', amount: spendingAmount, value: formatIndianRupee(spendingAmount), color: COLORS.warning, height: spendingHeight, left: 385},
					{label: 'Savings gap', amount: savingsAmount, value: formatIndianRupee(savingsAmount), color: gapShrank ? COLORS.danger : COLORS.positive, height: savingsHeight, left: 620},
				].map((bar) => (
					<div key={bar.label} style={{position: 'absolute', left: bar.left, bottom: 95, width: 150}}>
						<div
							style={{
								position: 'absolute',
								bottom: 0,
								width: '100%',
								height: bar.height,
								borderRadius: '8px 8px 0 0',
								background: `${bar.color}30`,
								border: `2px solid ${bar.color}`,
								boxShadow: `0 0 38px ${bar.color}55`,
								transform: `scaleY(${interpolate(reveal, [0, 1], [0.2, 1])})`,
								transformOrigin: 'bottom',
							}}
						/>
						<div
							style={{
								position: 'absolute',
								bottom: bar.height + 24,
								left: -55,
								width: 260,
								textAlign: 'center',
								opacity: bar.label === 'Savings gap' ? interpolate(gapProgress, [0, 0.45], [0.35, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1,
							}}
						>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 54, lineHeight: 0.95, color: bar.color}}>{bar.value}</div>
							<div style={{fontSize: TYPE_SCALE.micro.size + 3, color: COLORS.text_secondary, fontWeight: 900}}>{bar.label}</div>
						</div>
					</div>
				))}
				<svg viewBox="0 0 900 600" style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
					<path
						d={`M 515 ${505 - spendingHeight} C 575 ${430 - spendingHeight * 0.15}, 600 ${430 - savingsHeight * 0.12}, 675 ${505 - savingsHeight}`}
						stroke={gapShrank ? COLORS.danger : COLORS.positive}
						strokeWidth={8}
						strokeLinecap="round"
						fill="none"
						opacity={interpolate(gapProgress, [0.15, 0.75], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
					/>
				</svg>
			</div>

			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					bottom: SPACING.safe,
					width: 720,
					padding: '28px 34px',
					borderRadius: 8,
					border: `2px solid ${gapShrank ? COLORS.danger : COLORS.warning}`,
					background: gapShrank ? 'rgba(230,57,70,0.13)' : COLORS.bg_surface,
				opacity: phase === 'gap_revealed' ? interpolate(rawProgress, [0.25, 0.78], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0,
					zIndex: 4,
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>Result</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 74, lineHeight: 0.94, color: gapShrank ? COLORS.danger : COLORS.warning}}>
					{gapShrank ? 'Raise did not reach savings' : 'Savings gap finally grows'}
				</div>
			</div>
		</AbsoluteFill>
	);
};
