import React from 'react';
import {AbsoluteFill, interpolate, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, sceneText, sceneValues} from './visualUtils';

export const GrowthChart: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const values = sceneValues(scene);
	const start = String(beat.props?.start ?? sceneText(scene, 'start', values[0] || 'Start'));
	const end = String(beat.props?.end ?? sceneText(scene, 'end', values[values.length - 1] || beat.text || 'Result'));
	const rate = String(beat.props?.rate ?? sceneText(scene, 'rate', beat.subtext || ''));
	const curve = String(beat.props?.curve ?? sceneText(scene, 'curve', '')).toLowerCase();
	const visualType = sceneText(scene, 'visual_type', '').toLowerCase();
	const curveDown = curve === 'down' || visualType.includes('decay') || beat.text.toLowerCase().includes('leak') || beat.text.toLowerCase().includes('fall');
	const progress = interpolate(frameWithinBeat, [0, fps * 1.4], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const accent = curveDown ? COLORS.red : COLORS.teal;
	const lineWidth = 760 * progress;
	const endY = curveDown ? 420 : 210;

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, padding: 110, justifyContent: 'center'}}>
			<style>{FONT_FACES}</style>
			<div style={{display: 'grid', gridTemplateColumns: '360px 1fr 360px', gap: 56, alignItems: 'center'}}>
				<ValueBlock label="START" value={start} accent={COLORS.blue} />
				<div style={{height: 460, position: 'relative'}}>
					<div style={{position: 'absolute', left: 0, right: 0, bottom: 80, height: 2, background: COLORS.stroke}} />
					<div
						style={{
							position: 'absolute',
							left: 0,
							top: curveDown ? 190 : 390,
							width: lineWidth,
							height: 12,
							background: accent,
							transform: `rotate(${curveDown ? 13 : -13}deg)`,
							transformOrigin: 'left center',
							boxShadow: `0 0 40px ${accent}`,
						}}
					/>
					<div
						style={{
							position: 'absolute',
							left: Math.max(0, lineWidth - 26),
							top: endY,
							width: 34,
							height: 34,
							borderRadius: 999,
							background: accent,
							boxShadow: `0 0 36px ${accent}`,
							opacity: progress,
						}}
					/>
					{rate ? (
						<div
							style={{
								position: 'absolute',
								left: 210,
								top: 20,
								fontFamily: BODY_FONT_FAMILY,
								fontSize: 34,
								fontWeight: 900,
								color: accent,
							}}
						>
							{rate}
						</div>
					) : null}
				</div>
				<ValueBlock label={curveDown ? 'AFTER' : 'END'} value={end} accent={accent} />
			</div>
		</AbsoluteFill>
	);
};

const ValueBlock: React.FC<{label: string; value: string; accent: string}> = ({label, value, accent}) => (
	<div style={{background: COLORS.panel, border: `2px solid ${accent}`, padding: '46px 34px', minHeight: 250, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
		<div style={{fontFamily: BODY_FONT_FAMILY, fontSize: 28, color: COLORS.muted, fontWeight: 900}}>{label}</div>
		<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 72, lineHeight: 0.95, marginTop: 18}}>{value.toUpperCase()}</div>
	</div>
);
