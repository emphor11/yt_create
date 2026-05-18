import {Beat, Scene, Shot, VisualEventSequenceEvent} from '../../types';

export type VisualEventKind =
	| 'salary_hero'
	| 'drain_attack'
	| 'pressure_compression'
	| 'survivor_isolation'
	| 'baseline_life'
	| 'raise_arrival'
	| 'lifestyle_absorption'
	| 'savings_gap_reveal'
	| 'first_emi_comfort'
	| 'emi_stacking'
	| 'salary_squeeze'
	| 'critical_leftover'
	| 'today_anchor'
	| 'silent_erosion'
	| 'basket_shrink'
	| 'future_loss_reveal'
	| 'small_seed'
	| 'momentum_lift'
	| 'compounding_layer'
	| 'corpus_hero_reveal'
	| 'principal_anchor'
	| 'interest_attachment'
	| 'spiral_acceleration'
	| 'trap_consequence';

export type ResolvedVisualEvent = {
	kind: VisualEventKind;
	phase: string;
	actionName: string;
	semanticRole: string;
	focusTarget: string;
	shotType: string;
	attention: number;
	sequenceIndex: number;
	primitiveType: string;
	worldObject: string;
	perceptualWorld: string;
	activeEntity: string;
	narrationAnchor: string;
	suppressionTarget: string;
	visualPurpose: string;
};

type ComponentName =
	| 'MoneyFlowDiagram'
	| 'LifestyleCreepVisualizer'
	| 'EMIStackVisualizer'
	| 'InflationErosionVisualizer'
	| 'SIPGrowthEngine'
	| 'DebtSpiralVisualizer';

const isRecord = (value: unknown): value is Record<string, unknown> =>
	Boolean(value && typeof value === 'object' && !Array.isArray(value));

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));

const asShot = (value: unknown): Shot | null => (isRecord(value) ? (value as Shot) : null);

const activeShotFromBeat = (beat: Beat): Shot | null => {
	const data = isRecord(beat.data) ? beat.data : {};
	return asShot(beat.active_shot) ?? asShot(data.active_shot);
};

const activeSequenceEvent = (beat: Beat, scene: Scene | undefined): VisualEventSequenceEvent | null => {
	const sequence = scene?.visual_event_sequence;
	const events = Array.isArray(sequence?.events) ? sequence?.events ?? [] : [];
	if (!events.length) {
		return null;
	}
	const data = isRecord(beat.data) ? beat.data : {};
	const action = isRecord(data.active_action) ? data.active_action : {};
	const activeActionId = String(action.id ?? '');
	if (activeActionId) {
		const byAction = events.find((event) => String(event.source_action_id ?? '') === activeActionId);
		if (byAction) {
			return byAction;
		}
	}
	const duration = Number(scene?.duration ?? scene?.total_duration ?? 0);
	const midpoint = duration > 0
		? clamp((Number(beat.start_time ?? 0) + Number(beat.end_time ?? beat.start_time ?? 0)) / 2 / duration, 0, 1)
		: Number.NaN;
	if (Number.isFinite(midpoint)) {
		const byTime = events.find((event) => {
			const timing = isRecord(event.timing) ? event.timing : {};
			const start = Number(timing.start_progress ?? 0);
			const end = Number(timing.end_progress ?? 1);
			return midpoint >= start && midpoint <= end;
		});
		if (byTime) {
			return byTime;
		}
	}
	return events[Math.min(events.length - 1, Math.max(0, Number(beat.sentence_index ?? 0)))] ?? events[0] ?? null;
};

export const resolveVisualEvent = (
	beat: Beat,
	scene: Scene | undefined,
	component: ComponentName,
): ResolvedVisualEvent => {
	const data = isRecord(beat.data) ? beat.data : {};
	const action = isRecord(data.active_action) ? data.active_action : {};
	const shot = activeShotFromBeat(beat);
	const sequenceEvent = activeSequenceEvent(beat, scene);
	const phase = String(beat.beat_phase ?? data.active_phase ?? '');
	const actionName = String(action.action ?? sequenceEvent?.source_action_id ?? shot?.derived_from_action ?? '');
	const semanticRole = String(action.semantic_role ?? sequenceEvent?.semantic_role ?? shot?.focus_target ?? '');
	const focusTarget = String(shot?.focus_target ?? sequenceEvent?.active_entity ?? semanticRole);
	const shotType = String(shot?.shot_type ?? '');
	const sequenceIndex = Number.isFinite(Number(action.sequence_index))
		? Number(action.sequence_index)
		: Number.isFinite(Number(sequenceEvent?.sequence_index))
			? Number(sequenceEvent?.sequence_index)
			: -1;
	const attention = clamp(Number(shot?.attention_weight ?? 0.72), 0.45, 1);
	const primitiveType = String(sequenceEvent?.primitive_type ?? '');
	const worldObject = String(sequenceEvent?.world_object ?? '');
	const perceptualWorld = String(sequenceEvent?.perceptual_world ?? '');

	return {
		kind: resolveKind(component, phase, actionName, shotType, semanticRole, scene, sequenceEvent),
		phase,
		actionName,
		semanticRole,
		focusTarget,
		shotType,
		attention,
		sequenceIndex,
		primitiveType,
		worldObject,
		perceptualWorld,
		activeEntity: String(sequenceEvent?.active_entity ?? ''),
		narrationAnchor: String(sequenceEvent?.narration_anchor ?? ''),
		suppressionTarget: String(sequenceEvent?.suppression_target ?? ''),
		visualPurpose: String(sequenceEvent?.visual_purpose ?? ''),
	};
};

const resolveKind = (
	component: ComponentName,
	phase: string,
	actionName: string,
	shotType: string,
	semanticRole: string,
	scene: Scene | undefined,
	sequenceEvent: VisualEventSequenceEvent | null,
): VisualEventKind => {
	const p = phase.toLowerCase();
	const action = actionName.toLowerCase();
	const shot = shotType.toLowerCase();
	const role = semanticRole.toLowerCase();
	const primitive = String(sequenceEvent?.primitive_type ?? '').toLowerCase();
	const worldObject = String(sequenceEvent?.world_object ?? '').toLowerCase();
	const sourceMotion = String(sequenceEvent?.source_motion ?? '').toLowerCase();
	const sourceActionId = String(sequenceEvent?.source_action_id ?? '').toLowerCase();
	const visualPurpose = String(sequenceEvent?.visual_purpose ?? '').toLowerCase();

	if (component === 'MoneyFlowDiagram') {
		if (worldObject && !worldObject.includes('salary') && (primitive === 'arrival' || p === 'intro' || shot === 'wide_context')) return 'today_anchor';
		if (sourceActionId.includes('salary_arrives') || action === 'salary_arrives' || primitive === 'arrival' || p === 'intro' || shot === 'wide_context') return 'salary_hero';
		if (sourceActionId.includes('balance_revealed') || action === 'balance_revealed' || primitive === 'isolation' || p === 'remainder' || shot === 'survivor_isolation') return 'survivor_isolation';
		if (sourceActionId.includes('expense_drains') || action === 'expense_drains' || primitive === 'attack') return 'drain_attack';
		return 'pressure_compression';
	}

	if (component === 'LifestyleCreepVisualizer') {
		if (p === 'income_base' || action === 'income_baseline') return 'baseline_life';
		if (p === 'raise_arrives' || action === 'income_rises') return 'raise_arrival';
		if (p === 'gap_revealed' || action === 'savings_gap_revealed') return 'savings_gap_reveal';
		return 'lifestyle_absorption';
	}

	if (component === 'EMIStackVisualizer') {
		if (p === 'first_emi' || action === 'first_emi_appears') return 'first_emi_comfort';
		if (sourceActionId.includes('balance_revealed') || p === 'pressure' || action === 'balance_revealed' || primitive === 'isolation' || shot === 'survivor_isolation') return 'critical_leftover';
		if (sourceActionId.includes('salary_arrives') || action === 'salary_squeezed' || role.includes('salary') || visualPurpose.includes('source')) return 'salary_squeeze';
		if (sourceActionId.includes('emi_stacks') || sourceMotion.includes('stack') || primitive === 'stack') return 'emi_stacking';
		return 'emi_stacking';
	}

	if (component === 'InflationErosionVisualizer') {
		if (p === 'today' || action === 'value_anchor') return 'today_anchor';
		if (p === 'future' || action === 'time_exposes_loss') return 'future_loss_reveal';
		if (action === 'inflation_erodes' || p === 'erosion') return 'silent_erosion';
		return 'basket_shrink';
	}

	if (component === 'SIPGrowthEngine') {
		if (p === 'contribution' || action === 'contribution_starts' || shot === 'wide_context') return 'small_seed';
		if (action === 'return_rate_activates' || action === 'time_extends' || shot === 'upward_momentum') return 'momentum_lift';
		if (action === 'contributions_accumulate' || shot === 'focused_growth') return 'compounding_layer';
		return 'corpus_hero_reveal';
	}

	if (component === 'DebtSpiralVisualizer') {
		if (p === 'principal' || action === 'debt_appears') return 'principal_anchor';
		if (action === 'interest_rate_attaches') return 'interest_attachment';
		if (p === 'consequence' || action === 'minimum_payment_fails') return 'trap_consequence';
		return 'spiral_acceleration';
	}

	return scene?.beats?.length ? 'pressure_compression' : 'salary_hero';
};

export const eventAccent = (event: ResolvedVisualEvent, fallback: string) => {
	if (
		event.kind === 'drain_attack' ||
		event.kind === 'pressure_compression' ||
		event.kind === 'critical_leftover' ||
		event.kind === 'silent_erosion' ||
		event.kind === 'future_loss_reveal' ||
		event.kind === 'trap_consequence'
	) {
		return '#E63946';
	}
	if (
		event.kind === 'small_seed' ||
		event.kind === 'momentum_lift' ||
		event.kind === 'compounding_layer' ||
		event.kind === 'corpus_hero_reveal'
	) {
		return '#2EC4B6';
	}
	return fallback;
};
