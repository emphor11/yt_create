from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

import requests


class BrollAssetProvider:
    """Finds and caches external b-roll assets for legacy media generation."""

    def __init__(
        self,
        *,
        groq_json: Callable[[str, str, str], dict],
        logger: Any,
        request_get: Callable[..., Any] = requests.get,
    ) -> None:
        self.groq_json = groq_json
        self.logger = logger
        self.request_get = request_get

    def simplify_query(self, visual_instruction: str) -> str:
        try:
            result = self.groq_json(
                "You return only a short search query, nothing else.",
                (
                    "Convert this visual instruction into a simple 2-4 word Pexels stock "
                    "footage search query that will return good results.\n\n"
                    "Rules for the query:\n"
                    "- Use generic English words, not location-specific\n"
                    "- Pexels has: people, cities, offices, money, technology, nature, "
                    "food, transportation, business, finance\n"
                    "- Pexels does NOT have: specific Indian text, rupee signs, "
                    "niche financial scenarios\n"
                    "- Prefer the emotional or physical scene over the conceptual meaning\n"
                    "- Return valid JSON with a single field 'query' containing only the search query\n\n"
                    "Examples:\n"
                    "'Indian city streets with rent signs' → 'apartment building city'\n"
                    "'person checking stock market on phone' → 'person phone trading'\n"
                    "'luxury shopping mall lifestyle inflation' → 'shopping mall luxury'\n"
                    "'₹1.2 lakh credit card debt stress' → 'credit card stress person'\n"
                    "'Indian stock market footage' → 'stock market trading floor'\n"
                    "'Wall Street financial analysts working' → 'business analysts office'\n\n"
                    f"Instruction: {visual_instruction}"
                ),
                "broll_query_simplification",
            )
            return str(result.get("query", "")).strip() or "business finance office"
        except RuntimeError:
            words = re.findall(r"[a-zA-Z]+", visual_instruction.lower())
            stop = {"the", "a", "an", "of", "in", "on", "for", "with", "and", "or", "is", "are", "to", "from"}
            filtered = [w for w in words if w not in stop][:4]
            return " ".join(filtered) or "business finance"

    def pexels_broll(
        self,
        config: dict,
        project_id: int,
        scene_order: int,
        query: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        simplified_query = self.simplify_query(query)
        self.logger.log(
            "visual_generation",
            "running",
            f"Pexels search for scene {scene_order}: original='{query[:60]}' → simplified='{simplified_query}'",
            project_id,
        )

        cache_root = Path(config["STORAGE_ROOT"]) / "cache" / "pexels"
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_key = hashlib.sha1(simplified_query.lower().encode("utf-8")).hexdigest()
        cache_path = cache_root / f"{cache_key}.json"
        result = self.load_pexels_cache(cache_path)
        if result is None:
            result = self.fetch_pexels_result(config, simplified_query, target_duration)
            cache_path.write_text(json.dumps(result), encoding="utf-8")

        download_url = result["download_url"]
        output_path = self.broll_source_path(config, project_id, "pexels", scene_order)
        if not output_path.exists():
            response = self.request_get(
                download_url,
                timeout=config["PEXELS_API_TIMEOUT"],
                stream=True,
            )
            response.raise_for_status()
            with output_path.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        output_file.write(chunk)
        return output_path, "pexels_video"

    def load_pexels_cache(self, cache_path: Path) -> dict[str, str] | None:
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if payload.get("download_url"):
            return payload
        return None

    def fetch_pexels_result(self, config: dict, query: str, target_duration: float) -> dict[str, str]:
        response = self.request_get(
            "https://api.pexels.com/videos/search",
            params={
                "query": query,
                "per_page": config.get("PEXELS_SEARCH_LIMIT", 10),
                "orientation": "landscape",
            },
            headers={"Authorization": config["PEXELS_API_KEY"]},
            timeout=config["PEXELS_API_TIMEOUT"],
        )
        response.raise_for_status()
        payload = response.json()
        videos = payload.get("videos", [])
        if not videos:
            raise RuntimeError(f"Pexels returned no videos for query: '{query}'")

        matching_video = None
        for video in videos:
            vid_duration = float(video.get("duration") or 0)
            if 10 <= vid_duration <= 30:
                matching_video = video
                break
        if matching_video is None:
            for video in videos:
                if float(video.get("duration") or 0) >= target_duration:
                    matching_video = video
                    break
        if matching_video is None:
            matching_video = videos[0]

        video_files = matching_video.get("video_files", [])
        if not video_files:
            raise RuntimeError("Pexels did not include downloadable files.")

        best_file = next(
            (
                file_info
                for file_info in video_files
                if file_info.get("quality") == "hd" and file_info.get("link")
            ),
            None,
        )
        if best_file is None:
            best_file = next(
                (
                    file_info
                    for file_info in video_files
                    if file_info.get("quality") == "sd" and file_info.get("link")
                ),
                None,
            )
        if best_file is None:
            best_file = next(
                (file_info for file_info in video_files if file_info.get("link")),
                None,
            )
        if best_file is None:
            raise RuntimeError("Pexels did not include a usable download link.")

        return {
            "query": query,
            "video_id": str(matching_video.get("id", "")),
            "duration": str(matching_video.get("duration", "")),
            "download_url": best_file["link"],
        }

    def pixabay_broll(
        self,
        config: dict,
        project_id: int,
        scene_order: int,
        query: str,
        target_duration: float,
    ) -> tuple[Path, str]:
        simplified_query = self.simplify_query(query)
        api_key = config.get("PIXABAY_API_KEY")
        if not api_key:
            raise RuntimeError("PIXABAY_API_KEY is not configured for fallback.")

        self.logger.log(
            "visual_generation",
            "running",
            f"Pixabay fallback search for scene {scene_order}: '{simplified_query}'",
            project_id,
        )

        response = self.request_get(
            "https://pixabay.com/api/videos/",
            params={
                "key": api_key,
                "q": simplified_query,
                "per_page": 10,
            },
            timeout=config.get("PEXELS_API_TIMEOUT", 15),
        )
        response.raise_for_status()
        payload = response.json()
        hits = payload.get("hits", [])
        if not hits:
            raise RuntimeError(f"Pixabay returned no videos for query: '{simplified_query}'")

        video_data = hits[0]
        video_urls = video_data.get("videos", {})
        download_info = video_urls.get("small") or video_urls.get("tiny") or video_urls.get("medium") or {}
        download_url = download_info.get("url")
        if not download_url:
            raise RuntimeError("Pixabay did not include a usable download link.")

        output_path = self.broll_source_path(config, project_id, "pixabay", scene_order)
        if not output_path.exists():
            dl_response = self.request_get(download_url, timeout=30, stream=True)
            dl_response.raise_for_status()
            with output_path.open("wb") as f:
                for chunk in dl_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        self.logger.log(
            "visual_generation",
            "completed",
            f"Pixabay fallback used for scene {scene_order}.",
            project_id,
        )
        return output_path, "pixabay_video"

    def broll_source_path(self, config: dict, project_id: int, provider: str, scene_order: int) -> Path:
        source_root = Path(config["STORAGE_ROOT"]) / "downloads" / "broll" / str(project_id)
        source_root.mkdir(parents=True, exist_ok=True)
        return source_root / f"{provider}-scene-{scene_order:02d}.mp4"
