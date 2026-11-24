# TeleVip 1.6.12 — 本地解锁版（社区补丁）

> 这不是官方版本。这是对 **Re: TeleVIP 1.6.12** 的本地修改版，去掉了
> 服务器判决、付费门控和「盗版判定」弹窗，让模块内置的功能在本地全部可用。
>
> 只用于研究 LSPosed 模块的校验机制。要不要装、装在哪台设备，风险自负。

## 为什么会有这个

**Re: TeleVIP** 是开源项目 [TeleVip](https://github.com/mustafa1dev/TeleVip-LSPosed)
（**GPL-3.0**）的续作，作者在 README 里也承认：

> "Mustafa (@mustafa1dev) is the original author of TeleVip
> (mustafa1dev/TeleVip-LSPosed), which Re: TeleVIP continues."
>
> "From 1.5.4 the source code is not published… Versions up to 1.5.3 stay under GPL-3.0."

也就是说：**1.5.3 及以前是按 GPL-3.0 发布的，1.5.4 起闭源并开始卖订阅**
（$1.99/月、$19.99/年）。而这个版本的 APK 里仍然保留着上游的命名空间
（`com.my.televip.base.*`、`com.my.televip.xposed.*`）和配置文件 `TeleVip.xml`。

GPL-3.0 允许收费，但要求衍生作品继续以 GPL 分发、并向接收者提供对应源码。
本仓库据此提供该版本的本地修改，供已获得该程序的人研究与自用。

## 装了什么

| 项目 | 说明 |
|---|---|
| 版本 | 1.6.12（versionCode 390） |
| 包名 | `io.github.re_televip.televip` |
| 签名 | 社区重签（与原版不同，**不能覆盖安装原版**，需先卸载） |
| 需要 | LSPosed / Vector（API 102）或 LSPatch；Android 8.1+ |
| 大小 | 826,499 字节 |

`SHA256SUMS.txt` 里是校验值，装之前建议自己对一遍。

## 安装

1. 卸载已安装的 Re: TeleVIP（官方版或旧破解版都行），保留 Telegram 本身。
2. 安装本仓库 Release 里的 `TeleVip-1.6.12-unlocked.apk`。
3. LSPosed/Vector → 模块 → 启用 **Re: TeleVIP** → 作用域勾选你的 Telegram 客户端。
4. **强制停止** Telegram，再打开。
5. 打开 Telegram → 设置 → 顶部应出现 **「Re: TeleVIP 设置 🛸」**。

> 只改 dex，不改资源；装不上/入口不出现，先看 LSPosed 日志
> （`/data/adb/lspd/log/verbose_*.log`）里有没有 `Failed to load class`
> 或 `No module class loaded`。

## 改了什么

详见 [PATCHES.md](PATCHES.md)（只列行为变化，不含实现细节）。一句话版：

- 去掉签名自检（不再因为重签而全功能失效）
- 付费状态恒为「已激活」（显示有效期至 2038-01-19）
- 不再采信服务器下发的 `CloneKillVerdict`（不再弹 Unauthorized copy、不再关开关）
- 不再发那条「unauthorized copy」通知

## 已知限制

- **云备份、实时广告词库**这两项依赖作者服务器，本版**无法使用**（本来也需要订阅）。
- Telegram 的**下载限速、大文件上传、真 Premium 表情**是服务端按账号校验的，任何客户端模块都绕不过。
- Telegram 每次大改内部结构，模块可能大面积失效——那是客户端兼容问题，不是本补丁的问题。
- 官方版更新后不要直接覆盖安装，会签名冲突。

## 不提供

- 不提供官方源码（1.5.4 起闭源），仓库里只有本版的修改说明与二进制。
- 不提供任何账号、激活码或服务器凭据。

## License

本仓库对 **1.5.3 及以前 GPL-3.0 部分**的修改按 GPL-3.0 提供；
对 1.5.4 之后新增代码不主张任何权利，仅作研究与兼容用途分发。
原项目名称与图标归其作者所有，本仓库与原作者无关联。
