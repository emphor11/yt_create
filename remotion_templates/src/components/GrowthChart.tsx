import React from 'react';
import {AbsoluteFill, interpolate, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, sceneText, sceneValues} from './visualUtils';

export const GrowthChart: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat}) => {
	const {fps} = useVideoConfig();
	const values = sceneValues(scene);
	const start = String(beat.data?.start ?? beat.props?.start ?? sceneText(scene, 'start', values[0] || 'Start'));
	const end = String(beat.data?.end ?? beat.props?.end ?? sceneText(scene, 'end', values[values.length - 1] || beat.text || 'Result'));
	const rate = String(beat.data?.rate ?? beat.props?.rate ?? sceneText(scene, 'rate', beat.subtext || ''));
	const curve = String(beat.data?.curve ?? beat.props?.curve ?? sceneText(scene, 'curve', '')).toLowerCase();
	const visualType = String(beat.data?.visual_type ?? sceneText(scene, 'visual_type', '')).toLowerCase();
	const curveDown = curve === 'down' || visualType.includes('decay') || beat.text.toLowerCase().includes('leak') || beat.text.toLowerCase().includes('fall');
	const progress = interpolate(frameWithinBeat, [0, fps * 1.4], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const accent = curveDown ? COLORS.red : COLORS.teal;
	const lineWidth = 760 * progress;
	const endY = curveDown ? 420 : 210;
	const ghostBars = curveDown ? [0.92, 0.72, 0.52] : [0.32, 0.58, 0.92];

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.background, color: COLORS.text, padding: 110, justifyContent: 'center', overflow: 'hidden'}}>
			<style>{FONT_FACES}</style>
			<div
				style={{
					position: 'absolute',
					inset: -120,
					background: `radial-gradient(circle at ${curveDown ? 70 : 35}% ${curveDown ? 36 : 62}%, ${accent}24, transparent 28%), linear-gradient(120deg, #080811, #101521 58%, #07070d)`,
				}}
			/>
			<div style={{display: 'grid', gridTemplateColumns: '360px minmax(620px, 1fr) 360px', gap: 56, alignItems: 'center', width: '100%', position: 'relative', zIndex: 1}}>
				<ValueBlock label="START" value={start} accent={COLORS.blue} />
				<div style={{height: 460, position: 'relative'}}>
					<div style={{position: 'absolute', left: 0, right: 0, bottom: 80, height: 2, background: COLORS.stroke}} />
					{ghostBars.map((height, index) => (
						<div
							key={index}
							style={{
								position: 'absolute',
								left: 76 + index * 170,
								bottom: 84,
								width: 52,
								height: 260 * height * progress,
								background: `linear-gradient(180deg, ${accent}55, ${accent}11)`,
								border: `1px solid ${accent}55`,
								opacity: 0.5,
							}}
						/>
					))}
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
							borderRadius: 99,
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
