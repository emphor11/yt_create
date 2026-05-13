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

const scene = (scene_id: string, pattern: string, beats: Beat[], narration = ''): Scene => ({
	scene_id,
	pattern,
	narration,
	text: narration,
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

const leaks = {
	leaks: [
		{label: 'Food apps', value: '₹2,400', amount: 2400},
		{label: 'Subscriptions', value: '₹1,200', amount: 1200},
		{label: 'Impulse buys', value: '₹3,500', amount: 3500},
		{label: 'Convenience fees', value: '₹900', amount: 900},
	],
	monthly_loss: 8000,
};

const fomo = {
	points: [
		{x: 0.02, y: 0.68},
		{x: 0.18, y: 0.58},
		{x: 0.34, y: 0.42},
		{x: 0.52, y: 0.18},
		{x: 0.66, y: 0.28},
		{x: 0.82, y: 0.62},
		{x: 0.98, y: 0.78},
	],
};

const portfolio = {
	assets: [
		{label: 'Equity', allocation: 45, color: '#2EC4B6'},
		{label: 'Debt', allocation: 25, color: '#A7B0C0'},
		{label: 'FD', allocation: 15, color: '#FF9F1C'},
		{label: 'Gold', allocation: 10, color: '#B8A44C'},
		{label: 'Cash', allocation: 5, color: '#77839A'},
	],
};

const riskReturn = {
	safe_asset: 'FD',
	growth_asset: 'Equity',
	safe_rate: '6%',
	growth_rate: '12%',
	punch: 'Risk buys upside only when you can stay invested',
};

const emergencyFund = {
	buffer_months: 6,
	buffer_label: '6-month buffer',
	buffer_value: '₹1,50,000',
	shock_label: 'Medical bill',
	debt_label: 'Credit card debt',
	punch: 'The buffer buys breathing room before debt begins',
};

const outroRecap = {
	title: 'Build the system before the next salary arrives',
	actions: [
		{id: 'track', label: 'Track the leak', shortLabel: 'TRACK', keywords: ['track', 'spending', 'expenses'], color: '#4361EE'},
		{id: 'protect', label: 'Protect the buffer', shortLabel: 'PROTECT', keywords: ['protect', 'buffer', 'emergency'], color: '#2EC4B6'},
		{id: 'reduce_debt', label: 'Cut fixed pressure', shortLabel: 'CUT DEBT', keywords: ['debt', 'emi', 'loan'], color: '#FF9F1C'},
		{id: 'invest', label: 'Invest consistently', shortLabel: 'INVEST', keywords: ['invest', 'sip', 'compound'], color: '#2EC4B6'},
		{id: 'start', label: 'Start this month', shortLabel: 'START', keywords: ['start', 'this month'], color: '#FF9F1C'},
	],
};

export const visualEventFixtureScenes: Scene[] = [
	scene('fixture_money_flow', 'MoneyFlowDiagram', [
		timedBeat('MoneyFlowDiagram', '₹50,000 salary lands', 0, 3, 'intro', 'salary_arrives', 'salary_income', moneyFlow, 'wide_context'),
		timedBeat('MoneyFlowDiagram', '₹4,000 phone EMI hits', 3, 6, 'drain', 'expense_drains', 'phone_emi', moneyFlow, 'pressure_closeup'),
		timedBeat('MoneyFlowDiagram', 'Rent and food compress it', 6, 9, 'drain', 'expense_drains', 'rent_expense', moneyFlow, 'pressure_closeup'),
		timedBeat('MoneyFlowDiagram', '₹6,000 left', 9, 12, 'remainder', 'balance_revealed', 'remaining_balance', moneyFlow, 'survivor_isolation'),
	], 'Salary lands. Phone EMI hits first. Rent drains the account. Food apps compress the balance. Only ₹6,000 is left.'),
	scene('fixture_lifestyle', 'LifestyleCreepVisualizer', [
		timedBeat('LifestyleCreepVisualizer', 'Old lifestyle baseline', 0, 3, 'income_base', 'income_baseline', 'old_income', lifestyle, 'wide_context'),
		timedBeat('LifestyleCreepVisualizer', 'Raise arrives', 3, 6, 'raise_arrives', 'income_rises', 'raise_amount', lifestyle, 'upward_momentum'),
		timedBeat('LifestyleCreepVisualizer', 'Rent upgrade, food apps, weekend spending, shopping, and subscriptions absorb the raise', 6, 9, 'expenses_follow', 'expenses_follow', 'new_spending', lifestyle, 'pressure_closeup'),
		timedBeat('LifestyleCreepVisualizer', 'Savings gap exposed', 9, 12, 'gap_revealed', 'savings_gap_revealed', 'new_savings', lifestyle, 'survivor_isolation'),
	], 'Salary rises from ₹50,000 to ₹80,000. Rent upgrade arrives first. Food apps follow. Weekend spending expands. Shopping gets normalized. Subscriptions quietly become permanent. Savings stays almost flat.'),
	scene('fixture_emi', 'EMIStackVisualizer', [
		timedBeat('EMIStackVisualizer', 'One EMI looks harmless', 0, 3, 'first_emi', 'first_emi_appears', 'phone_emi', emi, 'wide_context'),
		timedBeat('EMIStackVisualizer', 'EMIs stack', 3, 6, 'stacking', 'emi_stacks', 'emi_group', emi, 'pressure_closeup'),
		timedBeat('EMIStackVisualizer', 'Salary gets squeezed', 6, 9, 'stacking', 'salary_squeezed', 'salary_income', emi, 'pressure_closeup'),
		timedBeat('EMIStackVisualizer', 'Only ₹6,000 left', 9, 12, 'pressure', 'balance_revealed', 'remaining_balance', emi, 'survivor_isolation'),
	], 'One phone EMI looks harmless. Then the bike EMI joins. A personal loan stacks on top. Salary gets squeezed by fixed payments. Only ₹6,000 is left after EMIs.'),
	scene('fixture_inflation', 'InflationErosionVisualizer', [
		timedBeat('InflationErosionVisualizer', '₹1,00,000 today', 0, 3, 'today', 'value_anchor', 'today_value', inflation, 'wide_context'),
		timedBeat('InflationErosionVisualizer', 'Inflation silently erodes', 3, 6, 'erosion', 'inflation_erodes', 'inflation_rate', inflation, 'pressure_closeup'),
		timedBeat('InflationErosionVisualizer', 'Basket shrinks', 6, 9, 'erosion', 'basket_shrinks', 'basket_units', inflation, 'focused_growth'),
		timedBeat('InflationErosionVisualizer', 'Future buying power falls', 9, 12, 'future', 'time_exposes_loss', 'future_value', inflation, 'survivor_isolation'),
	], '₹1,00,000 feels stable today. Inflation silently raises prices. The basket of groceries shrinks. After 5 years, the same money has less buying power.'),
	scene('fixture_sip', 'SIPGrowthEngine', [
		timedBeat('SIPGrowthEngine', '₹5,000 seed starts', 0, 3, 'contribution', 'contribution_starts', 'monthly_sip', sip, 'wide_context'),
		timedBeat('SIPGrowthEngine', 'Returns activate', 3, 6, 'growth', 'return_rate_activates', 'corpus_growth', sip, 'upward_momentum'),
		timedBeat('SIPGrowthEngine', 'Compounding layers', 6, 9, 'growth', 'contributions_accumulate', 'compounding_layers', sip, 'focused_growth'),
		timedBeat('SIPGrowthEngine', 'Corpus reveal', 9, 12, 'corpus', 'corpus_revealed', 'final_corpus', sip, 'reward_hero'),
	], 'A small ₹5,000 SIP starts quietly. The 12% return rate begins lifting the corpus. Time gives compounding more layers. After 20 years, the corpus becomes ₹50,00,000.'),
	scene('fixture_debt', 'DebtSpiralVisualizer', [
		timedBeat('DebtSpiralVisualizer', '₹1,00,000 principal', 0, 3, 'principal', 'debt_appears', 'principal_balance', debt, 'wide_context'),
		timedBeat('DebtSpiralVisualizer', 'Interest attaches', 3, 6, 'spiral', 'interest_rate_attaches', 'monthly_interest', debt, 'pressure_closeup'),
		timedBeat('DebtSpiralVisualizer', 'Spiral accelerates', 6, 9, 'spiral', 'interest_accumulates', 'debt_spiral', debt, 'pressure_closeup'),
		timedBeat('DebtSpiralVisualizer', 'Trap consequence', 9, 12, 'consequence', 'minimum_payment_fails', 'remaining_balance', debt, 'survivor_isolation'),
	], 'A ₹1,00,000 principal balance starts the spiral. Interest attaches every month. The minimum payment is not enough. The unpaid gap accelerates the spiral. After 12 months, you owe more.'),
	scene('fixture_leaks', 'SmallLeaksAccumulator', [
		timedBeat('SmallLeaksAccumulator', 'Food apps start the leak', 0, 3, 'first_leak', 'leak_appears', 'food_apps', leaks, 'wide_context'),
		timedBeat('SmallLeaksAccumulator', 'Subscriptions and impulse buys repeat', 3, 6, 'repeat', 'leaks_repeat', 'leak_group', leaks, 'pressure_closeup'),
		timedBeat('SmallLeaksAccumulator', 'Convenience fees add up', 6, 9, 'repeat', 'leaks_repeat', 'leak_group', leaks, 'pressure_closeup'),
		timedBeat('SmallLeaksAccumulator', 'Month end loss is exposed', 9, 12, 'month_end', 'month_end_loss', 'monthly_loss', leaks, 'survivor_isolation'),
	], 'Food apps start as one small leak. Subscriptions repeat in the background. Impulse buys join next. Convenience fees keep adding up. By month end, ₹8,000 is gone.'),
	scene('fixture_fomo', 'FOMOPriceCrashVisualizer', [
		timedBeat('FOMOPriceCrashVisualizer', 'Hype runs first', 0, 3, 'rise', 'hype_rises', 'price_rise', fomo, 'upward_momentum'),
		timedBeat('FOMOPriceCrashVisualizer', 'FOMO buys the peak', 3, 6, 'rise', 'buy_peak', 'peak_entry', fomo, 'pressure_closeup'),
		timedBeat('FOMOPriceCrashVisualizer', 'The crash arrives', 6, 9, 'crash', 'price_crashes', 'crash_drop', fomo, 'pressure_closeup'),
		timedBeat('FOMOPriceCrashVisualizer', 'Loss gets locked', 9, 12, 'loss', 'loss_locks', 'panic_loss', fomo, 'survivor_isolation'),
	], 'Hype runs first and the chart gets loud. FOMO buys at the peak. Then the crash drops fast. Panic after entry locks the loss.'),
	scene('fixture_portfolio', 'PortfolioDiversificationVisualizer', [
		timedBeat('PortfolioDiversificationVisualizer', 'One stock decides everything', 0, 3, 'concentrated', 'single_bet', 'one_stock', portfolio, 'wide_context'),
		timedBeat('PortfolioDiversificationVisualizer', 'Equity, debt, FD, gold, and cash spread risk', 3, 6, 'spread', 'risk_spreads', 'asset_mix', portfolio, 'comparison_focus'),
		timedBeat('PortfolioDiversificationVisualizer', 'One asset falls', 6, 9, 'impact', 'asset_falls', 'falling_asset', portfolio, 'pressure_closeup'),
		timedBeat('PortfolioDiversificationVisualizer', 'The portfolio absorbs impact', 9, 12, 'impact', 'impact_absorbed', 'portfolio_mix', portfolio, 'survivor_isolation'),
	], 'One stock decides everything. Equity gets one allocation. Debt gets another. FD, gold, and cash spread the risk. When one asset falls, the portfolio absorbs the impact.'),
	scene('fixture_risk_return', 'RiskReturnVisualizer', [
		timedBeat('RiskReturnVisualizer', 'FD feels calm', 0, 3, 'fd_anchor', 'safe_asset_anchors', 'fd_asset', riskReturn, 'wide_context'),
		timedBeat('RiskReturnVisualizer', 'Equity can grow faster', 3, 6, 'equity_growth', 'growth_asset_rises', 'equity_asset', riskReturn, 'upward_momentum'),
		timedBeat('RiskReturnVisualizer', 'Volatility is the price', 6, 9, 'volatility_price', 'risk_arrives', 'volatility', riskReturn, 'pressure_closeup'),
		timedBeat('RiskReturnVisualizer', 'Choose risk you can stay with', 9, 12, 'chosen_risk', 'risk_choice_revealed', 'decision', riskReturn, 'survivor_isolation'),
	], 'An FD gives 6% and feels calm. Equity offers higher long-term growth. Volatility is the price of that upside. Choose the risk you can stay with.'),
	scene('fixture_emergency_fund', 'EmergencyFundVisualizer', [
		timedBeat('EmergencyFundVisualizer', 'Cash buffer waits', 0, 3, 'boring_buffer', 'buffer_waits', 'cash_buffer', emergencyFund, 'wide_context'),
		timedBeat('EmergencyFundVisualizer', 'Medical bill hits', 3, 6, 'shock_focus', 'shock_hits', 'medical_bill', emergencyFund, 'pressure_closeup'),
		timedBeat('EmergencyFundVisualizer', 'Buffer blocks debt', 6, 9, 'debt_prevention', 'debt_blocked', 'credit_card_debt', emergencyFund, 'pressure_closeup'),
		timedBeat('EmergencyFundVisualizer', 'The plan survives', 9, 12, 'plan_survives', 'plan_survives', 'breathing_room', emergencyFund, 'survivor_isolation'),
	], 'An emergency fund looks boring. Then a medical bill hits the month. The cash buffer blocks credit card debt. The plan survives.'),
	scene('fixture_outro', 'OutroRecapVisualizer', [
		timedBeat('OutroRecapVisualizer', 'Track the leak', 0, 3, 'track', 'track_leaks', 'spending', outroRecap, 'wide_context'),
		timedBeat('OutroRecapVisualizer', 'Protect the buffer and cut fixed pressure', 3, 6, 'protect', 'protect_buffer', 'buffer', outroRecap, 'comparison_focus'),
		timedBeat('OutroRecapVisualizer', 'Invest consistently', 6, 9, 'invest', 'invest_consistently', 'sip', outroRecap, 'upward_momentum'),
		timedBeat('OutroRecapVisualizer', 'Start this month', 9, 12, 'start', 'start_now', 'action', outroRecap, 'reward_hero'),
	], 'Track your spending leaks. Protect an emergency buffer. Cut fixed EMI pressure. Invest consistently with a SIP. Start this month before the next salary disappears.'),
];
