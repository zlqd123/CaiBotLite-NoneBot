"""CaiBotLite 数据包与桥接协议。

桥接协议非常薄: 一条 WebSocket / HTTP 通道上流动的每一行都是一个信封::

    {"v": 1, "secret": "密钥", "package": "CaiBotLite 数据包(JSON字符串)"}

``package`` 就是 TShock 端使用的原始数据包, 因此两端可以各自独立演进.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from .config import config

PROTOCOL_VERSION = 1

TARGET_KEY = "__bridge"
FILE_KEY = "__file"

#: 各种数据包的协议版本, 与上游参考实现(caibotlite/enums/package_type.py、docs/api.md)保持一致
PACKAGE_VERSIONS: dict[str, str] = {
    "hello": "2025.7.18",
    "whitelist": "2025.12.18",
    "player_list": "2025.7.18",
    "progress": "2025.7.18",
    "look_bag": "2025.7.18",
    "world_file": "2025.7.18",
    "map_file": "2025.7.18",
    "map_image": "2025.7.18",
    "self_kick": "2025.7.18",
    "call_command": "2025.7.18",
    "unbind_server": "2025.7.18",
    "heartbeat": "2025.7.25",
    "rank_data": "2025.7.25",
    "plugin_list": "2025.7.25",
    "shop_buy": "2025.7.25",
    "shop_condition": "2025.7.25",
    "error": "2026.2.14",
    "unknown": "2007.5.24",
}

_SNAKE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def to_snake_case(name: str) -> str:
    """把 ``EyeOfCthulhu`` 转换成 ``eye_of_cthulhu``, 与 Newtonsoft 行为一致。"""
    return _SNAKE_BOUNDARY.sub("_", name).lower()


class ReplyTarget:
    """一条消息应该回复到哪里。

    QQ 官方 Bot 只认 openid(字符串), 因此这里的 group_id / user_id / message_id
    全部是字符串: 群=group_openid, 人=user_openid / member_openid。
    ``event`` 保留原始事件引用, 供发送层走 ``bot.send()`` 被动回复
    (不参与 to_dict 序列化, 不会写进桥接数据包)。
    """

    __slots__ = (
        "self_id",
        "group_id",
        "user_id",
        "message_id",
        "session",
        "at_sender",
        "nickname",
        "is_admin",
        "file_mode",
        "event",
    )
    def __init__(
        self,
        self_id: str = "",
        group_id: str = "",
        user_id: str = "",
        message_id: str = "",
        session: str = "",
        at_sender: bool = False,
        nickname: str = "",
        is_admin: bool = False,
        file_mode: str = "",
        event: Any = None,
    ) -> None:
        self.self_id = self_id
        self.group_id = group_id
        self.user_id = user_id
        self.message_id = message_id
        self.session = session
        self.at_sender = at_sender
        self.nickname = nickname
        self.is_admin = is_admin
        # 附件外发偏好: link=用下载链接(默认), inline=让服务器直接 base64 内联
        self.file_mode = file_mode
        # 原始事件引用(不序列化)
        self.event = event

    @classmethod
    def from_event(cls, event: Any) -> ReplyTarget:
        """从消息事件构造回复目标。

        兼容 QQ 官方适配器(群=group_openid, 人=user/member_openid, 消息 id=event.id)
        与 OneBot v11(群号/用户号/message_id)两种事件, 字段统一为字符串。
        """
        author = getattr(event, "author", None)
        nickname = ""
        if author is not None:
            nickname = getattr(author, "username", "") or ""
        if not nickname:
            sender = getattr(event, "sender", None)
            if sender is not None:
                nickname = getattr(sender, "card", "") or getattr(sender, "nickname", "") or ""

        return cls(
            self_id=str(getattr(event, "self_id", "") or ""),
            group_id=str(getattr(event, "group_openid", "") or getattr(event, "group_id", "") or ""),
            user_id=str(event.get_user_id() or ""),
            message_id=str(getattr(event, "id", "") or getattr(event, "message_id", "") or ""),
            at_sender=False,
            nickname=nickname,
            event=event,
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "self_id": self.self_id,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "message_id": self.message_id,
            "session": self.session,
            "at_sender": self.at_sender,
            "nickname": self.nickname,
            "is_admin": self.is_admin,
        }
        if self.file_mode:
            data["file_mode"] = self.file_mode
        return data

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<ReplyTarget group={self.group_id} user={self.user_id}>"


def build_package(
    package_type: str,
    payload: dict[str, Any] | None = None,
    *,
    is_request: bool = True,
    request_id: str | None = None,
    target: ReplyTarget | None = None,
) -> dict[str, Any]:
    """构造一个 CaiBotLite 数据包。"""
    body: dict[str, Any] = dict(payload or {})
    if target is not None:
        body[TARGET_KEY] = target.to_dict()

    return {
        "version": PACKAGE_VERSIONS.get(package_type, "2025.7.18"),
        "direction": "to_server",
        "type": package_type,
        "is_request": is_request,
        "request_id": request_id or uuid.uuid4().hex,
        "payload": body,
    }


def build_envelope(package: dict[str, Any]) -> str:
    """把数据包包装成桥接信封。"""
    return json.dumps(
        {
            "v": PROTOCOL_VERSION,
            "secret": config.secret,
            "package": json.dumps(package, ensure_ascii=False),
        },
        ensure_ascii=False,
    )


def parse_envelope(raw: str) -> dict[str, Any] | None:
    """解析桥接信封, 返回其中的 CaiBotLite 数据包。"""
    try:
        envelope = json.loads(raw)
    except (TypeError, ValueError):
        return None

    if not isinstance(envelope, dict):
        return None

    if envelope.get("secret") != config.secret:
        return None

    package = envelope.get("package")
    if isinstance(package, str):
        try:
            package = json.loads(package)
        except ValueError:
            return None

    if not isinstance(package, dict) or "type" not in package:
        return None

    return package


def get_target(package: dict[str, Any]) -> ReplyTarget | None:
    """取出数据包里的回复目标。"""
    raw = (package.get("payload") or {}).get(TARGET_KEY)
    if not isinstance(raw, dict):
        return None

    return ReplyTarget(
        self_id=str(raw.get("self_id", "") or ""),
        group_id=str(raw.get("group_id", "") or ""),
        user_id=str(raw.get("user_id", "") or ""),
        message_id=str(raw.get("message_id", "") or ""),
        session=str(raw.get("session", "") or ""),
        at_sender=bool(raw.get("at_sender", False)),
        nickname=str(raw.get("nickname", "") or ""),
        is_admin=bool(raw.get("is_admin", False)),
    )


def get_file(package: dict[str, Any]) -> dict[str, Any] | None:
    """取出数据包里的附件信息。"""
    raw = (package.get("payload") or {}).get(FILE_KEY)
    return raw if isinstance(raw, dict) else None
