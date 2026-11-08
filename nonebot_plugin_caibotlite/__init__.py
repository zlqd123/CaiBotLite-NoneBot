"""CaiBotLite 的 NoneBot 侧适配插件(QQ 官方 Bot 版)。

与 TShock 端 ``CaiBotLite`` 插件配套使用, 通过 QQ 官方 Bot 为 Terraria 服务器
提供进度、背包、排行、地图与远程指令等功能。玩家登录不经由本插件。

.. code-block:: text

    CAIBOTLITE__SECRET=0123456789abcdef   # 与 TShock 端 OneBot.通讯密钥 一致
    CAIBOTLITE__MODE=auto                 # 跨网络时先通的那条链路生效
    CAIBOTLITE__SERVER_URL=ws://127.0.0.1:17779/onebot/v11/ws
    CAIBOTLITE__DEFAULT_GROUP=<group_openid>  # 服务器广播的默认群(openid)
"""

from nonebot.plugin import PluginMetadata

from .config import Config, config
from .plugin import CaiBotLite, get_runtime, matcher

__all__ = ["CaiBotLite", "Config", "config", "get_runtime", "matcher"]

__version__ = "2.0.0"

__plugin_meta__ = PluginMetadata(
    name="CaiBotLite",
    description="CaiBotLite 的 NoneBot 侧适配插件(进度/背包/排行/远程指令, QQ 官方 Bot)",
    usage=(
        "1. 在 TShock 端执行 /cbl onebot 复制通讯密钥\n"
        "2. 在 .env 中配置 CAIBOTLITE__SECRET 与 CAIBOTLITE__MODE(默认 auto, 跨网络也能通)\n"
        "3. 群内 @机器人 /泰拉 帮助 查看全部指令\n"
        "4. 群 openid 可通过 iinfo 或启动日志获取, 填入 CAIBOTLITE__DEFAULT_GROUP"
    ),
    type="application",
    homepage="https://github.com/zlqd123/CaiBotLite-NoneBot",
    supported_adapters={"QQ"},
)
