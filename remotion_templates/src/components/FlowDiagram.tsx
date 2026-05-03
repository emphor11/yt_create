import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, propText, visualNodes} from './visualUtils';

export const FlowDiagram: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const nodes = visualNodes(beat, scene).slice(0, 4);
	const active = Math.min(nodes.length - 1, Math.floor(frameWithinBeat / 14));
	const title = propText(beat.props, 'title', beat.subtext || 'Money flow');
	const accentKey = String(beat.data?.accent ?? beat.props?.accent ?? scene?.data?.accent ?? '').toLowerCase();
	const accent =
		accentKey.includes('danger') || accentKey.includes('red')
			? COLORS.danger
			: accentKey.includes('teal') || accentKey.includes('positive')
				? COLORS.positive
				: COLORS.warning;
	const progress = interpolate(frameWithinBeat, [0, fps * 1.6], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, justifyContent: 'center', padding: 104, overflow: 'hidden'}}>
			<style>{FONT_FACES}</style>
			<div
				style={{
					position: 'absolute',
					inset: -120,
					background: `radial-gradient(circle at ${30 + progress * 28}% 34%, ${accent}2d, transparent 26%), linear-gradient(120deg, #080811, #111420 58%, #07070d)`,
					transform: `scale(${1.02 + progress * 0.035})`,
				}}
			/>
			<div style={{fontFamily: BODY_FONT_FAMILY, color: COLORS.muted, fontSize: 34, fontWeight: 900, marginBottom: 48}}>
				{title.toUpperCase()}
			</div>
			<div style={{display: 'grid', gridTemplateColumns: `repeat(${nodes.length}, 1fr)`, gap: 20, alignItems: 'center', position: 'relative'}}>
				{nodes.map((node, index) => {
					const local = Math.max(0, frameWithinBeat - index * 10);
					const reveal = spring({frame: Math.min(local, 14), fps, config: {damping: 15, stiffness: 170}, durationInFrames: 14});
					const isActive = index <= active;
					const nodeAccent = index === nodes.length - 1 ? accent : COLORS.teal;
					return (
						<div key={`${node.label}-${index}`} style={{display: 'grid', gridTemplateColumns: index === nodes.length - 1 ? '1fr' : '1fr 58px', alignItems: 'center', gap: 14}}>
							<div
								style={{
									opacity: interpolate(local, [0, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
									transform: `scale(${0.94 + reveal * 0.06})`,
									background: isActive ? 'rgba(255,255,255,0.115)' : 'rgba(255,255,255,0.055)',
									border: `2px solid ${isActive ? nodeAccent : COLORS.stroke}`,
									boxShadow: isActive ? `0 0 44px ${nodeAccent}22` : 'none',
									padding: '46px 26px',
									minHeight: 220,
									textAlign: 'center',
									borderRadius: 8,
								}}
							>
								{node.value ? (
									<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 64, lineHeight: 0.9, marginTop: 12, color: node.color || COLORS.text}}>
										{node.value.toUpperCase()}
									</div>
								) : null}
								<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: node.value ? 40 : 56, lineHeight: 0.95, marginTop: 14}}>
									{node.label.toUpperCase()}
								</div>
								{node.subtext ? (
									<div style={{fontFamily: BODY_FONT_FAMILY, fontSize: 24, fontWeight: 800, color: COLORS.muted, marginTop: 16}}>
										{node.subtext.toUpperCase()}
									</div>
								) : null}
							</div>
							{index < nodes.length - 1 ? (
								<div style={{height: 12, borderRadius: 99, background: COLORS.stroke, overflow: 'hidden', opacity: index < active ? 1 : 0.35}}>
									<div
										style={{
											width: `${Math.max(0, Math.min((progress * nodes.length - index) * 100, 100))}%`,
											height: '100%',
											background: nodeAccent,
											boxShadow: `0 0 24px ${nodeAccent}`,
										}}
									/>
								</div>
							) : null}
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};
