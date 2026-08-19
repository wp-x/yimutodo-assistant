# 一木清单 AI 助理 Skill

我平时会让 AI 帮我整理待办，但一木清单没有公开 API，AI 只能打开网页点来点去。这个项目把网页端使用的接口整理成了一个 Codex Skill 和命令行工具。装好以后，可以直接对 AI 说：

```text
帮我在一木清单里添加一个明天下午三点取快递的任务。
```

Codex 会读取这个 Skill，通过 API 查询或修改你的清单。项目基于网页端接口逆向整理，与一木清单官方无关。

## 能做什么

- 查看未完成、已完成或指定项目里的任务
- 创建、修改、完成和取消完成任务
- 查询项目、标签、任务组、提醒、习惯和打卡记录
- 调用一木清单的中文时间识别接口
- 管理回收站、专注记录和其他已整理的接口
- 在 Codex 中通过“一木清单”“帮我记个待办”等自然语言触发

删除项目、清空回收站、永久删除任务、修改密码等操作会影响真实数据。Skill 要求 AI 在执行这些操作前得到你的明确授权。

## 安装

需要 Python 3.10 或更高版本，并且已经安装 Codex。

把项目克隆到 Codex 的 Skill 目录：

```bash
git clone https://github.com/wp-x/yimutodo-assistant.git ~/.codex/skills/yimutodo-assistant
python3 -m pip install -r ~/.codex/skills/yimutodo-assistant/requirements.txt
```

如果你也使用读取 `~/.agents/skills` 的 Agent，可以再复制一份：

```bash
cp -R ~/.codex/skills/yimutodo-assistant ~/.agents/skills/yimutodo-assistant
```

安装完成后，新建一个 Codex 任务或重启 Codex，让 Skill 列表重新加载。

## 配置 Cookie

这个项目使用一木清单网页版的登录 Cookie。Cookie 等同于你的登录状态，拿到它的人可以访问你的清单。

先复制配置模板：

```bash
cd ~/.codex/skills/yimutodo-assistant
cp .env.example .env
chmod 600 .env
```

登录 [一木清单网页版](https://www.yimutodo.com)，按 `F12` 打开开发者工具，在 Application（应用）→ Cookies 中找到 `vertx-web.session`。把它写入 `.env`：

```dotenv
YIMUTODO_COOKIE='vertx-web.session=替换为你自己的值'
```

项目已经在 `.gitignore` 中排除了 `.env`。不要把 Cookie 粘贴到聊天、Issue、终端日志或公开仓库。

`yimutodo_cookie_tools/` 还提供了一个可选的油猴脚本。它申请 `GM_cookie` 和 `GM_setClipboard` 权限，用来读取一木清单域名下的 HttpOnly session 并复制到剪贴板。脚本不会向第三方服务器发送数据，但这两项权限可以接触登录凭据。不了解油猴权限时，使用开发者工具手动复制更稳妥。

## 在 AI 里使用

说出“一木清单”最容易触发：

```text
查看一木清单里还没完成的任务。
在一木清单添加一个明天下午三点取快递的任务。
把一木清单里的“取快递”标记为完成。
在一木清单创建一个每天喝八杯水的习惯。
```

需要强制指定时，可以写：

```text
使用 $yimutodo-assistant，查看我的未完成任务。
```

## 命令行用法

验证 Cookie：

```bash
python3 scripts/yimutodo_cli.py status
```

查询任务和项目：

```bash
python3 scripts/yimutodo_cli.py projects
python3 scripts/yimutodo_cli.py tasks --status open
python3 scripts/yimutodo_cli.py tasks --status all --query "快递"
```

创建和完成任务：

```bash
python3 scripts/yimutodo_cli.py add-task "取快递" --project-id 128338
python3 scripts/yimutodo_cli.py complete TASK_ID
```

其他接口可以通过统一分发命令调用：

```bash
python3 scripts/yimutodo_cli.py call TODO_TAG_ADD_V2 \
  --params '{"tagName":"工作","color":"#409EFF","positionWeight":0}'
```

完整方法和字段说明在 [API 参考](references/api-reference.md) 中。

## 已知限制

- 接口来自网页端逆向，一木清单升级后可能失效。
- Cookie 会过期，出现 `errorCode=1000004` 时需要重新登录并更新 `.env`。
- 时间字段使用毫秒时间戳，提醒、重复和打卡的字段组合比较严格。
- 普通自然语言可能被 AI 理解成系统日历。提示词里写出“一木清单”可以减少误触发。
- 这个项目不会绕过账号权限。所有修改都会直接作用于你自己的真实数据。

## 项目结构

```text
yimutodo-assistant/
├── SKILL.md                    # Codex 调用说明
├── agents/openai.yaml          # Skill 展示信息
├── scripts/yimutodo_cli.py     # API 命令行客户端
├── references/api-reference.md # 逆向 API 参考
├── yimutodo_cookie_tools/      # 可选 Cookie 获取工具
└── .env.example                # 本地认证配置模板
```

## 开发检查

```bash
python3 -m py_compile scripts/yimutodo_cli.py
python3 scripts/yimutodo_cli.py --help
```

真实接口测试会读取你的 Cookie，并可能修改账号数据。开发时给测试任务加上唯一标记，测试结束后检查回收站是否已经清理。

## License

[MIT](LICENSE)
