"""Subprocess adapter for Remotion CLI execution."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class RemotionCommandTimeout(RuntimeError):
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout
        super().__init__(f"Remotion command timed out after {timeout}s.")


class RemotionCommandUnavailable(RuntimeError):
    pass


class RemotionCommandFailed(RuntimeError):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class RemotionExecutor:
    def which(self, binary_name: str) -> str | None:
        return shutil.which(binary_name)

    def run(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
    ) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                command,
                cwd=cwd,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RemotionCommandTimeout(timeout) from exc
        except FileNotFoundError as exc:
            raise RemotionCommandUnavailable("Remotion CLI is not installed. Run npm install in your Remotion project.") from exc
        except subprocess.CalledProcessError as exc:
            raise RemotionCommandFailed(self.error_detail(exc)) from exc

    def error_detail(self, exc: subprocess.CalledProcessError) -> str:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        if len(detail) > 800:
            detail = detail[:800].rstrip() + "...[truncated]"
        return detail
