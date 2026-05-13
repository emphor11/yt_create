import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, getBeatData, getBeatProgress} from './visualUtils';
import {currentSceneProgress, firstKeywordIndex, narrationSentences, sceneNarrationText} from './narrationTiming';
import {activeCinematicEvent, eventPresence} from './cinematicEvents';
import {CinematicEvent} from '../types';

type EmergencyMode = 'boring_buffer' | 'shock_focus' | 'debt_prevention' | 'plan_survives';

type EmergencyMoment = {
	mode: EmergencyMode;
	startProgress: number;
	endProgress: number;
};

const keywords: Record<EmergencyMode, string[]> = {
	boring_buffer: ['emergency fund', 'cash buffer', 'buffer', 'six month', '6 month', 'boring', 'savings'],
	shock_focus: ['medical', 'hospital', 'bill', 'repair', 'job loss', 'income delay', 'unexpected', 'emergency', 'shock'],
	debt_prevention: ['credit card', 'debt', 'borrow', 'loan', 'swipe', 'interest'],
	plan_survives: ['survive', 'protect', 'breathing room', 'calm', 'buys time', 'plan', 'control'],
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const buildEmergencySequence = (narration: string): EmergencyMoment[] => {
	const sentences = narrationSentences(narration);
	const moments: EmergencyMoment[] = [];
	for (const sentence of sentences) {
		const hits = (Object.keys(keywords) as EmergencyMode[]).map((mode) => ({
			mode,
			hit: firstKeywordIndex(sentence.text, keywords[mode]),
		})).filter((item) => item.hit >= 0).sort((a, b) => a.hit - b.hit);
		if (hits.length === 0) {
			continue;
		}
		const span = sentence.endProgress - sentence.startProgress;
		hits.forEach((hit, index) => {
			moments.push({
				mode: hit.mode,
				startProgress: clamp(sentence.startProgress + (span * index) / hits.length - 0.008, 0, 1),
				endProgress: clamp(sentence.startProgress + (span * (index + 1)) / hits.length + 0.014, 0, 1),
			});
		});
	}
	return moments.length > 0
		? moments
		: [
			{mode: 'boring_buffer', startProgress: 0, endProgress: 0.28},
			{mode: 'shock_focus', startProgress: 0.24, endProgress: 0.54},
			{mode: 'debt_prevention', startProgress: 0.5, endProgress: 0.78},
			{mode: 'plan_survives', startProgress: 0.74, endProgress: 1},
		];
};

const resolveMode = (progress: number, narration: string, fallback: EmergencyMode): EmergencyMode => {
	const sequence = buildEmergencySequence(narration);
	const active = sequence.find((moment) => progress >= moment.startProgress && progress <= moment.endProgress);
	if (active) {
		return active.mode;
	}
	const previous = sequence.filter((moment) => moment.startProgress <= progress);
	return previous[previous.length - 1]?.mode ?? fallback;
};

const modeFromCinematicEvent = (event: CinematicEvent | null, fallback: EmergencyMode): EmergencyMode => {
	const mode = String(event?.visual_mode ?? '');
	const verb = String(event?.visual_verb ?? '');
	if (/shock|impact/.test(mode) || verb === 'impact') {
		return 'shock_focus';
	}
	if (/debt|spiral|expense/.test(mode)) {
		return 'debt_prevention';
	}
	if (/protect|buffer|protection/.test(mode)) {
		return 'boring_buffer';
	}
	if (/survivor|hero|reveal/.test(mode)) {
		return 'plan_survives';
	}
	return fallback;
};

const shockCopy = (event: CinematicEvent | null, fallback: string) => {
	const label = String(event?.label || fallback || 'Unexpected bill');
	const variant = String(event?.variant ?? '');
	if (/income_gap/.test(variant)) {
		return {hero: 'INCOME GAP', label, sub: 'the buffer buys time'};
	}
	if (/repair_hit/.test(variant)) {
		return {hero: 'REPAIR HIT', label, sub: 'life creates the bill first'};
	}
	if (/debt|card/.test(variant)) {
		return {hero: 'BORROWING BLOCKED', label, sub: 'one problem does not become two'};
	}
	return {hero: 'SHOCK', label, sub: 'life does not wait for payday'};
};

const Ring: React.FC<{size: number; color: string; opacity: number; top: number; left: number}> = ({size, color, opacity, top, left}) => (
	<div
		style={{
			position: 'absolute',
			top,
			left,
			width: size,
			height: size,
			borderRadius: '50%',
			border: `5px solid ${color}`,
			opacity,
		}}
	/>
);

export const EmergencyFundVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const narration = sceneNarrationText(scene);
	const sceneProgress = scene ? currentSceneProgress(scene, beat, frameWithinBeat, fps) : getBeatProgress(frameWithinBeat, durationFrames);
	const fallback = String(beat.beat_phase ?? data.active_phase ?? 'boring_buffer') as EmergencyMode;
	const cinematicEvent = activeCinematicEvent(scene, beat, frameWithinBeat, fps);
	const cinematicPresence = eventPresence(sceneProgress, cinematicEvent);
	const mode = modeFromCinematicEvent(cinematicEvent, resolveMode(sceneProgress, narration, fallback));
	const enter = spring({frame: frameWithinBeat, fps, config: {damping: 20, stiffness: 132, mass: 0.9}});
	const wave = interpolate(Math.sin(frameWithinBeat / 8), [-1, 1], [0.88, 1.08]);
	const bufferLabel = String(data.buffer_label ?? '6-month buffer');
	const bufferValue = String(data.buffer_value ?? '6 months');
	const shockLabel = String(data.shock_label ?? 'Unexpected bill');
	const shock = shockCopy(cinematicEvent, shockLabel);

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, overflow: 'hidden', color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY}}>
			<style>{FONT_FACES}</style>
			<AbsoluteFill
				style={{
					background: mode === 'shock_focus'
						? 'radial-gradient(circle at 42% 38%, rgba(230,57,70,0.26), rgba(10,10,20,0.98) 58%)'
						: mode === 'debt_prevention'
							? 'radial-gradient(circle at 58% 50%, rgba(255,159,28,0.24), rgba(10,10,20,0.98) 64%)'
							: 'radial-gradient(circle at 50% 48%, rgba(46,196,182,0.24), rgba(10,10,20,0.96) 64%)',
				}}
			/>
			{mode === 'boring_buffer' && (
				<div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center'}}>
					<div style={{transform: `scale(${0.92 + enter * 0.08})`}}>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 122, lineHeight: 0.92, color: COLORS.teal}}>{bufferValue}</div>
						<div style={{marginTop: 22, fontSize: 36, color: COLORS.muted}}>{bufferLabel}</div>
						<div style={{margin: '44px auto 0', width: 540, height: 30, borderRadius: 999, background: 'rgba(255,255,255,0.14)', overflow: 'hidden'}}>
							<div style={{height: '100%', width: `${70 + enter * 20}%`, borderRadius: 999, background: COLORS.teal, boxShadow: `0 0 38px ${COLORS.teal}66`}} />
						</div>
					</div>
				</div>
			)}
			{mode === 'shock_focus' && (
				<div style={{position: 'absolute', inset: 0}}>
					<Ring size={520 * wave} color={COLORS.red} opacity={0.26} top={80} left={280} />
					<Ring size={720 * wave} color={COLORS.red} opacity={0.12} top={-10} left={180} />
					<div style={{position: 'absolute', left: 310, top: 205, transform: `translateY(${(1 - enter) * 30}px)`}}>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: shock.hero.length > 12 ? 104 : 132, lineHeight: 0.88, color: COLORS.red}}>{shock.hero}</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 76, lineHeight: 0.95}}>{shock.label.toUpperCase()}</div>
						<div style={{marginTop: 28, fontSize: 34, color: COLORS.muted}}>{shock.sub}</div>
					</div>
				</div>
			)}
			{mode === 'debt_prevention' && (
				<div style={{position: 'absolute', inset: '90px 120px'}}>
					<div style={{position: 'absolute', left: 40, top: 140, width: 420, height: 240, borderRadius: 24, background: 'rgba(230,57,70,0.18)', border: `3px solid ${COLORS.red}`, transform: `translateX(${(1 - enter) * -80}px) rotate(-3deg)`}}>
						<div style={{padding: 36, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 62, color: COLORS.red}}>DEBT</div>
						<div style={{padding: '0 36px', fontSize: 30, color: COLORS.muted}}>credit card spiral</div>
					</div>
					<div style={{position: 'absolute', left: 500, top: 76, width: 108, height: 420, borderRadius: 32, background: COLORS.teal, boxShadow: `0 0 60px ${COLORS.teal}66`, transform: `scaleY(${0.88 + enter * 0.12})`}} />
					<div style={{position: 'absolute', left: 672, top: 130, width: 430}}>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 86, lineHeight: 0.92}}>{/minimum_due|card/.test(String(cinematicEvent?.variant ?? '')) ? 'CARD BILL STAYS CLOSED' : 'BUFFER BLOCKS BORROWING'}</div>
						<div style={{marginTop: 28, fontSize: 32, color: COLORS.muted}}>{String(cinematicEvent?.text || 'the emergency is paid without starting a second problem').slice(0, 92)}</div>
					</div>
				</div>
			)}
			{mode === 'plan_survives' && (
				<div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center'}}>
					<div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 118, lineHeight: 0.9, color: COLORS.text_primary}}>{/last_chip|tiny/.test(String(cinematicEvent?.variant ?? '')) ? 'WHAT IS' : 'THE PLAN'}</div>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 132, lineHeight: 0.88, color: COLORS.teal}}>{/last_chip|tiny/.test(String(cinematicEvent?.variant ?? '')) ? 'LEFT' : 'SURVIVES'}</div>
						<div style={{marginTop: 34, fontSize: 36, color: COLORS.muted}}>{String(cinematicEvent?.label || 'breathing room is the real product')}</div>
						<div style={{margin: '46px auto 0', width: 360, height: 360, borderRadius: '50%', border: `18px solid ${COLORS.teal}`, boxShadow: `0 0 ${64 + cinematicPresence * 70}px ${COLORS.teal}44`, transform: `scale(${0.86 + enter * 0.14 + cinematicPresence * 0.04})`}} />
					</div>
				</div>
			)}
		</AbsoluteFill>
	);
};
