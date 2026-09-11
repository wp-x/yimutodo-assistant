# 一木清单智能整理助手

把零碎口述先整理成通顺、可执行的书面任务，按实际行动拆分，再通过非官方 API 保存到一木清单。AI Agent 负责理解和改写，命令行工具负责保存及回读验证。

![](assets/Pasted-20260819-233712.png)

> 本项目来自网页端接口逆向，与一木清单官方无关。接口升级后可能失效。

## 一句话安装

复制下面整段，发给 Codex、Claude Code、Kimi、zcode 或其他能执行命令的 Agent：
![](assets/Pasted-20260819-232912.png)

```text
请帮我安装并配置一木清单 AI 助理 https://github.com/wp-x/yimutodo-assistant：先识别当前 Agent 的全局 Skill 或插件目录，把仓库安装为 yimutodo-assistant；如果当前 Agent 没有原生 Skill 机制，就安装到合适的工作目录并使用项目 CLI；安装 requirements.txt，复制 .env.example 为 .env 并将权限设为 600；然后告诉我 .env 的完整路径，指导我从本机一木清单网页的浏览器开发者工具中取得 vertx-web.session 并由我在本地填写，禁止要求我把 Cookie 发到聊天、日志或 Issue；我确认填写完成后，运行 status 做只读连接测试，成功后告诉我如何重载当前 Agent；不要覆盖目标目录中已有的未提交修改。
```

## 能做什么

- 默认整理口述标题、合并重复、自我纠正、区分条件和背景
- 按独立完成结果拆分任务，把连续步骤和执行要求整理进备注
- 修改已有标题时核验提醒正文，并保留原提醒时间和渠道
- 查询、创建、修改和完成任务
- 管理项目、标签、任务组、提醒、习惯和打卡
- 识别“明天下午三点”这类中文时间
- 查询回收站和专注记录
- 通过“一木清单”“帮我记个待办”等自然语言触发

例如：

```text
帮我在一木清单添加一个明天下午三点取快递的任务。
那个报价王总上次觉得贵，明天下午三点提醒我改一下价格再发给他。
把报价那条任务的标题写通顺，提醒文案也同步整理。
查看一木清单里还没完成的任务。
把“取快递”标记为完成。
```

说出“一木清单”可以减少 Agent 把请求误判成系统日历或浏览器操作。

第二句会整理成“修订报价单并发送给王总”，将“原报价偏高”放入备注，并设置准时提醒。不会把整段语音转写直接当标题，也不会机械拆成多次提醒。

智能整理是默认工作流，不需要另开开关。直接调用 CLI 时，仍需传入已经整理好的标题；CLI 本身不运行语言模型。

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
![](assets/Pasted-20260819-232610.png)

```dotenv
YIMUTODO_COOKIE='vertx-web.session=替换为你自己的值'
```

Cookie 等同于登录状态。项目已通过 `.gitignore` 排除 `.env`，仍需避免把它粘贴到聊天、Issue、截图或公开仓库。

![](assets/Pasted-20260819-232746.png)

`yimutodo_cookie_tools/` 提供了可选油猴脚本。只读取一木清单域名下的 session 并复制到剪贴板。不了解油猴权限时，使用开发者工具手动复制。

## 命令行

```bash
python3 scripts/yimutodo_cli.py status
python3 scripts/yimutodo_cli.py projects
python3 scripts/yimutodo_cli.py tasks --status open
python3 scripts/yimutodo_cli.py add-task "取快递"
python3 scripts/yimutodo_cli.py add-batch --file /tmp/yimu-plan.json --dry-run
python3 scripts/yimutodo_cli.py add-batch --file /tmp/yimu-plan.json
python3 scripts/yimutodo_cli.py rewrite-task TASK_ID "修订报价单并发送给王总"
python3 scripts/yimutodo_cli.py complete TASK_ID
```

计划字段、提醒设置和失败处理见 [CLI 约定](references/cli-contract.md)，文案标准见 [整理规则与案例](references/organizing-guide.md)。完整逆向接口文档不包含在公开仓库中，仅随本地安装保留。

## 更新与验证

更新实际被 Agent 加载的技能目录，确保 `SKILL.md`、`agents/`、`references/` 和整个 `scripts/` 来自同一版本。只更新下载源码或只复制主脚本不会更新另一个已安装副本。保留已有 `.env`，重载技能或开启新会话后生效。

```bash
python3 scripts/run_tests.py
python3 scripts/yimutodo_cli.py validate-plan --file /tmp/yimu-plan.json
```

测试在隔离环境中运行，设有 60 秒超时；`validate-plan` 不联网。`--dry-run` 会读取真实项目并解析时间，但不会创建任务。

## 使用限制

- Cookie 过期时会返回 `errorCode=1000004`，重新登录并更新 `.env` 即可。
- 提醒、重复和打卡需要严格的字段组合与毫秒时间戳。
- 提醒正文使用任务标题，`taskNotices.msg` 是“提前10分钟”等时间说明，不能作为正文修改。
- 结构测试和回读不证明设备推送已送达；已打开的客户端可能需要刷新才能清除缓存的旧文案。
- 所有写入都会直接修改用户的真实数据。
- 不同 Agent 的 Skill 目录和自动触发机制可能不同，CLI 可以独立运行。

## License

[MIT](LICENSE)
