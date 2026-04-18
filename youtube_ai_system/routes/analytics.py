from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models.repository import ProjectRepository
from ..services.analytics_service import AnalyticsService

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics")
def analytics_table():
    rows = ProjectRepository().list_analytics_rows()
    return render_template("analytics/table.html", rows=rows)


@analytics_bp.route("/projects/<int:project_id>/analytics/capture", methods=["POST"])
def capture_snapshot(project_id: int):
    snapshot_day = request.form.get("snapshot_day", "").strip() or "D1"
    AnalyticsService().capture_snapshot(project_id, snapshot_day)
    flash(f"Captured {snapshot_day} analytics snapshot.", "success")
    return redirect(url_for("analytics.analytics_table"))
