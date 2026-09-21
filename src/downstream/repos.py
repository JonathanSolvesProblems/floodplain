"""Resolve a dependent's source checkout: GitHub repo + the tag for a version.

Wheels rarely ship tests, so to run a dependent's suite we need its source at
the version that was current on the release date. We look for a GitHub URL in
the PyPI project_urls, then match the version against the repo's tags with
`git ls-remote` (no API quota). When no tag matches we fall back to the sdist.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
PREFERRED_KEYS = ("source", "source code", "repository", "code", "github", "homepage", "home")


@dataclass
class SourceRef:
    owner: str
    repo: str
    tag: str | None
    sha: str | None
    sdist_url: str | None = None   # fallback when no git ref resolves: PyPI source tarball

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}.git"

    @property
    def runnable(self) -> bool:
        return bool(self.sha or self.tag or self.sdist_url)


def sdist_url(release_json: dict) -> str | None:
    for f in release_json.get("urls") or []:
        if f.get("packagetype") == "sdist" and not f.get("yanked"):
            return f.get("url")
    return None


def github_repo(project_urls: dict[str, str]) -> tuple[str, str] | None:
    items = sorted(
        project_urls.items(),
        key=lambda kv: PREFERRED_KEYS.index(kv[0].lower()) if kv[0].lower() in PREFERRED_KEYS else 99,
    )
    for _key, url in items:
        m = GITHUB_RE.search(url or "")
        if m:
            owner, repo = m.group(1), m.group(2)
            repo = re.sub(r"\.git$", "", repo)
            return owner, repo
    return None


def tag_candidates(name: str, version: str) -> list[str]:
    n = name
    variants = {n, n.replace("-", "_"), n.replace("_", "-"), n.replace("-", ""), n.split("-")[-1]}
    out = [f"v{version}", version, f"V{version}"]
    for v in variants:
        out += [f"{v}-{version}", f"{v}-v{version}", f"{v}_{version}", f"{v}_v{version}",
                f"{v}/{version}", f"{v}/v{version}", f"{v}@{version}", f"{v}=={version}"]
    out += [f"release-{version}", f"release/{version}", f"rel-{version}", f"r{version}", f"{version}.0"]
    # Some projects tag 1.2 for version 1.2.0
    if version.endswith(".0"):
        short = version[:-2]
        out += [f"v{short}", short]
    seen: set[str] = set()
    return [t for t in out if not (t in seen or seen.add(t))]


async def list_remote_tags(clone_url: str) -> dict[str, str]:
    """tag name -> commit sha (peeled when available)."""
    proc = await asyncio.create_subprocess_exec(
        "git", "ls-remote", "--tags", clone_url,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _err = await asyncio.wait_for(proc.communicate(), timeout=120)
    tags: dict[str, str] = {}
    for line in out.decode("utf-8", "replace").splitlines():
        sha, _, ref = line.partition("\t")
        if not ref.startswith("refs/tags/"):
            continue
        name = ref[len("refs/tags/"):]
        if name.endswith("^{}"):
            tags[name[:-3]] = sha  # peeled annotated tag wins
        else:
            tags.setdefault(name, sha)
    return tags


async def resolve_source(name: str, version: str, project_urls: dict[str, str]) -> SourceRef | None:
    gh = github_repo(project_urls)
    if gh is None:
        return None
    owner, repo = gh
    ref = SourceRef(owner=owner, repo=repo, tag=None, sha=None)
    try:
        tags = await list_remote_tags(ref.clone_url)
    except (asyncio.TimeoutError, OSError):
        return ref
    for cand in tag_candidates(name, version):
        if cand in tags:
            ref.tag, ref.sha = cand, tags[cand]
            return ref
    fuzzy = fuzzy_tag(name, version, tags)
    if fuzzy is not None:
        ref.tag, ref.sha = fuzzy, tags[fuzzy]
    return ref


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def fuzzy_tag(name: str, version: str, tags: dict[str, str]) -> str | None:
    """Monorepo tags look like python-openinference-instrumentation-openai-v0.1.54 or
    livekit-plugins-openai@1.6.9. Accept a tag whose normalized form ends with the
    version and whose prefix contains the package name, when exactly one does."""
    nv = _norm(version)
    nn = _norm(name)
    hits = []
    for tag in tags:
        nt = _norm(tag)
        if not nt.endswith(nv) or len(nt) == len(nv):
            continue
        prefix = nt[: -len(nv)]
        if nn in prefix and prefix != nn + "v" + nv:
            hits.append(tag)
    return hits[0] if len(hits) == 1 else None
