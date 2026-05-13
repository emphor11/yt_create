import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, SPACING, SPRINGS, TYPE_SCALE, formatIndianRupee, getBeatData, getBeatProgress} from './visualUtils';
import {resolveVisualEvent} from './visualEvents';

type MoneyPoint = {
	value?: string;
	amount?: number;
};

type LifestyleCreepData = {
	start_income?: MoneyPoint;
	end_income?: MoneyPoint;
	old_spending?: MoneyPoint;
	new_spending?: MoneyPoint;
	old_savings?: MoneyPoint;
	new_savings?: MoneyPoint;
	raise?: MoneyPoint;
	active_phase?: string;
	title?: string;
};

type ResolvedMoneyPoint = Required<MoneyPoint>;

type LifestyleVisualRole = 'housing' | 'food' | 'experience' | 'retail' | 'subscription' | 'device' | 'comfort';

type GravityCenter = {
	x: number;
	y: number;
};

type LifestyleFocalEntity = {
	id: string;
	label: string;
	amount: number;
	color: string;
	visualRole: LifestyleVisualRole;
	gravityCenter: GravityCenter;
	keywords: string[];
	weight: number;
	sourceIndex: number;
};

type LifestyleFocalMoment = {
	entityId: string;
	startProgress: number;
	endProgress: number;
	dominance: number;
	decay: number;
	gravityCenter: GravityCenter;
	attentionWeight: number;
	visualMode:
		| 'entity_attack'
		| 'compression'
		| 'salary_anchor'
		| 'raise_hero'
		| 'savings_isolation'
		| 'rationalization_world'
		| 'permanence_lock_world'
		| 'paper_vs_real_world'
		| 'capture_raise_world'
		| 'protected_savings_world';
};

type TimedSentence = {
	text: string;
	startProgress: number;
	endProgress: number;
};

const moneyPoint = (point: unknown, fallbackAmount: number): ResolvedMoneyPoint => {
	const item = point && typeof point === 'object' ? (point as MoneyPoint) : {};
	const amount = Number.isFinite(Number(item.amount)) ? Number(item.amount) : fallbackAmount;
	return {
		amount,
		value: item.value || formatIndianRupee(amount),
	};
};

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const rupee = (amount: number) => formatIndianRupee(Math.round(amount));

const LIFESTYLE_ENTITY_CATALOG: Array<Omit<LifestyleFocalEntity, 'amount' | 'sourceIndex'>> = [
	{
		id: 'rent_upgrade',
		label: 'Rent upgrade',
		color: COLORS.warning,
		visualRole: 'housing',
		gravityCenter: {x: 1135, y: 170},
		keywords: ['rent', 'house', 'housing', 'apartment', 'better house', 'home upgrade'],
		weight: 0.32,
	},
	{
		id: 'food_apps',
		label: 'Food apps',
		color: COLORS.danger,
		visualRole: 'food',
		gravityCenter: {x: 1360, y: 345},
		keywords: ['food app', 'food apps', 'delivery', 'takeout', 'takeaway', 'better food', 'swiggy', 'zomato'],
		weight: 0.2,
	},
	{
		id: 'weekend_spending',
		label: 'Weekend plans',
		color: '#FF6B35',
		visualRole: 'experience',
		gravityCenter: {x: 1170, y: 570},
		keywords: ['weekend', 'weekends', 'plans', 'party', 'outing', 'trip', 'travel'],
		weight: 0.18,
	},
	{
		id: 'shopping',
		label: 'Shopping',
		color: '#FFD166',
		visualRole: 'retail',
		gravityCenter: {x: 1425, y: 715},
		keywords: ['shopping', 'clothes', 'fashion', 'purchase', 'buying'],
		weight: 0.18,
	},
	{
		id: 'subscriptions',
		label: 'Subscriptions',
		color: '#A78BFA',
		visualRole: 'subscription',
		gravityCenter: {x: 1088, y: 742},
		keywords: ['subscription', 'subscriptions', 'netflix', 'prime', 'ott', 'streaming', 'membership'],
		weight: 0.12,
	},
	{
		id: 'phone_upgrade',
		label: 'Phone upgrade',
		color: '#38BDF8',
		visualRole: 'device',
		gravityCenter: {x: 1460, y: 205},
		keywords: ['phone', 'nicer phone', 'mobile', 'device', 'gadget'],
		weight: 0.16,
	},
	{
		id: 'comfort_upgrade',
		label: 'Comfort upgrades',
		color: '#F472B6',
		visualRole: 'comfort',
		gravityCenter: {x: 1280, y: 505},
		keywords: ['comfort'],
		weight: 0.14,
	},
];

const visualRoleLabel: Record<LifestyleVisualRole, string> = {
	housing: 'HOME',
	food: 'FOOD',
	experience: 'WEEKEND',
	retail: 'BUY',
	subscription: 'AUTO',
	device: 'PHONE',
	comfort: 'COMFORT',
};

const sceneLanguage = (scene: BeatComponentProps['scene']): string => {
	const parts = [
		scene?.narration,
		scene?.text,
		...(scene?.beats ?? []).flatMap((item) => [item.text, item.source_text]),
	];
	return parts.filter(Boolean).map(String).join(' ').toLowerCase();
};

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

const wordCount = (text: string) => {
	const matches = text.match(/[A-Za-z0-9₹,]+/g);
	return matches?.length ?? 0;
};

const splitNarrationSentences = (text: string): string[] =>
	text
		.split(/(?<=[.!?])\s+/)
		.map((item) => item.trim())
		.filter(Boolean);

const narrationSentences = (text: string): TimedSentence[] => {
	const sentences = splitNarrationSentences(text);
	const totalWords = sentences.reduce((sum, sentence) => sum + wordCount(sentence), 0) || 1;
	let cursor = 0;

	return sentences.map((sentence) => {
		const duration = wordCount(sentence) / totalWords;
		const timed = {
			text: sentence,
			startProgress: cursor,
			endProgress: Math.min(1, cursor + duration),
		};
		cursor = timed.endProgress;
		return timed;
	});
};

const firstKeywordIndex = (text: string, keywords: string[]) => {
	const hits = keywords
		.map((keyword) => text.indexOf(keyword.toLowerCase()))
		.filter((index) => index >= 0);
	return hits.length > 0 ? Math.min(...hits) : -1;
};

const buildLifestyleEntities = (text: string, spendingDelta: number): LifestyleFocalEntity[] => {
	const found = LIFESTYLE_ENTITY_CATALOG.map((entity) => ({
		...entity,
		sourceIndex: firstKeywordIndex(text, entity.keywords),
		amount: 0,
	})).filter((entity) => entity.sourceIndex >= 0);
	const selected = [...found].sort((a, b) => a.sourceIndex - b.sourceIndex);

	for (const entity of LIFESTYLE_ENTITY_CATALOG) {
		if (selected.length >= 5) {
			break;
		}
		if (!selected.some((item) => item.id === entity.id)) {
			selected.push({...entity, sourceIndex: 100000 + selected.length, amount: 0});
		}
	}

	const totalWeight = selected.reduce((sum, entity) => sum + entity.weight, 0) || 1;
	const availableDelta = Math.max(spendingDelta, 1);

	return selected.slice(0, 6).map((entity) => ({
		...entity,
		amount: Math.max(900, Math.round((availableDelta * entity.weight) / totalWeight)),
	}));
};

const buildLifestyleFocalSequence = (entities: LifestyleFocalEntity[]): LifestyleFocalMoment[] => {
	const usableEntities = entities.slice(0, 6);
	const sequenceStart = 0.08;
	const sequenceEnd = 0.8;
	const windowSize = (sequenceEnd - sequenceStart) / Math.max(usableEntities.length, 1);
	const moments = usableEntities.map((entity, index) => ({
		entityId: entity.id,
		startProgress: sequenceStart + index * windowSize,
		endProgress: sequenceStart + (index + 0.92) * windowSize,
		dominance: 1.15 + index * 0.025,
		decay: 0.24,
		gravityCenter: entity.gravityCenter,
		attentionWeight: 0.82 + Math.min(index, 4) * 0.035,
		visualMode: 'entity_attack' as const,
	}));

	return [
		...moments,
		{
			entityId: 'compression_cluster',
			startProgress: 0.78,
			endProgress: 1,
			dominance: 1.08,
			decay: 0.34,
			gravityCenter: {x: 1280, y: 510},
			attentionWeight: 1,
			visualMode: 'compression',
		},
	];
};

const entityMentionsForSentence = (sentence: string, entities: LifestyleFocalEntity[]): LifestyleFocalEntity[] => {
	const lowered = sentence.toLowerCase();
	return entities
		.map((entity) => ({
			entity,
			index: firstKeywordIndex(lowered, entity.keywords),
		}))
		.filter((item) => item.index >= 0)
		.sort((a, b) => a.index - b.index)
		.map((item) => item.entity);
};

const semanticModeForSentence = (sentence: string): LifestyleFocalMoment['visualMode'] | null => {
	if (/next\s+raise.*captur|captur(e|ed)\s+the\s+raise|lifestyle\s+negotiates|save\s+the\s+difference|automate.*raise|allocate.*raise/i.test(sentence)) {
		return 'capture_raise_world';
	}
	if (/save before lifestyle|savings?\s+(jump|first)|decide\s+the\s+savings|protected?\s+at|protect(ed)?\s+the\s+raise|captured?\s+before|capture(d)?\s+before/i.test(sentence)) {
		return 'protected_savings_world';
	}
	if (/income\s+rises?.*paper|on\s+paper|savings?\s+(stays?|remain|stayed).*(flat|same)|flat\s+in\s+real\s+life|gap.*story|paper.*real/i.test(sentence)) {
		return 'paper_vs_real_world';
	}
	if (/becomes?\s+permanent|permanent\s+(bills?|costs?)|fixed\s+(bills?|costs?)|locked\s+in|recurring|monthly\s+bills?|routine\s+bill/i.test(sentence)) {
		return 'permanence_lock_world';
	}
	if (/problem\s+is\s+not\s+earning|not\s+earning\s+more|problem\s+is\s+giving.*new\s+expense/i.test(sentence)) {
		return 'compression';
	}
	if (/deserved?|normal|reward|irresponsible|earned|feels?\s+(good|fine|harmless|reasonable)|nothing\s+feels/i.test(sentence)) {
		return 'rationalization_world';
	}
	if (/never\s+reaches?\s+savings?|did\s+not\s+reach\s+savings|left\s+for\s+savings/i.test(sentence)) {
		return 'savings_isolation';
	}
	if (/absorbs?|new expense|permanent|lifestyle inflation|permanent bills|comfort quietly converts/i.test(sentence)) {
		return 'compression';
	}
	if (/\bsalary\b.*rises?|\bincome\b.*rises?|earning more/i.test(sentence)) {
		return 'salary_anchor';
	}
	if (/feels?\s+like\s+progress|raise\s+(arrives?|comes|hits)|extra\s*₹|extra\s+rs/i.test(sentence)) {
		return 'raise_hero';
	}
	return null;
};

const momentForSentence = (
	sentence: TimedSentence,
	visualMode: LifestyleFocalMoment['visualMode'],
): LifestyleFocalMoment => {
	const centers: Record<LifestyleFocalMoment['visualMode'], GravityCenter> = {
		entity_attack: {x: 1320, y: 420},
		compression: {x: 1280, y: 510},
		salary_anchor: {x: 960, y: 470},
		raise_hero: {x: 1120, y: 390},
		savings_isolation: {x: 960, y: 430},
		rationalization_world: {x: 960, y: 470},
		permanence_lock_world: {x: 960, y: 500},
		paper_vs_real_world: {x: 960, y: 500},
		capture_raise_world: {x: 960, y: 500},
		protected_savings_world: {x: 960, y: 500},
	};
	return {
		entityId: visualMode,
		startProgress: Math.max(0, sentence.startProgress - 0.002),
		endProgress: Math.min(1, sentence.endProgress + 0.008),
		dominance: visualMode === 'raise_hero' ? 1.18 : 1.08,
		decay: visualMode === 'compression' ? 0.34 : 0.22,
		gravityCenter: centers[visualMode],
		attentionWeight: 1,
		visualMode,
	};
};

const buildNarrationFocalSequence = (
	narration: string,
	entities: LifestyleFocalEntity[],
): LifestyleFocalMoment[] => {
	const moments: LifestyleFocalMoment[] = [];
	const sentences = narrationSentences(narration);
	const seen = new Set<string>();

	for (const sentence of sentences) {
		const semanticMode = semanticModeForSentence(sentence.text);
		const semanticFirstModes: Array<LifestyleFocalMoment['visualMode']> = [
			'rationalization_world',
			'permanence_lock_world',
			'paper_vs_real_world',
			'capture_raise_world',
			'protected_savings_world',
			'savings_isolation',
		];
		if (semanticMode && semanticFirstModes.includes(semanticMode)) {
			moments.push(momentForSentence(sentence, semanticMode));
			continue;
		}
		const mentioned = entityMentionsForSentence(sentence.text, entities);
		if (mentioned.length === 0) {
			if (semanticMode) {
				moments.push(momentForSentence(sentence, semanticMode));
			}
			continue;
		}
		const sentenceDuration = sentence.endProgress - sentence.startProgress;
		const slot = sentenceDuration / mentioned.length;
		mentioned.forEach((entity, index) => {
			const startProgress = Math.max(0, sentence.startProgress + slot * index - 0.004);
			const endProgress = Math.min(1, sentence.startProgress + slot * (index + 1) + 0.004);
			moments.push({
				entityId: entity.id,
				startProgress,
				endProgress,
				dominance: 1.2,
				decay: 0.18,
				gravityCenter: entity.gravityCenter,
				attentionWeight: 0.94,
				visualMode: 'entity_attack',
			});
			seen.add(entity.id);
		});
	}

	if (moments.length === 0) {
		return buildLifestyleFocalSequence(entities);
	}

	const finalEntityEnd = moments.filter((moment) => moment.visualMode === 'entity_attack').reduce((latest, moment) => Math.max(latest, moment.endProgress), 0);
	const savingsSentence = sentences.find((sentence) => /\bsavings?\b|\bgap\b|flat|never reaches/i.test(sentence.text));
	const compressionStart = Math.min(
		0.92,
		Math.max(finalEntityEnd + 0.025, savingsSentence ? savingsSentence.startProgress + 0.035 : finalEntityEnd + 0.08),
	);
	if (!moments.some((moment) => moment.visualMode === 'compression' && compressionStart >= moment.startProgress && compressionStart <= moment.endProgress)) {
		moments.push({
			entityId: 'compression_cluster',
			startProgress: compressionStart,
			endProgress: Math.min(1, compressionStart + 0.12),
			dominance: 1.08,
			decay: 0.34,
			gravityCenter: {x: 1280, y: 510},
			attentionWeight: 1,
			visualMode: 'compression',
		});
	}

	const hasLateSemanticCoverage = moments.some(
		(moment) =>
			moment.startProgress > 0.34 &&
			[
				'rationalization_world',
				'permanence_lock_world',
				'paper_vs_real_world',
				'capture_raise_world',
				'protected_savings_world',
				'savings_isolation',
				'compression',
			].includes(moment.visualMode),
	);

	for (const entity of entities) {
		if (hasLateSemanticCoverage || seen.has(entity.id) || moments.length >= 7) {
			continue;
		}
		const fallbackStart = Math.min(0.76, finalEntityEnd + 0.04 + moments.length * 0.035);
		moments.splice(Math.max(0, moments.length - 1), 0, {
			entityId: entity.id,
			startProgress: fallbackStart,
			endProgress: Math.min(0.9, fallbackStart + 0.07),
			dominance: 1.08,
			decay: 0.18,
			gravityCenter: entity.gravityCenter,
			attentionWeight: 0.86,
			visualMode: 'entity_attack',
		});
	}

	return moments.sort((a, b) => a.startProgress - b.startProgress);
};

const momentPresence = (progress: number, moment: LifestyleFocalMoment) => {
	if (progress < moment.startProgress || progress > moment.endProgress) {
		return 0;
	}
	const enterEnd = moment.startProgress + (moment.endProgress - moment.startProgress) * 0.34;
	const exitStart = moment.startProgress + (moment.endProgress - moment.startProgress) * 0.7;
	const enter = interpolate(progress, [moment.startProgress, enterEnd], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const exit = interpolate(progress, [exitStart, moment.endProgress], [1, 0.58], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return enter * exit;
};

const memoryPresence = (progress: number, moment: LifestyleFocalMoment) => {
	if (progress <= moment.endProgress) {
		return 0;
	}
	return interpolate(progress, [moment.endProgress, Math.min(1, moment.endProgress + 0.24)], [0.42, 0.18], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
};

const Shell: React.FC<{
	title: string;
	tone: 'calm' | 'optimistic' | 'pressure' | 'warning';
	children: React.ReactNode;
}> = ({title, tone, children}) => {
	const backgrounds = {
		calm: 'radial-gradient(circle at 52% 46%, rgba(46,196,182,0.16), transparent 34%), linear-gradient(135deg, #070912, #101725 58%, #070912)',
		optimistic:
			'radial-gradient(circle at 68% 34%, rgba(255,209,102,0.28), transparent 30%), radial-gradient(circle at 30% 72%, rgba(46,196,182,0.16), transparent 26%), linear-gradient(135deg, #080912, #15131d 56%, #08120f)',
		pressure:
			'radial-gradient(circle at 76% 42%, rgba(230,57,70,0.22), transparent 31%), radial-gradient(circle at 23% 70%, rgba(255,159,28,0.18), transparent 26%), linear-gradient(120deg, #080811, #15101a 56%, #090914)',
		warning: 'radial-gradient(circle at 50% 52%, rgba(230,57,70,0.18), transparent 24%), linear-gradient(135deg, #05060b, #0c0b12 58%, #05060b)',
	};
	const railColor = tone === 'calm' ? COLORS.positive : tone === 'optimistic' ? COLORS.warning : COLORS.danger;

	return (
		<AbsoluteFill
			style={{
				background: COLORS.bg_deep,
				color: COLORS.text_primary,
				padding: SPACING.safe,
				fontFamily: BODY_FONT_FAMILY,
				overflow: 'hidden',
			}}
		>
			<style>{FONT_FACES}</style>
			<div style={{position: 'absolute', inset: -120, background: backgrounds[tone]}} />
			<div style={{position: 'absolute', inset: 0, background: 'black', opacity: tone === 'warning' ? 0.38 : 0.06}} />
			<div style={{position: 'absolute', inset: 0, left: 0, width: 8, background: railColor}} />
			<div
				style={{
					position: 'relative',
					zIndex: 10,
					fontSize: TYPE_SCALE.label.size,
					fontWeight: 900,
					color: COLORS.text_secondary,
				}}
			>
				{title}
			</div>
			{children}
		</AbsoluteFill>
	);
};

const ValueBlock: React.FC<{
	label: string;
	value: string;
	color: string;
	size?: number;
	align?: 'left' | 'center';
}> = ({label, value, color, size = 106, align = 'left'}) => (
	<div style={{textAlign: align}}>
		<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>{label}</div>
		<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: size, lineHeight: 0.88, color}}>{value}</div>
	</div>
);

export const LifestyleCreepVisualizer: React.FC<BeatComponentProps> = ({beat, scene, frameWithinBeat, durationFrames}) => {
	const {fps} = useVideoConfig();
	const rawData = getBeatData<LifestyleCreepData>(beat) ?? {};
	const phase = String(beat.beat_phase ?? rawData.active_phase ?? 'expenses_follow');
	const event = resolveVisualEvent(beat, scene, 'LifestyleCreepVisualizer');
	const narration = sceneNarrationText(scene);
	const currentSceneSeconds = Number(beat.start_time ?? 0) + frameWithinBeat / fps;
	const sceneProgress = clamp(currentSceneSeconds / sceneDurationSeconds(scene, beat), 0, 1);
	const startIncome = moneyPoint(rawData.start_income, 50000);
	const endIncome = moneyPoint(rawData.end_income, 80000);
	const oldSpending = moneyPoint(rawData.old_spending, Math.round(startIncome.amount * 0.78));
	const newSpending = moneyPoint(rawData.new_spending, Math.round(endIncome.amount * 0.88));
	const oldSavings = moneyPoint(rawData.old_savings, Math.max(0, startIncome.amount - oldSpending.amount));
	const newSavings = moneyPoint(rawData.new_savings, Math.max(0, endIncome.amount - newSpending.amount));
	const raise = moneyPoint(rawData.raise, Math.max(0, endIncome.amount - startIncome.amount));
	const rawProgress = Math.min(getBeatProgress(frameWithinBeat, Math.floor(durationFrames * 0.82)), 1);
	const entry = spring({frame: Math.min(frameWithinBeat, 22), fps, config: SPRINGS.entry, durationInFrames: 22});
	const slowBreath = Math.sin((frameWithinBeat / fps) * Math.PI * 1.2);
	const raiseProgress = phase === 'income_base' ? 0 : phase === 'raise_arrives' ? rawProgress : 1;
	const creepProgress = phase === 'income_base' || phase === 'raise_arrives' ? 0 : phase === 'expenses_follow' ? rawProgress : 1;
	const incomeAmount = startIncome.amount + (endIncome.amount - startIncome.amount) * raiseProgress;
	const spendingAmount = oldSpending.amount + (newSpending.amount - oldSpending.amount) * creepProgress;
	const savingsAmount = Math.max(0, incomeAmount - spendingAmount);
	const gapShrank = newSavings.amount <= oldSavings.amount * 1.15;
	const newSpendDelta = Math.max(0, newSpending.amount - oldSpending.amount);
	const lifestyleEntities = buildLifestyleEntities(sceneLanguage(scene), newSpendDelta);
	const focalSequence = buildNarrationFocalSequence(narration, lifestyleEntities);
	const semanticMoment = focalSequence.find((moment) => sceneProgress >= moment.startProgress && sceneProgress <= moment.endProgress);
	const semanticEventProgress = semanticMoment
		? clamp((sceneProgress - semanticMoment.startProgress) / Math.max(semanticMoment.endProgress - semanticMoment.startProgress, 0.001), 0, 1)
		: rawProgress;
	const shouldUseNarrationFocalWorld = Boolean(semanticMoment && sceneProgress > 0.045);
	const semanticMode = shouldUseNarrationFocalWorld ? semanticMoment?.visualMode : undefined;

	if (semanticMode === 'salary_anchor' || (event.kind === 'baseline_life' && !shouldUseNarrationFocalWorld)) {
		const reserveWidth = interpolate(entry, [0, 1], [120, 430]);
		const spendRatio = clamp(oldSpending.amount / Math.max(startIncome.amount, 1), 0, 1);

		return (
			<Shell title="Baseline life" tone="calm">
				<div
					style={{
						position: 'absolute',
						inset: 0,
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						zIndex: 2,
						transform: `translateY(${interpolate(entry, [0, 1], [28, 0])}px)`,
						opacity: entry,
					}}
				>
					<div style={{width: 1020, textAlign: 'center'}}>
						<ValueBlock label="Monthly salary" value={startIncome.value} color={COLORS.text_primary} size={142} align="center" />
						<div
							style={{
								margin: '54px auto 0',
								width: 680,
								height: 28,
								borderRadius: 999,
								background: 'rgba(255,255,255,0.08)',
								overflow: 'hidden',
							}}
						>
							<div style={{height: '100%', width: `${spendRatio * 100}%`, background: 'rgba(255,255,255,0.22)'}} />
						</div>
						<div
							style={{
								margin: '44px auto 0',
								width: reserveWidth,
								minWidth: 280,
								padding: '22px 34px',
								border: `2px solid ${COLORS.positive}`,
								borderRadius: 8,
								background: 'rgba(46,196,182,0.12)',
								boxShadow: `0 0 ${26 + slowBreath * 6}px rgba(46,196,182,0.22)`,
							}}
						>
							<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>Stable savings</div>
							<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 72, lineHeight: 0.9, color: COLORS.positive}}>{oldSavings.value}</div>
						</div>
					</div>
				</div>
				<div style={{position: 'absolute', left: 250, bottom: 150, width: 280, height: 2, background: 'rgba(255,255,255,0.18)', opacity: 0.8}} />
				<div style={{position: 'absolute', right: 260, top: 210, width: 190, height: 2, background: 'rgba(255,255,255,0.16)', opacity: 0.7}} />
			</Shell>
		);
	}

	if (semanticMode === 'raise_hero' || (event.kind === 'raise_arrival' && !shouldUseNarrationFocalWorld)) {
		const raiseEventProgress = semanticMode === 'raise_hero' ? semanticEventProgress : rawProgress;
		const lift = interpolate(raiseEventProgress, [0, 1], [120, -36], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const glow = interpolate(raiseEventProgress, [0, 1], [0.28, 0.72], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const displayedIncome = rupee(startIncome.amount + (endIncome.amount - startIncome.amount) * raiseEventProgress);

		return (
			<Shell title="Raise arrival" tone="optimistic">
				<div
					style={{
						position: 'absolute',
						left: 220,
						top: 250,
						width: 980,
						zIndex: 3,
						opacity: entry,
						transform: `translateY(${interpolate(entry, [0, 1], [34, 0])}px)`,
					}}
				>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>New salary energy</div>
					<div
						style={{
							fontFamily: DISPLAY_FONT_FAMILY,
							fontSize: 176,
							lineHeight: 0.82,
							color: COLORS.text_primary,
							textShadow: `0 0 58px rgba(255,209,102,${glow})`,
						}}
					>
						{displayedIncome}
					</div>
					<div style={{marginTop: 26, fontSize: 44, fontWeight: 900, color: COLORS.warning}}>{raise.value} more per month</div>
				</div>
				<div
					style={{
						position: 'absolute',
						right: 255,
						bottom: 170 + lift,
						width: 360,
						height: 360,
						borderRadius: 180,
						border: `5px solid ${COLORS.warning}`,
						background: 'rgba(255,209,102,0.11)',
						boxShadow: '0 0 90px rgba(255,209,102,0.34)',
						transform: `scale(${0.72 + raiseEventProgress * 0.34})`,
						zIndex: 2,
					}}
				>
					<div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 150, fontWeight: 950, color: COLORS.warning}}>+</div>
				</div>
				{[0, 1, 2].map((index) => (
					<div
						key={index}
						style={{
							position: 'absolute',
							right: 500 + index * 120,
							bottom: 220 + index * 42 + lift * 0.36,
							width: 18,
							height: 190 + index * 45,
							borderRadius: 999,
							background: `linear-gradient(180deg, ${COLORS.warning}, rgba(255,209,102,0))`,
							opacity: interpolate(raiseEventProgress, [index * 0.12, 1], [0, 0.82], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
						}}
					/>
				))}
			</Shell>
		);
	}

	if (semanticMode === 'rationalization_world') {
		const visibleEntities = lifestyleEntities.slice(0, 3);
		const cardLabels = ['Feels deserved', 'Feels normal', 'Feels earned'];

		return (
			<Shell title="Lifestyle logic" tone="optimistic">
				<div
					style={{
						position: 'absolute',
						left: 240,
						top: 238,
						width: 560,
						zIndex: 3,
						opacity: entry,
						transform: `translateY(${interpolate(entry, [0, 1], [34, 0])}px)`,
					}}
				>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Nothing feels irresponsible</div>
					<div style={{marginTop: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 102, lineHeight: 0.88, color: COLORS.text_primary}}>
						Small upgrades feel harmless
					</div>
				</div>
				{visibleEntities.map((entity, index) => {
					const reveal = interpolate(semanticEventProgress, [index * 0.18, index * 0.18 + 0.34], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					});
					return (
						<div
							key={entity.id}
							style={{
								position: 'absolute',
								left: 1020 + (index % 2) * 270,
								top: 218 + index * 172,
								width: 430,
								padding: '28px 30px',
								borderRadius: 8,
								border: `2px solid ${entity.color}`,
								background: 'rgba(11,12,20,0.9)',
								boxShadow: `0 0 ${36 + reveal * 50}px ${entity.color}44`,
								opacity: reveal,
								transform: `translateY(${(1 - reveal) * 34}px) scale(${0.9 + reveal * 0.1})`,
								zIndex: 4,
							}}
						>
							<div style={{fontSize: TYPE_SCALE.micro.size + 2, color: entity.color, fontWeight: 950}}>{cardLabels[index] ?? 'Feels fine'}</div>
							<div style={{marginTop: 8, fontSize: 40, lineHeight: 1, color: COLORS.text_primary, fontWeight: 950}}>{entity.label}</div>
							<div style={{marginTop: 14, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58, lineHeight: 0.88, color: entity.color}}>+{rupee(entity.amount)}</div>
						</div>
					);
				})}
				<div
					style={{
						position: 'absolute',
						left: 750,
						top: 610,
						width: 330,
						height: 330,
						borderRadius: 165,
						border: `3px solid ${COLORS.warning}`,
						background: 'rgba(255,209,102,0.08)',
						boxShadow: '0 0 80px rgba(255,209,102,0.22)',
						opacity: interpolate(semanticEventProgress, [0.16, 0.86], [0.28, 0.84], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
					}}
				/>
			</Shell>
		);
	}

	if (semanticMode === 'permanence_lock_world') {
		const lockedEntities = lifestyleEntities.slice(0, 5);
		const lockProgress = interpolate(semanticEventProgress, [0.12, 0.86], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<Shell title="Permanent bills" tone="pressure">
				<div style={{position: 'absolute', left: 220, top: 214, width: 660, zIndex: 3}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Upgrade becomes a monthly obligation</div>
					<div style={{marginTop: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 112, lineHeight: 0.86, color: COLORS.text_primary}}>Lifestyle locks in</div>
				</div>
				<div
					style={{
						position: 'absolute',
						left: 1030,
						top: 150,
						width: 560,
						height: 740,
						borderRadius: 8,
						border: `2px solid ${COLORS.danger}`,
						background: 'rgba(230,57,70,0.09)',
						boxShadow: `0 0 ${50 + lockProgress * 54}px rgba(230,57,70,0.28)`,
						zIndex: 4,
					}}
				>
					<div style={{position: 'absolute', left: 38, top: 32, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Recurring cost stack</div>
					{lockedEntities.map((entity, index) => {
						const reveal = interpolate(semanticEventProgress, [index * 0.1, index * 0.1 + 0.28], [0, 1], {
							extrapolateLeft: 'clamp',
							extrapolateRight: 'clamp',
						});
						return (
							<div
								key={entity.id}
								style={{
									position: 'absolute',
									left: 38,
									top: 106 + index * 112,
									width: 484,
									height: 76,
									borderRadius: 8,
									border: `2px solid ${entity.color}`,
									background: `${entity.color}18`,
									opacity: reveal,
									transform: `translateX(${(1 - reveal) * 40}px)`,
								}}
							>
								<div style={{position: 'absolute', left: 22, top: 15, fontSize: 30, color: COLORS.text_primary, fontWeight: 950}}>{entity.label}</div>
								<div style={{position: 'absolute', right: 26, top: 13, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 42, color: entity.color}}>LOCKED</div>
							</div>
						);
					})}
				</div>
				<div style={{position: 'absolute', left: 260, bottom: 190, width: 560, height: 30, borderRadius: 999, background: 'rgba(255,255,255,0.08)', overflow: 'hidden'}}>
					<div style={{width: `${lockProgress * 100}%`, height: '100%', background: COLORS.danger}} />
				</div>
			</Shell>
		);
	}

	if (semanticMode === 'paper_vs_real_world') {
		const lineProgress = interpolate(semanticEventProgress, [0.08, 0.86], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

		return (
			<Shell title="Paper vs real life" tone="warning">
				<div style={{position: 'absolute', left: 190, top: 180, width: 690, height: 660, zIndex: 3}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Income on paper</div>
					<div style={{marginTop: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 126, lineHeight: 0.86, color: COLORS.positive}}>
						{endIncome.value}
					</div>
					<svg viewBox="0 0 620 310" style={{position: 'absolute', left: 0, top: 260, width: 620, height: 310, overflow: 'visible'}}>
						<path d="M 24 250 L 596 250" stroke="rgba(255,255,255,0.14)" strokeWidth={4} />
						<path d={`M 28 238 C 170 ${228 - lineProgress * 40}, 320 ${190 - lineProgress * 82}, 590 ${92 - lineProgress * 36}`} stroke={COLORS.positive} strokeWidth={14} strokeLinecap="round" fill="none" opacity={0.9} />
					</svg>
				</div>
				<div style={{position: 'absolute', right: 190, top: 180, width: 690, height: 660, zIndex: 3}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Savings in real life</div>
					<div style={{marginTop: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 126, lineHeight: 0.86, color: COLORS.danger}}>
						{newSavings.value}
					</div>
					<svg viewBox="0 0 620 310" style={{position: 'absolute', left: 0, top: 260, width: 620, height: 310, overflow: 'visible'}}>
						<path d="M 24 250 L 596 250" stroke="rgba(255,255,255,0.14)" strokeWidth={4} />
						<path d="M 28 216 C 180 218, 330 218, 590 216" stroke={COLORS.danger} strokeWidth={14} strokeLinecap="round" fill="none" opacity={0.95} />
					</svg>
				</div>
				<div
					style={{
						position: 'absolute',
						left: 818,
						top: 456,
						width: 284,
						padding: '28px 30px',
						borderRadius: 8,
						border: `2px solid ${COLORS.warning}`,
						background: 'rgba(255,209,102,0.1)',
						textAlign: 'center',
						zIndex: 6,
						opacity: interpolate(semanticEventProgress, [0.28, 0.72], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
					}}
				>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 72, color: COLORS.warning, lineHeight: 0.9}}>GAP</div>
				</div>
			</Shell>
		);
	}

	if (semanticMode === 'capture_raise_world') {
		const capture = interpolate(semanticEventProgress, [0.1, 0.72], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const leak = 1 - capture;

		return (
			<Shell title="Capture the raise" tone="optimistic">
				<div style={{position: 'absolute', left: 190, top: 230, width: 520, zIndex: 4}}>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Before lifestyle reacts</div>
					<div style={{marginTop: 18, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 120, lineHeight: 0.86, color: COLORS.warning}}>{raise.value}</div>
				</div>
				<svg viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, zIndex: 3, overflow: 'visible'}}>
					<path d="M 465 520 C 750 500, 850 500, 995 500" stroke={COLORS.warning} strokeWidth={28} strokeLinecap="round" fill="none" opacity={0.92} />
					<path d="M 995 500 C 1130 430, 1280 380, 1450 320" stroke={COLORS.positive} strokeWidth={28} strokeLinecap="round" fill="none" opacity={capture} />
					<path d="M 995 500 C 1160 590, 1320 650, 1490 720" stroke={COLORS.danger} strokeWidth={24} strokeLinecap="round" fill="none" opacity={leak * 0.42} />
				</svg>
				<div
					style={{
						position: 'absolute',
						left: 850,
						top: 375,
						width: 300,
						height: 250,
						borderRadius: 8,
						border: `4px solid ${COLORS.positive}`,
						background: 'rgba(46,196,182,0.14)',
						boxShadow: `0 0 ${54 + capture * 58}px rgba(46,196,182,0.36)`,
						zIndex: 5,
						transform: `scale(${0.9 + capture * 0.12})`,
					}}
				>
					<div style={{position: 'absolute', left: 34, top: 34, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Savings capture</div>
					<div style={{position: 'absolute', left: 34, bottom: 38, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 74, lineHeight: 0.88, color: COLORS.positive}}>
						FIRST
					</div>
				</div>
				<div style={{position: 'absolute', right: 250, bottom: 230, width: 390, padding: '24px 30px', borderRadius: 8, border: `2px solid ${COLORS.danger}`, background: 'rgba(230,57,70,0.08)', opacity: leak * 0.7, zIndex: 4}}>
					<div style={{fontSize: 38, color: COLORS.text_secondary, fontWeight: 950}}>Lifestyle waits outside</div>
				</div>
			</Shell>
		);
	}

	if (semanticMode === 'protected_savings_world') {
		const protect = interpolate(semanticEventProgress, [0.08, 0.78], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const savingsBoost = oldSavings.amount + raise.amount * protect;

		return (
			<Shell title="Protected savings" tone="calm">
				<div
					style={{
						position: 'absolute',
						left: 610,
						top: 220,
						width: 700,
						height: 520,
						borderRadius: 8,
						border: `4px solid ${COLORS.positive}`,
						background: 'rgba(46,196,182,0.12)',
						boxShadow: `0 0 ${70 + protect * 70}px rgba(46,196,182,0.34)`,
						zIndex: 4,
						textAlign: 'center',
					}}
				>
					<div style={{marginTop: 58, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>Savings jump decided first</div>
					<div style={{marginTop: 24, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 136, lineHeight: 0.86, color: COLORS.positive}}>
						{rupee(savingsBoost)}
					</div>
					<div style={{margin: '62px auto 0', width: 470, height: 34, borderRadius: 999, background: 'rgba(255,255,255,0.1)', overflow: 'hidden'}}>
						<div style={{height: '100%', width: `${22 + protect * 72}%`, background: COLORS.positive, boxShadow: `0 0 34px ${COLORS.positive}77`}} />
					</div>
				</div>
				{lifestyleEntities.slice(0, 4).map((entity, index) => (
					<div
						key={entity.id}
						style={{
							position: 'absolute',
							left: 178 + index * 386,
							bottom: 120,
							width: 290,
							height: 88,
							borderRadius: 8,
							border: `2px solid ${entity.color}`,
							background: `${entity.color}12`,
							opacity: 0.2 + (1 - protect) * 0.36,
							transform: `translateY(${protect * 32}px) scale(${1 - protect * 0.08})`,
							zIndex: 2,
						}}
					>
						<div style={{position: 'absolute', left: 22, top: 18, fontSize: 30, color: COLORS.text_secondary, fontWeight: 950}}>{entity.label}</div>
						<div style={{position: 'absolute', right: 22, bottom: 18, fontSize: 24, color: entity.color, fontWeight: 950}}>after savings</div>
					</div>
				))}
			</Shell>
		);
	}

	if (semanticMode === 'savings_isolation' || (event.kind === 'savings_gap_reveal' && !shouldUseNarrationFocalWorld)) {
		const savingsEventProgress = semanticMode === 'savings_isolation' ? semanticEventProgress : rawProgress;
		const collapse = interpolate(savingsEventProgress, [0, 0.68], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
		const tinyScale = interpolate(collapse, [0, 1], [1.12, 0.92]);

		return (
			<Shell title="Savings gap reveal" tone="warning">
				<div
					style={{
						position: 'absolute',
						inset: 0,
						zIndex: 2,
						opacity: 0.08 * (1 - collapse),
						transform: `scale(${1.22 - collapse * 0.2})`,
					}}
				>
					<div style={{position: 'absolute', left: 250, top: 360, width: 1180, height: 2, background: COLORS.stroke}} />
					<div style={{position: 'absolute', left: 420, top: 210, width: 160, height: 440, border: `2px solid ${COLORS.positive}`}} />
					<div style={{position: 'absolute', left: 760, top: 160, width: 160, height: 490, border: `2px solid ${COLORS.warning}`}} />
					<div style={{position: 'absolute', left: 1100, top: 540, width: 160, height: 110, border: `2px solid ${COLORS.danger}`}} />
				</div>
				<div
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						top: 312,
						textAlign: 'center',
						zIndex: 4,
						opacity: entry,
						transform: `translateY(${interpolate(entry, [0, 1], [32, 0])}px) scale(${tinyScale})`,
					}}
				>
					<div style={{fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 850}}>Actual savings left</div>
					<div
						style={{
							fontFamily: DISPLAY_FONT_FAMILY,
							fontSize: 118,
							lineHeight: 0.82,
							color: gapShrank ? COLORS.danger : COLORS.warning,
							textShadow: `0 0 ${70 + collapse * 40}px rgba(230,57,70,0.45)`,
						}}
					>
						{newSavings.value}
					</div>
					<div
						style={{
							margin: '54px auto 0',
							width: interpolate(collapse, [0, 1], [360, 130]),
							height: 18,
							borderRadius: 999,
							background: 'rgba(255,255,255,0.08)',
							overflow: 'hidden',
						}}
					>
						<div style={{height: '100%', width: '24%', background: gapShrank ? COLORS.danger : COLORS.warning}} />
					</div>
				</div>
				<div
					style={{
						position: 'absolute',
						left: 690,
						bottom: 132,
						width: 540,
						padding: '24px 32px',
						border: `2px solid ${gapShrank ? COLORS.danger : COLORS.warning}`,
						borderRadius: 8,
						background: gapShrank ? 'rgba(230,57,70,0.14)' : 'rgba(255,209,102,0.12)',
						textAlign: 'center',
						zIndex: 4,
						opacity: interpolate(savingsEventProgress, [0.24, 0.72], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
					}}
				>
					<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58, lineHeight: 0.94, color: gapShrank ? COLORS.danger : COLORS.warning}}>
						Raise did not reach savings
					</div>
				</div>
			</Shell>
		);
	}

	const focalProgress = shouldUseNarrationFocalWorld ? sceneProgress : rawProgress;
	const narrationIncomeProgress = shouldUseNarrationFocalWorld ? interpolate(sceneProgress, [0, 0.16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : raiseProgress;
	const narrationSpendProgress = shouldUseNarrationFocalWorld ? interpolate(focalProgress, [0.06, 0.64], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : creepProgress;
	const displayIncomeAmount = startIncome.amount + (endIncome.amount - startIncome.amount) * narrationIncomeProgress;
	const displaySpendingAmount = oldSpending.amount + (newSpending.amount - oldSpending.amount) * narrationSpendProgress;
	const displaySavingsAmount = Math.max(0, displayIncomeAmount - displaySpendingAmount);
	const boardReveal = shouldUseNarrationFocalWorld ? 1 : interpolate(rawProgress, [0, 0.28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const crowd = interpolate(focalProgress, [0.05, 0.72], [0.2, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const salaryWidth = interpolate(narrationSpendProgress, [0, 1], [640, 350], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const spendWidth = interpolate(narrationSpendProgress, [0, 1], [130, 660], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const savingsWidth = interpolate(displaySavingsAmount / Math.max(endIncome.amount, 1), [0, 0.32], [96, 310], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const compressionPresence = focalSequence
		.filter((moment) => moment.visualMode === 'compression')
		.reduce((maxPresence, moment) => Math.max(maxPresence, momentPresence(focalProgress, moment)), 0);
	const activeMoment =
		focalSequence
			.filter((moment) => focalProgress >= moment.startProgress && focalProgress <= moment.endProgress && moment.visualMode === 'entity_attack')
			.sort((a, b) => b.startProgress - a.startProgress)[0] ??
		(!shouldUseNarrationFocalWorld ? focalSequence.filter((moment) => moment.visualMode === 'entity_attack').slice(-1)[0] : undefined);
	const activeEntity = lifestyleEntities.find((entity) => entity.id === activeMoment?.entityId) ?? lifestyleEntities[0];
	const activePresence = activeMoment ? momentPresence(focalProgress, activeMoment) : 0;
	const activeDrift = activeMoment ? Math.sin((frameWithinBeat / fps) * Math.PI * 1.8) * 10 * activeMoment.attentionWeight : 0;

	return (
		<Shell title="Lifestyle absorption" tone="pressure">
			<div
				style={{
					position: 'absolute',
					left: 132,
					top: 188,
					width: 840,
					height: 590,
					borderRadius: 8,
					border: `1px solid ${COLORS.stroke}`,
					background: 'rgba(255,255,255,0.045)',
					boxShadow: '0 0 70px rgba(230,57,70,0.12)',
					opacity: boardReveal * (1 - compressionPresence * 0.45),
					transform: `translateX(${interpolate(boardReveal, [0, 1], [-70, 0])}px)`,
					zIndex: 2,
				}}
			>
				<div style={{position: 'absolute', left: 64, top: 76, fontSize: TYPE_SCALE.subtext.size, fontWeight: 900, color: COLORS.text_secondary}}>Raise being consumed</div>
				<div style={{position: 'absolute', left: 64, top: 158, width: 660, height: 86, opacity: 0.72}}>
					<div style={{fontSize: TYPE_SCALE.micro.size + 4, fontWeight: 900, color: COLORS.text_secondary}}>Income</div>
					<div style={{marginTop: 12, width: salaryWidth, height: 34, borderRadius: 999, background: COLORS.positive, boxShadow: `0 0 28px ${COLORS.positive}55`}} />
					<div style={{position: 'absolute', right: 0, top: 36, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 46, color: COLORS.positive}}>{rupee(displayIncomeAmount)}</div>
				</div>
				<div style={{position: 'absolute', left: 64, top: 294, width: 690, height: 116}}>
					<div style={{fontSize: TYPE_SCALE.micro.size + 4, fontWeight: 900, color: COLORS.text_secondary}}>Lifestyle spending</div>
					<div style={{marginTop: 12, width: spendWidth, height: 58, borderRadius: 8, background: COLORS.warning, boxShadow: `0 0 ${38 + crowd * 24}px ${COLORS.warning}66`}} />
					<div style={{position: 'absolute', right: 0, top: 32, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 56, color: COLORS.warning}}>{rupee(displaySpendingAmount)}</div>
				</div>
				<div style={{position: 'absolute', left: 64, bottom: 78, width: 660, height: 90}}>
					<div style={{fontSize: TYPE_SCALE.micro.size + 4, fontWeight: 900, color: COLORS.text_secondary}}>Savings squeezed</div>
					<div style={{marginTop: 12, width: savingsWidth, height: 26, borderRadius: 999, background: gapShrank ? COLORS.danger : COLORS.positive}} />
					<div style={{position: 'absolute', right: 0, top: 26, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 48, color: gapShrank ? COLORS.danger : COLORS.positive}}>{rupee(displaySavingsAmount)}</div>
				</div>
			</div>
			<div
				style={{
					position: 'absolute',
					left: 1080,
					top: 94,
					width: 520,
					height: 78,
					zIndex: 3,
					opacity: interpolate(focalProgress, [0.02, 0.18], [0, 0.82], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
				}}
			>
				<div style={{fontSize: TYPE_SCALE.micro.size + 4, fontWeight: 900, color: COLORS.text_secondary}}>Attention sequence</div>
				<div style={{marginTop: 13, height: 10, borderRadius: 999, background: 'rgba(255,255,255,0.1)', overflow: 'hidden'}}>
					<div style={{width: `${focalProgress * 100}%`, height: '100%', borderRadius: 999, background: activeEntity?.color ?? COLORS.warning}} />
				</div>
			</div>
			{activeEntity && activeMoment ? (
				<div
					style={{
						position: 'absolute',
						left: activeMoment.gravityCenter.x - 185,
						top: activeMoment.gravityCenter.y - 102 + activeDrift,
						width: 370,
						padding: '28px 30px',
						borderRadius: 8,
						border: `3px solid ${activeEntity.color}`,
						background: 'rgba(8,8,14,0.96)',
						boxShadow: `0 0 ${54 + activePresence * 48}px ${activeEntity.color}68`,
						opacity: activePresence * (1 - compressionPresence),
						transform: `scale(${0.82 + activePresence * activeMoment.dominance * 0.22})`,
						zIndex: 7,
					}}
				>
					<div style={{fontSize: TYPE_SCALE.micro.size + 2, color: activeEntity.color, fontWeight: 950, letterSpacing: 0}}>
						{visualRoleLabel[activeEntity.visualRole]}
					</div>
					<div style={{marginTop: 8, fontSize: 34, color: COLORS.text_secondary, fontWeight: 900}}>{activeEntity.label}</div>
					<div style={{marginTop: 2, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 68, lineHeight: 0.88, color: activeEntity.color}}>
						+{rupee(activeEntity.amount)}
					</div>
				</div>
			) : null}
			{lifestyleEntities.map((entity, index) => {
				const moment = focalSequence.find((item) => item.entityId === entity.id);
				const memory = moment ? memoryPresence(focalProgress, moment) : 0;
				const active = moment ? momentPresence(focalProgress, moment) : 0;
				const opacity = Math.max(memory, active * 0.16);
				const x = 1050 + (index % 3) * 238;
				const y = 845 + Math.floor(index / 3) * 74;

				return (
					<div
						key={entity.id}
						style={{
							position: 'absolute',
							left: x,
							top: y,
							width: 210,
							height: 60,
							borderRadius: 8,
							border: `1px solid ${entity.color}`,
							background: `${entity.color}18`,
							opacity,
							transform: `translateY(${(1 - opacity) * 18}px) scale(${0.92 + active * 0.08})`,
							zIndex: 4,
						}}
					>
						<div style={{position: 'absolute', left: 16, top: 8, fontSize: TYPE_SCALE.micro.size, color: COLORS.text_secondary, fontWeight: 900}}>{entity.label}</div>
						<div style={{position: 'absolute', left: 16, bottom: 8, fontSize: 18, color: entity.color, fontWeight: 950}}>spent</div>
					</div>
				);
			})}
			<div
				style={{
					position: 'absolute',
					left: 1068,
					top: 284,
					width: 560,
					height: 360,
					borderRadius: 8,
					border: `2px solid ${COLORS.danger}`,
					background: 'rgba(230,57,70,0.1)',
					opacity: compressionPresence,
					boxShadow: `0 0 ${70 + compressionPresence * 50}px rgba(230,57,70,0.35)`,
					zIndex: 6,
				}}
			>
				<div style={{position: 'absolute', left: 42, top: 34, fontSize: TYPE_SCALE.subtext.size, color: COLORS.text_secondary, fontWeight: 900}}>
					Compression cluster
				</div>
				<div style={{position: 'absolute', left: 42, top: 88, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 82, lineHeight: 0.88, color: COLORS.danger}}>
					{rupee(newSpending.amount)}
				</div>
				<div style={{position: 'absolute', left: 42, right: 42, bottom: 58, height: 30, borderRadius: 999, background: 'rgba(255,255,255,0.1)', overflow: 'hidden'}}>
					<div style={{height: '100%', width: '86%', background: COLORS.danger, boxShadow: `0 0 34px ${COLORS.danger}77`}} />
				</div>
				<div style={{position: 'absolute', right: 44, bottom: 104, fontSize: 32, color: COLORS.text_secondary, fontWeight: 900}}>
					{lifestyleEntities.length} upgrades locked in
				</div>
			</div>
			<svg viewBox="0 0 1920 1080" style={{position: 'absolute', inset: 0, zIndex: 3, overflow: 'visible', opacity: crowd}}>
				{lifestyleEntities.map((entity) => {
					const moment = focalSequence.find((item) => item.entityId === entity.id);
					const presence = moment ? Math.max(momentPresence(focalProgress, moment), memoryPresence(focalProgress, moment)) : 0;
					return (
					<path
						key={entity.id}
						d={`M ${entity.gravityCenter.x - 80} ${entity.gravityCenter.y + 30} C 1040 ${entity.gravityCenter.y}, 920 ${390}, 760 ${375}`}
						stroke={entity.color}
						strokeWidth={6}
						strokeLinecap="round"
						fill="none"
						opacity={presence * 0.82}
					/>
					);
				})}
			</svg>
		</Shell>
	);
};
