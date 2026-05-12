import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';
import {resolveVisualEvent} from './visualEvents';

type EMIItem = {
	label?: string;
	value?: string;
	amount?: number;
};

const getEmiData = (beat: BeatComponentProps['beat']) => {
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const salary = data.salary as {value?: string; amount?: number} | undefined;
	const totalEmi = data.total_emi as {value?: string; amount?: number} | undefined;
	const remaining = data.remaining as {value?: string; amount?: number; is_critical?: boolean} | undefined;
	const rawEmis = Array.isArray(data.emis) ? (data.emis as EMIItem[]) : [];
	const salaryAmount = Number(salary?.amount ?? 50000);
	const emis = (rawEmis.length ? rawEmis : [
		{label: 'Phone EMI', amount: 4000},
		{label: 'Bike EMI', amount: 6500},
		{label: 'Personal loan', amount: 7500},
	]).map((item, index) => ({
		label: String(item.label ?? `EMI ${index + 1}`),
		amount: Number(item.amount ?? 0),
		value: String(item.value ?? formatIndianRupee(Number(item.amount ?? 0))),
	}));
	const totalAmount = Number(totalEmi?.amount ?? emis.reduce((sum, item) => sum + item.amount, 0));
	const remainingAmount = Number(remaining?.amount ?? Math.max(salaryAmount - totalAmount, 0));
	return {
		salary: {value: salary?.value ?? formatIndianRupee(salaryAmount), amount: salaryAmount},
		emis,
		total_emi: {value: totalEmi?.value ?? formatIndianRupee(totalAmount), amount: totalAmount},
		remaining: {
			value: remaining?.value ?? formatIndianRupee(remainingAmount),
			amount: remainingAmount,
			is_critical: Boolean(remaining?.is_critical ?? remainingAmount / Math.max(salaryAmount, 1) < 0.12),
		},
	};
};

export const EMIStackVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'stacking');
	const event = resolveVisualEvent(beat, scene, 'EMIStackVisualizer');
	const {salary, emis, total_emi, remaining} = getEmiData(beat);
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const rawProgress = getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.82));
	const stackProgress = event.kind === 'first_emi_comfort' ? 0.28 : event.kind === 'critical_leftover' || event.kind === 'salary_squeeze' ? 1 : rawProgress;
	const visibleCount = Math.max(1, Math.ceil(stackProgress * emis.length));
	const remainingRatio = Math.max(0.04, Math.min(remaining.amount / Math.max(salary.amount, 1), 1));
	const pressureColor = remaining.is_critical ? COLORS.danger : COLORS.warning;
	const salaryOpacity = event.kind === 'emi_stacking' ? 0.54 : event.kind === 'critical_leftover' ? 0.22 : 1;
	const stackScale = event.kind === 'emi_stacking' ? 1.12 : event.kind === 'salary_squeeze' ? 1.24 : event.kind === 'critical_leftover' ? 0.82 : 0.9;
	const remainingScale = event.kind === 'critical_leftover' ? 1.28 : event.kind === 'salary_squeeze' ? 1.12 : 0.92;
	const dim = event.kind === 'critical_leftover' ? 0.34 : event.kind === 'salary_squeeze' ? 0.22 : 0.06;

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY}}>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: pressureColor}} />
			<div style={{position: 'absolute', inset: 0, background: 'black', opacity: dim}} />
			<div style={{position: 'absolute', left: SPACING.safe, top: SPACING.safe, opacity: salaryOpacity, transform: `scale(${event.kind === 'first_emi_comfort' ? 1.08 : 1})`, transformOrigin: 'left top'}}>
				<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 900, color: COLORS.text_secondary}}>
					{event.kind === 'first_emi_comfort'
						? 'One EMI looks small'
						: event.kind === 'critical_leftover'
							? 'Salary left after EMIs'
							: event.kind === 'salary_squeeze'
								? 'Salary gets squeezed'
								: 'Fixed payments stack'}
				</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 94, lineHeight: 0.95, marginTop: 20}}>
					{salary.value}
				</div>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 800}}>salary lands</div>
			</div>
			<div style={{position: 'absolute', left: event.kind === 'critical_leftover' ? 520 : 650, top: 170, width: 520, height: 760, transform: `scale(${stackScale})`, transformOrigin: 'center top', opacity: event.kind === 'critical_leftover' ? 0.42 : 1}}>
				{emis.map((emi, index) => {
					const isVisible = index < visibleCount;
					const cardReveal = interpolate(stackProgress, [index / emis.length, (index + 0.65) / emis.length], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					});
					return (
						<div
							key={emi.label}
							style={{
								position: 'absolute',
								left: index * 28,
								top: 60 + index * 128,
								width: 430,
								height: 108,
								borderRadius: 8,
								background: 'rgba(230,57,70,0.12)',
								border: `2px solid ${COLORS.danger}`,
								boxShadow: event.kind === 'emi_stacking' ? '0 0 70px rgba(230,57,70,0.24)' : '0 0 42px rgba(230,57,70,0.14)',
								padding: '22px 26px',
								opacity: isVisible ? cardReveal : 0,
								transform: `translateY(${(1 - cardReveal) * -48}px) scale(${interpolate(reveal, [0, 1], [0.98, 1]) * (event.kind === 'first_emi_comfort' && index > 0 ? 0.86 : 1)})`,
							}}
						>
							<div style={{fontSize: 25, color: COLORS.text_secondary, fontWeight: 900}}>{emi.label}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 54, lineHeight: 0.95}}>{emi.value}</div>
						</div>
					);
				})}
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, top: event.kind === 'critical_leftover' ? 250 : 180, width: 430, height: 660, transform: `scale(${remainingScale})`, transformOrigin: 'right center'}}>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>EMI total</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 78, lineHeight: 0.95, color: COLORS.danger}}>
					{total_emi.value}
				</div>
				<div
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						bottom: 0,
						height: 360,
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
							height: `${remainingRatio * 100}%`,
							background: pressureColor,
							boxShadow: `0 0 60px ${pressureColor}44`,
							transition: 'height 200ms linear',
						}}
					/>
				</div>
				<div style={{position: 'absolute', bottom: -96, right: 0, textAlign: 'right'}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>cash left</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 86, lineHeight: 0.92, color: pressureColor}}>
						{remaining.value}
					</div>
				</div>
			</div>
		</AbsoluteFill>
	);
};
