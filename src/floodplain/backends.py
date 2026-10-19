"""Execution substrates for Downstream.

Downstream needs one primitive: run a command on an immutable filesystem image and
optionally keep the result as a new immutable image, so that N children can be forked
from one parent. Three substrates provide it.

    ContreeBackend  Nebius Token Factory Sandboxes. The judged substrate. A run with
                    disposable=False returns a content-addressed uuid, and running N
                    times from one uuid is N forks.
    JobsBackend     Nebius AI Cloud Serverless Jobs. The fallback substrate when
                    Sandboxes is not activated: a job per fork, state carried in a
                    committed OCI image rather than a checkpoint.
    DockerBackend   Local Docker. Development only, so the pipeline can be proven
                    without waiting on beta access. `docker commit` stands in for the
                    checkpoint. Never used for a judged run; every result record
                    carries the backend name so a local number can never be quoted as
                    a Nebius one.

Choose with FLOODPLAIN_BACKEND=contree|jobs|docker (default contree).
"""

from __future__ import annotations

import asyncio
import os
import shlex
import time
import uuid as uuidlib
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ImageRef:
    """An immutable filesystem image. Forking means running twice from the same ref."""
    id: str
    backend: str

    def __str__(self) -> str:
        return f"{self.backend}:{self.id[:16]}"


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
    image: ImageRef | None          # the new checkpoint, when persist was requested
    elapsed_s: float
    cost: float = 0.0
    truncated: bool = False
    backend: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.error is None


@runtime_checkable
class Backend(Protocol):
    name: str

    async def prepare_base(self) -> ImageRef: ...

    async def run(self, image: ImageRef, shell: str, *, persist: bool = False,
                  timeout: int = 900, files: dict[str, bytes] | None = None,
                  env: dict[str, str] | None = None) -> ExecResult: ...

    async def read_file(self, image: ImageRef, path: str) -> bytes: ...

    async def close(self) -> None: ...


# The one environment every experiment starts from: python 3.12, git, uv, curl.
BASE_SETUP = (
    "apt-get update -qq && "
    "apt-get install -y -qq --no-install-recommends git ca-certificates curl build-essential "
    ">/dev/null 2>&1 && "
    "pip install --quiet --root-user-action=ignore uv && mkdir -p /work && uv --version"
)
BASE_OCI = "python:3.12-slim-bookworm"
BASE_TAG = "floodplain-base-py312"
OUTPUT_CAP = 8 * 1024 * 1024


def bash_wrap(script: str) -> str:
    """Run `script` under bash on every backend.

    The base image's /bin/sh is dash, and the install and test scripts use `set -o pipefail`
    and `${PIPESTATUS[0]}`, which dash rejects. Passing the script through base64 avoids
    every quoting question about what the outer shell does to it first.
    """
    import base64
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return f"printf %s {b64} | base64 -d > /tmp/ds-step.sh && bash /tmp/ds-step.sh"


# --------------------------------------------------------------------------- Nebius Sandboxes

class ContreeBackend:
    """Nebius Token Factory Sandboxes, via the contree SDK. The judged substrate."""

    name = "nebius-sandboxes"

    def __init__(self, sdk=None) -> None:
        from contree_sdk import Contree
        self.sdk = sdk or Contree()

    async def prepare_base(self) -> ImageRef:
        try:
            img = self.sdk.images.use(BASE_TAG, strict=True)
            img = await img if asyncio.iscoroutine(img) else img
            if getattr(img, "uuid", None):
                return ImageRef(str(img.uuid), self.name)
        except Exception:
            pass
        base = await self.sdk.images.oci(BASE_OCI)
        built = await base.run(shell=BASE_SETUP, disposable=False, tag=BASE_TAG, timeout=900)
        return ImageRef(str(built.uuid), self.name)

    async def run(self, image: ImageRef, shell: str, *, persist: bool = False,
                  timeout: int = 900, files: dict[str, bytes] | None = None,
                  env: dict[str, str] | None = None) -> ExecResult:
        img = self.sdk.images.use(image.id)
        t0 = time.monotonic()
        try:
            res = await img.run(shell=bash_wrap(shell), disposable=not persist, timeout=timeout,
                                files=files or None, env=env or None,
                                truncate_output_at=OUTPUT_CAP)
        except Exception as e:  # noqa: BLE001 - recorded, never hidden
            return ExecResult(-1, "", "", None, time.monotonic() - t0, backend=self.name,
                              error=f"{type(e).__name__}: {e}"[:2000])
        r = res.result
        return ExecResult(
            exit_code=r.exit_code, stdout=r.stdout or "", stderr=r.stderr or "",
            image=ImageRef(str(res.uuid), self.name) if (persist and res.uuid) else None,
            elapsed_s=r.elapsed_time.total_seconds(), cost=r.cost,
            truncated=r.truncated, backend=self.name,
        )

    async def read_file(self, image: ImageRef, path: str) -> bytes:
        return await self.sdk.images.use(image.id).read(path)

    async def close(self) -> None:
        return None


# --------------------------------------------------------------------------- local Docker

class DockerBackend:
    """Local Docker. Development only: `docker commit` stands in for a checkpoint.

    Forking is the same shape as Sandboxes: run twice from one image id, and each run
    that persists commits to a fresh image. Cost is always 0.0 and is never quoted.
    """

    name = "local-docker"

    def __init__(self, keep: bool = False) -> None:
        self.keep = keep
        self._made: list[str] = []

    async def _docker(self, *args: str, timeout: int = 900) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            "docker", *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 124, "", f"docker {args[0]} timed out after {timeout}s"
        return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    async def prepare_base(self) -> ImageRef:
        code, out, _ = await self._docker("image", "inspect", BASE_TAG, "--format", "{{.Id}}", timeout=60)
        if code == 0 and out.strip():
            return ImageRef(BASE_TAG, self.name)
        code, _, err = await self._docker("pull", "--quiet", BASE_OCI, timeout=900)
        if code != 0:
            raise RuntimeError(f"docker pull failed: {err[:500]}")
        cname = f"floodplain-base-{uuidlib.uuid4().hex[:10]}"
        code, _, err = await self._docker("run", "--name", cname, BASE_OCI, "sh", "-c", BASE_SETUP, timeout=1800)
        if code != 0:
            await self._docker("rm", "-f", cname, timeout=60)
            raise RuntimeError(f"base setup failed: {err[:500]}")
        await self._docker("commit", cname, BASE_TAG, timeout=300)
        await self._docker("rm", "-f", cname, timeout=60)
        return ImageRef(BASE_TAG, self.name)

    async def run(self, image: ImageRef, shell: str, *, persist: bool = False,
                  timeout: int = 900, files: dict[str, bytes] | None = None,
                  env: dict[str, str] | None = None) -> ExecResult:
        cname = f"ds-{uuidlib.uuid4().hex[:12]}"
        t0 = time.monotonic()
        script = shell
        if files:
            # Write uploads with a base64 heredoc so arbitrary bytes survive the shell.
            import base64
            prelude = []
            for path, content in files.items():
                b64 = base64.b64encode(content).decode()
                prelude.append(
                    f"mkdir -p {shlex.quote(os.path.dirname(path) or '/')} && "
                    f"printf %s {shlex.quote(b64)} | base64 -d > {shlex.quote(path)}"
                )
            script = " && ".join(prelude) + "\n" + shell
        args = ["run", "--name", cname]
        for k, v in (env or {}).items():
            args += ["-e", f"{k}={v}"]
        args += [image.id, "bash", "-c", script]
        code, out, err = await self._docker(*args, timeout=timeout)
        new_image = None
        if persist and code != 124:
            tag = f"floodplain-step:{uuidlib.uuid4().hex[:12]}"
            c2, _, e2 = await self._docker("commit", cname, tag, timeout=300)
            if c2 == 0:
                new_image = ImageRef(tag, self.name)
                self._made.append(tag)
        if not self.keep:
            await self._docker("rm", "-f", cname, timeout=120)
        out, err = out[:OUTPUT_CAP], err[:OUTPUT_CAP]
        return ExecResult(code, out, err, new_image, time.monotonic() - t0,
                          cost=0.0, backend=self.name,
                          error="timeout" if code == 124 else None)

    async def read_file(self, image: ImageRef, path: str) -> bytes:
        cname = f"ds-read-{uuidlib.uuid4().hex[:10]}"
        await self._docker("create", "--name", cname, image.id, "true", timeout=120)
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "cp", f"{cname}:{path}", "-",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            # docker cp to stdout emits a tar stream; pull the single member out.
            import io
            import tarfile
            with tarfile.open(fileobj=io.BytesIO(out)) as tf:
                member = next((m for m in tf.getmembers() if m.isfile()), None)
                if member is None:
                    raise FileNotFoundError(path)
                f = tf.extractfile(member)
                return f.read() if f else b""
        finally:
            await self._docker("rm", "-f", cname, timeout=60)

    async def close(self) -> None:
        if self.keep:
            return
        for tag in self._made:
            await self._docker("rmi", "-f", tag, timeout=120)
        self._made.clear()


# --------------------------------------------------------------------------- factory

def make_backend(kind: str | None = None) -> Backend:
    kind = (kind or os.environ.get("FLOODPLAIN_BACKEND") or "contree").lower()
    if kind in ("contree", "sandboxes", "nebius"):
        return ContreeBackend()
    if kind in ("docker", "local"):
        return DockerBackend()
    if kind in ("jobs", "serverless"):
        from .jobs_backend import JobsBackend
        return JobsBackend()
    raise ValueError(f"unknown backend {kind!r}")
