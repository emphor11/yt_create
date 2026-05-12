import {Beat, Scene, Shot} from '../types';

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

export const resolveVisualEvent = (
	beat: Beat,
	scene: Scene | undefined,
	component: ComponentName,
): ResolvedVisualEvent => {
	const data = isRecord(beat.data) ? beat.data : {};
	const action = isRecord(data.active_action) ? data.active_action : {};
	const shot = activeShotFromBeat(beat);
	const phase = String(beat.beat_phase ?? data.active_phase ?? '');
	const actionName = String(action.action ?? shot?.derived_from_action ?? '');
	const semanticRole = String(action.semantic_role ?? shot?.focus_target ?? '');
	const focusTarget = String(shot?.focus_target ?? semanticRole);
	const shotType = String(shot?.shot_type ?? '');
	const sequenceIndex = Number.isFinite(Number(action.sequence_index)) ? Number(action.sequence_index) : -1;
	const attention = clamp(Number(shot?.attention_weight ?? 0.72), 0.45, 1);

	return {
		kind: resolveKind(component, phase, actionName, shotType, semanticRole, scene),
		phase,
		actionName,
		semanticRole,
		focusTarget,
		shotType,
		attention,
		sequenceIndex,
	};
};

const resolveKind = (
	component: ComponentName,
	phase: string,
	actionName: string,
	shotType: string,
	semanticRole: string,
	scene: Scene | undefined,
): VisualEventKind => {
	const p = phase.toLowerCase();
	const action = actionName.toLowerCase();
	const shot = shotType.toLowerCase();
	const role = semanticRole.toLowerCase();

	if (component === 'MoneyFlowDiagram') {
		if (action === 'salary_arrives' || p === 'intro' || shot === 'wide_context') return 'salary_hero';
		if (action === 'balance_revealed' || p === 'remainder' || shot === 'survivor_isolation') return 'survivor_isolation';
		if (action === 'expense_drains' && (role.includes('rent') || role.includes('emi'))) return 'drain_attack';
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
		if (p === 'pressure' || action === 'balance_revealed' || shot === 'survivor_isolation') return 'critical_leftover';
		if (action === 'salary_squeezed' || role.includes('salary')) return 'salary_squeeze';
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
