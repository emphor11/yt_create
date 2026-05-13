import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {CinematicEvent} from '../types';
import {COLORS, SPACING, TYPE_SCALE} from './visualUtils';
import {activeCinematicEvent, eventColor, eventPresence, sceneCinematicEvents} from './cinematicEvents';
import {currentSceneProgress} from './narrationTiming';

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const shortText = (text: string, fallback: string) => {
	const words = text.replace(/[.!?]+$/g, '').split(/\s+/).filter(Boolean);
	return words.slice(0, 7).join(' ') || fallback;
};

const modeLabel = (event: CinematicEvent | null) =>
	String(event?.label || event?.entity_id || 'Key idea').replace(/_/g, ' ');

const verbLabel = (event: CinematicEvent | null) =>
	String(event?.visual_verb || event?.action || 'reveal').replace(/_/g, ' ').toUpperCase();

const MemoryChip: React.FC<{event: CinematicEvent; index: number; activeId: string}> = ({event, index, activeId}) => {
	const active = event.id === activeId;
	return (
		<div
			style={{
				height: 58,
				minWidth: 155,
				padding: '12px 18px',
				borderRadius: 8,
				border: `1px solid ${active ? COLORS.warning : 'rgba(255,255,255,0.16)'}`,
				background: active ? 'rgba(255,159,28,0.18)' : 'rgba(255,255,255,0.06)',
				opacity: active ? 1 : clamp(0.58 - index * 0.04, 0.22, 0.58),
				color: active ? COLORS.text_primary : COLORS.text_secondary,
				fontSize: 20,
				fontWeight: 850,
				whiteSpace: 'nowrap',
				overflow: 'hidden',
				textOverflow: 'ellipsis',
			}}
		>
			{modeLabel(event)}
		</div>
	);
};

export const UniversalMechanismRenderer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const events = sceneCinematicEvents(scene, beat);
	const progress = currentSceneProgress(scene, beat, frameWithinBeat, fps);
	const active = activeCinematicEvent(scene, beat, frameWithinBeat, fps);
	const presence = eventPresence(progress, active);
	const accent = eventColor(active, COLORS.warning);
	const enter = spring({frame: Math.min(frameWithinBeat, 24), fps, config: {damping: 20, stiffness: 130, mass: 0.8}});
	const gx = clamp(Number(active?.gravity?.x ?? 0.5), 0.18, 0.82);
	const gy = clamp(Number(active?.gravity?.y ?? 0.5), 0.22, 0.78);
	const x = gx * 1920;
	const y = gy * 1080;
	const mode = String(active?.visual_mode ?? 'generic_focus');
	const isNegative = /expense|debt|shock|erosion|survivor|spiral/.test(mode);
	const title = modeLabel(active);
	const subline = shortText(String(active?.text || beat.source_text || beat.text || ''), verbLabel(active));
	const ringScale = 0.84 + presence * 0.28;

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, overflow: 'hidden', padding: SPACING.safe}}>
			<style>{FONT_FACES}</style>
			<div
				style={{
					position: 'absolute',
					inset: -150,
					background: `radial-gradient(circle at ${gx * 100}% ${gy * 100}%, ${accent}38, transparent 27%), linear-gradient(135deg, #05050b, ${isNegative ? '#180a0f' : '#071512'} 56%, #05050b)`,
				}}
			/>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: accent}} />
			<div
				style={{
					position: 'absolute',
					left: x - 280,
					top: y - 190,
					width: 560,
					minHeight: 330,
					transform: `scale(${0.88 + enter * 0.1 + presence * 0.06})`,
					transformOrigin: 'center',
					textAlign: gx > 0.58 ? 'right' : 'left',
				}}
			>
				<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 950, color: accent, letterSpacing: 0}}>{verbLabel(active)}</div>
				<div style={{marginTop: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: title.length > 18 ? 82 : 104, lineHeight: 0.86, textTransform: 'uppercase'}}>
					{title}
				</div>
				<div style={{marginTop: 28, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 800, lineHeight: 1.15}}>
					{subline}
				</div>
			</div>
			<svg viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
				<circle cx={x} cy={y} r={170 * ringScale} fill="none" stroke={accent} strokeWidth={8} opacity={0.44} />
				<circle cx={x} cy={y} r={260 * ringScale} fill="none" stroke={accent} strokeWidth={3} opacity={0.2} />
				{events.slice(0, 9).map((event, index) => {
					const ex = clamp(Number(event.gravity?.x ?? 0.5), 0.18, 0.82) * 1920;
					const ey = clamp(Number(event.gravity?.y ?? 0.5), 0.22, 0.78) * 1080;
					const past = Number(event.start_progress ?? 0) <= progress;
					return (
						<g key={event.id ?? index} opacity={past ? 0.34 : 0.1}>
							<circle cx={ex} cy={ey} r={event.id === active?.id ? 14 : 8} fill={event.id === active?.id ? accent : 'rgba(255,255,255,0.5)'} />
							{index > 0 ? <path d={`M ${events[index - 1]?.gravity?.x ? clamp(Number(events[index - 1].gravity?.x), 0.18, 0.82) * 1920 : 960} ${events[index - 1]?.gravity?.y ? clamp(Number(events[index - 1].gravity?.y), 0.22, 0.78) * 1080 : 540} L ${ex} ${ey}`} stroke="rgba(255,255,255,0.2)" strokeWidth={3} /> : null}
						</g>
					);
				})}
			</svg>
			<div style={{position: 'absolute', left: 120, right: 120, bottom: 84, display: 'flex', gap: 12, justifyContent: 'center', overflow: 'hidden'}}>
				{events.slice(0, 8).map((event, index) => (
					<MemoryChip key={event.id ?? index} event={event} index={index} activeId={String(active?.id ?? '')} />
				))}
			</div>
			<div style={{position: 'absolute', right: 120, top: 94, fontSize: 22, fontWeight: 900, color: COLORS.text_tertiary}}>
				{Math.round(interpolate(progress, [0, 1], [1, Math.max(1, events.length)], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}))}/{Math.max(1, events.length)}
			</div>
		</AbsoluteFill>
	);
};
