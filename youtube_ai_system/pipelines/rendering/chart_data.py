from __future__ import annotations

import re


class RenderChartDataExtractor:
    """Extracts simple chart data points from render instructions."""

    def extract_data_points(self, text: str) -> list[dict[str, float | str]]:
        data_section = self.extract_data_section(text)
        pairs = re.findall(r"([^=,;:]+?)\s*=\s*₹?\s*([\d,.]+)", data_section)
        if pairs:
            return [
                {"label": label.strip(), "value": float(value.replace(",", ""))}
                for label, value in pairs[:6]
            ]
        pairs = re.findall(r"([A-Za-z]{3,9}\s?\d{0,4}|\d{4})\D{0,12}(\d+(?:\.\d+)?)", text)
        data = [{"label": label.strip(), "value": float(value)} for label, value in pairs[:6]]
        if len(data) >= 2:
            return data
        numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", text)[:5]]
        if len(numbers) >= 2:
            return [{"label": f"Point {idx}", "value": value} for idx, value in enumerate(numbers, start=1)]
        return []

    def extract_data_section(self, text: str) -> str:
        match = re.search(r"data\s*:\s*(.*?)(?:,\s*(?:title|color|unit|insight)\s*:|$)", text, re.I)
        return match.group(1) if match else text
