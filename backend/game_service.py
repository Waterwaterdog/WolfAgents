# -*- coding: utf-8 -*-
"""FastAPI 下运行 WolfMind 游戏的一些服务端辅助函数。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import queue
import re
import secrets
import time
import typing
from typing import Any, Callable

from agentscope.agent import AgentBase
from agentscope.message import Msg

from config import config
from core.knowledge_base import PlayerKnowledgeStore
from core.game_engine import werewolves_game

# 复用 CLI 入口中的官方 prompt 与 agent 构造函数，
# 避免在这里重复维护一大段系统提示词。
from main import get_official_agents  # noqa: E402


@dataclass
class GameStartResult:
    game_id: str


def _literal_values(annotation: Any) -> list[str]:
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return [str(x) for x in typing.get_args(annotation)]
    if origin is typing.Union:
        values: list[str] = []
        for arg in typing.get_args(annotation):
            values.extend(_literal_values(arg))
        return values
    return []


class HumanProxyAgent(AgentBase):
    def __init__(
        self,
        *,
        name: str,
        token: str,
        action_queue: queue.Queue,
        event_sink: Callable[[dict[str, Any]], None] | None,
        timeout_s: int = 90,
    ) -> None:
        super().__init__()
        self.name = name
        self._token = token
        self._q = action_queue
        self._event_sink = event_sink
        self._timeout_s = timeout_s
        self._pending: dict[str, dict[str, Any]] = {}

    def _emit(self, event: dict[str, Any]) -> None:
        if not self._event_sink:
            return
        try:
            event.setdefault("privateTo", self._token)
            self._event_sink(event)
        except Exception:
            return

    def _infer_turn_kind(self, structured_model: Any) -> str:
        fields = getattr(structured_model, "model_fields", {}) or {}
        if "vote" in fields:
            return "vote"
        if "resurrect" in fields:
            return "witch_resurrect"
        if "poison" in fields:
            return "witch_poison"
        if "shoot" in fields:
            return "hunter_shoot"
        if "name" in fields:
            return "select"
        return "speech"

    def _choices_from_model(self, structured_model: Any) -> list[str]:
        fields = getattr(structured_model, "model_fields", {}) or {}
        for key in ("vote", "name"):
            f = fields.get(key)
            if not f:
                continue
            ann = getattr(f, "annotation", None)
            vals = _literal_values(ann)
            vals = [v for v in vals if v not in {"abstain", "弃权"}]
            if vals:
                return vals
        return []

    def _wait_for_action(self, request_id: str, timeout_s: int) -> dict[str, Any] | None:
        if request_id in self._pending:
            return self._pending.pop(request_id, None)

        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            try:
                item = self._q.get(timeout=min(remaining, 1.0))
            except Exception:
                continue
            if not isinstance(item, dict):
                continue
            payload = item.get("payload")
            if not isinstance(payload, dict):
                payload = item
            rid = str(payload.get("requestId") or "").strip()
            if not rid:
                continue
            if rid == request_id:
                return payload
            self._pending[rid] = payload

    async def __call__(self, prompt: Msg, structured_model: Any = None, **kwargs: Any) -> Msg:
        request_id = secrets.token_urlsafe(10)
        kind = self._infer_turn_kind(structured_model)
        choices = self._choices_from_model(structured_model)
        self._emit(
            {
                "type": "your_turn",
                "requestId": request_id,
                "kind": kind,
                "prompt": getattr(prompt, "content", ""),
                "choices": choices,
            }
        )

        payload = await asyncio.to_thread(self._wait_for_action, request_id, self._timeout_s)

        meta: dict[str, Any] = {
            "thought": "",
            "behavior": "",
            "speech": "",
        }
        if isinstance(payload, dict):
            for k in ("thought", "behavior", "speech"):
                if payload.get(k) is not None:
                    meta[k] = str(payload.get(k) or "")
            if kind == "vote":
                v = payload.get("vote") if payload.get("vote") is not None else payload.get("target")
                if v is not None:
                    meta["vote"] = str(v)
            elif kind == "select":
                t = payload.get("name") if payload.get("name") is not None else payload.get("target")
                if t is not None:
                    meta["name"] = str(t)
            elif kind == "witch_resurrect":
                meta["resurrect"] = bool(payload.get("resurrect"))
            elif kind == "witch_poison":
                meta["poison"] = bool(payload.get("poison"))
                t = payload.get("name") if payload.get("name") is not None else payload.get("target")
                if t is not None:
                    meta["name"] = str(t)
            elif kind == "hunter_shoot":
                meta["shoot"] = bool(payload.get("shoot"))
                t = payload.get("name") if payload.get("name") is not None else payload.get("target")
                if t is not None:
                    meta["name"] = str(t)

        content = meta.get("speech") or ""
        return Msg(self.name, content, role="assistant", metadata=meta)

    async def observe(self, msg: Msg | list[Msg] | None) -> None:
        if msg is None:
            return
        items = msg if isinstance(msg, list) else [msg]
        for m in items:
            content = str(getattr(m, "content", "") or "")
            if not content:
                continue
            if content.startswith(f"[{self.name} ONLY]"):
                visible = content.split("]", 1)[-1].strip()
                self._emit({"type": "private_notice", "content": visible})
                role_m = re.search(r"your role is\s+([a-z_]+)", visible, flags=re.I)
                if role_m:
                    self._emit({"type": "your_role", "role": role_m.group(1).lower()})


def _model_label(provider: str, cfg: dict[str, str] | None) -> str:
    if provider == "openai" and cfg:
        return f"openai: {cfg.get('model_name', '')}"
    if provider == "dashscope":
        return f"dashscope: {config.dashscope_model_name}"
    if provider == "ollama":
        return f"ollama: {config.ollama_model_name}"
    return provider


def create_players(*, human: dict[str, Any] | None = None, action_queue: queue.Queue | None = None, event_sink: Callable[[dict[str, Any]], None] | None = None) -> tuple[list[AgentBase], dict[str, str]]:
    """创建 9 名玩家并返回 (agents, player_model_map)。"""

    human_enabled = bool(human and action_queue and event_sink and human.get("token"))

    model_overrides = config.openai_player_configs if config.model_provider == "openai" else [None] * 9

    agents: list[AgentBase] = []
    if human_enabled:
        agents.append(
            HumanProxyAgent(
                name="Player1",
                token=str(human.get("token")),
                action_queue=action_queue,
                event_sink=event_sink,
            )
        )
        for idx in range(1, 9):
            agents.append(get_official_agents(f"Player{idx + 1}", model_overrides[idx]))
    else:
        for idx in range(9):
            agents.append(get_official_agents(f"Player{idx + 1}", model_overrides[idx]))

    player_model_map = {
        player.name: ("human" if human_enabled and idx == 0 else _model_label(config.model_provider, model_overrides[idx]))
        for idx, player in enumerate(agents)
    }

    return agents, player_model_map


def create_knowledge_store(player_model_map: dict[str, str]) -> PlayerKnowledgeStore:
    """为本局创建并落盘一个空的知识库（经验存档）。"""

    store = PlayerKnowledgeStore(
        checkpoint_dir=config.experience_dir,
        base_filename=config.experience_id,
    )
    store.set_player_models(player_model_map)
    store.save()
    return store


async def run_game_session(*, game_id: str, event_sink=None, stop_event=None, human: dict[str, Any] | None = None, action_queue: queue.Queue | None = None) -> tuple[str, str]:
    """运行完整的一局游戏并返回 (log_path, experience_path)。"""

    is_valid, error_msg = config.validate()
    if not is_valid:
        raise RuntimeError(f"配置错误: {error_msg}")

    agents, player_model_map = create_players(human=human, action_queue=action_queue, event_sink=event_sink if callable(event_sink) else None)
    knowledge_store = create_knowledge_store(player_model_map)

    log_path, experience_path = await werewolves_game(
        agents,
        knowledge_store=knowledge_store,
        player_model_map=player_model_map,
        game_id=game_id,
        event_sink=event_sink if callable(event_sink) else None,
        shuffle_agents=not bool(human and action_queue),
        public_reveal_roles=not bool(human and action_queue),
        stop_event=stop_event,
    )

    return log_path, experience_path
