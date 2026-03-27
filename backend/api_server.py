# -*- coding: utf-8 -*-
"""WolfMind 的 FastAPI 服务端。

提供：
- POST /api/game/start  : 启动一局新游戏（以异步后台任务运行）
- GET  /api/game/status : 获取当前运行状态
- WS   /ws/game         : 实时推送结构化游戏事件

说明：游戏本体（LLM 智能体 + 引擎）在同一进程内运行；前端通过 WebSocket 订阅事件流。
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
import json
from pathlib import Path
import re
import secrets
import threading
import time
import queue
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from game_service import run_game_session


def _new_game_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _map_agent_id(agent_name: str | None) -> str | None:
    if not agent_name:
        return None
    # 后端玩家名为 Player1..Player9；前端展示使用 player_1..player_9
    if agent_name.lower().startswith("player"):
        suffix = agent_name[6:]
        if suffix.isdigit():
            return f"player_{int(suffix)}"
    return agent_name


class EventBus:
    def __init__(self, *, buffer_size: int = 500):
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        self._subscribers: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        # 主事件循环（FastAPI/uvicorn）启动时绑定，用于跨线程安全推送。
        self._loop = loop

    def _publish_in_loop(self, event: dict[str, Any]) -> None:
        # 若事件中含有玩家标识，则统一转换为前端使用的 agentId
        if "agentName" in event and "agentId" not in event:
            event["agentId"] = _map_agent_id(event.get("agentName"))
        elif "agentId" in event:
            event["agentId"] = _map_agent_id(event.get("agentId"))

        self._buffer.append(event)
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # 客户端过慢时丢弃该条推送，避免阻塞服务端
                continue
            except Exception:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    def publish(self, event: dict[str, Any]) -> None:
        # 允许从非主线程调用；统一切回 FastAPI 事件循环推送，避免跨线程操作 asyncio.Queue。
        loop = self._loop
        if loop is None:
            self._publish_in_loop(event)
            return

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is loop:
            self._publish_in_loop(event)
            return

        try:
            loop.call_soon_threadsafe(self._publish_in_loop, event)
        except Exception:
            # 兜底：若调度失败，避免影响游戏流程
            return

    def subscribe(self) -> tuple[asyncio.Queue, list[dict[str, Any]]]:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.add(q)
        # 前端期望 historical.events 为“最新在前”
        snapshot = list(self._buffer)
        snapshot.reverse()
        return q, snapshot

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)


@dataclass
class GameRuntime:
    status: str = "idle"  # idle|running|error（空闲|运行中|异常）
    game_id: str | None = None
    # 游戏在独立线程内运行，避免阻塞 FastAPI 主事件循环
    thread: threading.Thread | None = None
    thread_loop: asyncio.AbstractEventLoop | None = None
    thread_task: asyncio.Task | None = None
    stop_event: threading.Event | None = None
    log_path: str | None = None
    experience_path: str | None = None
    last_error: str | None = None
    human_token: str | None = None
    human_profile: dict[str, Any] | None = None
    action_queue: queue.Queue | None = None
    viewer_roles: dict[str, str] = field(default_factory=dict)
    werewolf_teams: dict[str, set[str]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


class StartGameResponse(BaseModel):
    gameId: str
    status: str
    wsUrl: str


class StopGameResponse(BaseModel):
    status: str
    gameId: str | None = None
    message: str


class StatusResponse(BaseModel):
    status: str
    gameId: str | None = None
    logPath: str | None = None
    experiencePath: str | None = None
    lastError: str | None = None


class PlayerInsight(BaseModel):
    impressions: dict[str, str] = {}
    knowledge: str = ""


class PlayersInsightsResponse(BaseModel):
    updatedAt: str
    logSource: str | None = None
    experienceSource: str | None = None
    players: dict[str, PlayerInsight] = {}


class LoginRequest(BaseModel):
    username: str
    avatarUrl: str | None = None


class LoginResponse(BaseModel):
    token: str
    user: dict[str, Any]


def _now_ms() -> int:
    return int(time.time() * 1000)



def create_app() -> FastAPI:
    app = FastAPI(title="WolfMind API", version="0.1.0")

    repo_root = Path(__file__).resolve().parents[1]
    static_dir = repo_root / "static"
    (static_dir / "avatars").mkdir(parents=True, exist_ok=True)
    (static_dir / "backgrounds").mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    data_dir = repo_root / "data"
    logs_dir = data_dir / "game_logs"

    def _pick_latest_file(folder: Path, *, allowed_suffixes: tuple[str, ...]) -> Path | None:
        try:
            if not folder.exists() or not folder.is_dir():
                return None
            candidates = [p for p in folder.iterdir() if p.is_file(
            ) and p.suffix.lower() in allowed_suffixes]
            if not candidates:
                return None
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
        except Exception:
            return None

    def _resolve_file(path_str: str | None, *, fallback_dir: Path, allowed_suffixes: tuple[str, ...]) -> Path:
        # Prefer the runtime path if available; otherwise fall back to latest file under fallback_dir.
        chosen: Path | None = None
        if path_str:
            p = Path(path_str)
            chosen = (p if p.is_absolute() else (repo_root / p)).resolve()
        if chosen is None or not chosen.exists() or not chosen.is_file():
            chosen = _pick_latest_file(
                fallback_dir, allowed_suffixes=allowed_suffixes)
        if chosen is None:
            raise HTTPException(
                status_code=404, detail="No export file available")

        # Safety: ensure resolved file stays within the expected directory.
        allowed_root = fallback_dir.resolve()
        chosen_resolved = chosen.resolve()
        if allowed_root not in chosen_resolved.parents:
            raise HTTPException(status_code=400, detail="Invalid export path")
        if chosen_resolved.suffix.lower() not in allowed_suffixes:
            raise HTTPException(
                status_code=400, detail="Invalid export file type")
        return chosen_resolved

    def _normalize_player_id(name: str | None) -> str | None:
        if not name:
            return None
        raw = str(name).strip()
        low = raw.lower()
        if low.startswith("player"):
            suffix = raw[6:]
            if suffix.isdigit():
                return f"player_{int(suffix)}"
        return raw

    _REFLECTION_HEADER_RE = re.compile(
        r"^\[(\d{2}:\d{2}:\d{2})\]\s+\[第(\d+)回合-反思\]\s+(.+?)\s*$")
    _FIELD_LINE_RE = re.compile(r"^\s+\((思考|印象)\)\s+(.*)$")

    def _parse_latest_impressions(log_file: Path) -> dict[str, dict[str, str]]:
        """Parse the latest reflections in a log file.

        Returns: {player_id: {other_player_id: impression_text}}
        """
        try:
            lines = log_file.read_text(
                encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return {}

        out: dict[str, dict[str, str]] = {}
        i = 0
        while i < len(lines):
            m = _REFLECTION_HEADER_RE.match(lines[i])
            if not m:
                i += 1
                continue

            player_raw = m.group(3).strip()
            player_id = _normalize_player_id(player_raw)
            if not player_id:
                i += 1
                continue

            current_field: str | None = None
            thought_lines: list[str] = []
            impression_lines: list[str] = []

            i += 1
            # Consume until blank line or file end.
            while i < len(lines) and lines[i].strip() != "":
                line = lines[i].rstrip("\n")
                fm = _FIELD_LINE_RE.match(line)
                if fm:
                    current_field = fm.group(1)
                    payload = fm.group(2).strip()
                    if current_field == "思考":
                        thought_lines = [payload] if payload else []
                    elif current_field == "印象":
                        impression_lines = [payload] if payload else []
                else:
                    # Continuation lines are aligned with spaces; keep content trimmed.
                    if current_field == "思考":
                        thought_lines.append(line.strip())
                    elif current_field == "印象":
                        impression_lines.append(line.strip())
                i += 1

            # Extract impression map
            imp_map: dict[str, str] = {}
            for raw_line in impression_lines:
                s = (raw_line or "").strip()
                if not s or s in ("(无更新)", "(暂无)"):
                    continue
                if ":" not in s:
                    continue
                k, v = s.split(":", 1)
                other_id = _normalize_player_id(k.strip())
                if not other_id:
                    continue
                imp_map[other_id] = v.strip()

            # Keep the latest occurrence for each player (later blocks override earlier ones)
            out[player_id] = imp_map

            # Skip the blank line
            i += 1

        return out

    def _load_experience_knowledge(exp_file: Path) -> dict[str, str]:
        """Load player knowledge from experience JSON.

        Returns: {player_id: knowledge_text}
        """
        try:
            data = json.loads(exp_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

        players = data.get("players", {}) if isinstance(data, dict) else {}
        if not isinstance(players, dict):
            return {}

        out: dict[str, str] = {}
        for k, v in players.items():
            pid = _normalize_player_id(str(k))
            if not pid:
                continue
            out[pid] = str(v or "")
        return out

    # 开发期 CORS（前端通常运行在 :5173）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    bus = EventBus()
    runtime = GameRuntime()
    runtime.action_queue = queue.Queue()

    @app.on_event("startup")
    async def _startup() -> None:
        # 绑定主事件循环，以便支持跨线程事件推送
        bus.bind_loop(asyncio.get_running_loop())

    async def _run_game_async(game_id: str, stop_event: threading.Event | None) -> None:
        with runtime.lock:
            runtime.status = "running"
            runtime.game_id = game_id
            runtime.last_error = None
            runtime.log_path = None
            runtime.experience_path = None
            runtime.viewer_roles = {}
            runtime.werewolf_teams = {}

        bus.publish(
            {"type": "system", "content": f"游戏启动中… (game_id={game_id})"})

        try:
            with runtime.lock:
                human_token = runtime.human_token
                human_profile = runtime.human_profile
                action_q = runtime.action_queue

            human = None
            if human_token and isinstance(human_profile, dict) and action_q is not None:
                human = {**human_profile, "token": human_token}

            log_path, experience_path = await run_game_session(
                game_id=game_id,
                event_sink=bus.publish,
                stop_event=stop_event,
                human=human,
                action_queue=action_q,
            )
            with runtime.lock:
                runtime.log_path = log_path
                runtime.experience_path = experience_path
                runtime.status = "idle"
            bus.publish(
                {
                    "type": "system",
                    "content": f"游戏结束。日志: {log_path}，经验: {experience_path}",
                    "logPath": log_path,
                    "experiencePath": experience_path,
                }
            )
        except asyncio.CancelledError:
            # 被显式终止（例如前端点击“终止游戏”）
            with runtime.lock:
                runtime.status = "idle"
            bus.publish({"type": "system", "content": "游戏已终止"})
            raise
        except Exception as exc:  # noqa: BLE001
            with runtime.lock:
                runtime.status = "error"
                runtime.last_error = str(exc)
            bus.publish({"type": "day_error", "content": f"游戏异常终止: {exc}"})

    def _thread_entry(game_id: str, stop_event: threading.Event) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task: asyncio.Task | None = None
        try:
            task = loop.create_task(_run_game_async(game_id, stop_event))
            with runtime.lock:
                runtime.thread_loop = loop
                runtime.thread_task = task
            loop.run_until_complete(task)
        except BaseException as exc:  # noqa: BLE001
            # 若为取消则不当作异常；其它异常已在 _run_game_async 里记录并推送
            if isinstance(exc, asyncio.CancelledError):
                return
        finally:
            try:
                if task and not task.done():
                    task.cancel()
            except Exception:
                pass
            try:
                loop.stop()
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass
            with runtime.lock:
                runtime.thread_loop = None
                runtime.thread_task = None
                runtime.thread = None
                runtime.stop_event = None

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=PlainTextResponse)
    async def root() -> str:
        return "WolfMind 后端已启动。访问 /docs 查看接口文档，或调用 /api/game/start 开始游戏。"

    @app.get("/favicon.ico")
    async def favicon() -> Response:
        # 浏览器通常会自动请求 favicon；这里返回空内容避免日志出现 404
        return Response(content=b"", media_type="image/x-icon")

    @app.get("/api/game/status", response_model=StatusResponse)
    async def game_status() -> StatusResponse:
        return StatusResponse(
            status=runtime.status,
            gameId=runtime.game_id,
            logPath=runtime.log_path,
            experiencePath=runtime.experience_path,
            lastError=runtime.last_error,
        )

    @app.get("/api/exports/log")
    async def export_latest_log() -> FileResponse:
        with runtime.lock:
            log_path = runtime.log_path
        resolved = _resolve_file(
            log_path, fallback_dir=logs_dir, allowed_suffixes=(".log", ".txt"))
        return FileResponse(
            path=str(resolved),
            filename=resolved.name,
            media_type="text/plain; charset=utf-8",
        )

    @app.get("/api/exports/experience")
    async def export_latest_experience() -> FileResponse:
        with runtime.lock:
            exp_path = runtime.experience_path
        resolved = _resolve_file(
            exp_path, fallback_dir=experiences_dir, allowed_suffixes=(".json",))
        return FileResponse(
            path=str(resolved),
            filename=resolved.name,
            media_type="application/json",
        )

    @app.get("/api/players/insights", response_model=PlayersInsightsResponse)
    async def get_players_insights() -> PlayersInsightsResponse:
        """Return per-player insights for the UI hover popover.

        - impressions: parsed from latest log reflection blocks
        - knowledge: loaded from latest experience JSON
        """
        with runtime.lock:
            log_path = runtime.log_path
            exp_path = runtime.experience_path

        resolved_log = _resolve_file(
            log_path, fallback_dir=logs_dir, allowed_suffixes=(".log", ".txt"))
        resolved_exp = _resolve_file(
            exp_path, fallback_dir=experiences_dir, allowed_suffixes=(".json",))

        impressions_by_player = _parse_latest_impressions(resolved_log)
        knowledge_by_player = _load_experience_knowledge(resolved_exp)

        # Merge keys
        players: dict[str, PlayerInsight] = {}
        keys = set(impressions_by_player.keys()) | set(
            knowledge_by_player.keys())
        for pid in keys:
            players[pid] = PlayerInsight(
                impressions=impressions_by_player.get(pid, {}),
                knowledge=knowledge_by_player.get(pid, ""),
            )

        return PlayersInsightsResponse(
            updatedAt=datetime.now().isoformat(),
            logSource=str(resolved_log.name),
            experienceSource=str(resolved_exp.name),
            players=players,
        )

    def _require_token(authorization: str | None) -> str:
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing Authorization")
        m = re.match(r"^Bearer\s+(.+)$", authorization.strip(), flags=re.I)
        if not m:
            raise HTTPException(status_code=401, detail="Invalid Authorization")
        return m.group(1).strip()

    @app.post("/api/login", response_model=LoginResponse)
    async def login(body: LoginRequest) -> LoginResponse:
        username = (body.username or "").strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username required")
        if len(username) > 20:
            raise HTTPException(status_code=400, detail="Username too long")

        token = secrets.token_urlsafe(24)
        avatar_url = (body.avatarUrl or "").strip() or "/avatars/villager.svg"
        user = {
            "id": token[:10],
            "username": username,
            "avatarUrl": avatar_url,
        }
        with runtime.lock:
            runtime.human_token = token
            runtime.human_profile = user
        bus.publish({"type": "system", "content": f"用户已登录：{username}"})
        return LoginResponse(token=token, user=user)

    @app.post("/api/logout")
    async def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
        token = _require_token(authorization)
        with runtime.lock:
            if runtime.human_token == token:
                runtime.human_token = None
                runtime.human_profile = None
        return {"status": "ok"}

    @app.get("/api/user")
    async def get_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        token = _require_token(authorization)
        with runtime.lock:
            if runtime.human_token != token or not runtime.human_profile:
                raise HTTPException(status_code=401, detail="Invalid session")
            return {"user": runtime.human_profile}

    @app.post("/api/upload/avatar")
    async def upload_avatar(file: UploadFile = File(...), authorization: str | None = Header(default=None)) -> dict[str, str]:
        token = _require_token(authorization)
        with runtime.lock:
            if runtime.human_token != token:
                raise HTTPException(status_code=401, detail="Invalid session")

        ct = (file.content_type or "").lower()
        if ct not in {"image/png", "image/jpeg", "image/jpg"}:
            raise HTTPException(status_code=400, detail="Only PNG/JPG allowed")

        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large")

        suffix = ".png" if ct == "image/png" else ".jpg"
        filename = f"{token[:10]}_{_now_ms()}{suffix}"
        path = (static_dir / "avatars" / filename).resolve()
        if static_dir.resolve() not in path.parents:
            raise HTTPException(status_code=400, detail="Invalid path")
        try:
            path.write_bytes(raw)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc))

        avatar_url = f"/static/avatars/{filename}"
        with runtime.lock:
            if runtime.human_profile is not None:
                runtime.human_profile["avatarUrl"] = avatar_url

        return {"avatarUrl": avatar_url}

    @app.post("/api/game/start", response_model=StartGameResponse)
    async def start_game() -> StartGameResponse:
        with runtime.lock:
            running = runtime.thread is not None and runtime.thread.is_alive()
        if running:
            raise HTTPException(
                status_code=409, detail="A game is already running")

        game_id = _new_game_id()
        stop_event = threading.Event()
        t = threading.Thread(target=_thread_entry, args=(
            game_id, stop_event), daemon=True)
        with runtime.lock:
            runtime.stop_event = stop_event
            runtime.thread = t
            runtime.status = "running"
            runtime.game_id = game_id
            runtime.last_error = None
            runtime.log_path = None
            runtime.experience_path = None
        t.start()

        # 通知已连接的 WS 客户端
        bus.publish({"type": "system", "content": "已收到开始游戏请求"})

        return StartGameResponse(gameId=game_id, status="running", wsUrl="/ws/game")

    @app.post("/api/game/stop", response_model=StopGameResponse)
    async def stop_game() -> StopGameResponse:
        with runtime.lock:
            thread = runtime.thread
            loop = runtime.thread_loop
            task = runtime.thread_task
            stop_event = runtime.stop_event
            status = runtime.status
            game_id = runtime.game_id

        # 无运行任务时直接返回
        if not thread or not thread.is_alive() or status != "running":
            with runtime.lock:
                runtime.status = "idle"
            return StopGameResponse(status="idle", gameId=game_id, message="当前没有运行中的游戏")

        # 请求取消：同时设置 stop_event + 取消线程内任务（若已可用）
        bus.publish({"type": "system", "content": "已收到终止游戏请求"})
        if stop_event:
            stop_event.set()
        if loop:
            try:
                # cancel main task (if known)
                if task:
                    loop.call_soon_threadsafe(task.cancel)
                # cancel any other tasks spawned in the game loop

                def _cancel_all() -> None:
                    try:
                        for t in asyncio.all_tasks(loop):
                            t.cancel()
                    except Exception:
                        return
                loop.call_soon_threadsafe(_cancel_all)
            except Exception:
                pass

        # 尝试等待线程快速收尾（避免状态长时间卡住）
        try:
            await asyncio.to_thread(thread.join, 2.0)
        except Exception:
            pass

        with runtime.lock:
            # 若线程仍在跑，保持 running；否则置 idle
            if runtime.thread is None or (runtime.thread and not runtime.thread.is_alive()):
                if runtime.status == "running":
                    runtime.status = "idle"
            status = runtime.status
            game_id = runtime.game_id

        return StopGameResponse(status=status, gameId=game_id, message="已请求终止游戏")

    @app.websocket("/ws/game")
    async def ws_game(ws: WebSocket) -> None:
        token = ws.query_params.get("token")
        await ws.accept()

        def _is_review_mode() -> bool:
            with runtime.lock:
                return runtime.status != "running"

        def _viewer_role() -> str:
            if not token:
                return ""
            with runtime.lock:
                return str(runtime.viewer_roles.get(token) or "")

        def _werewolf_team() -> set[str]:
            if not token:
                return set()
            with runtime.lock:
                return set(runtime.werewolf_teams.get(token) or set())

        def _record_viewer_state(event: dict[str, Any]) -> None:
            if not token:
                return
            et = str(event.get("type") or "")
            if et == "your_role":
                r = str(event.get("role") or "").strip().lower()
                if r:
                    with runtime.lock:
                        runtime.viewer_roles[token] = r
            if et == "werewolf_team":
                ids = event.get("teamIds")
                if isinstance(ids, list):
                    team = {str(x or "") for x in ids if str(x or "").strip()}
                    with runtime.lock:
                        runtime.werewolf_teams[token] = team

        def _project_event(event: dict[str, Any]) -> dict[str, Any] | None:
            if not isinstance(event, dict):
                return None

            private_to = event.get("privateTo")
            if private_to and private_to != token:
                return None

            e = dict(event)
            _record_viewer_state(e)

            if _is_review_mode():
                return e

            et = str(e.get("type") or "")
            viewer_role = _viewer_role()
            is_werewolf = viewer_role == "werewolf"
            wolf_team = _werewolf_team()

            public_categories = {"白天讨论", "发言", "PK发言"}
            wolf_private_categories = {"狼人讨论", "狼人投票", "狼人投票结果"}

            if et in {"agent_message", "conference_message"}:
                category = str(e.get("category") or "")
                is_public = category in public_categories or category.startswith("PK发言")
                if not is_public:
                    if not (is_werewolf and category in wolf_private_categories):
                        return None

                agent_id = str(e.get("agentId") or "")
                allow_thought = is_werewolf and agent_id in wolf_team
                if not allow_thought:
                    e["thought"] = ""
                    e["behavior"] = ""
                    speech = str(e.get("speech") or "").strip()
                    if speech:
                        e["content"] = speech
                e.pop("role", None)
                return e

            if et == "agent_typing":
                category = str(e.get("category") or "")
                is_public = category in public_categories or category.startswith("PK发言") or "遗言" in category
                if not is_public:
                    if not (is_werewolf and category.startswith("狼人")):
                        return None
                return e

            return e

        q, snapshot = bus.subscribe()
        try:
            # 先发送历史缓冲（回放）
            if snapshot:
                chronological = list(reversed(snapshot))
                projected_chrono: list[dict[str, Any]] = []
                for raw in chronological:
                    if not isinstance(raw, dict):
                        continue
                    projected = _project_event(raw)
                    if projected is not None:
                        projected_chrono.append(projected)
                await ws.send_json({"type": "historical", "events": list(reversed(projected_chrono))})

            while True:
                # 同时等待：客户端消息（用于 ping）或服务端新事件
                try:
                    recv_task = asyncio.create_task(ws.receive_text())
                    send_task = asyncio.create_task(q.get())
                    done, pending = await asyncio.wait(
                        {recv_task, send_task}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for p in pending:
                        p.cancel()

                    for d in done:
                        if d is recv_task:
                            raw = d.result()
                            # 基础 ping/pong
                            if raw:
                                try:
                                    msg = json.loads(raw)
                                    if isinstance(msg, dict) and msg.get("type") == "ping":
                                        await ws.send_json({"type": "pong"})
                                        continue
                                    if isinstance(msg, dict) and msg.get("type") in {"player_action", "player_ready"}:
                                        with runtime.lock:
                                            allowed = runtime.human_token and token and runtime.human_token == token
                                            q_action = runtime.action_queue
                                        if allowed and q_action is not None:
                                            try:
                                                q_action.put_nowait(msg)
                                            except Exception:
                                                pass
                                except Exception:
                                    # 忽略非 JSON 文本
                                    pass
                        else:
                            event = d.result()
                            if not isinstance(event, dict):
                                continue
                            projected = _project_event(event)
                            if projected is None:
                                continue
                            await ws.send_json(projected)
                except WebSocketDisconnect:
                    break
                except Exception:
                    continue
        finally:
            bus.unsubscribe(q)

    return app


app = create_app()
