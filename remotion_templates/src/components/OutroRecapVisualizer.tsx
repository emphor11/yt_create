import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, getBeatData, getBeatProgress} from './visualUtils';
import {currentSceneProgress, firstKeywordIndex, narrationSentences, sceneNarrationText} from './narrationTiming';

type OutroAction = {
	id: string;
	label: string;
	shortLabel: string;
	keywords: string[];
	color: string;
};

type OutroMoment = {
	action: OutroAction;
	startProgress: number;
	endProgress: number;
};

const defaultActions: OutroAction[] = [
	{id: 'track', label: 'Track the leak', shortLabel: 'TRACK', keywords: ['track', 'notice', 'write', 'budget', 'spending', 'expenses'], color: COLORS.blue},
	{id: 'protect', label: 'Protect the buffer', shortLabel: 'PROTECT', keywords: ['protect', 'emergency', 'buffer', 'savings', 'fund'], color: COLORS.teal},
	{id: 'reduce_debt', label: 'Cut fixed pressure', shortLabel: 'CUT DEBT', keywords: ['debt', 'emi', 'loan', 'credit card', 'avoid'], color: COLORS.orange},
	{id: 'invest', label: 'Invest consistently', shortLabel: 'INVEST', keywords: ['invest', 'sip', 'compound', 'long term', 'wealth'], color: COLORS.teal},
	{id: 'start', label: 'Start this month', shortLabel: 'START', keywords: ['start', 'today', 'this month', 'small', 'next salary'], color: COLORS.warning},
];

const normalizeAction = (item: unknown, index: number): OutroAction | null => {
	if (!item || typeof item !== 'object') {
		return null;
	}
	const source = item as Record<string, unknown>;
	const label = String(source.label ?? source.text ?? '').trim();
	if (!label) {
		return null;
	}
	return {
		id: String(source.id ?? `action_${index}`),
		label,
		shortLabel: String(source.shortLabel ?? label.split(/\s+/).slice(0, 2).join(' ')).toUpperCase(),
		keywords: Array.isArray(source.keywords) ? source.keywords.map(String) : label.toLowerCase().split(/[^a-z0-9]+/).filter((word) => word.length > 2),
		color: String(source.color ?? defaultActions[index % defaultActions.length].color),
	};
};

const resolveActions = (data: Record<string, unknown>): OutroAction[] => {
	const raw = Array.isArray(data.actions) ? data.actions.map(normalizeAction).filter(Boolean) as OutroAction[] : [];
	return raw.length > 0 ? raw.slice(0, 6) : defaultActions;
};

const buildMoments = (narration: string, actions: OutroAction[]): OutroMoment[] => {
	const sentences = narrationSentences(narration);
	const moments: OutroMoment[] = [];
	for (const sentence of sentences) {
		const hits = actions.map((action) => ({action, hit: firstKeywordIndex(sentence.text, action.keywords)})).filter((item) => item.hit >= 0).sort((a, b) => a.hit - b.hit);
		if (hits.length === 0) {
			continue;
		}
		const span = sentence.endProgress - sentence.startProgress;
		hits.forEach((hit, index) => {
			moments.push({
				action: hit.action,
				startProgress: Math.max(0, sentence.startProgress + (span * index) / hits.length - 0.006),
				endProgress: Math.min(1, sentence.startProgress + (span * (index + 1)) / hits.length + 0.018),
			});
		});
	}
	if (moments.length > 0) {
		return moments;
	}
	const slot = 0.82 / Math.max(actions.length, 1);
	return actions.map((action, index) => ({
		action,
		startProgress: index * slot,
		endProgress: Math.min(0.92, (index + 1.05) * slot),
	}));
};

export const OutroRecapVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? scene?.data ?? {};
	const narration = sceneNarrationText(scene);
	const progress = scene ? currentSceneProgress(scene, beat, frameWithinBeat, fps) : getBeatProgress(frameWithinBeat, durationFrames);
	const actions = resolveActions(data);
	const moments = buildMoments(narration, actions);
	const previousMoments = moments.filter((moment) => moment.startProgress <= progress);
	const active = moments.find((moment) => progress >= moment.startProgress && progress <= moment.endProgress) ?? previousMoments[previousMoments.length - 1] ?? moments[0];
	const activeIndex = actions.findIndex((action) => action.id === active.action.id);
	const finalMode = progress > 0.88;
	const enter = spring({frame: frameWithinBeat, fps, config: {damping: 21, stiffness: 142, mass: 0.9}});
	const orbit = Math.sin(frameWithinBeat / 12) * 8;

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, overflow: 'hidden', color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY}}>
			<style>{FONT_FACES}</style>
			<AbsoluteFill style={{background: `radial-gradient(circle at ${42 + activeIndex * 7}% ${44 + orbit / 3}%, ${active.action.color}33, rgba(10,10,20,0.97) 62%)`}} />
			<div style={{position: 'absolute', inset: 90}}>
				<div style={{position: 'absolute', left: 0, top: 0, display: 'flex', gap: 14}}>
					{actions.map((action, index) => {
						const isActive = action.id === active.action.id && !finalMode;
						const seen = index < activeIndex || finalMode;
						return (
							<div
								key={action.id}
								style={{
									padding: '12px 18px',
									borderRadius: 999,
									border: `2px solid ${isActive ? action.color : 'rgba(255,255,255,0.14)'}`,
									color: isActive ? COLORS.text_primary : COLORS.muted,
									background: isActive ? `${action.color}22` : seen ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.035)',
									fontWeight: 800,
									fontSize: 22,
									opacity: isActive ? 1 : seen ? 0.58 : 0.28,
								}}
							>
								{action.shortLabel}
							</div>
						);
					})}
				</div>

				{!finalMode && (
					<div style={{position: 'absolute', left: 110 + activeIndex * 56, top: 178, width: 850, transform: `translateY(${(1 - enter) * 28}px)`}}>
						<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 134, lineHeight: 0.9, color: active.action.color}}>
							{active.action.shortLabel}
						</div>
						<div style={{marginTop: 26, fontSize: 44, fontWeight: 900, color: COLORS.text_primary}}>{active.action.label}</div>
						<div style={{marginTop: 34, width: 620, height: 18, borderRadius: 999, background: 'rgba(255,255,255,0.14)', overflow: 'hidden'}}>
							<div style={{height: '100%', width: `${Math.max(12, progress * 100)}%`, borderRadius: 999, background: active.action.color, boxShadow: `0 0 34px ${active.action.color}66`}} />
						</div>
					</div>
				)}

				{!finalMode && actions.filter((action) => action.id !== active.action.id).slice(0, 4).map((action, index) => (
					<div
						key={action.id}
						style={{
							position: 'absolute',
							right: 40,
							top: 172 + index * 72,
							width: 270,
							padding: '18px 20px',
							borderRadius: 18,
							border: '1px solid rgba(255,255,255,0.11)',
							background: 'rgba(255,255,255,0.045)',
							color: COLORS.muted,
							fontSize: 24,
							fontWeight: 800,
							opacity: 0.36,
						}}
					>
						{action.label}
					</div>
				))}

				{finalMode && (
					<div style={{position: 'absolute', inset: '130px 90px', display: 'grid', placeItems: 'center', textAlign: 'center'}}>
						<div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 114, lineHeight: 0.9}}>YOUR SALARY NEEDS</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 142, lineHeight: 0.86, color: COLORS.teal}}>A SYSTEM</div>
							<div style={{marginTop: 36, fontSize: 36, color: COLORS.muted}}>track, protect, reduce pressure, invest, repeat</div>
						</div>
					</div>
				)}
			</div>
		</AbsoluteFill>
	);
};
