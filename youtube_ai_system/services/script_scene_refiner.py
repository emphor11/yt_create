from __future__ import annotations

from typing import Any

from .visual_scene_normalizer import VisualSceneNormalizer


class ScriptSceneRefiner:
    """Expands weak body scenes into visual-ready finance narration."""

    MIN_BODY_WORDS = 160

    def __init__(self) -> None:
        self.normalizer = VisualSceneNormalizer()

    def refine_scene(
        self,
        scene: dict[str, Any],
        narration: str,
        *,
        index: int,
        topic: str,
        angle: str,
    ) -> dict[str, Any]:
        source = dict(scene)
        source["narration"] = narration
        visual_scene = self.normalizer.normalize(source, index - 1)
        if self._has_multiple_mechanisms(narration):
            return {
                "narration": narration,
                "visual_scene": visual_scene.to_dict(),
                "refined": False,
                "allow_grouping": True,
            }
        if self._is_strong_enough(narration, visual_scene.mechanism):
            return {
                "narration": narration,
                "visual_scene": visual_scene.to_dict(),
                "refined": False,
                "allow_grouping": False,
            }

        refined = self._template_for(visual_scene.mechanism, narration, topic, angle)
        refined_scene = self.normalizer.normalize(
            {
                **source,
                "narration": refined,
                "mechanism": visual_scene.mechanism,
                "emotion": visual_scene.emotion,
            },
            index - 1,
        )
        return {
            "narration": refined,
            "visual_scene": refined_scene.to_dict(),
            "refined": True,
            "allow_grouping": False,
        }

    def _has_multiple_mechanisms(self, narration: str) -> bool:
        lowered = narration.lower()
        groups = [
            ("lifestyle", ("lifestyle", "raise", "upgrade", "spending rises")),
            ("debt", ("credit card", "minimum payment", "minimum dues", "debt trap", "interest")),
            ("inflation", ("inflation", "purchasing power")),
            ("sip", ("sip", "compound", "compounding")),
            ("risk", ("risk", "return", "diversification")),
        ]
        hits = 0
        for _, keywords in groups:
            if any(keyword in lowered for keyword in keywords):
                hits += 1
        return hits >= 2

    def _is_strong_enough(self, narration: str, mechanism: str) -> bool:
        words = narration.split()
        if len(words) < self.MIN_BODY_WORDS:
            return False
        sentence_count = sum(1 for part in narration.replace("?", ".").replace("!", ".").split(".") if part.strip())
        if sentence_count < 4:
            return False
        if mechanism in {"salary_drain", "debt_trap", "emi_pressure", "inflation_erosion", "sip_growth", "compounding"}:
            return any(token in narration for token in ("₹", "%")) or any(char.isdigit() for char in narration)
        return True

    def _template_for(self, mechanism: str, narration: str, topic: str, angle: str) -> str:
        templates = {
            "salary_drain": (
                "Your ₹50,000 salary lands and feels powerful for one day. Then ₹18,000 goes to EMI. "
                "₹12,000 goes to rent. Food, travel, and small spends take another ₹14,000. "
                "By day 20, only ₹6,000 is still breathing. The salary did not disappear randomly. "
                "It drained through fixed costs before you started making choices."
            ),
            "lifestyle_inflation": (
                "Your salary rises from ₹50,000 to ₹80,000. At first, it feels like progress. "
                "Then rent upgrades, food apps, weekend plans, and shopping expand with it. "
                "The extra ₹30,000 never reaches savings. Lifestyle absorbs the raise before you notice it. "
                "The problem is not earning more. The problem is giving every raise a new expense."
            ),
            "emi_pressure": (
                "One EMI feels harmless. Then a phone EMI joins it. Then a bike EMI joins it. "
                "Then a personal loan starts taking its share. Suddenly ₹18,000 leaves before the month even begins. "
                "That is how EMI pressure builds. The trap is not one huge payment. "
                "It is five small payments behaving like one big leak."
            ),
            "debt_trap": (
                "A ₹1,00,000 credit card balance does not look scary at first. The bank says the minimum payment is only ₹3,000. "
                "But at 40% annual interest, the monthly interest itself is around ₹3,300. "
                "So even after paying, the balance barely moves. Sometimes it grows. "
                "That is the debt trap. The payment feels responsible, but the interest is still winning."
            ),
            "inflation_erosion": (
                "Inflation does not attack your savings loudly. It works quietly. "
                "If ₹1,00,000 sits idle while prices rise at 7%, its buying power keeps shrinking. "
                "After 10 years, the same money feels almost half as useful. "
                "Your bank balance may look stable. But the real value is leaking every year."
            ),
            "sip_growth": (
                "A ₹5,000 SIP looks boring in the first month. It still looks small in the first year. "
                "But at 12% annual return over 20 years, the story changes. "
                "You invest about ₹12 lakh from your pocket. Compounding can turn it into nearly ₹50 lakh. "
                "The magic is not speed. The magic is staying invested long enough."
            ),
            "compounding": (
                "Compound interest feels slow because the first few years look unimpressive. "
                "A ₹5,000 monthly investment does not explode immediately. "
                "But every year, returns start earning their own returns. "
                "After 10 years, the curve bends. After 20 years, time does most of the work. "
                "That is why starting early beats waiting for the perfect amount."
            ),
            "risk_return": (
                "Risk and return are connected. An FD may offer around 6% and feel calm. "
                "Equity can offer higher long-term growth, but the price is volatility. "
                "Low risk usually means lower upside. Higher upside usually means emotional discomfort. "
                "The goal is not to avoid risk completely. The goal is to choose risk you understand."
            ),
            "diversification": (
                "Putting all your money into one stock feels exciting when it rises. "
                "But one bad result, one bad quarter, or one panic fall can hurt everything. "
                "Diversification spreads the risk across assets. Some money can sit in equity. "
                "Some can sit in debt funds or FD. The point is simple. One basket should not decide your future."
            ),
            "speculation_risk": (
                "FOMO investing feels like action. A stock runs up, everyone talks about it, and you enter late. "
                "Then the price falls and panic starts. That is not investing. That is emotion wearing a finance costume. "
                "Real investing starts with understanding what you own. If you cannot explain it, you probably should not buy it."
            ),
            "emergency_fund": (
                "An emergency fund looks boring until life becomes expensive. "
                "One medical bill, job delay, or family emergency can break a perfect budget. "
                "A six-month cash buffer stops that shock from becoming credit card debt. "
                "It does not make you rich. It keeps one bad month from destroying the plan."
            ),
        }
        if mechanism in templates:
            return self._ensure_min_words(templates[mechanism], mechanism, topic, angle)
        context = topic or angle or "money"
        return self._ensure_min_words(
            f"Most people notice {context} only after the damage is visible. A small money decision feels harmless at first. "
            "Then it repeats every week. The amount looks tiny in isolation, but the pattern becomes expensive. "
            "By the end of the month, the viewer is not confused because of one big mistake. "
            "The pressure comes from small choices adding up quietly.",
            mechanism,
            topic,
            angle,
        )

    def _ensure_min_words(self, narration: str, mechanism: str, topic: str, angle: str) -> str:
        text = " ".join(str(narration or "").split()).strip()
        if len(text.split()) >= self.MIN_BODY_WORDS:
            return text

        tails = self._expansion_tails(mechanism, topic, angle)
        used: list[str] = []
        for sentence in tails:
            if len(text.split()) >= self.MIN_BODY_WORDS:
                break
            cleaned = " ".join(sentence.split()).strip()
            if cleaned and cleaned not in used:
                used.append(cleaned)
                text = f"{text} {cleaned}".strip()
        return text

    def _expansion_tails(self, mechanism: str, topic: str, angle: str) -> list[str]:
        common = [
            "The important part is that the viewer can see the money system, not just hear generic advice.",
            "Every rupee has a job before the month starts, and the scene should make that job visible.",
            "That is why the next step is not motivation, it is changing the default path of the money.",
        ]
        tails = {
            "salary_drain": [
                "Notice the order of damage.",
                "The salary enters first, but the fixed costs reach it before savings does.",
                "Rent, EMIs, food, travel, and small convenience spends all behave like automatic claims.",
                "By the time the viewer starts making daily choices, the real battle is already mostly over.",
                "This is why a person can earn a respectable income and still feel broke.",
                "The fix starts by mapping the drain before trying to cut random expenses.",
                "When the drain is visible, the month stops feeling mysterious.",
                *common,
            ],
            "lifestyle_inflation": [
                "The dangerous part is that nothing feels irresponsible in the moment.",
                "A better house feels deserved.",
                "Better food feels normal.",
                "A nicer phone feels like a reward for working hard.",
                "But when every upgrade becomes permanent, the raise stops building freedom.",
                "Income rises on paper while savings stays almost flat in real life.",
                "That gap is the entire story of lifestyle inflation.",
                "The transition is simple: the next raise must be captured before lifestyle negotiates with it.",
                *common,
            ],
            "emi_pressure": [
                "The first EMI does not look dangerous because it feels affordable alone.",
                "The second EMI still looks manageable.",
                "Then the third fixed payment arrives, and suddenly flexibility disappears.",
                "The trap is that each payment was approved separately, but the salary faces them together.",
                "This is why EMI pressure is a cash-flow problem before it becomes a debt problem.",
                "The viewer should see payments stacking before any spending choice begins.",
                "Once fixed payments cross a line, discipline cannot rescue the month by itself.",
                *common,
            ],
            "debt_trap": [
                "The minimum payment is designed to feel emotionally comfortable.",
                "It gives the feeling of progress without attacking the real balance.",
                "Interest keeps working quietly in the background.",
                "That means the borrower can pay every month and still feel stuck.",
                "The visual should make the balance look stubborn while interest keeps adding pressure.",
                "This is the moment where the viewer understands that debt is not only an amount.",
                "It is a machine that charges rent on delay.",
                *common,
            ],
            "inflation_erosion": [
                "Inflation is hard to fear because the bank balance does not visibly fall.",
                "The number on the screen can stay the same while the shopping basket gets smaller.",
                "That is what makes it dangerous.",
                "The viewer should see value shrinking, not just hear a percentage.",
                "A fixed deposit can feel safe and still fail if returns do not beat price rise.",
                "The lesson is not to hate safety.",
                "The lesson is to understand real return after inflation.",
                *common,
            ],
            "sip_growth": [
                "The first few months feel boring because compounding has not had enough time to show off.",
                "That boredom is the test.",
                "The monthly SIP is not supposed to look dramatic on day one.",
                "It is supposed to create a repeatable habit that survives mood, market noise, and salary stress.",
                "Over time, contributions become the base and returns start adding their own returns.",
                "The viewer should see a slow engine becoming powerful because it keeps running.",
                "That is the transition from saving what is left to investing by design.",
                *common,
            ],
            "compounding": [
                "Compounding looks unimpressive when the timeline is short.",
                "That is why people underestimate it.",
                "The early years build the base quietly.",
                "Later, returns begin to earn returns, and the curve bends upward.",
                "The viewer should not see magic.",
                "They should see time doing mechanical work on repeated contributions.",
                "The point is simple: starting early gives the engine more road.",
                *common,
            ],
            "risk_return": [
                "Risk is not a villain by itself.",
                "Unclear risk is the real problem.",
                "A calm product usually gives calmer returns.",
                "A volatile product may create more growth, but it demands emotional strength.",
                "The viewer should see that every return has a price.",
                "Sometimes that price is low growth.",
                "Sometimes that price is market volatility.",
                "The goal is to choose risk deliberately instead of reacting later.",
                *common,
            ],
            "diversification": [
                "One winner can feel genius until it becomes the only thing holding the future.",
                "That is concentration risk.",
                "Diversification is less exciting, but it makes one mistake less powerful.",
                "The viewer should see risk moving from one fragile point into several buckets.",
                "Equity, debt, cash, and emergency money do different jobs.",
                "None of them needs to be the hero in every situation.",
                "The portfolio becomes stronger because every rupee is not exposed to the same shock.",
                *common,
            ],
            "speculation_risk": [
                "FOMO feels like research because everyone is talking about the same opportunity.",
                "But popularity is not a thesis.",
                "When the price rises first and thinking comes later, the viewer is no longer investing.",
                "They are buying emotional relief.",
                "The visual should show excitement turning into a drop, then panic turning into a bad exit.",
                "The lesson is not to avoid markets.",
                "The lesson is to avoid entering without understanding what can go wrong.",
                *common,
            ],
            "emergency_fund": [
                "An emergency fund does not create glamorous returns.",
                "Its job is different.",
                "It protects the plan when life interrupts the spreadsheet.",
                "A medical bill, job delay, or family emergency can force a person into expensive debt.",
                "Cash buffer stops that shock from becoming a credit card problem.",
                "The viewer should see the emergency hitting the system and the buffer absorbing it.",
                "That is why boring money can be the most powerful money in the room.",
                *common,
            ],
        }
        return tails.get(mechanism, [
            f"The topic is {topic or 'money'}, but the scene still needs one concrete mechanism.",
            f"The angle is {angle or 'the hidden money mistake'}, so the example should show a visible before-and-after.",
            "The viewer should see what changes, which number moves, and why that movement matters.",
            "A generic lesson is not enough for this format.",
            "The scene needs a system, a pressure point, and a consequence.",
            "Only then can the next scene build on the same money journey.",
            *common,
        ])
