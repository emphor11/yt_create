export type Beat = {
	component: string;
	text: string;
	start_time: number;
	end_time: number;
	emphasis: 'normal' | 'subtle' | 'hero';
	subtext?: string;
	steps?: Array<Record<string, unknown>>;
	props?: Record<string, unknown>;
};

export type Scene = {
	id?: string;
	scene_id?: string;
	concept?: string;
	pattern: string;
	data?: Record<string, unknown>;
	beats: Beat[];
	duration?: number;
	total_duration?: number;
	audio_file: string;
};

export type VideoSpec = {
	scenes: Scene[];
};
