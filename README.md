# CaiBotLite-NoneBot（QQ 官方 Bot 版）

通过 **QQ 官方机器人**（NoneBot2 `adapter-qq`，群聊 `qq_group_openid` 通道）
接入 **TShock CaiBotLite**：群里一条指令查世界进度、看在线玩家、翻背包（**仿游戏界面的
背包全景图**）、拉排行榜，还能改时间、造天气、下载地图与存档。

```
QQ 群(@机器人) ──官方 Bot WS──▶  NoneBot 插件  ──WebSocket──▶  TShock 插件  ──▶  你的服务器
                (adapter-qq, openid)          (CaiBotLite.dll)
                        ↑ 本仓库(qqbot 分支)     ↑ 见下方"TShock 端"
```

> **分支说明**：本分支（`qqbot`）为 QQ 官方 Bot 适配版（v2.0.0，标识符全部为
> 字符串 openid）；**OneBot v11 版（v1.1.0，Lagrange / NapCat / LLOneBot）在
> [`NoneBot` 分支](https://github.com/zlqd123/CaiBotLite-NoneBot/tree/NoneBot)**，
> 两版互相独立，按机器人通道二选一。

- **不经过官方 CaiBot 机器人**，数据全在自己手上。
- **玩家登录完全不经过机器人**，进服走 TShock 自己的 `/login` `/register` 和 SSC。
- 桥接双向（`auto` 模式监听+主动连两条都试），**跨网络只要一端有公网地址就能配通**。
- 群聊**只收 @ 消息**，指令需写成 `@机器人 /泰拉 进度`（根指令名必须显式出现）；
  标识符全部为字符串 openid（群=`group_openid`，人=`user_openid` / `member_openid`）；
  发送统一走 adapter-qq：被动回复 `bot.send(event)`，服务器推送走
  `send_to_group` / `send_to_c2c`。

- **不经过官方 CaiBot 机器人**，数据全在自己手上。
- **玩家登录完全不经过机器人**，进服走 TShock 自己的 `/login` `/register` 和 SSC。
- 桥接双向（`auto` 模式监听+主动连两条都试），**跨网络只要一端有公网地址就能配通**。

| 相关仓库 | 内容 |
| --- | --- |
| [`nonebot_plugin_caibotlite/`](nonebot_plugin_caibotlite/) | **NoneBot 插件本体** |
| [`assets/`](assets/) | 图片渲染素材（物品 / 增益图标、字体、背景，出自上游） |
| [CaiBotLitePlugin](https://github.com/zlqd123/CaiBotLitePlugin-nonebot) | TShock 端插件（源码 + 编译好的 DLL） |
| [UnrealMultiple/TShockPlugin](https://github.com/UnrealMultiple/TShockPlugin) | 上游官方 TShock 插件仓库 |
| [UnrealMultiple/CaiBotLite](https://github.com/UnrealMultiple/CaiBotLite) | 上游官方 QQ 机器人参考实现（本仓库 `caibotlite/` 目录即其副本，仅作参考） |

---

## 安装

### 1. TShock 端

先装好 TShock 端插件（两个 DLL 丢进 `ServerPlugins/`、`/cbl onebot` 改配置），
详细步骤见 **[CaiBotLitePlugin 的 README](https://github.com/zlqd123/CaiBotLitePlugin-nonebot)**。

### 2. 机器人端

NoneBot2 接入 **QQ 官方机器人适配器 adapter-qq**（`nonebot-plugin-adapter-qq`，
在 QQ 开放平台创建机器人、配置 WS 回调），然后：

```bash
pip install pydantic-settings websockets httpx Pillow
```

把插件放进你的 NoneBot 工程（两种方式任选）：

```text
方式 A（推荐，直接用本仓库的素材）:
  把本仓库整个克隆到机器人旁，然后把 nonebot_plugin_caibotlite/ 目录
  拷进（或软链到）你机器人的 plugins/ 里。
  插件会自动向上查找到与本目录同级的 assets/，素材开箱即用。

方式 B（只拷两个目录，保持并列）:
  把 nonebot_plugin_caibotlite/ 和 assets/ 两个目录一起拷进 plugins/：
  plugins/
  ├── nonebot_plugin_caibotlite/
  └── assets/
```

最后在 `pyproject.toml`（或启动插件的配置）里声明
`plugins = ["nonebot_plugin_caibotlite"]`（或放入 `plugin_dirs` 指定的目录）。

`.env` 里至少填（**全部是 openid 字符串，不是 QQ 号**）：

```dotenv
CAIBOTLITE__SECRET=和 TShock 端一致的通讯密钥
CAIBOTLITE__MODE=auto
CAIBOTLITE__ADMINS=["机器人管理员的 user_openid"]
CAIBOTLITE__DEFAULT_GROUP=服务器主动发消息时默认回送的群 openid
```

---

## 配置项

全部前缀 `CAIBOTLITE__`，写进 `.env`。只列常用的，完整定义见
[`config.py`](nonebot_plugin_caibotlite/config.py)：

| 配置 | 默认 | 说明 |
| --- | --- | --- |
| `SECRET` | 空 | **必填**，与 TShock 端 `通讯密钥` 一致 |
| `MODE` | `auto` | `auto` / `client`(主动连 TShock) / `server`(监听) / `http`(HTTP 推送) |
| `SERVER_URL` | `ws://127.0.0.1:17779/onebot/v11/ws` | TShock 端地址（client/auto 模式用） |
| `LISTEN_HOST` / `LISTEN_PORT` / `LISTEN_PATH` | `0.0.0.0` / `8080` / `/caibotlite` | server 模式监听参数 |
| `SERVER_NAME` | `Terraria 服务器` | 展示用服务器名，握手后会被服务器名覆盖 |
| `DEFAULT_GROUP` | `""` | 服务器主动发来的消息默认回送到哪个群（**群 openid**） |
| `GROUPS` | `[]` | 允许使用机器人的群 openid 列表，空 = 不限制 |
| `ADMINS` / `SUPERUSERS` | `[]` | 机器人管理员 / 超级管理员的 openid（群管理身份**不算**） |
| `PREFIX` / `ROOTS` | `["", "/", "。"]` / `["泰拉", "tl"]` | 指令前缀与根指令名 |
| `COMMANDS_PATH` | 空 | 指令表 `commands.json` 路径，空 = 用插件自带那份 |
| `RANK_LIMIT` | `10` | 排行榜每页条数 |
| `BAG_IMAGE` | `true` | 查背包渲染成图片；素材缺失或绘制失败自动回退纯文本 |
| `REQUEST_TIMEOUT` / `FILE_REQUEST_TIMEOUT` | `15` / `60` | 普通请求 / 地图存档类大请求超时（秒） |
| `DEBUG` | `false` | 打印桥接数据与每条收到的指令 |

### 连通性

| 谁能被访问到 | TShock 端 `OneBot通道` | 机器人端 `MODE` | 谁去连谁 |
| --- | --- | --- | --- |
| **TShock** 有公网 IP/域名 | `server`（监听 17779） | `client`（主动连） | 机器人 → TShock |
| **机器人** 有公网 IP/域名 | `client`（主动连） | `server`（监听 8080） | TShock → 机器人 |
| 不确定 / 两边都行 | `auto` | `auto` | 两条都试，先通的生效 |

---

## 指令

**所有指令都必须写成 `@机器人 /泰拉 xxx`**（官方 Bot 群聊只收 @ 消息，根指令名
`泰拉` 或简写 `tl` 必须显式出现）。指令表在
[`commands.json`](nonebot_plugin_caibotlite/commands.json) 里，**没写死在代码中**，
改 JSON 即生效，`/泰拉 帮助` 的内容也完全由它生成。

### 对所有人开放

| 指令 | 说明 |
| --- | --- |
| `/泰拉 帮助` | 指令列表 |
| `/泰拉 进度` | 世界进度、已击败 BOSS、击杀次数、进度锁 |
| `/泰拉 在线` | 在线人数与玩家列表 |
| `/泰拉 排行 <类型> [参数] [页码]` | `boss 史莱姆王`、`死亡`、`在线`、`钓鱼`、`货币 金币`；结尾纯数字当页码翻页 |
| `/泰拉 查背包 <角色名>` | **背包全景图**（仿游戏界面，见下）；素材缺失自动回退文字版 |
| `/泰拉 插件列表` | 服务器插件 / MOD 列表（按名称排序） |
| `/泰拉 服务器信息` | 游戏 / 服务端 / 适配插件版本、系统、白名单状态（不发请求） |
| `/泰拉 执行 time` | 改时间（不接参数则查看当前时间） |
| `/泰拉 执行 clear` | 停雨停风 |
| `/泰拉 执行 wind <风速>` | 调风力 |
| `/泰拉 执行 worldevent <事件>` | 造天气，如 `rain` `meteor` `bloodmoon`；不带参数服务器会自己列 |

### 需要机器人管理员

`.env` 里 `CAIBOTLITE__ADMINS` / `CAIBOTLITE__SUPERUSERS` 中的 QQ 才能用，
**群管理身份不算**。权限不足时机器人只回 `无权限`。

| 指令 | 说明 |
| --- | --- |
| `/泰拉 执行 <其它指令>` | 除默认开放以外的服务器指令 |
| `/泰拉 上传地图` | 生成并发送地图图片（需服务器装 `GenerateMap`） |
| `/泰拉 下载地图` | 发送 `.map` 文件 |
| `/泰拉 下载存档` | 发送 `.wld` 存档 |

### 查背包图片渲染

`查背包` 会用 Pillow 把结构化背包数据画成 **1920×1080 仿游戏界面全景图**：
主背包 / 存钱罐 / 安全箱 / 熔炉 / 虚空保险箱四组容器、三套换装方案（数字牌标识）、
装备 / 染料 / 饰品列、Buff 与永久强化图标、渔夫任务、经济插件信息，布局与上游菜姬一致。

- 素材即本仓库的 [`assets/`](assets/)（物品 / 增益图标、霞鹜文楷字体、背景图）；
- tModLoader 模组物品（负数 net_id）按上游映射表显示占位图标，其余画灰色占位框，**不丢格**；
- 素材缺失、Pillow 未安装或绘制出错时**自动回退纯文本**，不影响响应；
- `CAIBOTLITE__BAG_IMAGE=false` 可整体关闭图片模式。

---

## 鉴权在哪一边

**只有 TShock 端是安全边界。** 远程执行跑在 `CaiBotPlayer`（固定超管身份）上，
TShock 自身权限检查对它无效，服务端 `CaiBotLite.json` 的 `允许远程执行的指令`
是唯一拦得住东西的地方：

- 本插件的 `commands.json` 只决定"群里谁可以发什么"，拦不住拿到 `通讯密钥` 的人直连 17779；
- 机器人会从 `plugin_list` 响应读取服务端真实白名单（`allowed_commands`），
  `/泰拉 帮助` 里如实显示，若与 `commands.json` 的开放名单脱节会**启动告警**；
- 要放行新指令，只改 TShock 端一处（游戏里 `/cbl onebot exec + <指令>`）。

---

## 已下线 / 不再提供

| 功能 | 原因 |
| --- | --- |
| 白名单管理、群黑名单 | 登录不经由机器人 |
| 设备授权（`/泰拉 登录`） | 登录不经由机器人 |
| 群商店（`/泰拉 购买`） | 依赖 Economics 插件 |
| 自踢（`/泰拉 踢出`） | 不需要 |
| 角色绑定（`/泰拉 角色`） | 背包谁都能查 |

---

## 致谢与许可

- 图片渲染布局、槽位方案与全部素材来自
  [**UnrealMultiple/CaiBotLite**](https://github.com/UnrealMultiple/CaiBotLite)
  （官方 QQ 机器人参考实现）；
- TShock 端协议与数据包设计来自
  [**UnrealMultiple/TShockPlugin**](https://github.com/UnrealMultiple/TShockPlugin)；
- QQ 官方机器人接入基于 [nonebot-adapter-qq](https://github.com/nonebot/adapter-qq)
  （QQ 开放平台机器人协议）；OneBot v11 版实现见
  [`NoneBot` 分支](https://github.com/zlqd123/CaiBotLite-NoneBot/tree/NoneBot)。

本仓库以 **GPL-3.0** 发布（与 TShock 端 [CaiBotLitePlugin](https://github.com/zlqd123/CaiBotLitePlugin-nonebot) 一致），
`caibotlite/` 目录为上游参考实现副本，权利归其原作者所有。
