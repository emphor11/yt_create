import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, stepLabels} from './visualUtils';

export const StepFlow: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const steps = stepLabels(beat, scene);
	const revealCount = Math.min(steps.length, Math.max(1, Math.floor(frameWithinBeat / 10) + 1));

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, justifyContent: 'center', padding: 100}}>
			<style>{FONT_FACES}</style>
			<div style={{fontFamily: BODY_FONT_FAMILY, color: COLORS.muted, fontSize: 34, fontWeight: 900, marginBottom: 42}}>
				{(beat.subtext || 'Step by step').toUpperCase()}
			</div>
			<div style={{display: 'grid', gridTemplateColumns: `repeat(${steps.length}, 1fr)`, gap: 24, alignItems: 'center'}}>
				{steps.map((step, index) => {
					const local = Math.max(0, frameWithinBeat - index * 10);
					const reveal = spring({frame: Math.min(local, 14), fps, config: {damping: 15, stiffness: 170}, durationInFrames: 14});
					const visible = index < revealCount;
					return (
						<div key={`${step}-${index}`} style={{display: 'contents'}}>
							<div
								style={{
									opacity: visible ? interpolate(local, [0, 10], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 0,
									transform: `translateY(${(1 - reveal) * 28}px)`,
									background: index === steps.length - 1 ? COLORS.panelStrong : COLORS.panel,
									border: `2px solid ${index === steps.length - 1 ? COLORS.orange : COLORS.stroke}`,
									padding: '42px 28px',
									minHeight: 210,
								}}
							>
								<div style={{fontFamily: BODY_FONT_FAMILY, fontSize: 28, fontWeight: 900, color: COLORS.orange}}>
									{String(index + 1).padStart(2, '0')}
								</div>
								<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 54, lineHeight: 0.95, marginTop: 18}}>
									{step.toUpperCase()}
								</div>
							</div>
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};

