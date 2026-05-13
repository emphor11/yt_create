import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';
import {resolveVisualEvent} from './visualEvents';

type EMIItem = {
	label?: string;
	value?: string;
	amount?: number;
};

type ResolvedEmiItem = {
	label: string;
	value: string;
	amount: number;
	keywords: string[];
};

type TimedSentence = {
	text: string;
	startProgress: number;
	endProgress: number;
};

type EMIFocalMoment = {
	emiIndex?: number;
	startProgress: number;
	endProgress: number;
	visualMode: 'single_emi_focus' | 'first_emi_comfort' | 'emi_stacking' | 'salary_squeeze' | 'critical_leftover';
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const sceneNarrationText = (scene: BeatComponentProps['scene']): string => {
	const direct = String(scene?.narration ?? scene?.text ?? '').trim();
	if (direct) {
		return direct;
	}
	return (scene?.beats ?? [])
		.map((item) => String(item.source_text ?? item.text ?? '').trim())
		.filter(Boolean)
		.join(' ');
};

const sceneDurationSeconds = (scene: BeatComponentProps['scene'], beat: BeatComponentProps['beat']) => {
	const explicit = Number(scene?.duration ?? scene?.total_duration);
	if (Number.isFinite(explicit) && explicit > 0) {
		return explicit;
	}
	const beatEnd = Math.max(...(scene?.beats ?? [beat]).map((item) => Number(item.end_time ?? 0)));
	return Number.isFinite(beatEnd) && beatEnd > 0 ? beatEnd : Math.max(Number(beat.end_time ?? 0), 1);
};

const wordCount = (text: string) => text.match(/[A-Za-z0-9₹,]+/g)?.length ?? 0;

const narrationSentences = (text: string): TimedSentence[] => {
	const sentences = text
		.split(/(?<=[.!?])\s+/)
		.map((item) => item.trim())
		.filter(Boolean);
	const totalWords = sentences.reduce((sum, sentence) => sum + wordCount(sentence), 0) || 1;
	let cursor = 0;
	return sentences.map((sentence) => {
		const duration = wordCount(sentence) / totalWords;
		const timed = {text: sentence, startProgress: cursor, endProgress: Math.min(1, cursor + duration)};
		cursor = timed.endProgress;
		return timed;
	});
};

const keywordsForEmi = (label: string) => {
	const lowered = label.toLowerCase();
	const words = lowered.split(/[^a-z0-9]+/).filter((word) => word.length > 2 && word !== 'emi');
	const semantic = [
		lowered.includes('phone') ? 'mobile' : '',
		lowered.includes('bike') ? 'scooter' : '',
		lowered.includes('personal') ? 'loan' : '',
		lowered.includes('credit') ? 'card' : '',
		lowered.includes('home') ? 'housing' : '',
	].filter(Boolean);
	return Array.from(new Set([lowered, ...words, ...semantic]));
};

const firstKeywordIndex = (text: string, keywords: string[]) => {
	const hits = keywords.map((keyword) => text.indexOf(keyword)).filter((index) => index >= 0);
	return hits.length > 0 ? Math.min(...hits) : -1;
};

const semanticModeForSentence = (sentence: string): EMIFocalMoment['visualMode'] | null => {
	if (/leftover|left\s+after|cash\s+left|remaining|critical|survive|only\s+₹|only\s+rs/i.test(sentence)) {
		return 'critical_leftover';
	}
	if (/salary.*squeez|squeez.*salary|paycheck|income.*squeez|month\s+starts.*gone/i.test(sentence)) {
		return 'salary_squeeze';
	}
	if (/stack|multiple|pile|fixed\s+payments?|every\s+emi|too\s+many|one\s+after\s+another/i.test(sentence)) {
		return 'emi_stacking';
	}
	if (/first\s+emi|one\s+emi|looks?\s+(small|harmless|comfortable)|manageable|comfort/i.test(sentence)) {
		return 'first_emi_comfort';
	}
	return null;
};

const buildNarrationFocalSequence = (narration: string, emis: ResolvedEmiItem[]): EMIFocalMoment[] => {
	const sentences = narrationSentences(narration);
	const moments: EMIFocalMoment[] = [];
	const seen = new Set<number>();

	for (const sentence of sentences) {
		const lowered = sentence.text.toLowerCase();
		const semanticMode = semanticModeForSentence(sentence.text);
		if (semanticMode === 'salary_squeeze' || semanticMode === 'critical_leftover') {
			moments.push({
				startProgress: Math.max(0, sentence.startProgress - 0.004),
				endProgress: Math.min(1, sentence.endProgress + 0.01),
				visualMode: semanticMode,
			});
			continue;
		}
		const mentioned = emis
			.map((emi, index) => ({index, hit: firstKeywordIndex(lowered, emi.keywords)}))
			.filter((item) => item.hit >= 0)
			.sort((a, b) => a.hit - b.hit);
		if (mentioned.length > 0) {
			const span = sentence.endProgress - sentence.startProgress;
			const slot = span / mentioned.length;
			mentioned.forEach((item, order) => {
				moments.push({
					emiIndex: item.index,
					startProgress: Math.max(0, sentence.startProgress + slot * order - 0.004),
					endProgress: Math.min(1, sentence.startProgress + slot * (order + 1) + 0.006),
					visualMode: 'single_emi_focus',
				});
				seen.add(item.index);
			});
			continue;
		}
		if (semanticMode) {
			moments.push({
				startProgress: Math.max(0, sentence.startProgress - 0.004),
				endProgress: Math.min(1, sentence.endProgress + 0.01),
				visualMode: semanticMode,
			});
		}
	}

	if (moments.length === 0) {
		const windowSize = 0.56 / Math.max(emis.length, 1);
		return [
			...emis.map((_, index) => ({
				emiIndex: index,
				startProgress: 0.12 + index * windowSize,
				endProgress: 0.12 + (index + 0.86) * windowSize,
				visualMode: 'single_emi_focus' as const,
			})),
			{startProgress: 0.72, endProgress: 0.9, visualMode: 'salary_squeeze' as const},
			{startProgress: 0.88, endProgress: 1, visualMode: 'critical_leftover' as const},
		];
	}

	if (!moments.some((moment) => moment.visualMode === 'emi_stacking') && seen.size > 1) {
		const latestMention = moments.filter((moment) => moment.visualMode === 'single_emi_focus').reduce((max, moment) => Math.max(max, moment.endProgress), 0);
		moments.push({startProgress: Math.min(0.78, latestMention + 0.025), endProgress: Math.min(0.9, latestMention + 0.16), visualMode: 'emi_stacking'});
	}

	if (!moments.some((moment) => moment.visualMode === 'critical_leftover')) {
		moments.push({startProgress: 0.86, endProgress: 1, visualMode: 'critical_leftover'});
	}

	return moments.sort((a, b) => a.startProgress - b.startProgress);
};

const momentPresence = (progress: number, moment: EMIFocalMoment) => {
	if (progress < moment.startProgress || progress > moment.endProgress) {
		return 0;
	}
	const enterEnd = moment.startProgress + (moment.endProgress - moment.startProgress) * 0.32;
	const exitStart = moment.startProgress + (moment.endProgress - moment.startProgress) * 0.72;
	const enter = interpolate(progress, [moment.startProgress, enterEnd], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const exit = interpolate(progress, [exitStart, moment.endProgress], [1, 0.64], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return enter * exit;
};

const parseMoneyAmount = (text: string) => {
	const match = text.match(/(?:₹\s*|rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)/i);
	if (!match) {
		return null;
	}
	const amount = Number(match[1].replace(/,/g, ''));
	return Number.isFinite(amount) ? amount : null;
};

const explicitSalaryAmount = (text: string) => {
	const patterns = [
		/(?:salary|income|paycheck|pay)\D{0,18}(?:₹\s*|rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)/i,
		/(?:₹\s*|rs\.?\s*)?(\d[\d,]*(?:\.\d+)?)\D{0,18}(?:salary|income|paycheck|pay)/i,
	];
	for (const pattern of patterns) {
		const match = text.match(pattern);
		if (match) {
			const amount = Number(match[1].replace(/,/g, ''));
			if (Number.isFinite(amount)) {
				return amount;
			}
		}
	}
	return null;
};

const getEmiData = (beat: BeatComponentProps['beat'], narration = '') => {
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const salary = data.salary as {value?: string; amount?: number} | undefined;
	const totalEmi = data.total_emi as {value?: string; amount?: number} | undefined;
	const remaining = data.remaining as {value?: string; amount?: number; is_critical?: boolean} | undefined;
	const rawEmis = Array.isArray(data.emis) ? (data.emis as EMIItem[]) : [];
	let salaryAmount = Number(salary?.amount ?? 50000);
	const emis = (rawEmis.length ? rawEmis : [
		{label: 'Phone EMI', amount: 4000},
		{label: 'Bike EMI', amount: 6500},
		{label: 'Personal loan', amount: 7500},
	]).map((item, index): ResolvedEmiItem => ({
		label: String(item.label ?? `EMI ${index + 1}`),
		amount: Number(item.amount ?? 0),
		value: String(item.value ?? formatIndianRupee(Number(item.amount ?? 0))),
		keywords: keywordsForEmi(String(item.label ?? `EMI ${index + 1}`)),
	}));
	const totalAmount = Number(totalEmi?.amount ?? emis.reduce((sum, item) => sum + item.amount, 0));
	const explicitSalary = explicitSalaryAmount(narration);
	const salaryLooksLikeEmiTotal = salaryAmount <= totalAmount * 1.05 && !explicitSalary;
	if (salaryLooksLikeEmiTotal) {
		salaryAmount = Math.max(50000, Math.round(totalAmount * 2.6 / 1000) * 1000);
	} else if (explicitSalary) {
		salaryAmount = explicitSalary;
	}
	const explicitRemaining = remaining?.amount ?? (
		/(?:left|remaining|cash\s+left|leftover)\D{0,18}(?:₹\s*|rs\.?\s*)?\d/i.test(narration)
			? parseMoneyAmount(narration.slice(Math.max(0, narration.toLowerCase().search(/left|remaining|cash\s+left|leftover/i))))
			: null
	);
	const remainingAmount = Number(remaining?.amount ?? Math.max(salaryAmount - totalAmount, 0));
	const resolvedRemainingAmount = explicitRemaining !== null && explicitRemaining !== undefined ? Number(explicitRemaining) : remainingAmount;
	return {
		salary: {value: formatIndianRupee(salaryAmount), amount: salaryAmount},
		emis,
		total_emi: {value: totalEmi?.value ?? formatIndianRupee(totalAmount), amount: totalAmount},
		remaining: {
			value: formatIndianRupee(resolvedRemainingAmount),
			amount: resolvedRemainingAmount,
			is_critical: Boolean(remaining?.is_critical ?? resolvedRemainingAmount / Math.max(salaryAmount, 1) < 0.12),
		},
	};
};

export const EMIStackVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const data = getBeatData<Record<string, unknown>>(beat) ?? {};
	const phase = String(beat.beat_phase ?? data.active_phase ?? 'stacking');
	const event = resolveVisualEvent(beat, scene, 'EMIStackVisualizer');
	const narration = sceneNarrationText(scene);
	const currentSceneSeconds = Number(beat.start_time ?? 0) + frameWithinBeat / fps;
	const sceneProgress = clamp(currentSceneSeconds / sceneDurationSeconds(scene, beat), 0, 1);
	const {salary, emis, total_emi, remaining} = getEmiData(beat, narration);
	const reveal = spring({frame: Math.min(frameWithinBeat, 18), fps, config: SPRINGS.entry, durationInFrames: 18});
	const rawProgress = getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.82));
	const stackProgress = event.kind === 'first_emi_comfort' ? 0.28 : event.kind === 'critical_leftover' || event.kind === 'salary_squeeze' ? 1 : rawProgress;
	const visibleCount = Math.max(1, Math.ceil(stackProgress * emis.length));
	const remainingRatio = Math.max(0.04, Math.min(remaining.amount / Math.max(salary.amount, 1), 1));
	const pressureColor = remaining.is_critical ? COLORS.danger : COLORS.warning;
	const salaryOpacity = event.kind === 'emi_stacking' ? 0.54 : event.kind === 'critical_leftover' ? 0.22 : 1;
	const stackScale = event.kind === 'emi_stacking' ? 1.12 : event.kind === 'salary_squeeze' ? 1.24 : event.kind === 'critical_leftover' ? 0.82 : 0.9;
	const remainingScale = event.kind === 'critical_leftover' ? 1.28 : event.kind === 'salary_squeeze' ? 1.12 : 0.92;
	const dim = event.kind === 'critical_leftover' ? 0.34 : event.kind === 'salary_squeeze' ? 0.22 : 0.06;
	const focalSequence = buildNarrationFocalSequence(narration, emis);
	const semanticMoment = focalSequence
		.filter((moment) => sceneProgress >= moment.startProgress && sceneProgress <= moment.endProgress)
		.sort((a, b) => b.startProgress - a.startProgress)[0];
	const semanticEventProgress = semanticMoment
		? clamp((sceneProgress - semanticMoment.startProgress) / Math.max(semanticMoment.endProgress - semanticMoment.startProgress, 0.001), 0, 1)
		: rawProgress;
	const activeEmi = typeof semanticMoment?.emiIndex === 'number' ? emis[semanticMoment.emiIndex] : undefined;

	if (semanticMoment?.visualMode === 'single_emi_focus' && activeEmi) {
		const focusGlow = interpolate(semanticEventProgress, [0, 0.42, 1], [0.3, 1, 0.76], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -120, background: 'radial-gradient(circle at 72% 38%, rgba(230,57,70,0.26), transparent 30%), linear-gradient(125deg, #070711, #15101a 58%, #080811)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.danger}} />
				<div style={{position: 'absolute', left: SPACING.safe, top: SPACING.safe, fontSize: TYPE_SCALE.label.size, color: COLORS.text_secondary, fontWeight: 900}}>EMI focus</div>
				<div style={{position: 'absolute', left: 210, top: 250, width: 440, opacity: 0.5, zIndex: 2}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Salary context</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 96, lineHeight: 0.92}}>{salary.value}</div>
				</div>
				<div
					style={{
						position: 'absolute',
						left: 720,
						top: 260,
						width: 560,
						padding: '44px 50px',
						borderRadius: 8,
						border: `4px solid ${COLORS.danger}`,
						background: 'rgba(10,10,18,0.96)',
						boxShadow: `0 0 ${70 + focusGlow * 78}px rgba(230,57,70,0.36)`,
						transform: `scale(${0.88 + focusGlow * 0.14})`,
						zIndex: 5,
					}}
				>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 950}}>This payment enters</div>
					<div style={{marginTop: 12, fontSize: 46, color: COLORS.text_primary, fontWeight: 950}}>{activeEmi.label}</div>
					<div style={{marginTop: 20, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 112, lineHeight: 0.86, color: COLORS.danger}}>{activeEmi.value}</div>
				</div>
				<div style={{position: 'absolute', right: 210, top: 300, width: 300, opacity: 0.7}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>EMI total</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 76, lineHeight: 0.92, color: COLORS.danger}}>{total_emi.value}</div>
				</div>
				<div style={{position: 'absolute', left: 350, bottom: 126, right: 350, display: 'flex', gap: 18, justifyContent: 'center'}}>
					{emis.map((emi, index) => (
						<div
							key={emi.label}
							style={{
								width: 210,
								height: 72,
								borderRadius: 8,
								border: `1px solid ${index === semanticMoment.emiIndex ? COLORS.danger : COLORS.stroke}`,
								background: index === semanticMoment.emiIndex ? 'rgba(230,57,70,0.16)' : 'rgba(255,255,255,0.045)',
								opacity: index === semanticMoment.emiIndex ? 1 : 0.34,
								padding: '12px 16px',
							}}
						>
							<div style={{fontSize: 21, color: COLORS.text_secondary, fontWeight: 900}}>{emi.label}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 30, color: index === semanticMoment.emiIndex ? COLORS.danger : COLORS.text_secondary}}>{emi.value}</div>
						</div>
					))}
				</div>
			</AbsoluteFill>
		);
	}

	if (semanticMoment?.visualMode === 'salary_squeeze') {
		const squeeze = interpolate(semanticEventProgress, [0.08, 0.86], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: -120, background: 'radial-gradient(circle at 70% 46%, rgba(230,57,70,0.28), transparent 31%), linear-gradient(120deg, #070711, #17101a 58%, #080811)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: COLORS.danger}} />
				<div style={{position: 'absolute', left: SPACING.safe, top: SPACING.safe, fontSize: TYPE_SCALE.label.size, color: COLORS.text_secondary, fontWeight: 900}}>Salary squeeze</div>
				<div style={{position: 'absolute', left: 210, top: 382, width: 1120, height: 94, borderRadius: 999, background: 'rgba(46,196,182,0.18)', border: `2px solid ${COLORS.positive}`, overflow: 'hidden'}}>
					<div style={{height: '100%', width: `${100 - squeeze * 58}%`, background: COLORS.positive, boxShadow: `0 0 48px ${COLORS.positive}66`}} />
					<div style={{position: 'absolute', left: 38, top: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58, lineHeight: 0.9}}>{salary.value}</div>
				</div>
				{emis.map((emi, index) => {
					const slam = interpolate(semanticEventProgress, [index * 0.08, index * 0.08 + 0.28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
					return (
						<div
							key={emi.label}
							style={{
								position: 'absolute',
								left: 1040 + index * 28 - slam * (470 - index * 34),
								top: 250 + index * 102,
								width: 330,
								height: 88,
								borderRadius: 8,
								background: 'rgba(230,57,70,0.16)',
								border: `2px solid ${COLORS.danger}`,
								boxShadow: `0 0 ${32 + slam * 46}px rgba(230,57,70,0.24)`,
								opacity: slam,
								padding: '16px 20px',
								zIndex: 4 + index,
							}}
						>
							<div style={{fontSize: 24, color: COLORS.text_secondary, fontWeight: 900}}>{emi.label}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 42, color: COLORS.danger}}>{emi.value}</div>
						</div>
					);
				})}
				<div style={{position: 'absolute', right: 210, bottom: 158, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>cash left</div>
				<div style={{position: 'absolute', right: 210, bottom: 60, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 102, lineHeight: 0.9, color: pressureColor}}>{remaining.value}</div>
			</AbsoluteFill>
		);
	}

	if (semanticMoment?.visualMode === 'critical_leftover') {
		const isolate = interpolate(semanticEventProgress, [0.08, 0.78], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY, overflow: 'hidden'}}>
				<style>{FONT_FACES}</style>
				<div style={{position: 'absolute', inset: 0, background: 'black', opacity: 0.42}} />
				<div style={{position: 'absolute', inset: -140, background: 'radial-gradient(circle at 50% 52%, rgba(230,57,70,0.2), transparent 25%), linear-gradient(135deg, #04050a, #0c0a12 60%, #04050a)'}} />
				<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: pressureColor}} />
				<div style={{position: 'absolute', left: SPACING.safe, top: SPACING.safe, fontSize: TYPE_SCALE.label.size, color: COLORS.text_secondary, fontWeight: 900}}>Critical leftover</div>
				<div style={{position: 'absolute', left: 0, right: 0, top: 300, textAlign: 'center', zIndex: 4, transform: `scale(${0.94 + isolate * 0.1})`}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Cash left after fixed payments</div>
					<div style={{marginTop: 14, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 154, lineHeight: 0.84, color: pressureColor, textShadow: `0 0 ${56 + isolate * 70}px ${pressureColor}66`}}>{remaining.value}</div>
					<div style={{margin: '58px auto 0', width: interpolate(isolate, [0, 1], [420, 128]), height: 20, borderRadius: 999, background: 'rgba(255,255,255,0.09)', overflow: 'hidden'}}>
						<div style={{height: '100%', width: `${Math.max(12, remainingRatio * 100)}%`, background: pressureColor}} />
					</div>
				</div>
				<div style={{position: 'absolute', left: 250, bottom: 130, right: 250, display: 'flex', gap: 14, justifyContent: 'center', opacity: 0.18}}>
				{emis.map((emi) => (
						<div key={emi.label} style={{width: 220, height: 66, borderRadius: 8, border: `1px solid ${COLORS.danger}`, background: 'rgba(230,57,70,0.12)', padding: '10px 14px'}}>
							<div style={{fontSize: 20, color: COLORS.text_secondary, fontWeight: 900}}>{emi.label}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 28, color: COLORS.danger}}>{emi.value}</div>
						</div>
					))}
				</div>
			</AbsoluteFill>
		);
	}

	return (
		<AbsoluteFill style={{background: COLORS.bg_deep, color: COLORS.text_primary, fontFamily: BODY_FONT_FAMILY}}>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: pressureColor}} />
			<div style={{position: 'absolute', inset: 0, background: 'black', opacity: dim}} />
			<div style={{position: 'absolute', left: SPACING.safe, top: SPACING.safe, opacity: salaryOpacity, transform: `scale(${event.kind === 'first_emi_comfort' ? 1.08 : 1})`, transformOrigin: 'left top'}}>
				<div style={{fontSize: TYPE_SCALE.label.size, fontWeight: 900, color: COLORS.text_secondary}}>
					{event.kind === 'first_emi_comfort'
						? 'One EMI looks small'
						: event.kind === 'critical_leftover'
							? 'Salary left after EMIs'
							: event.kind === 'salary_squeeze'
								? 'Salary gets squeezed'
								: 'Fixed payments stack'}
				</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 94, lineHeight: 0.95, marginTop: 20}}>
					{salary.value}
				</div>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 800}}>salary lands</div>
			</div>
			<div style={{position: 'absolute', left: event.kind === 'critical_leftover' ? 520 : 650, top: 170, width: 520, height: 760, transform: `scale(${stackScale})`, transformOrigin: 'center top', opacity: event.kind === 'critical_leftover' ? 0.42 : 1}}>
				{emis.map((emi, index) => {
					const isVisible = index < visibleCount;
					const cardReveal = interpolate(stackProgress, [index / emis.length, (index + 0.65) / emis.length], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					});
					return (
						<div
							key={emi.label}
							style={{
								position: 'absolute',
								left: index * 28,
								top: 60 + index * 128,
								width: 430,
								height: 108,
								borderRadius: 8,
								background: 'rgba(230,57,70,0.12)',
								border: `2px solid ${COLORS.danger}`,
								boxShadow: event.kind === 'emi_stacking' ? '0 0 70px rgba(230,57,70,0.24)' : '0 0 42px rgba(230,57,70,0.14)',
								padding: '22px 26px',
								opacity: isVisible ? cardReveal : 0,
								transform: `translateY(${(1 - cardReveal) * -48}px) scale(${interpolate(reveal, [0, 1], [0.98, 1]) * (event.kind === 'first_emi_comfort' && index > 0 ? 0.86 : 1)})`,
							}}
						>
							<div style={{fontSize: 25, color: COLORS.text_secondary, fontWeight: 900}}>{emi.label}</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 54, lineHeight: 0.95}}>{emi.value}</div>
						</div>
					);
				})}
			</div>
			<div style={{position: 'absolute', right: SPACING.safe, top: event.kind === 'critical_leftover' ? 250 : 180, width: 430, height: 660, transform: `scale(${remainingScale})`, transformOrigin: 'right center'}}>
				<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>EMI total</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 78, lineHeight: 0.95, color: COLORS.danger}}>
					{total_emi.value}
				</div>
				<div
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						bottom: 0,
						height: 360,
						borderRadius: 8,
						background: COLORS.bg_surface,
						border: `2px solid ${COLORS.stroke}`,
						overflow: 'hidden',
					}}
				>
					<div
						style={{
							position: 'absolute',
							left: 0,
							right: 0,
							bottom: 0,
							height: `${remainingRatio * 100}%`,
							background: pressureColor,
							boxShadow: `0 0 60px ${pressureColor}44`,
							transition: 'height 200ms linear',
						}}
					/>
				</div>
				<div style={{position: 'absolute', bottom: -96, right: 0, textAlign: 'right'}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>cash left</div>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 86, lineHeight: 0.92, color: pressureColor}}>
						{remaining.value}
					</div>
				</div>
			</div>
		</AbsoluteFill>
	);
};
