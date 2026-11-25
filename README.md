# TeleVip 1.7.1 — 本地解锁版（社区补丁）

> 这不是官方版本。这是对 **Re: TeleVIP 1.7.1** 的本地修改版，去掉了
> 服务器判决、付费门控和「盗版判定」弹窗，让模块内置的功能在本地全部可用。
>
> 只用于研究 LSPosed 模块的校验机制，仅供学习交流，请在下载后的24小时内删除

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
| 版本 | 1.7.1（versionCode 392） |
| 包名 | `io.github.re_televip.televip` |
| 签名 | 社区重签 `CN=ReTeleVip Unlocked`（与官方版、与 1.6.12 版都不同，**不能覆盖安装**；1.7 → 1.7.1 是同一把 key，可直接覆盖升级） |
| 需要 | LSPosed / Vector（API 102）或 LSPatch；Android 8.1+（minSdk 27） |
| 大小 | 957,706 字节 |

`SHA256SUMS.txt` 里是校验值，装之前建议自己对一遍。

## 从仓库旧版升级

- 从 **1.7** 升级：同一把 key，直接装 `TeleVip-1.7.1-unlocked.apk` 覆盖即可，设置和作用域都保留。
- 从 **1.6.12** 或官方版升级：签名不同，**必须卸载**后重装：

1. 卸载旧版（Telegram 本体保留）。
2. 安装 Release 里的 `TeleVip-1.7.1-unlocked.apk`。
3. LSPosed/Vector 里重新给模块勾作用域（卸载模块会清掉勾选）。
4. 模块设置会丢，重新按需打开；`TeleVip.xml` 里的 `CloneKill*` 等残留键不影响使用。

## 安装

1. 卸载已安装的 Re: TeleVIP（官方版或其它破解版都行），保留 Telegram 本身。
2. 安装本仓库 Release 里的 `TeleVip-1.7.1-unlocked.apk`。
3. LSPosed/Vector → 模块 → 启用 **Re: TeleVIP** → 作用域勾选你的 Telegram 客户端。
4. **强制停止** Telegram，再打开。
5. 打开 Telegram → 设置 → 顶部应出现 **「Re: TeleVIP 设置 🛸」**。

> 只改 dex，不改资源；装不上/入口不出现，先看 LSPosed 日志
> （`/data/adb/lspd/log/verbose_*.log`）里有没有 `Failed to load class`
> 或 `No module class loaded`。

## 改了什么

详见 [PATCHES.md](PATCHES.md)（只列行为变化，不含实现细节）。一句话版：

- 付费状态恒为「已激活」（显示有效期至 **2100-01-01**，不限制账号数）
- 不再采信服务器下发的 `CloneKillVerdict`；通知弹窗本体也一并短路（不再弹 Unauthorized copy、开关不会被重置）
- 模块自报的构建身份伪装成官方签名证书，服务端看到的也是「官方构建」
- 远端「高级版分级表」不再生效，所有 ⭐ 项按普通功能处理

## 1.7.1 相对 1.7 的变化（上游）

- 修复 LSPatch 嵌入后的启动器图标（新增 `LauncherIcon` / `LauncherIconReceiver`）
- 设置里加了「检查更新」入口；时间显示改用系统相对时间格式
- 框架识别细化（区分 `:lspatch` / `:vector`）
- 校验机制未变，仍为凭证验签 + 订阅状态 + 服务器盗版判决三件套

## 1.7 相对 1.6.12 的变化（上游）

- 新增免费试用凭证（FreePass）；高级版细则与名单仍由服务器下发（`/premium/spec`、`/premium/adlist`）
- 更新器改为可直接调起安装（新增 `REQUEST_INSTALL_PACKAGES` 权限）
- 语言包扩充（ta / ur / uk / ko 等），设置项与钩子位点随 Telegram 新版本调整
- 「盗版判定」机制未变，仍由服务器下发签名判决

## 已知限制

- **云备份、实时广告/诈骗词库刷新**这两项依赖作者服务器，本版**无法使用**（本来也需要订阅）。
- 「实时广告和诈骗名单」的开关与匹配读的是本地缓存（`TeleVip.xml` 里的 `PremiumAdListText`），
  缓存有内容就能用，但「立即刷新」永远失败。
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
