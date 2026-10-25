"""把 look_bag 的结构化数据渲染成背包全景图。

布局、坐标、槽位顺序完整移植上游 CaiBotLite 的
``caibotlite/services/lookbag.py``(LookBag.get_bag_png): 仿游戏界面、
图标作区域标签(猪猪=存钱罐/保险箱/熔炉/虚空/数字牌=换装方案)、
玩家名顶部居中、左下 "By Cai" 式页脚。素材来自其 assets 目录,
需先复制到本插件目录的 assets/ 下。

槽位顺序(与上游一致, 也同步在 render.SLOTS 里):
    0-49   主背包(5x10, 热键栏+背包)      50-57  弹药/装备(2x4)
    59-78  装备(当前方案, 2列x10)         79-88  染料(1列x10)
    89-98  饰品/坐骑(2x5)                 99-138 存钱罐(4x10)
    139-178 安全箱(4x10)                  179    垃圾桶(1格)
    180-219 熔炉(4x10)                    220-259 虚空保险箱(4x10)
    260-289 未使用                        290-319 换装方案2(装备+染料)
    320-349 换装方案3(装备+染料)

素材或 Pillow 缺失、绘制出错时返回 None, 调用方(render.render_look_bag)
自动回退纯文本。
"""

from __future__ import annotations

import base64
import io
import time
from pathlib import Path
from typing import Any

from nonebot.log import logger

try:
    from PIL import Image, ImageDraw, ImageFont

    _PIL_OK = True
except ImportError:  # pragma: no cover - 容器里没装 Pillow 时整个机器人不该挂
    _PIL_OK = False

def _find_asset_dir() -> Path:
    """素材目录查找: 优先插件自带的 assets/, 其次向上级目录找(仓库布局:
    插件目录与 assets/ 同级), 最后试当前工作目录。都找不到时返回默认路径,
    让缺素材告警给出准确的位置提示。"""
    here = Path(__file__).resolve().parent
    candidates = [here / "assets"]
    candidates += [parent / "assets" for parent in here.parents[:4]]
    candidates.append(Path.cwd() / "assets")
    for candidate in candidates:
        if (candidate / "images" / "items").is_dir():
            return candidate
    return here / "assets"


ASSET_DIR = _find_asset_dir()
FONT_PATH = ASSET_DIR / "fonts" / "LXGWWenKaiMono-Medium.ttf"
ITEM_DIR = ASSET_DIR / "images" / "items"
BUFF_DIR = ASSET_DIR / "images" / "buffs"
BACKGROUND = ASSET_DIR / "images" / "backgrounds" / "Background_4.png"

#: tModLoader 模组物品的负数 net_id -> 原版占位物品图标(抄自上游 NET_DEFAULTS)
NET_DEFAULTS: dict[int, int] = {
    -1: 3521, -2: 3520, -3: 3519, -4: 3518, -5: 3517, -6: 3516, -7: 3515,
    -8: 3514, -9: 3513, -10: 3512, -11: 3511, -12: 3510, -13: 3509, -14: 3508,
    -15: 3507, -16: 3506, -17: 3505, -18: 3504, -19: 3764, -20: 3765,
    -21: 3766, -22: 3767, -23: 3768, -24: 3769, -25: 3503, -26: 3502,
    -27: 3501, -28: 3500, -29: 3499, -30: 3498, -31: 3497, -32: 3496,
    -33: 3495, -34: 3494, -35: 3493, -36: 3492, -37: 3491, -38: 3490,
    -39: 3489, -40: 3488, -41: 3487, -42: 3486, -43: 3485, -44: 3484,
    -45: 3483, -46: 3482, -47: 3481, -48: 3480,
}

_fonts: dict[int, Any] = {}
_images: dict[str, Any] = {}
_warned_assets = False


# ------------------------------------------------------------------ 素材加载

def _font(size: int) -> Any:
    if size not in _fonts:
        try:
            _fonts[size] = ImageFont.truetype(str(FONT_PATH), size)
        except OSError:
            _fonts[size] = ImageFont.load_default()
    return _fonts[size]


def _open(rel: str) -> Any:
    """按相对路径读 assets 下的图片(带缓存), 失败返回 None。"""
    if rel not in _images:
        path = ASSET_DIR / rel
        try:
            _images[rel] = Image.open(path).convert("RGBA") if path.is_file() else None
        except Exception:
            _images[rel] = None
    return _images[rel]


def _buff_icon(buff_id: int) -> Any:
    return _open(f"images/buffs/Buff_{buff_id}.png")


def _resize(rel: str, size: int) -> Any:
    key = f"rz_{rel}_{size}"
    if key not in _images:
        image = _open(rel)
        if image is not None:
            image = image.resize((size, size), Image.LANCZOS)
        _images[key] = image
    return _images[key]


def _paste(canvas: Any, image: Any, pos: tuple[int, int]) -> None:
    if image is not None:
        canvas.paste(image, pos, image)


# ------------------------------------------------------------------ 绘制

def _draw_item(canvas: Any, draw: Any, x: int, y: int, net_id: int, stack: int) -> None:
    """画一格物品: 负数 id 先按 NET_DEFAULTS 换算, 没图标画灰色占位框。

    物品图标与格子底图同为 52x52, 原尺寸直贴即可对齐(同上游)。
    """
    if net_id == 0 or stack <= 0:
        return
    if net_id < 0:
        net_id = NET_DEFAULTS.get(net_id, 0)
    icon = _open(f"images/items/Item_{net_id}.png") if net_id else None
    if icon is not None:
        _paste(canvas, icon, (x, y))
    else:
        draw.rounded_rectangle(
            (x + 4, y + 4, x + 48, y + 48), 5,
            fill=(96, 96, 108, 210), outline=(140, 140, 155, 255), width=1,
        )
    if stack not in (0, 1):
        draw.text((x + 6, y + 30), str(stack), font=_font(14),
                  fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))


def _draw_buff(canvas: Any, x: int, y: int, buff_id: int) -> None:
    if buff_id == 0:
        return
    _paste(canvas, _buff_icon(buff_id), (x, y))


def _grid_backs(canvas: Any, back: Any, x: int, rows: int, cols: int, y: int, step: int) -> None:
    """铺一片空格子底图(先铺底再画物品, 与上游一致)。"""
    if back is None:
        return
    for row in range(rows):
        for col in range(cols):
            canvas.paste(back, (x + col * step, y + row * back.height), back)


def render_bag_image(payload: dict[str, Any]) -> bytes | None:
    """渲染背包全景图(上游布局), 失败返回 None(调用方回退文本)。"""
    if not _PIL_OK:
        return None

    global _warned_assets
    if not FONT_PATH.is_file() or not ITEM_DIR.is_dir():
        if not _warned_assets:
            _warned_assets = True
            logger.warning(
                f"查背包图片渲染缺少素材(需要 {ASSET_DIR} 下的 fonts/ 与 images/items/), "
                "已回退纯文本。素材来自上游 CaiBotLite 仓库的 assets 目录"
            )
        return None

    inv = _parse_inventory(payload)
    name = str(payload.get("name") or "玩家")

    # 画布: 直接用背景图原尺寸(上游 Background_4.png), 缺失则 1920x1080 纯色
    background = _open("images/backgrounds/Background_4.png")
    if background is not None:
        canvas = background.copy()
    else:
        canvas = Image.new("RGBA", (1920, 1080), (24, 26, 34, 255))
    draw = ImageDraw.Draw(canvas)

    # 各分区用的格子底图与图标(文件名与上游一致)
    back1 = _open("images/items/Inventory_Back.png")        # 背包格
    back2 = _open("images/items/Inventory_Back11.png")      # 容器格
    back3 = _open("images/items/Inventory_Back7.png")       # 装备格(浅)
    back4 = _open("images/items/Inventory_Back8.png")       # 装备格
    back5 = _open("images/items/Inventory_Back3.png")       # 染料格
    back6 = _open("images/items/Inventory_Back12.png")      # 垃圾桶格
    if back1 is None:
        # 没有底图素材时退回自画格子, 保证布局仍可辨认
        back1 = Image.new("RGBA", (48, 48), (52, 46, 92, 200))
        back2 = Image.new("RGBA", (48, 48), (94, 42, 42, 200))
        back3 = Image.new("RGBA", (48, 48), (52, 46, 92, 200))
        back4 = Image.new("RGBA", (48, 48), (52, 46, 92, 200))
        back5 = Image.new("RGBA", (48, 48), (72, 60, 108, 200))
        back6 = Image.new("RGBA", (48, 48), (94, 42, 42, 200))
    w1, h1 = back1.size
    w2, h2 = back2.size
    w3 = back3.size[0]
    w4 = back4.size[0]

    def slot(i: int) -> tuple[int, int]:
        return inv[i] if 0 <= i < len(inv) else (0, 0)

    # ── 玩家名: 顶部居中, 超过 7 个字用小号字体(同上游) ─────────────
    if len(name) > 7:
        f_name, name_y = _font(60), 15
    else:
        f_name, name_y = _font(100), 0
    box = draw.textbbox((0, 0), name, font=f_name)
    draw.text(((canvas.width - (box[2] - box[0])) / 2, name_y), name,
              font=f_name, fill=(255, 255, 255))

    # ── 左列: 主背包 5x10 (0-49), 小背包图标 ────────────────────────
    _paste(canvas, _resize("images/items/Item_5343.png", 70), (150 - 60, 110))
    _grid_backs(canvas, back1, 150, 5, 10, 120, w1)
    for h in range(5):
        for i in range(10):
            net_id, stack = slot(h * 10 + i)
            _draw_item(canvas, draw, 150 + i * w1, h1 * h + 120, net_id, stack)

    # ── 中列: 存钱罐 4x10 (99-138), 猪猪图标 ───────────────────────
    _paste(canvas, _resize("images/items/Item_87.png", 80), (740 - 65, h2 * 2))
    _grid_backs(canvas, back2, 740, 4, 10, 120, w2)
    for h in range(4):
        for i in range(10):
            net_id, stack = slot(99 + h * 10 + i)
            _draw_item(canvas, draw, 740 + i * w2, h2 * h + 120, net_id, stack)

    # ── 右列: 安全箱(139-178) / 熔炉(180-219) / 虚空(220-259) ──────
    for y0, start, icon, icon_y in (
        (120, 139, "images/items/Item_346.png", h2 * 2 + 5),
        (120 + 280, 180, "images/items/Item_3813.png", h2 * 2 + 25 + 265),
        (120 + 560, 220, "images/items/Item_4076.png", h2 * 2 + 25 + 280 + 265),
    ):
        _paste(canvas, _resize(icon, 70), (1330 - 60, icon_y))
        _grid_backs(canvas, back2, 1330, 4, 10, y0, w2)
        for h in range(4):
            for i in range(10):
                net_id, stack = slot(start + h * 10 + i)
                _draw_item(canvas, draw, 1330 + i * w2, h2 * h + y0, net_id, stack)

    # ── 装备区三组(各 3 列 x 10 行): 当前方案(59-88)/方案2(290)/方案3(320)
    #    列序与上游一致: 最右=装备前10, 中=装备后10, 最左=染料;
    #    每组左侧配数字牌图标(2703/2704/2705 = 方案 1/2/3) ──────────
    for x0, plate, base in (
        (150, "images/items/Item_2703.png", 59),    # 当前装备, 数字牌 1
        (350, "images/items/Item_2704.png", 290),   # 方案 2
        (550, "images/items/Item_2705.png", 320),   # 方案 3
    ):
        _paste(canvas, _resize(plate, 70), (x0 - 60, 120 + 280 + 20))
        for row in range(10):
            canvas.paste(back3, (x0, h2 * row + 120 + 280 + 30), back3)
            canvas.paste(back4, (x0 + w3, h2 * row + 120 + 280 + 30), back4)
            canvas.paste(back5, (x0 + w3 + w4, h2 * row + 120 + 280 + 30), back5)
        for col in range(3):
            # col 0->最右(装备前10), 1->中(装备后10), 2->最左(染料)
            x = x0 + w3 + w4 if col == 0 else (x0 + w3 if col == 1 else x0)
            for row in range(10):
                net_id, stack = slot(base + col * 10 + row)
                _draw_item(canvas, draw, x, h2 * row + 120 + 280 + 30, net_id, stack)

    # ── 饰品/坐骑 2x5 (89-98), 矿车图标 ────────────────────────────
    _paste(canvas, _resize("images/items/Item_2343.png", 65), (755 - 60, 125 + 280 + 15))
    for h in range(5):
        canvas.paste(back1, (750, h2 * h + 120 + 280 + 30), back1)
        canvas.paste(back1, (750 + w2, h2 * h + 120 + 280 + 30), back1)
    for h in range(5):
        net_id, stack = slot(89 + h)
        _draw_item(canvas, draw, 750 + w2, h2 * h + 120 + 280 + 30, net_id, stack)
        net_id, stack = slot(94 + h)
        _draw_item(canvas, draw, 750, h2 * h + 120 + 280 + 30, net_id, stack)

    # ── 弹药/装备 2x4 (50-57), 箭矢图标; 第 5 行是垃圾桶(179) ──────
    _paste(canvas, _resize("images/items/Item_40.png", 70), (915 - 65, 120 + 280 + 20))
    for h in range(4):
        canvas.paste(back1, (900, h2 * h + 120 + 280 + 30), back1)
        canvas.paste(back1, (900 + w2, h2 * h + 120 + 280 + 30), back1)
    for h in range(4):
        net_id, stack = slot(50 + h)
        _draw_item(canvas, draw, 900, h2 * h + 120 + 280 + 30, net_id, stack)
        net_id, stack = slot(54 + h)
        _draw_item(canvas, draw, 900 + w2, h2 * h + 120 + 280 + 30, net_id, stack)

    trash_y = h2 * 4 + 120 + 280 + 30
    canvas.paste(back6, (900, trash_y), back6)
    canvas.paste(back6, (900 + w2, trash_y), back6)
    _paste(canvas, _open("images/items/Trash.png"), (900 + 10, trash_y + 10))
    net_id, stack = slot(179)
    _draw_item(canvas, draw, 900 + w2, trash_y, net_id, stack)

    # ── Buff 区 8x6, 红药图标 ─────────────────────────────────────
    buffs = [b for b in (payload.get("buffs") or []) if isinstance(b, int) and b != 0]
    if buffs:
        _paste(canvas, _resize("images/items/Item_678.png", 70), (712 - 15, 120 + 600 + 8))
        for index, buff_id in enumerate(buffs[:48]):
            _draw_buff(
                canvas, 750 + 34 * (index % 8), 120 + 600 + 30 + 34 * (index // 8), buff_id,
            )

    # ── 玩家信息面板: 书图标 + 生命/魔力/渔夫/永久强化 ──────────────
    _paste(canvas, _resize("images/items/Item_149.png", 70), (915 + 50 + 50, 120 + 280 + 20))
    draw.text((915 + 50 + 60 + 50, 120 + 280 + 30), "玩家信息",
              font=_font(38), fill=(0, 0, 0))

    _paste(canvas, _resize("images/items/Item_58.png", 70), (915 + 50 + 60, 120 + 280 + 30 + 30 + 15))
    draw.text((915 + 50 + 60 + 50, 120 + 280 + 30 + 30 + 30),
              "生命:" + str(payload.get("life", "-")), font=_font(30), fill=(255, 106, 106))

    _paste(canvas, _resize("images/items/Item_184.png", 70), (915 + 50 + 60, 120 + 280 + 30 + 30 + 15 + 40))
    draw.text((915 + 50 + 60 + 50, 120 + 280 + 30 + 30 + 30 + 40),
              "魔力:" + str(payload.get("mana", "-")), font=_font(30), fill=(30, 144, 255))

    quests = payload.get("quests_completed") or 0
    rod = "images/items/Item_2294.png" if quests >= 50 else "images/items/Item_2296.png"
    rod_y = 120 + 280 + 30 + 30 + 30 + 40 + (40 if quests >= 50 else 30)
    _paste(canvas, _resize(rod, 50), (915 + 50 + 70, rod_y))
    draw.text((915 + 50 + 60 + 50, 120 + 280 + 30 + 30 + 30 + 40 + 40),
              f"渔夫任务数:{quests}次", font=_font(30),
              fill=(255, 223, 0) if quests >= 50 else (0, 0, 205))

    enhances = [e for e in (payload.get("enhances") or []) if isinstance(e, int) and e > 0]
    _paste(canvas, _resize("images/items/Item_4382.png", 50),
           (915 + 50 + 70, 120 + 280 + 30 + 30 + 30 + 40 + 40 + 30))
    if not enhances:
        draw.text((915 + 50 + 60 + 50, 120 + 280 + 30 + 30 + 30 + 40 + 40 + 40),
                  "永久增益:无", font=_font(30), fill=(112, 128, 144))
    else:
        draw.text((915 + 50 + 60 + 50, 120 + 280 + 30 + 30 + 30 + 40 + 40 + 40),
                  "永久增益:", font=_font(30), fill=(255, 20, 147))
        for index, net_id in enumerate(enhances[:14]):
            _draw_item(canvas, draw,
                       915 + 50 + 60 + 50 + 130 + 35 * index,
                       120 + 280 + 30 + 30 + 30 + 40 + 40 + 30 + 5, net_id, 1)

    # ── 经济插件信息 ──────────────────────────────────────────────
    economic = payload.get("economic")
    if isinstance(economic, dict) and str(economic.get("Coins") or ""):
        _paste(canvas, _resize("images/items/Item_5336.png", 70), (915 + 50 + 50, 250 + 120 + 280 + 20))
        draw.text((915 + 50 + 60 + 50, 250 + 120 + 280 + 30),
                  "Economic", font=_font(38), fill=(138, 43, 226))
        _paste(canvas, _resize("images/items/Item_3817.png", 50), (915 + 50 + 70, 250 + 120 + 280 + 30 + 30 + 22))
        draw.text((915 + 50 + 60 + 50, 250 + 120 + 280 + 30 + 30 + 30),
                  str(economic.get("Coins")), font=_font(30), fill=(255, 215, 0))

        line = economic.get("Coins") and str(economic["Coins"]).count("\n") + 1 or 1
        if str(economic.get("LevelName") or ""):
            _paste(canvas, _resize("images/items/Item_490.png", 50),
                   (915 + 50 + 70, 250 + 120 + 280 + 30 + 30 + 22 + 40 * line))
            draw.text((915 + 50 + 60 + 50, 250 + 120 + 280 + 30 + 30 + 30 + 40 * line),
                      str(economic["LevelName"]), font=_font(30), fill=(30, 144, 255))
            line += 1
        if str(economic.get("Skill") or ""):
            _paste(canvas, _resize("images/items/Item_903.png", 50),
                   (915 + 50 + 70, 250 + 120 + 280 + 30 + 30 + 22 + 40 * line))
            draw.text((915 + 50 + 60 + 50, 250 + 120 + 280 + 30 + 30 + 30 + 40 * line),
                      str(economic["Skill"]), font=_font(30), fill=(0, 0, 205))

    # ── 页脚: 署名 + 时间戳(同上游位置) ───────────────────────────
    footer_y = canvas.height - 40
    draw.text((10, footer_y), "By CaiBotLite", font=_font(30), fill=(255, 255, 255))
    draw.text((250, footer_y), time.strftime("%Y-%m-%d %H:%M:%S"),
              font=_font(30), fill=(255, 255, 255))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _parse_inventory(payload: dict[str, Any]) -> list[tuple[int, int]]:
    """inventory 与格子一一对应, 坏条目原位补空, 保证下标即格子。"""
    inv: list[tuple[int, int]] = []
    for entry in payload.get("inventory") or []:
        try:
            inv.append((int(entry[0]), int(entry[1])))
        except (TypeError, ValueError, IndexError):
            inv.append((0, 0))
    return inv


def render_bag_base64(payload: dict[str, Any]) -> str | None:
    """渲染结果转 base64 文本, 可直接拼进 ``base64://`` 消息段。"""
    data = render_bag_image(payload)
    if data is None:
        return None
    return base64.b64encode(data).decode()
