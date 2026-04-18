from ..models.repository import ProjectRepository


class RunLogger:
    def __init__(self) -> None:
        self.repo = ProjectRepository()

    def log(self, stage_name: str, status: str, message: str, project_id: int | None = None) -> None:
        self.repo.add_run_log(
            stage_name=stage_name,
            status=status,
            message=message,
            project_id=project_id,
        )
