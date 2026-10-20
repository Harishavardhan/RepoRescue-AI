"""RepoRescue AI backend: inspect public GitHub repositories and explain fixes."""

from __future__ import annotations

import json
import os
import re
from enum import Enum
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator


GITHUB_REPOSITORY = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")
LOCKFILES = {
    "requirements.txt", "requirements-dev.txt", "poetry.lock", "Pipfile.lock",
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
    "go.sum", "Cargo.lock", "Gemfile.lock", "composer.lock", "mix.lock",
}
TEST_MARKERS = ("test", "tests", "spec", "__tests__")


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class InspectRequest(BaseModel):
    github_url: str = Field(description="HTTPS URL for a public GitHub repository")
    demo: bool = False

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        normalized = value.strip()
        if not GITHUB_REPOSITORY.fullmatch(normalized):
            raise ValueError("Use a public GitHub URL such as https://github.com/owner/repository")
        return normalized.rstrip("/")


class Finding(BaseModel):
    key: str
    severity: Severity
    title: str
    explanation: str
    fix: str


class RepositorySummary(BaseModel):
    owner: str
    name: str
    default_branch: str | None = None
    description: str | None = None
    file_count: int


class InspectionResponse(BaseModel):
    repository: RepositorySummary
    demo: bool
    findings: list[Finding]
    inspected_files: list[str]


app = FastAPI(title="RepoRescue AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _finding(key: str, severity: Severity, title: str, explanation: str, fix: str) -> Finding:
    return Finding(key=key, severity=severity, title=title, explanation=explanation, fix=fix)


def demo_inspection() -> InspectionResponse:
    """Return stable sample output so the frontend can be developed without GitHub access."""
    files = ["README.md", "pyproject.toml", "src/app.py", "tests/test_app.py", ".env.example"]
    return InspectionResponse(
        repository=RepositorySummary(owner="demo", name="reporescue-sample", default_branch="main", description="Demo repository", file_count=len(files)),
        demo=True,
        inspected_files=files,
        findings=[
            _finding("missing-lockfile", Severity.high, "Dependencies are not locked", "The project has a pyproject.toml but no dependency lockfile was found, so installs can drift between environments.", "Commit a generated lockfile (for example poetry.lock or uv.lock) and use it in CI and deployments."),
            _finding("runtime-unpinned", Severity.medium, "Runtime version is not pinned", "No runtime version marker was detected, which can produce different behavior across developer machines and CI.", "Add a .python-version, runtime.txt, or tool configuration with the supported Python version."),
            _finding("dockerfile-missing", Severity.low, "No Dockerfile found", "The repository does not document a reproducible container build.", "Add a small, multi-stage Dockerfile based on the pinned runtime and run the app as a non-root user."),
        ],
    )


def _github_json(path: str) -> dict[str, Any]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoRescue-AI/1.0"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"https://api.github.com{path}", headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise HTTPException(status_code=404, detail="Repository not found or not public") from error
        if error.code == 403:
            raise HTTPException(status_code=429, detail="GitHub API rate limit reached; try again with GITHUB_TOKEN") from error
        raise HTTPException(status_code=502, detail="GitHub API request failed") from error
    except (URLError, TimeoutError) as error:
        raise HTTPException(status_code=502, detail="Unable to reach GitHub") from error


def inspect_repository(github_url: str) -> InspectionResponse:
    match = GITHUB_REPOSITORY.fullmatch(github_url)
    if not match:
        raise HTTPException(status_code=422, detail="Invalid GitHub URL")
    owner, name = match.group("owner"), match.group("repo")
    metadata = _github_json(f"/repos/{owner}/{name}")
    branch = metadata.get("default_branch") or "main"
    tree = _github_json(f"/repos/{owner}/{name}/git/trees/{branch}?recursive=1")
    paths = sorted(item["path"] for item in tree.get("tree", []) if item.get("type") == "blob")
    basenames = {path.rsplit("/", 1)[-1] for path in paths}
    findings: list[Finding] = []
    if not any(path.lower() in {"readme", "readme.md", "readme.rst", "readme.txt"} for path in basenames):
        findings.append(_finding("readme-missing", Severity.medium, "README is missing", "The repository has no README file explaining how to install, run, or contribute to the project.", "Add a README with prerequisites, setup, usage, testing, and deployment instructions."))
    if not basenames.intersection(LOCKFILES):
        findings.append(_finding("missing-lockfile", Severity.high, "Dependencies are not locked", "No recognized dependency lockfile was found, so installs can drift between environments.", "Generate and commit the lockfile for the project's package manager and use frozen installs in CI."))
    if not any(any(marker in part.lower() for marker in TEST_MARKERS) for path in paths for part in path.split("/")):
        findings.append(_finding("tests-missing", Severity.high, "Tests are missing", "No conventional test directory or test-named file was found.", "Add a fast unit-test suite and run it in CI before merging changes."))
    if "Dockerfile" not in basenames and "dockerfile" not in {name.lower() for name in basenames}:
        findings.append(_finding("dockerfile-missing", Severity.low, "No Dockerfile found", "The repository does not document a reproducible container build.", "Add a Dockerfile based on the pinned runtime and run the app as a non-root user."))
    runtime_files = {".python-version", ".node-version", ".ruby-version", "runtime.txt", ".tool-versions", ".nvmrc"}
    if not basenames.intersection(runtime_files):
        findings.append(_finding("runtime-unpinned", Severity.medium, "Runtime version is not pinned", "No common runtime version marker was detected.", "Add a runtime version file or tool configuration and use the same version in CI and production."))
    if ".env.example" not in basenames and ".env.template" not in basenames:
        findings.append(_finding("env-example-missing", Severity.medium, "Environment variables are undocumented", "No .env.example or .env.template was found for local configuration discovery.", "Commit a redacted .env.example containing required variable names and safe placeholder values."))
    return InspectionResponse(
        repository=RepositorySummary(owner=owner, name=name, default_branch=branch, description=metadata.get("description"), file_count=len(paths)),
        demo=False, findings=findings, inspected_files=paths,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/inspect", response_model=InspectionResponse)
def inspect(request: InspectRequest) -> InspectionResponse:
    return demo_inspection() if request.demo else inspect_repository(request.github_url)
