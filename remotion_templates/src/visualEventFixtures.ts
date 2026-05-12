import {Beat, Scene} from './types';

const timedBeat = (
	component: string,
	text: string,
	start: number,
	end: number,
	phase: string,
	action: string,
	semanticRole: string,
	data: Record<string, unknown>,
	shotType: string,
): Beat => ({
	component,
	text,
	start_time: start,
	end_time: end,
	emphasis: end >= 9 ? 'hero' : 'normal',
	beat_phase: phase,
	data: {
		...data,
		active_phase: phase,
		active_action: {
			id: `fixture:${component}:${action}:${semanticRole}`,
			action,
			semantic_role: semanticRole,
			sequence_index: Math.round(start / 3),
		},
		active_shot: {
			shot_type: shotType,
			focus_target: semanticRole,
			attention_weight: end >= 9 ? 0.94 : 0.78,
			start_frame: Math.round(start * 30),
			end_frame: Math.round(end * 30),
		},
	},
	active_shot: {
		shot_type: shotType,
		focus_target: semanticRole,
		attention_weight: end >= 9 ? 0.94 : 0.78,
		start_frame: Math.round(start * 30),
		end_frame: Math.round(end * 30),
	},
});

const scene = (scene_id: string, pattern: string, beats: Beat[]): Scene => ({
	scene_id,
	pattern,
	duration: 12,
	audio_file: '',
	beats,
});

const moneyFlow = {
	source: {label: 'Salary', value: '₹50,000', amount: 50000},
	flows: [
		{label: 'Phone EMI', value: '₹4,000', amount: 4000, color: 'red', order: 1},
		{label: 'Rent', value: '₹18,000', amount: 18000, color: 'orange', order: 2},
		{label: 'Food apps', value: '₹8,000', amount: 8000, color: 'red', order: 3},
	],
	remainder: {value: '₹6,000', amount: 6000, is_dangerous: true},
};

const lifestyle = {
	start_income: {value: '₹50,000', amount: 50000},
	end_income: {value: '₹80,000', amount: 80000},
	old_spending: {value: '₹39,000', amount: 39000},
	new_spending: {value: '₹74,000', amount: 74000},
	old_savings: {value: '₹11,000', amount: 11000},
	new_savings: {value: '₹6,000', amount: 6000},
	raise: {value: '₹30,000', amount: 30000},
};

const emi = {
	salary: {value: '₹50,000', amount: 50000},
	emis: [
		{label: 'Phone EMI', value: '₹4,000', amount: 4000},
		{label: 'Bike EMI', value: '₹7,500', amount: 7500},
		{label: 'Personal loan', value: '₹12,000', amount: 12000},
	],
	total_emi: {value: '₹23,500', amount: 23500},
	remaining: {value: '₹6,000', amount: 6000, is_critical: true},
};

const inflation = {
	start: '₹1,00,000',
	end: '₹72,000',
	rate: '6% inflation',
	years: '5',
	items: [
		{name: 'Basket', current: 10, future: 7},
	],
};

const sip = {
	monthly_sip: {value: '₹5,000', amount: 5000},
	duration_years: 20,
	annual_return_rate: 12,
	total_invested: 1200000,
	final_corpus: 5000000,
	returns_earned: 3800000,
	awe_ratio: 4.2,
};

const debt = {
	principal: {value: '₹1,00,000', amount: 100000},
	monthly_interest: 3200,
	minimum_payment: 2200,
	month_12_balance: 112000,
	is_trap: true,
	balances: Array.from({length: 12}).map((_, index) => ({
		month: index + 1,
		balance: 100000 + index * 1100,
		interest: 3200,
		principal_paid: 2200,
	})),
};

export const visualEventFixtureScenes: Scene[] = [
	scene('fixture_money_flow', 'MoneyFlowDiagram', [
		timedBeat('MoneyFlowDiagram', '₹50,000 salary lands', 0, 3, 'intro', 'salary_arrives', 'salary_income', moneyFlow, 'wide_context'),
		timedBeat('MoneyFlowDiagram', '₹4,000 phone EMI hits', 3, 6, 'drain', 'expense_drains', 'phone_emi', moneyFlow, 'pressure_closeup'),
		timedBeat('MoneyFlowDiagram', 'Rent and food compress it', 6, 9, 'drain', 'expense_drains', 'rent_expense', moneyFlow, 'pressure_closeup'),
		timedBeat('MoneyFlowDiagram', '₹6,000 left', 9, 12, 'remainder', 'balance_revealed', 'remaining_balance', moneyFlow, 'survivor_isolation'),
	]),
	scene('fixture_lifestyle', 'LifestyleCreepVisualizer', [
		timedBeat('LifestyleCreepVisualizer', 'Old lifestyle baseline', 0, 3, 'income_base', 'income_baseline', 'old_income', lifestyle, 'wide_context'),
		timedBeat('LifestyleCreepVisualizer', 'Raise arrives', 3, 6, 'raise_arrives', 'income_rises', 'raise_amount', lifestyle, 'upward_momentum'),
		timedBeat('LifestyleCreepVisualizer', 'Lifestyle absorbs raise', 6, 9, 'expenses_follow', 'expenses_follow', 'new_spending', lifestyle, 'pressure_closeup'),
		timedBeat('LifestyleCreepVisualizer', 'Savings gap exposed', 9, 12, 'gap_revealed', 'savings_gap_revealed', 'new_savings', lifestyle, 'survivor_isolation'),
	]),
	scene('fixture_emi', 'EMIStackVisualizer', [
		timedBeat('EMIStackVisualizer', 'One EMI looks harmless', 0, 3, 'first_emi', 'first_emi_appears', 'phone_emi', emi, 'wide_context'),
		timedBeat('EMIStackVisualizer', 'EMIs stack', 3, 6, 'stacking', 'emi_stacks', 'emi_group', emi, 'pressure_closeup'),
		timedBeat('EMIStackVisualizer', 'Salary gets squeezed', 6, 9, 'stacking', 'salary_squeezed', 'salary_income', emi, 'pressure_closeup'),
		timedBeat('EMIStackVisualizer', 'Only ₹6,000 left', 9, 12, 'pressure', 'balance_revealed', 'remaining_balance', emi, 'survivor_isolation'),
	]),
	scene('fixture_inflation', 'InflationErosionVisualizer', [
		timedBeat('InflationErosionVisualizer', '₹1,00,000 today', 0, 3, 'today', 'value_anchor', 'today_value', inflation, 'wide_context'),
		timedBeat('InflationErosionVisualizer', 'Inflation silently erodes', 3, 6, 'erosion', 'inflation_erodes', 'inflation_rate', inflation, 'pressure_closeup'),
		timedBeat('InflationErosionVisualizer', 'Basket shrinks', 6, 9, 'erosion', 'basket_shrinks', 'basket_units', inflation, 'focused_growth'),
		timedBeat('InflationErosionVisualizer', 'Future buying power falls', 9, 12, 'future', 'time_exposes_loss', 'future_value', inflation, 'survivor_isolation'),
	]),
	scene('fixture_sip', 'SIPGrowthEngine', [
		timedBeat('SIPGrowthEngine', '₹5,000 seed starts', 0, 3, 'contribution', 'contribution_starts', 'monthly_sip', sip, 'wide_context'),
		timedBeat('SIPGrowthEngine', 'Returns activate', 3, 6, 'growth', 'return_rate_activates', 'corpus_growth', sip, 'upward_momentum'),
		timedBeat('SIPGrowthEngine', 'Compounding layers', 6, 9, 'growth', 'contributions_accumulate', 'compounding_layers', sip, 'focused_growth'),
		timedBeat('SIPGrowthEngine', 'Corpus reveal', 9, 12, 'corpus', 'corpus_revealed', 'final_corpus', sip, 'reward_hero'),
	]),
	scene('fixture_debt', 'DebtSpiralVisualizer', [
		timedBeat('DebtSpiralVisualizer', '₹1,00,000 principal', 0, 3, 'principal', 'debt_appears', 'principal_balance', debt, 'wide_context'),
		timedBeat('DebtSpiralVisualizer', 'Interest attaches', 3, 6, 'spiral', 'interest_rate_attaches', 'monthly_interest', debt, 'pressure_closeup'),
		timedBeat('DebtSpiralVisualizer', 'Spiral accelerates', 6, 9, 'spiral', 'interest_accumulates', 'debt_spiral', debt, 'pressure_closeup'),
		timedBeat('DebtSpiralVisualizer', 'Trap consequence', 9, 12, 'consequence', 'minimum_payment_fails', 'remaining_balance', debt, 'survivor_isolation'),
	]),
];
