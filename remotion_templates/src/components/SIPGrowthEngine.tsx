import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';

export const SIPGrowthEngine: React.FC<BeatComponentProps> = ({beat, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const sip = data.monthly_sip as {value?: string; amount?: number} | undefined;
	const totalInvested = Number(data.total_invested ?? 0);
	const finalCorpus = Number(data.final_corpus ?? 0);
	const returnsEarned = Number(data.returns_earned ?? Math.max(finalCorpus - totalInvested, 0));
	const durationYears = Number(data.duration_years ?? 20);
	const annualReturn = Number(data.annual_return_rate ?? 12);
	const aweRatio = Number(data.awe_ratio ?? (totalInvested ? finalCorpus / totalInvested : 0));
	const progress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.75)), 1);
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const investedHeight = 230;
	const corpusHeight = Math.min(540, Math.max(260, investedHeight * Math.max(aweRatio, 1.2) * 0.78));
	const investedFill = investedHeight * Math.min(progress * 1.35, 1);
	const corpusFill = corpusHeight * Math.max(0, Math.min((progress - 0.28) / 0.72, 1));

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
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.positive}} />
			<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 800, color: COLORS.text_secondary}}>
				Compounding engine
			</div>
			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					top: 220,
					width: 560,
					transform: `scale(${interpolate(reveal, [0, 1], [0.96, 1])})`,
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>Monthly SIP</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 104, lineHeight: 0.94}}>
					{sip?.value ?? formatIndianRupee(Number(sip?.amount ?? 0))}
				</div>
				<div style={{marginTop: SPACING.md, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>
					{durationYears} years at {annualReturn}% returns
				</div>
			</div>
			<div
				style={{
					position: 'absolute',
					left: 780,
					right: SPACING.safe,
					bottom: 190,
					height: 620,
					display: 'flex',
					alignItems: 'flex-end',
					gap: 120,
				}}
			>
				<div style={{width: 280}}>
					<div
						style={{
							height: investedHeight,
							borderRadius: 8,
							background: COLORS.bg_surface,
							border: `1px solid ${COLORS.stroke}`,
							display: 'flex',
							alignItems: 'flex-end',
							overflow: 'hidden',
						}}
					>
						<div style={{height: investedFill, width: '100%', background: COLORS.neutral}} />
					</div>
					<div style={{marginTop: SPACING.md, fontSize: TYPE_SCALE.micro.size + 4, color: COLORS.text_secondary, fontWeight: 700}}>
						You invested
					</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 52, lineHeight: 1}}>
						{formatIndianRupee(totalInvested)}
					</div>
				</div>
				<div style={{width: 340}}>
					<div
						style={{
							height: corpusHeight,
							borderRadius: 8,
							background: 'rgba(46,196,182,0.08)',
							border: `2px solid ${COLORS.positive}`,
							display: 'flex',
							alignItems: 'flex-end',
							overflow: 'hidden',
							boxShadow: '0 0 60px rgba(46,196,182,0.18)',
						}}
					>
						<div style={{height: corpusFill, width: '100%', background: COLORS.positive}} />
					</div>
					<div style={{marginTop: SPACING.md, fontSize: TYPE_SCALE.micro.size + 4, color: COLORS.text_secondary, fontWeight: 700}}>
						Final corpus
					</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 64, lineHeight: 1, color: COLORS.positive}}>
						{formatIndianRupee(finalCorpus)}
					</div>
				</div>
			</div>
			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					bottom: SPACING.safe,
					padding: '24px 30px',
					borderRadius: 8,
					background: COLORS.bg_surface,
					border: `1px solid ${COLORS.stroke}`,
					opacity: interpolate(progress, [0.72, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>Returns earned</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 74, lineHeight: 0.95, color: COLORS.positive}}>
					{formatIndianRupee(returnsEarned)}
				</div>
			</div>
		</AbsoluteFill>
	);
};
