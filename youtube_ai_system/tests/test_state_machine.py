from youtube_ai_system.services.state_machine import STATE_FLOW


def test_required_transitions_exist():
    assert "script_review" in STATE_FLOW["drafted"]
    assert "assets_ready" in STATE_FLOW["scene_review"]
    assert "scheduled" in STATE_FLOW["ready_to_publish"]


def test_direct_skip_is_not_allowed():
    assert "script_approved" not in STATE_FLOW["drafted"]
    assert "ready_to_publish" not in STATE_FLOW["scene_review"]
