---
name: yimutodo-assistant
description: 通过一木清单（yimutodo.com）的非官方逆向 API 查询和管理任务、项目、标签、任务组、提醒、重复、习惯、打卡、专注记录与回收站。用户提到一木清单、待办事项、添加或完成任务、查看今日或未完成任务、管理项目标签习惯，或要求 AI 充当一木清单助理管家时使用。
---

# 一木清单助理

使用 `scripts/yimutodo_cli.py` 调用真实 API。认证按以下优先级读取：进程环境变量 `YIMUTODO_COOKIE`，其次是 Skill 根目录的 `.env`。首次使用时从 `.env.example` 复制配置。认证值接受完整 Cookie（如 `vertx-web.session=...`）、带 `Cookie:` 前缀的值或单独的 session 值。不得把 Cookie 写入源码、文档、日志或回答；`.env` 必须保持在 `.gitignore` 中且文件权限为仅当前用户可读写。

## 工作流

1. 读取操作先执行，不要求额外确认。
2. 新增或修改前，从用户原话提取标题、项目、时间、优先级等；缺少项目时使用收集箱。
3. 如果用户用项目名、标签名或任务名，先查询并解析成唯一 ID。匹配到多个对象时列出候选并询问，不猜测。
4. 创建、修改、完成任务属于用户明确要求后的正常执行步骤。删除、清空回收站、注销、改密、解绑账号等高影响操作必须在本轮得到明确授权。
5. 执行后查询结果验证，并简洁报告实际变更。API 失败时原样暴露错误码和消息，不声称成功。

## 快速调用

```bash
python3 scripts/yimutodo_cli.py status
python3 scripts/yimutodo_cli.py projects
python3 scripts/yimutodo_cli.py tasks --status open --query "报告"
python3 scripts/yimutodo_cli.py add-task "提交周报" --project-id 128338
python3 scripts/yimutodo_cli.py complete TASK_ID
python3 scripts/yimutodo_cli.py uncomplete TASK_ID
python3 scripts/yimutodo_cli.py update-task TASK_ID --fields '{"title":"新标题","level":2}'
python3 scripts/yimutodo_cli.py delete-task TASK_ID
python3 scripts/yimutodo_cli.py nlp "明天下午三点提醒我开会"
```

所有命令输出 JSON。需要 CLI 未提供的能力时，先阅读 [references/api-reference.md](references/api-reference.md)，再用统一分发命令：

```bash
python3 scripts/yimutodo_cli.py call TODO_TAG_ADD_V2 --params '{"tagName":"工作","color":"#409EFF","positionWeight":0}'
```

`call` 默认自动加入 `systemType=PC`。公开接口才使用 `--suffix /public`。不要用 `call` 绕过高影响操作的授权要求。

## 时间与字段规则

- 时间均为 Unix 毫秒时间戳；创建普通任务未给开始时间时使用当前时间。
- 完成任务：`completeTime=当前毫秒时间戳`；取消完成：`completeTime=0`。
- `taskType`: `0` 普通、`1` 日期、`2` 习惯；`level`: `0` 到 `3`。
- 富文本、提醒和打卡详情等字段是 JSON 字符串，不是嵌套对象。
- 永久删除现有任务必须先软删，再硬删；CLI 的 `delete-task --permanent` 已按此顺序执行。
- 详细端点、实体字段和危险操作见 [references/api-reference.md](references/api-reference.md)。

## 认证失效

`errorCode=1000004` 表示登录失效。停止操作并要求用户更新 Skill 根目录的 `.env` 或进程环境变量 `YIMUTODO_COOKIE`，不要尝试读取浏览器 Cookie 或其他凭据。
