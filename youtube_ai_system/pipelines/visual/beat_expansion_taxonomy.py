"""Static component taxonomy for visual beat expansion."""

from __future__ import annotations


PRIMARY_MECHANISM_COMPONENTS = {
    "MoneyFlowDiagram",
    "DebtSpiralVisualizer",
    "SIPGrowthEngine",
    "InflationErosionVisualizer",
    "LifestyleCreepVisualizer",
    "EMIStackVisualizer",
    "FOMOPriceCrashVisualizer",
    "PortfolioDiversificationVisualizer",
    "SmallLeaksAccumulator",
    "RiskReturnVisualizer",
    "EmergencyFundVisualizer",
    "OutroRecapVisualizer",
    "UniversalMechanismRenderer",
}


MECHANISM_PHASES = {
    "MoneyFlowDiagram": ("intro", "drain", "drain", "drain", "remainder", "remainder", "remainder"),
    "DebtSpiralVisualizer": ("principal", "spiral", "spiral", "spiral", "consequence", "consequence", "consequence"),
    "SIPGrowthEngine": ("contribution", "growth", "growth", "growth", "corpus", "corpus", "corpus"),
    "InflationErosionVisualizer": ("today", "erosion", "erosion", "erosion", "future", "future", "future"),
    "LifestyleCreepVisualizer": ("income_base", "raise_arrives", "expenses_follow", "expenses_follow", "gap_revealed", "gap_revealed", "gap_revealed"),
    "EMIStackVisualizer": ("first_emi", "stacking", "stacking", "stacking", "pressure", "pressure", "pressure"),
    "FOMOPriceCrashVisualizer": ("rise", "crash", "crash", "crash", "loss", "loss", "loss"),
    "PortfolioDiversificationVisualizer": ("concentrated", "spread", "spread", "spread", "impact", "impact", "impact"),
    "SmallLeaksAccumulator": ("first_leak", "repeat", "repeat", "repeat", "month_end", "month_end", "month_end"),
    "RiskReturnVisualizer": ("fd_anchor", "equity_growth", "volatility_price", "volatility_price", "chosen_risk", "chosen_risk", "chosen_risk"),
    "EmergencyFundVisualizer": ("boring_buffer", "shock_focus", "shock_focus", "debt_prevention", "plan_survives", "plan_survives", "plan_survives"),
    "OutroRecapVisualizer": ("track", "protect", "reduce_debt", "invest", "start", "start", "start"),
    "UniversalMechanismRenderer": ("focus", "shift", "pressure", "reveal", "choice", "consequence", "takeaway"),
}


OBJECT_TO_VIEWER_TEXT = {
    "phone_account": "Money hits the account",
    "salary_balance": "Salary lands",
    "emi_stack": "Fixed payments stack up",
    "debt_pressure": "Debt starts compounding",
    "inflation_basket": "Buying power starts shrinking",
    "sip_jar": "Compounding starts working",
    "portfolio_grid": "Risk gets distributed",
    "emergency_buffer": "Safety net absorbs the shock",
}
