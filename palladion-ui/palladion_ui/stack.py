"""Starts and stops the processes under the UI: Qdrant (in WSL) and the Palladion API, one model at a time.

It only ever stops what it started. A Qdrant or Palladion that was already running is used as it is and left alone.
The Groq key is read from the repository's .env only when a model is explicitly chosen, handed to the child process
through its environment, and never logged, returned or sent to a browser.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from palladion_ui.settings import Settings

KEY_VARIABLE = "PALLADION_UI_GROQ_KEY"
KEY_NAME = "GROQ_API_KEY"
LIVE_TIMEOUT = 40  # seconds one Groq request may take (serve.py --model-timeout)
START_TIMEOUT = 90.0


class StackError(Exception):
    """Raised with a message that is safe to show to a person."""


def read_groq_key(env_file: Path) -> str:
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise StackError("The repository .env file could not be read, so no model can be started.") from error
    for line in lines:
        name, _, value = line.partition("=")
        if name.strip() == KEY_NAME and value.strip().strip("'\""):
            return value.strip().strip("'\"")
    raise StackError(f"No {KEY_NAME} in the repository .env file, so no model can be started.")


def palladion_command(settings: Settings, model: str | None) -> list[str]:
    python = settings.app_dir / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    command = [str(python), "scripts/serve.py", "--root", str(settings.data_root), "--url", settings.qdrant_url,
               "--collection", settings.collection, "--port", str(settings.upstream_port), "--rerank"]
    if model is not None:
        command += ["--enable-live-llm", "--model", model, "--key-env", KEY_VARIABLE,
                    "--request-timeout", str(settings.request_timeout), "--model-timeout", str(LIVE_TIMEOUT)]
    return command


async def http_up(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            return (await client.get(url)).status_code < 500
    except httpx.HTTPError:
        return False


def kill_tree(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        process.terminate()


class Stack:
    def __init__(self, settings: Settings, *, spawn: Callable[..., subprocess.Popen[Any]] = subprocess.Popen,
                 probe: Callable[[str], Awaitable[bool]] = http_up,
                 key_reader: Callable[[Path], str] = read_groq_key) -> None:
        self.settings, self._spawn, self._probe, self._key_reader = settings, spawn, probe, key_reader
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._api: subprocess.Popen[Any] | None = None
        self._qdrant: subprocess.Popen[Any] | None = None
        self.state = "stopped"  # stopped | starting | ready | error
        self.model: str | None = None
        self.error: str | None = None
        self.since = time.time()

    # Reporting ------------------------------------------------------------------------------------------------

    async def status(self) -> dict[str, Any]:
        api_up = await self._probe(f"{self.settings.upstream_url}/health/live")
        if self.state == "ready" and not api_up:
            self.state, self.error = "error", "Palladion stopped unexpectedly. Check the log in .runtime/logs."
        return {"state": self.state, "model": self.model, "mode": "agent" if self.model else "search",
                "error": self.error, "api": api_up, "managed": self.settings.managed,
                "qdrant": await self._probe(self.settings.qdrant_url), "since": self.since}

    def _set(self, state: str, error: str | None = None) -> None:
        self.state, self.error, self.since = state, error, time.time()

    # Control --------------------------------------------------------------------------------------------------

    async def start(self, model: str | None) -> None:
        """Start (or restart) the API in search-only mode (model None) or with one explicitly chosen model."""
        if model is not None and model not in self.settings.model_ids:
            raise StackError("That model is not one Palladion allows.")
        if not self.settings.managed:
            raise StackError("This UI does not manage Palladion; start it yourself and point the UI at it.")
        async with self._lock:
            self._set("starting")
            self.model = model
            try:
                env = dict(os.environ)
                if model is not None:
                    env[KEY_VARIABLE] = self._key_reader(self.settings.env_file)
                await self._ensure_qdrant()
                self._stop_api()
                if await self._probe(f"{self.settings.upstream_url}/health/live"):
                    raise StackError(f"Port {self.settings.upstream_port} is already in use by a Palladion this UI "
                                     "did not start. Stop it, or choose another port.")
                self.settings.log_dir.mkdir(parents=True, exist_ok=True)
                log = (self.settings.log_dir / f"palladion-{self.settings.upstream_port}.log").open("ab")
                self._api = self._spawn(palladion_command(self.settings, model), cwd=self.settings.app_dir, env=env,
                                        stdout=log, stderr=subprocess.STDOUT)
                await self._wait_for_api(model is not None)
            except StackError as error:
                self._stop_api()
                self._set("error", str(error))
                raise
            except Exception as error:  # a spawn failure is shown, not hidden
                self._stop_api()
                self._set("error", "Palladion could not be started. See .runtime/logs for the reason.")
                raise StackError(self.error or "") from error
            self._set("ready")

    def begin(self, model: str | None) -> None:
        """Start in the background and report "starting" at once, so a client never sees the old state."""
        if model is not None and model not in self.settings.model_ids:
            raise StackError("That model is not one Palladion allows.")
        if not self.settings.managed:
            raise StackError("This UI does not manage Palladion; start it yourself and point the UI at it.")
        self._set("starting")
        self.model = model
        self._task = asyncio.create_task(self._start_quietly(model))

    async def _start_quietly(self, model: str | None) -> None:
        try:
            await self.start(model)
        except StackError:
            pass  # start() has already recorded the reason in self.error

    async def stop(self) -> None:
        async with self._lock:
            self._stop_api()
            self.model = None
            self._set("stopped")

    async def shutdown(self) -> None:
        async with self._lock:
            self._stop_api()
            self._stop_qdrant()
            self._set("stopped")

    def _stop_api(self) -> None:
        if self._api is not None:
            kill_tree(self._api)
            self._api = None

    async def _wait_for_api(self, needs_model: bool) -> None:
        deadline = time.monotonic() + START_TIMEOUT
        live = f"{self.settings.upstream_url}/health/live"
        while time.monotonic() < deadline:
            if self._api is not None and self._api.poll() is not None:
                raise StackError("Palladion stopped while starting. See .runtime/logs for the reason.")
            if await self._probe(live):
                if not needs_model:
                    return
                ready = f"{self.settings.upstream_url}/health/ready"
                if await self._probe(ready):
                    return
            await asyncio.sleep(0.5)
        raise StackError("Palladion did not become ready in time. See .runtime/logs for the reason.")

    # Qdrant (WSL) ---------------------------------------------------------------------------------------------

    async def _ensure_qdrant(self) -> None:
        if await self._probe(self.settings.qdrant_url):
            return
        if os.name != "nt":
            raise StackError(f"Qdrant is not running on port {self.settings.qdrant_port}. Start it, then retry.")
        home = subprocess.run(["wsl.exe", "-d", "Ubuntu", "--exec", "sh", "-c", "echo $HOME"],
                              capture_output=True, text=True, check=False).stdout.replace("\0", "").strip()
        if not home.startswith("/"):
            raise StackError("WSL Ubuntu is not available, so Qdrant cannot be started.")
        base = f"{home}/.local/share/palladion-ui/qdrant"
        binary = f"{home}/.local/share/palladion/qdrant/bin-1.19.2/qdrant"
        config = (f'storage:\n  storage_path: "{base}/storage"\nservice:\n  host: 127.0.0.1\n'
                  f"  http_port: {self.settings.qdrant_port}\n  grpc_port: {self.settings.qdrant_port + 1}\n"
                  "telemetry_disabled: true\n")
        # A Qdrant left behind by an earlier crash of this UI (recorded in its own pid file) is cleared first;
        # nothing else is touched.
        script = (f"mkdir -p {base}/storage && cat > {base}/standalone.yaml && test -x {binary} && "
                  f"if [ -f {base}/server.pid ] && kill -0 $(cat {base}/server.pid) 2>/dev/null; then "
                  f"kill $(cat {base}/server.pid); sleep 2; kill -9 $(cat {base}/server.pid) 2>/dev/null; fi; "
                  f"echo $$ > {base}/server.pid && exec {binary} --config-path {base}/standalone.yaml")
        self.settings.log_dir.mkdir(parents=True, exist_ok=True)
        log = (self.settings.log_dir / "qdrant.log").open("ab")
        self._qdrant = self._spawn(["wsl.exe", "-d", "Ubuntu", "--exec", "sh", "-c", script], stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT)
        assert self._qdrant.stdin is not None
        self._qdrant.stdin.write(config.encode())
        self._qdrant.stdin.close()
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            if self._qdrant.poll() is not None:
                raise StackError("Qdrant stopped while starting. Is Palladion's Qdrant binary installed in WSL?")
            if await self._probe(self.settings.qdrant_url):
                return
            await asyncio.sleep(0.5)
        raise StackError("Qdrant did not start in time.")

    def _stop_qdrant(self) -> None:
        if self._qdrant is None:
            return
        base = "$HOME/.local/share/palladion-ui/qdrant"
        subprocess.run(["wsl.exe", "-d", "Ubuntu", "--exec", "sh", "-c", f"kill $(cat {base}/server.pid)"],
                       capture_output=True, check=False)
        kill_tree(self._qdrant)
        self._qdrant = None
