import React from 'react';
import {AbsoluteFill, interpolate, spring, useVideoConfig} from 'remotion';
import {BODY_FONT_FAMILY, DISPLAY_FONT_FAMILY, FONT_FACES} from '../fonts';
import {BeatComponentProps} from './types';
import {COLORS, formatIndianRupee, SPACING, TYPE_SCALE} from './visualUtils';

type Intent = {
	visual_mode?: string;
	human_action?: string;
	metaphor?: string;
	overlay_text?: string;
	motion_treatment?: string;
	asset_query?: string;
	texture?: string;
};

type StoryState = {
	scene_role?: string;
	protagonist_state?: string;
	active_objects?: string[];
	state_change?: {
		money?: {from?: string; to?: string; change_label?: string};
		emotion?: {from?: string; to?: string};
		risk?: {from?: string; to?: string};
	};
	callback_from?: string | null;
	callback_to?: string | null;
	visual_question?: string;
	visual_answer?: string;
};

type VisualStory = {
	goal?: {
		label?: string;
		target_amount?: string;
		desired_outcome?: string;
	};
	protagonist?: {
		role?: string;
		visual_id?: string;
		emotional_state?: string;
	};
};

const intentFromScene = (scene: BeatComponentProps['scene']): Intent =>
	(scene?.cinematic_intent ?? {}) as Intent;

const storyStateFromScene = (scene: BeatComponentProps['scene']): StoryState =>
	(scene?.story_state ?? {}) as StoryState;

const visualStoryFromScene = (scene: BeatComponentProps['scene']): VisualStory =>
	(scene?.visual_story ?? {}) as VisualStory;

const activeObjects = (storyState: StoryState): string[] =>
	Array.isArray(storyState.active_objects)
		? storyState.active_objects.map((item) => String(item))
		: [];

const accentForIntent = (intent: Intent): string => {
	const joined = `${intent.motion_treatment ?? ''} ${intent.metaphor ?? ''}`.toLowerCase();
	if (joined.includes('erosion') || joined.includes('debt') || joined.includes('panic') || joined.includes('leak')) {
		return COLORS.danger;
	}
	if (joined.includes('compound') || joined.includes('growth') || joined.includes('calm')) {
		return COLORS.positive;
	}
	return COLORS.warning;
};

const accentForStory = (intent: Intent, storyState: StoryState): string => {
	const joined = `${storyState.protagonist_state ?? ''} ${storyState.scene_role ?? ''} ${storyState.state_change?.risk?.to ?? ''} ${activeObjects(storyState).join(' ')}`.toLowerCase();
	if (joined.includes('stressed') || joined.includes('pressure') || joined.includes('debt') || joined.includes('emi')) {
		return COLORS.danger;
	}
	if (joined.includes('disciplined') || joined.includes('confident') || joined.includes('sip') || joined.includes('portfolio') || joined.includes('buffer')) {
		return COLORS.positive;
	}
	if (joined.includes('aware') || joined.includes('mechanism')) {
		return COLORS.neutral;
	}
	return accentForIntent(intent);
};

const humanizeToken = (value: string): string =>
	value
		.replace(/_/g, ' ')
		.replace(/\b\w/g, (char) => char.toUpperCase())
		.trim();

const weakObjectText: Record<string, string> = {
	'phone account': 'Money hits the account',
	'salary balance': 'Balance starts moving',
	'emi stack': 'Fixed payments stack',
	'debt pressure': 'Pressure becomes visible',
	'inflation basket': 'Buying power shrinks',
	'sip jar': 'System starts growing',
	'portfolio grid': 'Risk gets spread',
	'emergency buffer': 'One shock gets absorbed',
};

const cleanTitle = (text: string): string => {
	const normalized = text.replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
	return weakObjectText[normalized.toLowerCase()] ?? normalized;
};

const storyTitle = (beat: BeatComponentProps['beat'], intent: Intent, storyState: StoryState): string => {
	const answer = String(storyState.visual_answer ?? '').trim();
	const overlay = String(intent.overlay_text ?? '').trim();
	const raw = String(beat.text ?? '').trim();
	const change = String(storyState.state_change?.money?.change_label ?? '').trim();
	const question = String(storyState.visual_question ?? '').trim();
	if (beat.emphasis === 'hero') {
		return cleanTitle(answer || overlay || change || raw || question);
	}
	return cleanTitle(raw || change || overlay || answer || question);
};

const storySubtitle = (beat: BeatComponentProps['beat'], intent: Intent, storyState: StoryState, story: VisualStory): string => {
	const change = storyState.state_change?.money?.change_label;
	const question = storyState.visual_question;
	const role = storyState.scene_role ? humanizeToken(storyState.scene_role) : '';
	const goal = story.goal?.label;
	const metaphor = intent.metaphor;
	if (beat.emphasis === 'hero') {
		return String(change || question || goal || metaphor || '').trim();
	}
	return String(question || change || role || metaphor || '').trim();
};

export const CinematicScene: React.FC<BeatComponentProps> = ({
	beat,
	scene,
	frameWithinBeat,
	durationFrames,
}) => {
	const {fps} = useVideoConfig();
	const intent = intentFromScene(scene);
	const storyState = storyStateFromScene(scene);
	const story = visualStoryFromScene(scene);
	const treatment = String(intent.motion_treatment ?? 'slow_push');
	const accent = accentForStory(intent, storyState);
	const reveal = spring({
		frame: Math.min(frameWithinBeat, 18),
		fps,
		config: {damping: 18, stiffness: 170, mass: 0.9},
		durationInFrames: 18,
	});
	const progress = interpolate(frameWithinBeat, [0, Math.max(durationFrames - 1, 1)], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
	});
	const title = storyTitle(beat, intent, storyState).toUpperCase();
	const subtitle = storySubtitle(beat, intent, storyState, story).toUpperCase();

	return (
		<AbsoluteFill style={{backgroundColor: COLORS.bg_deep, color: COLORS.text_primary, overflow: 'hidden'}}>
			<style>{FONT_FACES}</style>
			<CinematicBackground progress={progress} accent={accent} treatment={treatment} />
			<CinematicObject progress={progress} accent={accent} treatment={treatment} intent={intent} storyState={storyState} story={story} />
			<div
				style={{
					position: 'absolute',
					left: SPACING.safe,
					right: SPACING.safe,
					bottom: 116,
					borderLeft: `8px solid ${accent}`,
					paddingLeft: SPACING.xl,
					opacity: interpolate(frameWithinBeat, [0, 12], [0, 1], {
						extrapolateLeft: 'clamp',
						extrapolateRight: 'clamp',
					}),
					transform: `translateY(${(1 - reveal) * 26}px)`,
				}}
			>
				<div
					style={{
						fontFamily: DISPLAY_FONT_FAMILY,
						fontSize: beat.emphasis === 'hero' ? TYPE_SCALE.hero_value.size : TYPE_SCALE.major_value.size,
						lineHeight: 0.9,
						maxWidth: 1180,
						textTransform: 'uppercase',
					}}
				>
					{title}
				</div>
				{subtitle ? (
					<div
						style={{
							marginTop: SPACING.lg,
							fontFamily: BODY_FONT_FAMILY,
							fontSize: TYPE_SCALE.subtext.size,
							fontWeight: 800,
							color: COLORS.text_secondary,
							maxWidth: 980,
						}}
					>
						{subtitle}
					</div>
				) : null}
			</div>
			<FilmGrain />
		</AbsoluteFill>
	);
};

const CinematicBackground: React.FC<{progress: number; accent: string; treatment: string}> = ({
	progress,
	accent,
	treatment,
}) => {
	const push = treatment === 'dolly_zoom' ? progress * 48 : progress * 24;
	return (
		<AbsoluteFill>
			<div
				style={{
					position: 'absolute',
					inset: -80,
					background: `radial-gradient(circle at ${30 + progress * 18}% 35%, ${accent}33, transparent 28%), linear-gradient(120deg, #090912, #111422 55%, #07070d)`,
					transform: `scale(${1.03 + progress * 0.04}) translateX(${-push}px)`,
				}}
			/>
			<div
				style={{
					position: 'absolute',
					inset: 0,
					background: 'linear-gradient(90deg, rgba(0,0,0,0.72), rgba(0,0,0,0.18) 52%, rgba(0,0,0,0.72))',
				}}
			/>
		</AbsoluteFill>
	);
};

const CinematicObject: React.FC<{
	progress: number;
	accent: string;
	treatment: string;
	intent: Intent;
	storyState: StoryState;
	story: VisualStory;
}> = ({
	progress,
	accent,
	treatment,
	intent,
	storyState,
	story,
}) => {
	const objects = activeObjects(storyState);
	if (objects.includes('emi_stack')) {
		return <NotificationStack progress={progress} accent={accent} labels={notificationLabels(storyState, 'emi_stack')} />;
	}
	if (objects.includes('emergency_buffer')) {
		return <EmergencyBuffer progress={progress} accent={accent} storyState={storyState} />;
	}
	if (objects.includes('sip_jar')) {
		return <SIPJar progress={progress} accent={accent} storyState={storyState} />;
	}
	if (objects.includes('portfolio_grid')) {
		return <PortfolioGrid progress={progress} accent={accent} />;
	}
	if (objects.includes('inflation_basket')) {
		return <ValueErosion progress={progress} accent={accent} />;
	}
	if (objects.includes('debt_pressure')) {
		return <DebtPressure progress={progress} accent={accent} storyState={storyState} />;
	}
	if (objects.includes('phone_account') || objects.includes('salary_balance')) {
		return <AccountPanel progress={progress} accent={accent} storyState={storyState} story={story} />;
	}
	if (treatment === 'notification_stack') {
		return <NotificationStack progress={progress} accent={accent} labels={notificationLabels(storyState, 'salary')} />;
	}
	if (treatment === 'value_erosion') {
		return <ValueErosion progress={progress} accent={accent} />;
	}
	if (String(intent.metaphor ?? '').toLowerCase().includes('portfolio')) {
		return <PortfolioGrid progress={progress} accent={accent} />;
	}
	return <PhoneSilhouette progress={progress} accent={accent} />;
};

const notificationLabels = (storyState: StoryState, mode: 'emi_stack' | 'salary'): string[] => {
	if (mode === 'emi_stack') {
		return ['SALARY CREDIT', 'EMI AUTO-DEBIT', 'RENT PAID', 'CASH LEFT SHRINKS'];
	}
	const money = storyState.state_change?.money;
	return [
		money?.from ? `${money.from} CREDITED` : 'SALARY CREDIT',
		'EXPENSES START',
		money?.change_label ? money.change_label.toUpperCase() : 'BALANCE CHANGES',
		money?.to ? `${money.to} LEFT` : 'DAY 20 CHECK',
	];
};

const PhoneSilhouette: React.FC<{progress: number; accent: string}> = ({progress, accent}) => (
	<div
		style={{
			position: 'absolute',
			right: 190,
			top: 120,
			width: 390,
			height: 700,
			borderRadius: 52,
			border: `3px solid ${accent}88`,
			background: 'rgba(255,255,255,0.045)',
			boxShadow: `0 0 80px ${accent}33`,
			transform: `rotate(-7deg) translateY(${progress * -28}px)`,
		}}
	>
		<div style={{position: 'absolute', left: 50, right: 50, top: 80, height: 28, borderRadius: 99, background: `${accent}99`}} />
		{[0, 1, 2].map((index) => (
			<div
				key={index}
				style={{
					position: 'absolute',
					left: 44,
					right: 44,
					top: 170 + index * 120,
					height: 72,
					borderRadius: 18,
					background: 'rgba(255,255,255,0.08)',
					border: '1px solid rgba(255,255,255,0.16)',
				}}
			/>
		))}
	</div>
);

const NotificationStack: React.FC<{progress: number; accent: string; labels: string[]}> = ({progress, accent, labels}) => (
	<div style={{position: 'absolute', right: 160, top: 170, width: 620}}>
		{labels.map((label, index) => {
			const local = Math.max(0, Math.min((progress * 5 - index) / 1.2, 1));
			return (
				<div
					key={label}
					style={{
						marginBottom: 24,
						height: 92,
						borderRadius: 18,
						padding: '22px 30px',
						background: index === 0 ? 'rgba(46,196,182,0.18)' : 'rgba(255,255,255,0.08)',
						border: `2px solid ${index === 0 ? COLORS.positive : accent}`,
						fontFamily: BODY_FONT_FAMILY,
						fontSize: 28,
						fontWeight: 900,
						letterSpacing: 0,
						opacity: local,
						transform: `translateX(${(1 - local) * 130}px)`,
					}}
				>
					{label}
				</div>
			);
		})}
	</div>
);

const AccountPanel: React.FC<{progress: number; accent: string; storyState: StoryState; story: VisualStory}> = ({
	progress,
	accent,
	storyState,
	story,
}) => {
	const money = storyState.state_change?.money ?? {};
	const from = money.from || story.goal?.target_amount || '₹50,000';
	const to = money.to || 'DAY 20';
	const change = money.change_label || 'salary balance changes';
	const activeObjects = storyState.active_objects ?? [];
	const label = activeObjects.includes('salary_balance') ? 'SALARY IN' : activeObjects.includes('debt_pressure') ? 'OUTSTANDING' : 'BALANCE';
	return (
		<div
			style={{
				position: 'absolute',
				right: 150,
				top: 125,
				width: 640,
				height: 520,
				borderRadius: 36,
				border: `2px solid ${accent}88`,
				background: 'linear-gradient(145deg, rgba(255,255,255,0.11), rgba(255,255,255,0.035))',
				boxShadow: `0 0 90px ${accent}25`,
				transform: `translateY(${progress * -26}px) rotate(-2deg)`,
				padding: 42,
				fontFamily: BODY_FONT_FAMILY,
			}}
		>
			<div style={{color: COLORS.text_secondary, fontSize: 24, fontWeight: 900, letterSpacing: 0}}>{label}</div>
			<div style={{marginTop: 34, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 88, lineHeight: 0.9}}>{from}</div>
			<div style={{marginTop: 24, height: 16, borderRadius: 99, background: COLORS.stroke, overflow: 'hidden'}}>
				<div
					style={{
						width: `${Math.max(14, 100 - progress * 72)}%`,
						height: '100%',
						background: accent,
						boxShadow: `0 0 36px ${accent}`,
					}}
				/>
			</div>
			<div
				style={{
					marginTop: 36,
					display: 'flex',
					justifyContent: 'space-between',
					alignItems: 'flex-end',
					gap: 24,
				}}
			>
				<div style={{fontSize: 28, fontWeight: 900, color: COLORS.text_secondary, maxWidth: 360}}>
					{change.toUpperCase()}
				</div>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 56, color: accent}}>{to}</div>
			</div>
		</div>
	);
};

const DebtPressure: React.FC<{progress: number; accent: string; storyState: StoryState}> = ({
	progress,
	accent,
	storyState,
}) => {
	const label = storyState.state_change?.risk?.to || storyState.state_change?.money?.change_label || 'pressure builds';
	return (
		<div style={{position: 'absolute', right: 160, top: 150, width: 580, height: 500}}>
			{[0, 1, 2].map((index) => (
				<div
					key={index}
					style={{
						position: 'absolute',
						inset: 58 - index * 28 + progress * 24,
						borderRadius: 38,
						border: `3px solid ${accent}${index === 0 ? 'aa' : '55'}`,
						opacity: Math.max(0.2, 1 - index * 0.2),
					}}
				/>
			))}
			<div
				style={{
					position: 'absolute',
					left: 82,
					right: 82,
					top: 145,
					height: 220,
					borderRadius: 28,
					background: 'rgba(230,57,70,0.14)',
					border: `2px solid ${accent}`,
					padding: 32,
					fontFamily: BODY_FONT_FAMILY,
					fontSize: 32,
					fontWeight: 900,
					textTransform: 'uppercase',
				}}
			>
				<div style={{fontFamily: DISPLAY_FONT_FAMILY, fontSize: 68}}>DEBT</div>
				<div style={{color: COLORS.text_secondary}}>{label}</div>
			</div>
		</div>
	);
};

const SIPJar: React.FC<{progress: number; accent: string; storyState: StoryState}> = ({
	progress,
	accent,
	storyState,
}) => {
	const money = storyState.state_change?.money;
	return (
		<div style={{position: 'absolute', right: 170, top: 130, width: 560, height: 560}}>
			<div
				style={{
					position: 'absolute',
					left: 142,
					right: 142,
					bottom: 30,
					height: 390,
					borderRadius: '34px 34px 70px 70px',
					border: `4px solid ${accent}`,
					overflow: 'hidden',
					background: 'rgba(255,255,255,0.045)',
					boxShadow: `0 0 76px ${accent}28`,
				}}
			>
				<div
					style={{
						position: 'absolute',
						left: 0,
						right: 0,
						bottom: 0,
						height: `${22 + progress * 68}%`,
						background: `linear-gradient(0deg, ${accent}dd, ${accent}55)`,
					}}
				/>
			</div>
			{Array.from({length: 9}).map((_, index) => {
				const local = Math.max(0, Math.min(progress * 9 - index, 1));
				return (
					<div
						key={index}
						style={{
							position: 'absolute',
							left: 135 + (index % 3) * 84,
							top: 32 + Math.floor(index / 3) * 48 + local * 270,
							width: 58,
							height: 58,
							borderRadius: 99,
							background: `${accent}${local > 0.4 ? 'dd' : '66'}`,
							opacity: local,
							boxShadow: `0 0 32px ${accent}55`,
						}}
					/>
				);
			})}
			<div style={{position: 'absolute', left: 0, bottom: 0, fontFamily: BODY_FONT_FAMILY, fontSize: 28, fontWeight: 900}}>
				{(money?.from || '₹5,000').toUpperCase()} MONTHLY
				<div style={{color: accent, fontFamily: DISPLAY_FONT_FAMILY, fontSize: 58}}>
					{(money?.to || formatIndianRupee(5000000)).toUpperCase()}
				</div>
			</div>
		</div>
	);
};

const EmergencyBuffer: React.FC<{progress: number; accent: string; storyState: StoryState}> = ({
	progress,
	accent,
	storyState,
}) => (
	<div style={{position: 'absolute', right: 140, top: 130, width: 620, height: 520}}>
		<div
			style={{
				position: 'absolute',
				left: 40,
				top: 120,
				width: 250,
				height: 300,
				borderRadius: 28,
				border: `2px solid ${COLORS.danger}`,
				background: 'rgba(230,57,70,0.11)',
				transform: `translateX(${progress * 70}px) rotate(-8deg)`,
				fontFamily: BODY_FONT_FAMILY,
				fontSize: 30,
				fontWeight: 900,
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'center',
				textAlign: 'center',
				padding: 28,
			}}
		>
			UNEXPECTED BILL
		</div>
		<div
			style={{
				position: 'absolute',
				right: 70,
				top: 70,
				width: 280,
				height: 360,
				borderRadius: '140px 140px 54px 54px',
				border: `5px solid ${accent}`,
				background: 'rgba(46,196,182,0.12)',
				boxShadow: `0 0 90px ${accent}33`,
				transform: `scale(${0.92 + progress * 0.08})`,
				fontFamily: DISPLAY_FONT_FAMILY,
				fontSize: 62,
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'center',
				textAlign: 'center',
			}}
		>
			BUFFER
		</div>
		<div
			style={{
				position: 'absolute',
				left: 70,
				right: 40,
				bottom: 16,
				fontFamily: BODY_FONT_FAMILY,
				fontSize: 28,
				fontWeight: 900,
				color: COLORS.text_secondary,
				textTransform: 'uppercase',
			}}
		>
			{storyState.state_change?.risk?.to || 'shock becomes planned'}
		</div>
	</div>
);

const ValueErosion: React.FC<{progress: number; accent: string}> = ({progress, accent}) => (
	<div style={{position: 'absolute', right: 130, top: 180, width: 680, height: 440}}>
		<div style={{position: 'absolute', left: 0, bottom: 60, width: 620, height: 4, background: COLORS.stroke}} />
		<div
			style={{
				position: 'absolute',
				left: 0,
				top: 70 + progress * 210,
				width: 560 * progress,
				height: 14,
				background: accent,
				transform: 'rotate(18deg)',
				transformOrigin: 'left center',
				boxShadow: `0 0 50px ${accent}`,
			}}
		/>
		<div
			style={{
				position: 'absolute',
				right: 40,
				bottom: 86,
				width: 210,
				height: 210 - progress * 90,
				border: `3px solid ${accent}`,
				background: 'rgba(255,255,255,0.055)',
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'center',
				fontFamily: DISPLAY_FONT_FAMILY,
				fontSize: 46,
			}}
		>
			BASKET
		</div>
	</div>
);

const PortfolioGrid: React.FC<{progress: number; accent: string}> = ({progress, accent}) => (
	<div style={{position: 'absolute', right: 160, top: 170, width: 560, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 22}}>
		{Array.from({length: 9}).map((_, index) => {
			const local = Math.max(0.18, Math.min((progress * 10 - index) / 2, 1));
			return (
				<div
					key={index}
					style={{
						height: 130,
						borderRadius: 16,
						background: `rgba(255,255,255,${0.04 + local * 0.08})`,
						border: `2px solid ${index === 4 ? accent : COLORS.stroke}`,
						opacity: local,
					}}
				/>
			);
		})}
	</div>
);

const FilmGrain: React.FC = () => (
	<AbsoluteFill
		style={{
			pointerEvents: 'none',
			opacity: 0.13,
			backgroundImage:
				'radial-gradient(rgba(255,255,255,0.18) 0.8px, transparent 0.8px), radial-gradient(rgba(255,255,255,0.10) 0.8px, transparent 0.8px)',
			backgroundPosition: '0 0, 13px 17px',
			backgroundSize: '28px 28px',
			mixBlendMode: 'screen',
		}}
	/>
);
