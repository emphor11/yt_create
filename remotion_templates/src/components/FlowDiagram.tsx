import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, stepLabels} from './visualUtils';

export const FlowDiagram: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const nodes = stepLabels(beat, scene).slice(0, 4);
	const active = Math.min(nodes.length - 1, Math.floor(frameWithinBeat / 14));

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, justifyContent: 'center', padding: 104}}>
			<style>{FONT_FACES}</style>
			<div style={{fontFamily: BODY_FONT_FAMILY, color: COLORS.muted, fontSize: 34, fontWeight: 900, marginBottom: 48}}>
				{(beat.subtext || 'Money flow').toUpperCase()}
			</div>
			<div style={{display: 'grid', gridTemplateColumns: `repeat(${nodes.length}, 1fr)`, gap: 20, alignItems: 'center'}}>
				{nodes.map((node, index) => {
					const local = Math.max(0, frameWithinBeat - index * 10);
					const reveal = spring({frame: Math.min(local, 14), fps, config: {damping: 15, stiffness: 170}, durationInFrames: 14});
					const isActive = index <= active;
					const accent = index === nodes.length - 1 ? COLORS.orange : COLORS.teal;
					return (
						<div key={`${node}-${index}`} style={{display: 'grid', gridTemplateColumns: index === nodes.length - 1 ? '1fr' : '1fr 58px', alignItems: 'center', gap: 14}}>
							<div
								style={{
									opacity: interpolate(local, [0, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
									transform: `scale(${0.94 + reveal * 0.06})`,
									background: isActive ? COLORS.panelStrong : COLORS.panel,
									border: `2px solid ${isActive ? accent : COLORS.stroke}`,
									padding: '46px 26px',
									minHeight: 220,
									textAlign: 'center',
								}}
							>
								<div style={{fontFamily: BODY_FONT_FAMILY, fontSize: 24, fontWeight: 900, color: COLORS.dim}}>FLOW {index + 1}</div>
								<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 56, lineHeight: 0.95, marginTop: 18}}>{node.toUpperCase()}</div>
							</div>
							{index < nodes.length - 1 ? (
								<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 44, color: COLORS.orange, opacity: index < active ? 1 : 0.28}}>
									&gt;
								</div>
							) : null}
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

