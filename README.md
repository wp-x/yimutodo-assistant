# 一木清单 AI 助理

让 AI Agent 通过非官方 API 查询和管理一木清单。支持自然语言触发，也可以单独使用命令行工具。

> 本项目来自网页端接口逆向，与一木清单官方无关。接口升级后可能失效。

## 给 Agent：读取后执行安装

如果用户要求安装这个项目，请完成下面的操作，不要只把命令发给用户：

1. 确认当前 Agent 的全局 Skill 目录。优先读取运行环境或配置提供的路径，不要猜测。
   - Codex：`~/.codex/skills`
   - Claude Code：`~/.claude/skills`
   - 通用 Agent 兼容目录：`~/.agents/skills`
   - Kimi、zcode 或其他 Agent：读取自身配置；没有原生 Skill 机制时，把仓库放进用户指定目录并直接调用 CLI。
2. 将仓库克隆到 `<技能目录>/yimutodo-assistant`。目标已存在时先检查用户改动，不要直接覆盖。
3. 运行 `python3 -m pip install -r requirements.txt`。
4. 将 `.env.example` 复制为 `.env`，执行 `chmod 600 .env`。
5. 告诉用户 `.env` 的完整路径，引导用户在本地填入 Cookie。不要要求用户把 Cookie 发到聊天、日志或 Issue。
6. 用户配置完成后运行 `python3 scripts/yimutodo_cli.py status`。成功后提醒用户重启或重新加载 Agent。

`.env` 内容：

```dotenv
YIMUTODO_COOKIE='vertx-web.session=替换为用户自己的值'
```

安装完成后，用自然语言完成一次只读查询。涉及删除项目、清空回收站、永久删除、修改密码等操作时，必须先获得用户明确授权。

## 给用户：它能做什么

- 查询、创建、修改和完成任务
- 管理项目、标签、任务组、提醒、习惯和打卡
- 识别“明天下午三点”这类中文时间
- 查询回收站和专注记录
- 通过“一木清单”“帮我记个待办”等自然语言触发

例如：

```text
帮我在一木清单添加一个明天下午三点取快递的任务。
查看一木清单里还没完成的任务。
把“取快递”标记为完成。
```

说出“一木清单”可以减少 Agent 把请求误判成系统日历或浏览器操作。

## 手动安装

需要 Python 3.10 或更高版本。以通用 Agent 目录为例：

```bash
git clone https://github.com/wp-x/yimutodo-assistant.git ~/.agents/skills/yimutodo-assistant
cd ~/.agents/skills/yimutodo-assistant
python3 -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

登录 [一木清单网页版](https://www.yimutodo.com)，按 `F12` 打开开发者工具，在 Application（应用）→ Cookies 中找到 `vertx-web.session`，填入 `.env`。

Cookie 等同于登录状态。项目已通过 `.gitignore` 排除 `.env`，仍需避免把它粘贴到聊天、Issue、截图或公开仓库。

`yimutodo_cookie_tools/` 提供了可选油猴脚本。它申请 `GM_cookie` 和 `GM_setClipboard` 权限，只读取一木清单域名下的 session 并复制到剪贴板。不了解油猴权限时，使用开发者工具手动复制。

## 命令行

```bash
python3 scripts/yimutodo_cli.py status
python3 scripts/yimutodo_cli.py projects
python3 scripts/yimutodo_cli.py tasks --status open
python3 scripts/yimutodo_cli.py add-task "取快递"
python3 scripts/yimutodo_cli.py complete TASK_ID
```

完整接口与字段见 [API 参考](references/api-reference.md)。

## 使用限制

- Cookie 过期时会返回 `errorCode=1000004`，重新登录并更新 `.env` 即可。
- 提醒、重复和打卡需要严格的字段组合与毫秒时间戳。
- 所有写入都会直接修改用户的真实数据。
- 不同 Agent 的 Skill 目录和自动触发机制可能不同，CLI 可以独立运行。

## License

[MIT](LICENSE)
