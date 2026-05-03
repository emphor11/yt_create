export type Beat = {
	component: string;
	text: string;
	start_time: number;
	end_time: number;
	emphasis: 'normal' | 'subtle' | 'hero';
	subtext?: string;
	steps?: Array<Record<string, unknown>>;
	props?: Record<string, unknown>;
	data?: Record<string, unknown>;
	source_text?: string;
	sentence_index?: number;
};

export type Scene = {
	id?: string;
	scene_id?: string;
	concept?: string;
	concept_type?: string;
	visual_mode?: string;
	cinematic_intent?: Record<string, unknown>;
	visual_story?: Record<string, unknown>;
	story_state?: Record<string, unknown>;
	pattern: string;
	data?: Record<string, unknown>;
	direction?: Record<string, unknown> | null;
	theme?: Record<string, string>;
	beats: Beat[];
	duration?: number;
	total_duration?: number;
	audio_file: string;
};

export type VideoSpec = {
	scenes: Scene[];
};
