import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';

type Flow = {
	label: string;
	value: string;
	amount: number;
	color: 'red' | 'orange' | 'teal';
	order: number;
};

const moneyFlowData = (beat: BeatComponentProps['beat']) => {
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const source = data.source as {label?: string; value?: string; amount?: number} | undefined;
	const flows = Array.isArray(data.flows) ? (data.flows as Flow[]) : [];
	const remainder = data.remainder as {value?: string; amount?: number; is_dangerous?: boolean} | undefined;
	return {
		source: {
			label: source?.label ?? 'Salary',
			value: source?.value ?? formatIndianRupee(Number(source?.amount ?? 0)),
			amount: Number(source?.amount ?? 0),
		},
		flows: flows
			.map((flow, index) => ({
				label: String(flow.label ?? `Expense ${index + 1}`),
				value: String(flow.value ?? formatIndianRupee(Number(flow.amount ?? 0))),
				amount: Number(flow.amount ?? 0),
				color: flow.color ?? 'orange',
				order: Number(flow.order ?? index + 1),
			}))
			.sort((a, b) => a.order - b.order)
			.slice(0, 5),
		remainder: {
			value: remainder?.value ?? formatIndianRupee(Number(remainder?.amount ?? 0)),
			amount: Number(remainder?.amount ?? 0),
			is_dangerous: Boolean(remainder?.is_dangerous),
		},
	};
};

export const MoneyFlowDiagram: React.FC<BeatComponentProps> = ({beat, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const {source, flows, remainder} = moneyFlowData(beat);
	const total = Math.max(source.amount, 1);
	const progress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.75)) / 1, 1);
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const opacity = interpolate(reveal, [0, 1], [0, 1]);
	const sourceX = 240;
	const sourceY = 540;
	const pipeStartX = 500;
	const pipeEndX = 1380;
	const rowStartY = 290;
	const rowGap = 118;
	const accentColor = remainder.is_dangerous ? COLORS.danger : COLORS.warning;

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
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: accentColor}} />
			<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 800, color: COLORS.text_secondary}}>
				Where the money goes
			</div>
			<div
				style={{
					position: 'absolute',
					left: sourceX - 110,
					top: sourceY - 100,
					width: 220,
					height: 200,
					borderRadius: 8,
					background: COLORS.bg_surface,
					border: `2px solid ${COLORS.stroke}`,
					display: 'flex',
					flexDirection: 'column',
					alignItems: 'center',
					justifyContent: 'center',
					opacity,
					transform: `scale(${interpolate(reveal, [0, 1], [0.94, 1])})`,
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>
					{source.label}
				</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58, lineHeight: 1}}>
					{source.value}
				</div>
			</div>
			<svg viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0}}>
				{flows.map((flow, index) => {
					const y = rowStartY + index * rowGap;
					const width = Math.max(10, Math.min(68, (flow.amount / total) * 120));
					const color = flow.color === 'red' ? COLORS.danger : flow.color === 'teal' ? COLORS.positive : COLORS.warning;
					const drawX = pipeStartX + (pipeEndX - pipeStartX) * progress;
					return (
						<g key={`${flow.label}-${index}`}>
							<path
								d={`M ${pipeStartX} ${sourceY} C 680 ${sourceY}, 680 ${y}, ${pipeEndX} ${y}`}
								stroke="rgba(255,255,255,0.10)"
								strokeWidth={width + 10}
								fill="none"
								strokeLinecap="round"
							/>
							<path
								d={`M ${pipeStartX} ${sourceY} C 680 ${sourceY}, 680 ${y}, ${drawX} ${y}`}
								stroke={color}
								strokeWidth={width}
								fill="none"
								strokeLinecap="round"
								opacity={0.92}
							/>
							<circle cx={drawX} cy={y} r={Math.max(8, width / 3)} fill={color} opacity={progress > 0.04 ? 1 : 0} />
						</g>
					);
				})}
			</svg>
			{flows.map((flow, index) => {
				const y = rowStartY + index * rowGap;
				return (
					<div
						key={flow.label}
						style={{
							position: 'absolute',
							left: pipeEndX + 40,
							top: y - 38,
							opacity: progress,
						}}
					>
						<div style={{fontSize: TYPE_SCALE.subtext.size, fontWeight: 800}}>{flow.label}</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 48, lineHeight: 1}}>{flow.value}</div>
					</div>
				);
			})}
			<div
				style={{
					position: 'absolute',
					right: SPACING.safe,
					bottom: SPACING.safe,
					padding: '26px 34px',
					borderRadius: 8,
					background: remainder.is_dangerous ? 'rgba(230,57,70,0.16)' : COLORS.bg_surface,
					border: `2px solid ${accentColor}`,
					textAlign: 'right',
					opacity: interpolate(progress, [0.72, 1], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
				}}
			>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 700}}>Left over</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 82, lineHeight: 0.95, color: accentColor}}>
					{remainder.value}
				</div>
			</div>
		</AbsoluteFill>
	);
};
