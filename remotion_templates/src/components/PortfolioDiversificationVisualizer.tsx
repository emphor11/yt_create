import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, getBeatData, getBeatProgress} from './visualUtils';

type Asset = {
	label?: string;
	allocation?: number;
	color?: string;
};

const defaultAssets: Asset[] = [
	{label: 'Equity', allocation: 45, color: COLORS.positive},
	{label: 'Debt', allocation: 25, color: COLORS.neutral},
	{label: 'FD', allocation: 15, color: COLORS.warning},
	{label: 'Gold', allocation: 10, color: '#B8A44C'},
	{label: 'Cash', allocation: 5, color: COLORS.text_secondary},
];

export const PortfolioDiversificationVisualizer: React.FC<BeatComponentProps> = ({beat, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'spread');
	const assets = (Array.isArray(data.assets) ? (data.assets as Asset[]) : defaultAssets).slice(0, 6);
	const progress = phase === 'concentrated' ? 0.2 : phase === 'impact' ? 1 : getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.8));
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const gridOpacity = phase === 'concentrated' ? 0 : interpolate(progress, [0.18, 0.62], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const shock = phase === 'impact' ? interpolate(frameWithinBeat % 30, [0, 15, 30], [0, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0;

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, padding: SPACING.safe}}>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.positive}} />
			<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 84, lineHeight: 0.92, maxWidth: 700, opacity: reveal}}>
				{phase === 'concentrated' ? 'ONE BET DECIDES EVERYTHING' : phase === 'impact' ? 'ONE FALL DOES NOT BREAK ALL' : 'RISK GETS SPREAD'}
			</div>
			<div style={{position: 'absolute', left: 190, bottom: 170, width: 500, height: 500}}>
				<div
					style={{
						position: 'absolute',
						left: 115,
						top: 115,
						width: 270,
						height: 270,
						borderRadius: 8,
						background: 'rgba(230,57,70,0.14)',
						border: `3px solid ${COLORS.danger}`,
						transform: `scale(${phase === 'concentrated' ? 1 : interpolate(progress, [0, 0.5], [1, 0.48], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}) rotate(${shock * -4}deg)`,
						opacity: phase === 'spread' ? 0.35 : 1,
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: 68,
						lineHeight: 0.9,
						textAlign: 'center',
					}}
				>
					ONE STOCK
				</div>
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, top: 230, width: 920, height: 650, opacity: gridOpacity}}>
				{assets.map((asset, index) => {
					const row = Math.floor(index / 3);
					const col = index % 3;
					const drop = phase === 'impact' && index === 0;
					return (
						<div
							key={`${asset.label}-${index}`}
							style={{
								position: 'absolute',
								left: col * 300,
								top: row * 260 + (drop ? 70 : 0),
								width: 240,
								height: 190,
								borderRadius: 8,
								background: drop ? 'rgba(230,57,70,0.16)' : COLORS.bg_surface,
								border: `2px solid ${drop ? COLORS.danger : asset.color ?? COLORS.positive}`,
								boxShadow: `0 0 42px ${drop ? COLORS.danger : asset.color ?? COLORS.positive}22`,
								padding: 24,
								transform: `translateY(${(1 - reveal) * 34}px)`,
							}}
						>
							<div style={{fontSize: 26, color: COLORS.text_secondary, fontWeight: 900}}>{asset.label ?? `Asset ${index + 1}`}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 70, lineHeight: 0.95}}>
								{Math.round(Number(asset.allocation ?? 0))}%
							</div>
							<div style={{fontSize: 22, color: drop ? COLORS.danger : COLORS.text_secondary, fontWeight: 900}}>
								{drop ? 'falls' : 'holds'}
							</div>
						</div>
					);
				})}
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, bottom: SPACING.safe, fontSize: 32, color: COLORS.text_secondary, fontWeight: 900}}>
				No single basket should decide the future.
			</div>
		</AbsoluteFill>
	);
};
