"""把服务器发来的数据包渲染成 QQ 消息。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import config
from .i18n import boss_name, progress_name, rank_name
from .models import get_file

#: 背包各分区在扁平物品列表中的下标范围
#: (与上游 CaiBotLite 的 NetItem 顺序一致: 179=垃圾桶单格, 180-219=熔炉,
#:  220-259=虚空, 290/320=换装方案2/3; 当前装备即方案1, 用 装备栏/染料栏)
SLOTS: list[tuple[str, int, int]] = [
    ("主背包", 0, 59),
    ("装备栏", 59, 79),
    ("染料栏", 79, 89),
    ("饰品栏", 89, 99),
    ("存钱罐", 99, 139),
    ("安全箱", 139, 179),
    ("垃圾桶", 179, 180),
    ("熔炉", 180, 220),
    ("虚空保险箱", 220, 260),
    ("装备方案2", 290, 310),
    ("染料方案2", 310, 320),
    ("装备方案3", 320, 340),
    ("染料方案3", 340, 350),
]

#: 服务器没有下发名称时的兜底物品名
FALLBACK_ITEMS: dict[int, str] = {
    8: "铜矿",
    9: "铁矿",
    10: "银矿",
    11: "金矿",
    71: "铜币",
    72: "银币",
    73: "金币",
    331: "铁锭",
    332: "铜锭",
    333: "银锭",
    334: "金锭",
}


@dataclass
class RenderResult:
    """渲染结果。"""

    text: str = ""
    image: str = ""
    file: str = ""
    file_name: str = ""
    quote: bool = False
    extras: list[str] = field(default_factory=list)


def _names(payload: dict[str, Any], key: str) -> dict[str, str]:
    raw = payload.get(key)
    return raw if isinstance(raw, dict) else {}


def _item_name(net_id: int, names: dict[str, str]) -> str:
    return names.get(str(net_id)) or FALLBACK_ITEMS.get(net_id) or f"物品#{net_id}"


def _join(items: list[str], empty: str = "-") -> str:
    return "、".join(items) if items else empty


# ---------------------------------------------------------------- 玩家列表


def render_player_list(payload: dict[str, Any]) -> RenderResult:
    server_name = payload.get("server_name") or config.server_name
    players = [str(p) for p in (payload.get("player_list") or [])]
    online = payload.get("current_online", 0)
    maximum = payload.get("max_online", 0)
    process = payload.get("process") or ""

    lines = [f"【{server_name}】", f"在线: {online}/{maximum}"]
    if process:
        lines.append(f"进度: {process}")
    lines.append(f"玩家: {_join(players, '暂无玩家在线')}")
    return RenderResult(text="\n".join(lines))


# ---------------------------------------------------------------- 进度


def render_progress(payload: dict[str, Any]) -> RenderResult:
    # 文本模式: 服务器(尤其 tModLoader 服)直接给一段可显示的文本, 不带结构化字段
    if payload.get("is_text"):
        return RenderResult(
            text=str(payload.get("text") or "").strip() or "服务器没有返回进度信息"
        )

    world = payload.get("world_name") or "未知世界"
    process: dict[str, Any] = payload.get("process") or {}
    kills: dict[str, Any] = payload.get("kill_counts") or {}
    locks: dict[str, Any] = payload.get("boss_lock") or {}

    lines = [f"【{world}】"]

    flags = []
    if payload.get("drunk_world"):
        flags.append("醉酒")
    if payload.get("zenith_world"):
        flags.append("天顶")
    if flags:
        lines.append(f"世界类型: {'/'.join(flags)}")

    # 世界吞噬者 / 克苏鲁之脑三个 key 表示同一档进度, 单独处理避免重复或漏显:
    # 合并 key 为真表示两边都过了(醉酒/天顶世界), 否则分别看各自的单项 key
    combined_key = "Eater of Worlds or Brain of Cthulhu"
    done = [
        boss_name(k)
        for k, v in process.items()
        if v and k not in (combined_key, "Eater of Worlds", "Brain of Cthulhu")
    ]
    if process.get(combined_key):
        done.append(boss_name(combined_key))
    else:
        if process.get("Eater of Worlds"):
            done.append(boss_name("Eater of Worlds"))
        if process.get("Brain of Cthulhu"):
            done.append(boss_name("Brain of Cthulhu"))
    if done:
        lines.append("已击败: " + _join(done))

    if kills:
        top = sorted(
            ((boss_name(k), v) for k, v in kills.items() if isinstance(v, int) and v > 0),
            key=lambda x: x[1],
            reverse=True,
        )
        if top:
            lines.append("击杀次数: " + "、".join(f"{n}×{c}" for n, c in top[:10]))

    if locks:
        lines.append("进度锁: " + _join([f"{boss_name(k)}({v})" for k, v in locks.items()]))

    if len(lines) == 1:
        lines.append("还没有任何进度记录~")

    return RenderResult(text="\n".join(lines))


# ---------------------------------------------------------------- 背包


def render_look_bag(payload: dict[str, Any], target: str = "") -> RenderResult:
    if not payload.get("exist"):
        return RenderResult(text=f"没有找到玩家 {target}" if target else "没有找到该玩家")

    # 文本模式: 服务器(尤其 tModLoader 服)直接给一段可显示的文本
    if payload.get("is_text"):
        return RenderResult(
            text=str(payload.get("text") or "").strip() or "服务器没有返回背包信息"
        )

    name = payload.get("name") or target or "该玩家"
    item_names = _names(payload, "item_names")
    buff_names = _names(payload, "buff_names")
    enhance_names = _names(payload, "enhance_names")

    lines = [f"【{name} 的背包】"]
    lines.append(f"生命: {payload.get('life', '-')}  魔力: {payload.get('mana', '-')}")
    quests = payload.get("quests_completed", 0)
    if quests:
        lines.append(f"渔夫任务: {quests}")

    # inventory 与 TShock 的 NetItem 一一对应, 下标就是格子位置。
    # 空格子(net_id 为 0)必须原位保留, 不能从列表里剔除——否则后面的格子
    # 会整体前移, 装备/饰品/存钱罐全被切错区间。展示时再跳过空格子。
    items: list[tuple[int, int]] = []
    for entry in payload.get("inventory") or []:
        try:
            net_id, stack = int(entry[0]), int(entry[1])
        except (TypeError, ValueError, IndexError):
            net_id, stack = 0, 0
        items.append((net_id, stack))

    filled = [(net_id, stack) for net_id, stack in items if net_id != 0 and stack > 0]

    if filled:
        for title, start, end in SLOTS:
            part = [
                f"{_item_name(net_id, item_names)}×{stack}"
                for net_id, stack in items[start:end]
                if net_id != 0 and stack > 0
            ]
            if part:
                lines.append(f"{title}: " + "、".join(part))
    else:
        lines.append("背包空空如也")

    buffs = [b for b in (payload.get("buffs") or []) if isinstance(b, int) and b > 0]
    if buffs:
        lines.append(
            "状态: "
            + _join([_item_name(b, buff_names) for b in buffs])
        )

    enhances = [e for e in (payload.get("enhances") or []) if isinstance(e, int) and e > 0]
    if enhances:
        lines.append("永久强化: " + _join([_item_name(e, enhance_names) for e in enhances]))

    economic = payload.get("economic") or {}
    if isinstance(economic, dict):
        extra = [
            str(economic.get(key) or "").strip()
            for key in ("Coins", "LevelName", "Skill")
        ]
        extra = [item for item in extra if item]
        if extra:
            lines.append("经济: " + " | ".join(extra))

    result = RenderResult(text="\n".join(lines))

    # 结构化数据齐全时优先画图(与上游菜姬一致的观感); 素材缺失/绘制失败回退文本
    if config.bag_image:
        try:
            from .bag_image import render_bag_base64

            image = render_bag_base64(payload)
        except Exception as exc:  # 画图挂了不能连文本都发不出
            from nonebot.log import logger

            logger.warning(f"查背包图片渲染失败, 回退纯文本: {exc}")
            image = None
        if image:
            return RenderResult(image=f"base64://{image}")

    return result


# ---------------------------------------------------------------- 排行


def render_rank(payload: dict[str, Any], page: int = 1) -> RenderResult:
    if not payload.get("rank_type_support", True):
        supported = payload.get("support_rank_types") or []
        return RenderResult(text="不支持的排行类型, 支持: " + _join([str(s) for s in supported]))

    if not payload.get("arg_support", True):
        args = payload.get("support_args") or []
        message = payload.get("message") or ""
        return RenderResult(text=(str(message) + "\n" + _join([str(a) for a in args])).strip())

    rank = payload.get("rank")
    if not isinstance(rank, dict):
        return RenderResult(text="没有拿到排行数据")

    title = rank_name(str(rank.get("title") or "排行"))
    lines = rank.get("rank_lines") or {}
    if not lines:
        return RenderResult(text=f"【{title}】\n暂无数据")

    # 翻页: 每页 rank_limit 条, 与上游 build_rank 一致把页码夹在合法范围内
    limit = max(1, config.rank_limit)
    items = list(lines.items())
    total_pages = max(1, (len(items) + limit - 1) // limit)
    page = max(1, min(page, total_pages))
    chunk = items[(page - 1) * limit : page * limit]

    text = [f"【{title}】"]
    for index, (player, value) in enumerate(chunk, (page - 1) * limit + 1):
        text.append(f"{index}. {player} - {value}")
    if total_pages > 1:
        text.append(f"第 {page}/{total_pages} 页, 每页 {limit} 条; 翻页: 排行 <类型> [参数] [页码]")
    return RenderResult(text="\n".join(text))


# ---------------------------------------------------------------- 插件列表


def render_plugins(payload: dict[str, Any]) -> RenderResult:
    plugins = payload.get("plugins") or []
    # TShock 直接把 C# 插件对象序列化了, 键名是大写的 Name/Author/Version
    dicts = [p for p in plugins if isinstance(p, dict)]
    # 与上游一致按名称排序, tModLoader 服(is_mod)时标题用 MOD 列表
    dicts.sort(key=lambda x: str(x.get("Name") or x.get("name") or ""))
    title = "MOD 列表" if payload.get("is_mod") else "插件列表"

    lines: list[str] = []
    for item in dicts:
        name = item.get("Name") or item.get("name") or "(未命名)"
        version = item.get("Version") or item.get("version") or ""
        author = item.get("Author") or item.get("author") or ""
        lines.append(f"{name} v{version}" if version else str(name))
        if author and str(author) not in ("None", ""):
            lines.append(f"    作者: {author}")
    # 不是对象的条目(理论上不该有)排在最后, 保证计数不丢
    lines.extend(str(p) for p in plugins if not isinstance(p, dict))

    if not lines:
        return RenderResult(text=f"服务器没有安装任何{'MOD' if payload.get('is_mod') else '插件'}")

    header = f"【{title}】共 {len(plugins)} 个"
    limit = max(1, config.rank_limit) * 4
    if len(lines) > limit:
        lines = lines[:limit] + [f"... 还有 {len(lines) - limit} 行省略"]
    return RenderResult(text="\n".join([header, *lines]))


# ---------------------------------------------------------------- 商店条件


def render_conditions(payload: dict[str, Any]) -> RenderResult:
    unmet = payload.get("unmet_conditions") or []
    if not unmet:
        return RenderResult(text="条件已全部满足")
    return RenderResult(text="未满足的条件: " + _join([progress_name(str(c)) for c in unmet]))


# ---------------------------------------------------------------- 指令输出


def render_command_output(payload: dict[str, Any]) -> RenderResult:
    output = payload.get("output") or []
    if isinstance(output, str):
        output = [output]
    if not output:
        return RenderResult(text="指令执行完毕(没有输出)")

    text = "\n".join(str(line) for line in output)
    if len(text) > 3000:
        text = text[:3000] + "\n……(输出过长已截断)"
    return RenderResult(text=text)


# ---------------------------------------------------------------- 附件


def render_file(package: dict[str, Any], reachable: bool = True) -> RenderResult | None:
    """渲染地图图片 / .map / .wld。

    ``reachable`` 为 False 表示 TShock 提供的下载链接在机器人这边打不开
    (两台机器不在同一网络且 TShock 没有公网地址), 这时只能退回 base64 内联。
    """
    payload = package.get("payload") or {}
    info = get_file(package)

    if info and reachable:
        url = str(info.get("url") or "")
        if url:
            name = str(info.get("name") or "文件")
            size = int(info.get("size") or 0)
            kind = str(info.get("kind") or "file")
            size_text = f"{size / 1024 / 1024:.2f}MB" if size > 1024 * 1024 else f"{size // 1024}KB"

            if kind == "image":
                return RenderResult(text=f"地图已生成({size_text})", image=url)

            return RenderResult(text=f"{name}({size_text})", file=url, file_name=name)

    inline = decode_inline_image(payload.get("base64"))
    if inline:
        note = "" if info else "(服务器未开启文件外发, 直接内联发送)"
        if info and not reachable:
            note = "(下载链接不可达, 直接内联发送)"
        return RenderResult(text=f"地图已生成{note}", image=f"base64://{inline}")

    if info:
        return RenderResult(
            text=(
                f"{info.get('name') or '文件'}发送失败: 服务器地址在本机不可达\n"
                "请让管理员检查 TShock 端的『本服公开地址』, 或用内网穿透暴露 17779 端口"
            )
        )

    if payload.get("too_large"):
        return RenderResult(
            text=(
                "文件发不出去: 服务器既没给下载链接(检查 TShock 端 OneBot.本服公开地址),"
                "内容也超过了内联上限(OneBot.内联附件上限)"
            )
        )

    return None


def decode_inline_image(raw: Any) -> str | None:
    """服务器内联发来的图片 -> 可直接放进 ``base64://`` 的 base64 文本。

    TShock 端的 ``Utils.CompressBase64`` 是对 base64 **文本**的 UTF-8 字节做 gzip,
    所以这里解出来应该是一段 base64 文本; 万一对方直接压的是原始字节,
    就再补一次 base64 编码, 两种情况都能用。
    """
    if not raw:
        return None

    try:
        import base64
        import binascii
        import gzip

        data = gzip.decompress(base64.b64decode(str(raw)))
    except (ValueError, OSError, binascii.Error):
        return None

    try:
        text = data.decode("ascii").strip()
    except UnicodeDecodeError:
        return base64.b64encode(data).decode()

    # 校验它确实是一段 base64, 否则退回"原始字节"的情况
    try:
        if base64.b64decode(text, validate=True):
            return text
    except (ValueError, binascii.Error):
        pass

    return base64.b64encode(data).decode()


# ---------------------------------------------------------------- 通用


def render_error(payload: dict[str, Any]) -> RenderResult:
    error = str(payload.get("error") or "未知错误")
    lines = [line.strip() for line in error.splitlines() if line.strip()]
    head = lines[0] if lines else "未知错误"
    if len(head) > 200:
        head = head[:200] + "……"
    return RenderResult(text=f"服务器处理请求时出错: {head}")


def render(package: dict[str, Any], reachable: bool = True, page: int = 1) -> RenderResult:
    """按数据包类型渲染。``page`` 只对 rank_data 有意义(客户端侧翻页)。"""
    payload = package.get("payload") or {}
    package_type = str(package.get("type") or "")

    if package_type in ("map_image", "map_file", "world_file"):
        return render_file(package, reachable) or RenderResult(
            text="服务器没有开启文件外发功能, 请检查 TShock 端的 OneBot 配置"
        )

    if package_type == "player_list":
        return render_player_list(payload)
    if package_type == "progress":
        return render_progress(payload)
    if package_type == "look_bag":
        return render_look_bag(payload, str(payload.get("name") or ""))
    if package_type == "rank_data":
        return render_rank(payload, page)
    if package_type == "plugin_list":
        return render_plugins(payload)
    if package_type == "shop_condition":
        return render_conditions(payload)
    if package_type == "call_command":
        return render_command_output(payload)
    if package_type == "error":
        return render_error(payload)

    return RenderResult(text=f"收到未处理的数据包: {package_type}")
