from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..application.use_cases import BuildAnalyticsTableUseCase, CaptureAnalyticsSnapshotUseCase

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics")
def analytics_table():
    return render_template("analytics/table.html", **BuildAnalyticsTableUseCase().execute().data)


@analytics_bp.route("/projects/<int:project_id>/analytics/capture", methods=["POST"])
def capture_snapshot(project_id: int):
    result = CaptureAnalyticsSnapshotUseCase().execute(project_id, request.form.get("snapshot_day", ""))
    flash(result.message, "success")
    return redirect(url_for("analytics.analytics_table"))
