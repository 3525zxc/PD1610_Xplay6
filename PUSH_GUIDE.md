# GitHub 上传操作卡（PD1610 项目）

准备状态：本地仓库 `D:/xplay6/github_pd1610` 已 `git init` + 首次提交完成，
**1047 个跟踪文件 / 19,603,128 B（18.7 MiB）**，commit `3114499`。
无需再 `git add` / `git commit`，只差推送。

---

## 先说结论：不用代理行不行

| 通道 | 实测（2026-11-15 00:00） | 结论 |
|---|---|---|
| HTTPS 直连 `github.com:443` | `curl` 首页偶尔 200，但 `git ls-remote` **0/10 成功**（`Connection was reset`） | ❌ 不可靠 |
| SSH `ssh.github.com:443` | TCP + SSH 握手成功，返回 `Permission denied (publickey)` | ✅ 通道通，只差公钥 |
| 走 Clash `127.0.0.1:7897` | 全局 git 配置已指向它，开软件即可用 | ✅ 最省事 |

**关键发现**：你的全局 git 配置有
```
http.proxy  = http://127.0.0.1:7897
https.proxy = http://127.0.0.1:7897
```
GitHub Desktop 的 git 会读它。我已在**本仓库**把这两个覆盖成空（`file:.git/config`），
不影响你别的项目。所以本仓库现在是纯直连状态。

---

## 路线 A：真·不用代理（推荐，SSH over 443）

### 1. 把公钥加到 GitHub（只需做一次）

打开 https://github.com/settings/keys → **New SSH key**
- Title: `pd1610-win-443`
- Key type: Authentication Key
- Key: 粘贴下面这一整行

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFmQCjBOx+8HRzSPBUSRiOwJ+RD58MnAU3/+YrHpt0+K pd1610-github-443
```

> 私钥在 `C:\Users\Tse\.ssh\id_ed25519_github443`（无口令）。
> SSH 配置追加了独立别名 `github-443` → `ssh.github.com:443`，
> 原配置备份在 `config.bak_pd1610`，不会影响你其他 SSH 主机。

### 2. 在 GitHub 网页建一个**空**仓库

https://github.com/new
- Repository name 例：`pd1610-kernel-research`
- Public / Private 随你（公开按你之前决定）
- **不要**勾 `Add a README` / `.gitignore` / license（本地已有，勾了会冲突）

建完后页面会显示仓库地址，记下 `你的用户名/仓库名`。

### 3. 推送（一条命令， Git Bash 里执行）

```bash
cd /d/xplay6/github_pd1610
bash push_github_443.sh <你的用户名> <仓库名>
```

脚本会：设 remote 为 `git@github-443:用户/仓库.git` → 测 SSH 连通 → `git push -u origin main`。
失败会打印具体原因，不会假装成功。

### 4. 让它出现在 GitHub Desktop（可选，纯管理用）

Desktop → `File` → `Add Local Repository...` → 选 `D:\xplay6\github_pd1610` → `Add repository`。
之后 Desktop 里能看到历史、改动；推送/拉取会沿用仓库里已设好的 SSH remote。

> 注意：不要用 Desktop 的 **Publish repository** 按钮走这条路 —— 它默认建 HTTPS remote，
> 而 HTTPS 直连在你这台机器上实测不通。用上面的脚本推完再 Add 进来最稳。

---

## 路线 B：开 Clash Verge，全程 GitHub Desktop 图形界面

1. 启动 `D:\MOJIE1\Clash Verge`，确认系统代理开、`127.0.0.1:7897` 在监听。
2. 打开 GitHub Desktop（已登录）→ `File` → `Add Local Repository...` → 选 `D:\xplay6\github_pd1610`。
3. 右上角点 **Publish repository** → 填名字、选 Public/Private → 取消 `Keep this code private`（若要公开）→ `Publish Repository`。

但本仓库的 `http.proxy` 已被我置空，走这条路线需要临时恢复代理：

```bash
cd /d/xplay6/github_pd1610
git config --local http.proxy  http://127.0.0.1:7897
git config --local https.proxy http://127.0.0.1:7897
```

想切回直连：
```bash
git config --local http.proxy  ""
git config --local https.proxy ""
```

---

## 「上传更快」的实际做法

你的仓库只有 18.7 MiB、1047 个小文件，**瓶颈是连接建立，不是带宽**。已替你设好的：

| 配置 | 值 | 作用 |
|---|---|---|
| `http.version` | `HTTP/1.1` | 避开国内常见的 HTTP/2 stream reset / `RPC failed` |
| `http.postBuffer` | `524288000` | 避免大 pack 被分块限流 |
| `core.autocrlf` | `false` | 不改写换行，避免 1047 个文件被误判改动 |
| `http.proxy` / `https.proxy` | 空 | 本仓库直连，不受全局代理影响 |
| SSH `ServerAliveInterval` | 30 | 长连接保活，减少重连 |

另外三条有效的：

1. **一次推完**：全部文件已在单个 commit 里，别在 Desktop 里分批 add/commit，重复打包只会更慢。
2. **避开晚高峰**：23:00–01:00 国际出口最挤，实测刚才这段时间 HTTPS 10 连全断；早上 8–11 点直连成功率明显高。
3. **用有线或 5GHz**：你现在是 `WLAN`，2.4G 抖动会放大 TLS 重置；换 5GHz 比调任何 git 参数都管用。

如果 `git push` 中途断，直接重跑同一条命令即可（git 会续传未完成的 pack，不会重复传已有的对象）。

---

## 校验推送成功

```bash
cd /d/xplay6/github_pd1610
git ls-remote origin main          # 应返回与本地相同的 3114499...
```
或网页打开仓库，确认 `README.md`、`offline/12_ai_handoff_index.md`、`prebuilt/` 三个入口都在。

---

## 边界

- 本卡写于 2026-11-15 00:05；`git ls-remote` 直连 HTTPS 的实测结果是**当时**的，网络状况会变。
- 公钥尚未添加到 GitHub（需你操作），因此 **SSH 完整链路未验证**；只验证到「TCP + SSH 握手到达 GitHub 认证层」。
- 尚未执行任何 push；本地 commit 已完成，不会丢失。
