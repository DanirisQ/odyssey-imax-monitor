# MOViE MOViE《奥德赛》IMAX 开场监控

这个小工具专门监控上海 **MOViE MOViE影城（前滩太古里店）** 的《奥德赛》IMAX 排片。

默认目标已经写好：

- 猫眼影院 ID：`37534`
- 猫眼上海城市 ID：`10`
- 电影：`奥德赛 / The Odyssey`
- 版本过滤：`IMAX`
- 时区：`Asia/Shanghai`

## 它会做什么

1. 每次运行读取猫眼影院排片。
2. 只保留《奥德赛》的 IMAX 场。
3. 用 `日期 + 开场时间 + 影厅 + 版本` 生成唯一键。
4. 第一次运行只建立基线，不发送旧场次邮件。
5. 以后只要出现从未见过的新场次：
   - 立即把“第一次看到它的时间”写入 `data/history.csv`；
   - 发一封邮件；
   - 在 `data/state.json` 里记录是否已经通知。
6. SMTP 如果临时失败，场次仍会保留为“待通知”，下一次运行会重试，不会悄悄丢提醒。

> `first_seen_at` 是程序首次抓到该场次的时间，不是影院后台真正点击“开票”的精确时间。误差上限大致等于轮询间隔，加上平台调度延迟。

## 推荐部署：GitHub Actions（无需自己开电脑）

仓库里已经放好了 `.github/workflows/monitor.yml`，默认每 5 分钟运行一次。

### 1. 新建一个 GitHub 仓库

把这个项目整个上传到仓库根目录。

### 2. 添加仓库 Secrets

进入：

`Settings -> Secrets and variables -> Actions -> New repository secret`

至少添加：

| Secret | 示例 |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | 你的发件邮箱 |
| `SMTP_PASSWORD` | Gmail App Password / QQ或163授权码 |
| `EMAIL_FROM` | 你的发件邮箱 |
| `EMAIL_TO` | 接收提醒的邮箱；多个用逗号隔开 |
| `SMTP_USE_SSL` | Gmail/QQ/163 通常填 `true` |
| `SMTP_STARTTLS` | Outlook 587 通常填 `true`，SSL 则填 `false` |

`MAOYAN_COOKIE` 是可选的。先不填；如果后续日志显示猫眼匿名访问被风控，再从浏览器复制自己在 `maoyan.com` 的 Cookie 到这个 Secret。

### 常见邮箱参数

**Gmail**

- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=465`
- `SMTP_USE_SSL=true`
- `SMTP_STARTTLS=false`
- `SMTP_PASSWORD` 使用 Google App Password，不是普通登录密码。

**Outlook / Microsoft 365**

- `SMTP_HOST=smtp.office365.com`
- `SMTP_PORT=587`
- `SMTP_USE_SSL=false`
- `SMTP_STARTTLS=true`

**QQ 邮箱**

- `SMTP_HOST=smtp.qq.com`
- `SMTP_PORT=465`
- `SMTP_USE_SSL=true`
- 密码位置填 SMTP 授权码。

**163 邮箱**

- `SMTP_HOST=smtp.163.com`
- `SMTP_PORT=465`
- `SMTP_USE_SSL=true`
- 密码位置填客户端授权码。

### 3. 手动跑第一次

进入仓库的 **Actions** 页，选择 `Monitor MOViE MOViE Odyssey IMAX`，点 **Run workflow**。

第一次只会把当时已经存在的 IMAX 场写入基线，不会把旧场次发给你。

之后一旦影院新增场次，邮件标题大概长这样：

`[MOViE MOViE] 奥德赛新增 IMAX 场次：08/19 09:40；08/20 13:10`

## 本地运行

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入 SMTP
python -m odyssey_monitor
```

如果你想在自己的服务器/NAS上更快轮询，可以用系统 cron 每 1 分钟运行一次：

```cron
* * * * * cd /path/to/movie_movie_odyssey_monitor && /path/to/.venv/bin/python -m odyssey_monitor >> monitor.log 2>&1
```

这种方式比 GitHub Actions 更接近“开票就提醒”，因为 GitHub 的定时任务虽然写成 5 分钟，但繁忙时可能发生调度延迟。

## 记录文件

`data/history.csv` 会保留所有首次发现的场次，例如：

```csv
show_key,movie,show_date,start_time,hall,version,language,source_id,source,first_seen_at
2026-08-19|09:40|imax 激光厅|英语imax2d,奥德赛,2026-08-19,09:40,IMAX 激光厅,英语IMAX2D,英语IMAX2D,,maoyan-mobile-json,2026-08-17T23:41:12+08:00
```

以后你就可以分析 MOViE MOViE 通常在一天中的什么时间放出次日/后日 IMAX 排片。

## 抓取策略

程序先请求猫眼移动端影院排片 JSON；如果没有得到可识别结果，再尝试解析猫眼桌面影院页。解析器对猫眼历史上常见的字段名和页面 class 做了兼容。

如果猫眼启用验证码/更严格风控，最常见的解决办法是提供 `MAOYAN_COOKIE`。不要把 Cookie 直接写进代码或提交到公开仓库，始终放 GitHub Secret。

## 注意

- 请保持低频、个人使用；不要把它改造成高并发抓取器。
- 猫眼页面/API属于第三方服务，结构以后可能变化；如果日志开始持续报“no matching screenings”，需要更新解析器。
- 这个工具只提醒“新增排片”，不会自动下单、抢座或付款。
