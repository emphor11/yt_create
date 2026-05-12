import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';
import {resolveVisualEvent} from './visualEvents';

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

type ResolvedMoneyPoint = Required<MoneyPoint>;

type ExpenseAttack = {
	label: string;
	amount: number;
	color: string;
	x: number;
	y: number;
	delay: number;
};

const moneyPoint = (point: unknown, fallbackAmount: number): ResolvedMoneyPoint => {
	const item = point && typeof point === 'object' ? (point as MoneyPoint) : {};
	const amount = Number.isFinite(Number(item.amount)) ? Number(item.amount) : fallbackAmount;
	return {
		amount,
		value: item.value || formatIndianRupee(amount),
	};
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const rupee = (amount: number) => formatIndianRupee(Math.round(amount));

const Shell: React.FC<{
	title: string;
	tone: 'calm' | 'optimistic' | 'pressure' | 'warning';
	children: React.ReactNode;
}> = ({title, tone, children}) => {
	const backgrounds = {
		calm: 'radial-gradient(circle at 52% 46%, rgba(46,196,182,0.16), transparent 34%), linear-gradient(135deg, #070912, #101725 58%, #070912)',
		optimistic:
			'radial-gradient(circle at 68% 34%, rgba(255,209,102,0.28), transparent 30%), radial-gradient(circle at 30% 72%, rgba(46,196,182,0.16), transparent 26%), linear-gradient(135deg, #080912, #15131d 56%, #08120f)',
		pressure:
			'radial-gradient(circle at 76% 42%, rgba(230,57,70,0.22), transparent 31%), radial-gradient(circle at 23% 70%, rgba(255,159,28,0.18), transparent 26%), linear-gradient(120deg, #080811, #15101a 56%, #090914)',
		warning: 'radial-gradient(circle at 50% 52%, rgba(230,57,70,0.18), transparent 24%), linear-gradient(135deg, #05060b, #0c0b12 58%, #05060b)',
	};
	const railColor = tone === 'calm' ? COLORS.positive : tone === 'optimistic' ? COLORS.warning : COLORS.danger;

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
			<div style={{position: 'absolute', inset: -120, background: backgrounds[tone]}} />
			<div style={{position: 'absolute', inset: 0, background: 'black', opacity: tone === 'warning' ? 0.38 : 0.06}} />
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: railColor}} />
			<div
				style={{
					position: 'relative',
					zIndex: 10,
					fontSize: TYPE_SCALE.label.size,
					fontWeight: 900,
					color: COLORS.text_secondary,
				}}
			>
				{title}
			</div>
			{children}
		</AbsoluteFill>
	);
};

const ValueBlock: React.FC<{
	label: string;
	value: string;
	color: string;
	size?: number;
	align?: 'left' | 'center';
}> = ({label, value, color, size = 106, align = 'left'}) => (
	<div style={{textAlign: align}}>
		<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>{label}</div>
		<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: size, lineHeight: 0.88, color}}>{value}</div>
	</div>
);

export const LifestyleCreepVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const rawData = getBeatData<LifestyleCreepData>(beat) ?? {};
	const phase = String(beat.beat_phase ?? rawData.active_phase ?? 'expenses_follow');
	const event = resolveVisualEvent(beat, scene, 'LifestyleCreepVisualizer');
	const startIncome = moneyPoint(rawData.start_income, 50000);
	const endIncome = moneyPoint(rawData.end_income, 80000);
	const oldSpending = moneyPoint(rawData.old_spending, Math.round(startIncome.amount * 0.78));
	const newSpending = moneyPoint(rawData.new_spending, Math.round(endIncome.amount * 0.88));
	const oldSavings = moneyPoint(rawData.old_savings, Math.max(0, startIncome.amount - oldSpending.amount));
	const newSavings = moneyPoint(rawData.new_savings, Math.max(0, endIncome.amount - newSpending.amount));
	const raise = moneyPoint(rawData.raise, Math.max(0, endIncome.amount - startIncome.amount));
	const rawProgress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.82)), 1);
	const entry = spring({frame: Math.min(frameWithinBeat, 22), fps, config: SPRINGS.entry, durationInFrames: 22});
	const slowBreath = Math.sin((frameWithinBeat / fps) * Math.PI * 1.2);
	const raiseProgress = phase === 'income_base' ? 0 : phase === 'raise_arrives' ? rawProgress : 1;
	const creepProgress = phase === 'income_base' || phase === 'raise_arrives' ? 0 : phase === 'expenses_follow' ? rawProgress : 1;
	const incomeAmount = startIncome.amount + (endIncome.amount - startIncome.amount) * raiseProgress;
	const spendingAmount = oldSpending.amount + (newSpending.amount - oldSpending.amount) * creepProgress;
	const savingsAmount = Math.max(0, incomeAmount - spendingAmount);
	const gapShrank = newSavings.amount <= oldSavings.amount * 1.15;
	const newSpendDelta = Math.max(0, newSpending.amount - oldSpending.amount);
	const attacks: ExpenseAttack[] = [
		{label: 'Rent upgrade', amount: Math.round(newSpendDelta * 0.34), color: COLORS.warning, x: 1150, y: 178, delay: 0.04},
		{label: 'Food apps', amount: Math.round(newSpendDelta * 0.2), color: COLORS.danger, x: 1330, y: 350, delay: 0.2},
		{label: 'Weekends', amount: Math.round(newSpendDelta * 0.22), color: '#FF6B35', x: 1225, y: 535, delay: 0.36},
		{label: 'Shopping', amount: Math.round(newSpendDelta * 0.24), color: '#FFD166', x: 1395, y: 720, delay: 0.52},
	];

	if (event.kind === 'baseline_life') {
		const reserveWidth = interpolate(entry, [0, 1], [120, 430]);
		const spendRatio = clamp(oldSpending.amount / Math.max(startIncome.amount, 1), 0, 1);

		return (
			<Shell title="Baseline life" tone="calm">
				<div
					style={{
						position: 'absolute',
						inset: 0,
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						zIndex: 2,
						transform: `translateY(${interpolate(entry, [0, 1], [28, 0])}px)`,
						opacity: entry,
					}}
				>
					<div style={{width: 1020, textAlign: 'center'}}>
						<ValueBlock label="Monthly salary" value={startIncome.value} color={COLORS.text_primary} size={142} align="center" />
						<div
							style={{
								margin: '54px auto 0',
								width: 680,
								height: 28,
								borderRadius: 999,
								background: 'rgba(255,255,255,0.08)',
								overflow: 'hidden',
							}}
						>
							<div style={{height: '100%', width: `${spendRatio * 100}%`, background: 'rgba(255,255,255,0.22)'}} />
						</div>
						<div
							style={{
								margin: '44px auto 0',
								width: reserveWidth,
								minWidth: 280,
								padding: '22px 34px',
								border: `2px solid ${COLORS.positive}`,
								borderRadius: 8,
								background: 'rgba(46,196,182,0.12)',
								boxShadow: `0 0 ${26 + slowBreath * 6}px rgba(46,196,182,0.22)`,
							}}
						>
							<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>Stable savings</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 72, lineHeight: 0.9, color: COLORS.positive}}>{oldSavings.value}</div>
						</div>
					</div>
				</div>
				<div style={{position: 'absolute', left: 250, bottom: 150, width: 280, height: 2, background: 'rgba(255,255,255,0.18)', opacity: 0.8}} />
				<div style={{position: 'absolute', right: 260, top: 210, width: 190, height: 2, background: 'rgba(255,255,255,0.16)', opacity: 0.7}} />
			</Shell>
		);
	}

	if (event.kind === 'raise_arrival') {
		const lift = interpolate(rawProgress, [0, 1], [120, -36], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const glow = interpolate(rawProgress, [0, 1], [0.28, 0.72], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const displayedIncome = rupee(startIncome.amount + (endIncome.amount - startIncome.amount) * rawProgress);

		return (
			<Shell title="Raise arrival" tone="optimistic">
				<div
					style={{
						position: 'absolute',
						left: 220,
						top: 250,
						width: 980,
						zIndex: 3,
						opacity: entry,
						transform: `translateY(${interpolate(entry, [0, 1], [34, 0])}px)`,
					}}
				>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>New salary energy</div>
					<div
						style={{
							fontFamily: DISPLAY_FONT_FAMILY,
							fontSize: 176,
							lineHeight: 0.82,
							color: COLORS.text_primary,
							textShadow: `0 0 58px rgba(255,209,102,${glow})`,
						}}
					>
						{displayedIncome}
					</div>
					<div style={{marginTop: 26, fontSize: 44, fontWeight: 900, color: COLORS.warning}}>{raise.value} more per month</div>
				</div>
				<div
					style={{
						position: 'absolute',
						right: 255,
						bottom: 170 + lift,
						width: 360,
						height: 360,
						borderRadius: 180,
						border: `5px solid ${COLORS.warning}`,
						background: 'rgba(255,209,102,0.11)',
						boxShadow: '0 0 90px rgba(255,209,102,0.34)',
						transform: `scale(${0.72 + rawProgress * 0.34})`,
						zIndex: 2,
					}}
				>
					<div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 150, fontWeight: 950, color: COLORS.warning}}>+</div>
				</div>
				{[0, 1, 2].map((index) => (
					<div
						key={index}
						style={{
							position: 'absolute',
							right: 500 + index * 120,
							bottom: 220 + index * 42 + lift * 0.36,
							width: 18,
							height: 190 + index * 45,
							borderRadius: 999,
							background: `linear-gradient(180deg, ${COLORS.warning}, rgba(255,209,102,0))`,
							opacity: interpolate(rawProgress, [index * 0.12, 1], [0, 0.82], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
						}}
					/>
				))}
			</Shell>
		);
	}

	if (event.kind === 'savings_gap_reveal') {
		const collapse = interpolate(rawProgress, [0, 0.68], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const tinyScale = interpolate(collapse, [0, 1], [1.12, 0.92]);

		return (
			<Shell title="Savings gap reveal" tone="warning">
				<div
					style={{
						position: 'absolute',
						inset: 0,
						zIndex: 2,
						opacity: 0.08 * (1 - collapse),
						transform: `scale(${1.22 - collapse * 0.2})`,
					}}
				>
					<div style={{position: 'absolute', left: 250, top: 360, width: 1180, height: 2, background: COLORS.stroke}} />
					<div style={{position: 'absolute', left: 420, top: 210, width: 160, height: 440, border: `2px solid ${COLORS.positive}`}} />
					<div style={{position: 'absolute', left: 760, top: 160, width: 160, height: 490, border: `2px solid ${COLORS.warning}`}} />
					<div style={{position: 'absolute', left: 1100, top: 540, width: 160, height: 110, border: `2px solid ${COLORS.danger}`}} />
				</div>
				<div
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						top: 312,
						textAlign: 'center',
						zIndex: 4,
						opacity: entry,
						transform: `translateY(${interpolate(entry, [0, 1], [32, 0])}px) scale(${tinyScale})`,
					}}
				>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>Actual savings left</div>
					<div
						style={{
							fontFamily: DISPLAY_FONT_FAMILY,
							fontSize: 118,
							lineHeight: 0.82,
							color: gapShrank ? COLORS.danger : COLORS.warning,
							textShadow: `0 0 ${70 + collapse * 40}px rgba(230,57,70,0.45)`,
						}}
					>
						{newSavings.value}
					</div>
					<div
						style={{
							margin: '54px auto 0',
							width: interpolate(collapse, [0, 1], [360, 130]),
							height: 18,
							borderRadius: 999,
							background: 'rgba(255,255,255,0.08)',
							overflow: 'hidden',
						}}
					>
						<div style={{height: '100%', width: '24%', background: gapShrank ? COLORS.danger : COLORS.warning}} />
					</div>
				</div>
				<div
					style={{
						position: 'absolute',
						left: 690,
						bottom: 132,
						width: 540,
						padding: '24px 32px',
						border: `2px solid ${gapShrank ? COLORS.danger : COLORS.warning}`,
						borderRadius: 8,
						background: gapShrank ? 'rgba(230,57,70,0.14)' : 'rgba(255,209,102,0.12)',
						textAlign: 'center',
						zIndex: 4,
						opacity: interpolate(rawProgress, [0.24, 0.72], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
					}}
				>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58, lineHeight: 0.94, color: gapShrank ? COLORS.danger : COLORS.warning}}>
						Raise did not reach savings
					</div>
				</div>
			</Shell>
		);
	}

	const boardReveal = interpolate(rawProgress, [0, 0.28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const crowd = interpolate(rawProgress, [0.1, 0.88], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const salaryWidth = interpolate(rawProgress, [0, 1], [680, 380], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const spendWidth = interpolate(rawProgress, [0, 1], [170, 700], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const savingsWidth = interpolate(rawProgress, [0, 1], [310, 96], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

	return (
		<Shell title="Lifestyle absorption" tone="pressure">
			<div
				style={{
					position: 'absolute',
					left: 132,
					top: 180,
					width: 960,
					height: 640,
					borderRadius: 8,
					border: `1px solid ${COLORS.stroke}`,
					background: 'rgba(255,255,255,0.045)',
					boxShadow: '0 0 70px rgba(230,57,70,0.12)',
					opacity: boardReveal,
					transform: `translateX(${interpolate(boardReveal, [0, 1], [-70, 0])}px)`,
					zIndex: 2,
				}}
			>
				<div style={{position: 'absolute', left: 64, top: 76, fontSize: TYPE_SCALE.subtext.size, fontWeight: 900, color: COLORS.text_secondary}}>Raise being consumed</div>
				<div style={{position: 'absolute', left: 64, top: 160, width: 730, height: 86}}>
					<div style={{fontSize: TYPE_SCALE.micro.size + 4, fontWeight: 900, color: COLORS.text_secondary}}>Income</div>
					<div style={{marginTop: 12, width: salaryWidth, height: 34, borderRadius: 999, background: COLORS.positive, boxShadow: `0 0 28px ${COLORS.positive}55`}} />
					<div style={{position: 'absolute', right: 0, top: 36, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 46, color: COLORS.positive}}>{rupee(incomeAmount)}</div>
				</div>
				<div style={{position: 'absolute', left: 64, top: 300, width: 800, height: 116}}>
					<div style={{fontSize: TYPE_SCALE.micro.size + 4, fontWeight: 900, color: COLORS.text_secondary}}>Lifestyle spending</div>
					<div style={{marginTop: 12, width: spendWidth, height: 58, borderRadius: 8, background: COLORS.warning, boxShadow: `0 0 ${38 + crowd * 24}px ${COLORS.warning}66`}} />
					<div style={{position: 'absolute', right: 0, top: 32, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 56, color: COLORS.warning}}>{rupee(spendingAmount)}</div>
				</div>
				<div style={{position: 'absolute', left: 64, bottom: 100, width: 760, height: 90}}>
					<div style={{fontSize: TYPE_SCALE.micro.size + 4, fontWeight: 900, color: COLORS.text_secondary}}>Savings squeezed</div>
					<div style={{marginTop: 12, width: savingsWidth, height: 26, borderRadius: 999, background: gapShrank ? COLORS.danger : COLORS.positive}} />
					<div style={{position: 'absolute', right: 0, top: 26, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 48, color: gapShrank ? COLORS.danger : COLORS.positive}}>{rupee(savingsAmount)}</div>
				</div>
			</div>
			{attacks.map((attack) => {
				const attackIn = interpolate(rawProgress, [attack.delay, attack.delay + 0.22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
				const x = attack.x - attackIn * 150;
				const y = attack.y + Math.sin((frameWithinBeat / fps + attack.delay * 4) * Math.PI * 2) * 8;

				return (
					<div
						key={attack.label}
						style={{
							position: 'absolute',
							left: x,
							top: y,
							width: 300,
							padding: '22px 24px',
							borderRadius: 8,
							border: `2px solid ${attack.color}`,
							background: 'rgba(12,12,20,0.92)',
							boxShadow: `0 0 46px ${attack.color}42`,
							opacity: attackIn,
							transform: `scale(${0.78 + attackIn * 0.22})`,
							zIndex: 4,
						}}
					>
						<div style={{fontSize: TYPE_SCALE.micro.size + 3, color: COLORS.text_secondary, fontWeight: 900}}>{attack.label}</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 54, lineHeight: 0.9, color: attack.color}}>
							+{rupee(attack.amount)}
						</div>
					</div>
				);
			})}
			<svg viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, zIndex: 3, overflow: 'visible', opacity: crowd}}>
				{attacks.map((attack, index) => (
					<path
						key={attack.label}
						d={`M ${attack.x - 8} ${attack.y + 64} C ${980 + index * 20} ${attack.y + 30}, ${920 - index * 22} ${350 + index * 36}, ${780} ${330 + index * 62}`}
						stroke={attack.color}
						strokeWidth={6}
						strokeLinecap="round"
						fill="none"
						opacity={0.7}
					/>
				))}
			</svg>
		</Shell>
	);
};
