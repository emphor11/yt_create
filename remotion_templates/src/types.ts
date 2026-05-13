export type Shot = {
	shot_type?: string;
	focus_target?: string;
	framing_profile?: string;
	composition_emphasis?: string;
	attention_weight?: number;
	start_frame?: number;
	end_frame?: number;
	composition_window?: {
		start_frame?: number;
		end_frame?: number;
	};
	derived_from_action?: string;
	derived_from_state?: string;
	component?: string;
	overlap_group?: string;
	source_beat_indices?: number[];
	source_action_ids?: string[];
	shot_index?: number;
};

export type Beat = {
	component: string;
	text: string;
	start_time: number;
	end_time: number;
	emphasis: 'normal' | 'subtle' | 'hero';
	beat_role?: 'introduce' | 'process' | 'change' | 'result' | 'punch' | string;
	beat_phase?: string;
	subtext?: string;
	steps?: Array<Record<string, unknown>>;
	props?: Record<string, unknown>;
	data?: Record<string, unknown>;
	active_shot?: Shot;
	source_text?: string;
	sentence_index?: number;
};

export type CinematicEvent = {
	id?: string;
	sentence_index?: number;
	text?: string;
	entity_id?: string;
	label?: string;
	role?: string;
	action?: string;
	visual_verb?: string;
	visual_mode?: string;
	variant?: string;
	start_progress?: number;
	end_progress?: number;
	gravity?: {
		x?: number;
		y?: number;
	};
	attention_weight?: number;
	decay_after?: number;
};

export type Scene = {
	id?: string;
	scene_id?: string;
	narration?: string;
	text?: string;
	concept?: string;
	concept_type?: string;
	visual_mode?: string;
	cinematic_intent?: Record<string, unknown>;
	visual_story?: Record<string, unknown>;
	story_state?: Record<string, unknown>;
	cinematic_events?: CinematicEvent[];
	pattern: string;
	data?: Record<string, unknown>;
	direction?: Record<string, unknown> | null;
	theme?: Record<string, string>;
	beats: Beat[];
	shot_sequence?: {
		source?: string;
		shots?: Shot[];
		shot_count?: number;
		fps?: number;
	};
	duration?: number;
	total_duration?: number;
	audio_file: string;
};

export type VideoSpec = {
	scenes: Scene[];
};
