# 整理计划与 CLI 约定

CLI 只接收已经由 AI 整理的任务，不调用独立模型、不自动润色原始口述。语义整理规则见 [organizing-guide.md](organizing-guide.md)。

## 高级操作

普通任务、备注及提前提醒使用本文的封装命令。项目、标签、习惯、复杂重复、全天指定钟点或其他渠道可以通过 `call` 调用，但需要本地已核实的 `references/api-reference.md`。该完整逆向文档不随公开仓库发布；本地不存在时不猜测方法或参数。

## 创建计划

`add-batch --file PATH` 和 `validate-plan --file PATH` 接受 JSON 数组；省略 `--file` 时从 stdin 读取。每条支持以下字段，拼错/未知字段会报错。

| 字段 | 含义 |
|---|---|
| `title` | 必填，AI 整理后的完整书面标题；不用原始口述或 NLP 的 suggestText |
| `content` | 可选纯文本备注，CLI 编码为一木清单富文本 JSON 字符串 |
| `project` | 已查询确认的准确项目名；重名必须用 ID |
| `projectId` | 字符串 ID；如同时提供 project，两者必须一致 |
| `level` | 整数 0—3，默认 0 |
| `startTime` / `endTime` | 非负整数，Unix 毫秒；0 的 endTime 表示没有结束时间 |
| `time` | 中文时间表达；与 startTime 二选一；建议先 nlp 核对后写明确时间戳 |
| `reminder` | `{"beforeMinutes":0}` 为准时提醒，10 为提前 10 分钟；需要明确任务开始时间 |

未指定项目时从真实项目列表解析收集箱；指定项目错误时直接报错，不改投收集箱。今天、本周、所有等聚合视图不是写入项目。没有时间时使用当前开始时间；不生成提醒。

示例（这里是已整理结果，不是原话）：

```json
[
  {
    "title": "修订报价单并发送给王总",
    "content": "王总反馈上次报价偏高，调整价格后再发送。",
    "startTime": 1789196400000,
    "reminder": {"beforeMinutes": 0}
  },
  {
    "title": "下班后购买两盒牛奶"
  }
]
```

示例时间为 Asia/Shanghai 的 2026-09-12 15:00，仅用于说明；真实任务必须按当前日期解析。`content` 是完整备注，不添加没有用途的“来源：用户口述”等模板。

```bash
python3 scripts/yimutodo_cli.py validate-plan --file /tmp/yimu-plan.json
python3 scripts/yimutodo_cli.py add-batch --file /tmp/yimu-plan.json --dry-run
python3 scripts/yimutodo_cli.py add-batch --file /tmp/yimu-plan.json
python3 scripts/yimutodo_cli.py add-task "修订报价单并发送给王总" --time "明天下午三点" --remind-before 0
```

`validate-plan` 离线验证结构；`--dry-run` 还会读取项目、解析时间并输出实际 API 参数，但不写入。对于已授权的任务，AI 自行核对后直接执行，无需用户审批预览。

创建流程先准备整个计划，再顺序写入并回读任务和提醒。新提醒使用应用渠道；不自动开启邮箱或微信渠道。`reminder.beforeMinutes` 覆盖普通一次性提前提醒，重复任务、全天指定钟点和其他渠道使用已核对的原始 API。

## 已有任务整理

```bash
python3 scripts/yimutodo_cli.py tasks --status open --query "报价"
python3 scripts/yimutodo_cli.py rewrite-task TASK_ID "修订报价单并发送给王总"
python3 scripts/yimutodo_cli.py rewrite-task TASK_ID "修订报价单并发送给王总" --content "合并原有资料后的完整备注"
python3 scripts/yimutodo_cli.py update-task TASK_ID --fields '{"title":"修订报价单并发送给王总","level":2}'
```

`rewrite-task` 省略 content 时保留原备注；提供时替换全部备注。`update-task` 接受原始 API 字段，其中 content 需要自行编码；通常优先用 rewrite-task 处理文字。两条路径更新标题时均校验原提醒规则和渠道未变化，并检查最近队列中的标题。

通知正文共用任务标题；不提供一个容易过期的独立 `reminderText` 字段。`taskNotices.msg` 是提前时间说明，`noticeInfo` 是应用/微信/邮箱渠道，均不是通知正文。

## 返回值与失败恢复

- 成功返回 `ok: true`、逐条 `results`、任务 ID 和 `stage: verified`。提醒结果包含当前标题及 `recentQueueMatches`。
- `recentQueueMatches: 0` 表示最近队列中没有该任务，并不证明提醒丢失。`deliveryVerified: false` 表示没有验证设备推送送达。
- 输入和项目/时间准备失败：整批尚未写入，非零退出并报告原因。
- 写入或回读失败：非零退出，保留已知 `taskId`、`noticeIds`、失败阶段和 `unattempted`。之前成功的任务依然存在。
- 发生写入失败后停止当前批次，不自动重试。超时可能发生在服务器已写入之后，先查询真实任务和提醒，再处理缺失步骤；不要重跑整个文件，也不自动删除已经创建的数据。
- 所有外部错误明确显示；脚本没有项目回落、未识别时间改成当前时刻、假成功或网络重试路径。

## 维护验证

```bash
python3 scripts/run_tests.py
python3 scripts/yimutodo_cli.py --help
```

测试执行器对后端测试设置 60 秒硬超时。回归测试使用隔离的接口替身检查真实执行代码，不连接账号或写入线上任务；`--dry-run` 可验证真实账号的只读准备过程。测试替身不属于运行时实现。
