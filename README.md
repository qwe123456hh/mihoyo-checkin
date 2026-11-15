# 米游社每日签到（GitHub Actions）

- 每天 UTC 23:30（北京时间 07:30）自动签到
- 多账号：Secrets 里配置 `COOKIE_JSON_B64`、`COOKIE_JSON_B64_2` … 最多 5 个
- 看板：GitHub Pages `docs/index.html`
- 记录：`history.json`（昵称、UID 已脱敏）

## Cookie 从哪来
在手机上用米游社 App 扫码登录后，把 `cookie.json` 做 base64：
```bash
base64 -w0 cookie.json
```
把结果存进仓库 Secret `COOKIE_JSON_B64`（第二个账号用 `_2`）。

## 手动触发
Actions → mihoyo-checkin → Run workflow
