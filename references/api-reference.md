# 一木清单非官方 API 参考

本参考来自 Web 前端逆向与 2026-08-19 真实账号测试。该 API 并非官方公开接口，服务端升级后字段或行为可能变化。

## 协议

- 基址：`https://yimutodo.com`
- 统一入口：`POST /api/v/atop`
- JSON body：`{"method":"TODO_SYNC_PAGE","systemType":"PC", ...参数}`
- 成功：`{"errorCode":0,"data":...}`
- 常见失败：`1000001` 服务器繁忙或字段错误；`1000004` 会话失效。
- 必须使用 `Content-Type: application/json`。客户端禁用系统代理环境变量，以规避本地代理导致的 502。

直接路径接口：

| HTTP | 路径 | 用途 |
|---|---|---|
| GET | `/api/v/atop/user/info` | 当前用户 |
| POST | `/api/v/atop/login/auth` | 第三方授权码登录 |
| POST | `/api/v/login` | 账号登录，密码 MD5 |
| POST | `/api/v/register` | 注册，密码 MD5 |
| GET | `/api/v/logout` | 退出 |

## 查询和同步

| method | 参数 | 结果或用途 |
|---|---|---|
| `TODO_SYNC_PAGE` | `gmtModified` | 全量/增量任务与项目数据 |
| `TODO_SYNC_PAGE_DELETED` | `gmtModified` | 已删除 ID |
| `TODO_TASK_GET_BY_ID` | `id` | 单个任务 |
| `TODO_PROJECT_GET_MEMBER_BY_PROJECT_IDS` | `projectIds` | 项目成员 |
| `TODO_TASK_NOTICE_RECENT_QUERY` | 无 | 最近提醒 |
| `RECYCLE_PAGE_PROJECT` | `page,pageSize` | 回收站项目 |
| `RECYCLE_PAGE_TASK` | `projectId,page,pageSize` | 回收站任务 |

`TODO_SYNC_PAGE` 的数据键包括：`tasks`、`projectDTOS`、`tags`、`taskGroups`、`addresses`、`taskNotices`、`taskRepeats`、`taskHabits`、`taskClockedHistories`、`absorbs`、`stickers`、`taskModules`、`lastSyncTime`。

## 写入方法

| method | 关键参数 |
|---|---|
| `TODO_PROJECT_ADD` | `name,projectType,parentProjectId,parentProjectName,positionWeight,iconUrl` |
| `TODO_PROJECT_UPDATE` | 上述字段加 `projectIdStr` |
| `TODO_PROJECT_DELETE` | `projectId` |
| `TODO_PROJECT_QUIT` | `projectId` |
| `TODO_TASK_ADD_V2` | `title,projectIdStr,taskType,level,startTime,endTime,positionWeight,isTop,giveUp,completeTime` |
| `TODO_TASK_UPDATE` | `taskIdStr` 加需修改字段 |
| `TODO_TASK_DELETE` | `taskIdStr,completely` |
| `TODO_TASK_GROUP_ADD_V2` | `projectIdStr,name,positionWeight` |
| `TODO_TASK_GROUP_UPDATE` | `groupId` 加需修改字段 |
| `TODO_TASK_GROUP_DELETE` | `groupId` |
| `TODO_TAG_ADD_V2` | `tagName,color,positionWeight` |
| `TODO_TAG_UPDATE` | `tagId` 加需修改字段 |
| `TODO_TAG_DELETE` | `tagId` |
| `TODO_ADDRESS_ADD_V2` | `poiAddress,totalAddress,longitude,latitude,name` |
| `TODO_ADDRESS_UPDATE` | `addressIdStr` 加需修改字段 |
| `TODO_ADDRESS_DELETE` | `addressIdStr` |
| `TODO_TASK_NOTICE_ADD` | `taskIdStr,msg,mode,hour,minute,day,time` |
| `TODO_TASK_NOTICE_DELETE` | `taskNoticeIdStr` |
| `TODO_TASK_REPEAT_ADD` | `taskId,repeatMode,weekdays,interval,jumpWeekend` 等 |
| `TODO_TASK_REPEAT_DELETE` | `taskId` |
| `TODO_TASK_HABIT_ADD_V2` | `taskId,taskIdStr,habitType,habitUnit,habitDayNum,habitOnceNum,autoShowLog,autoAbsorbed` |
| `TODO_TASK_HABIT_UPDATE` | 同上 |
| `TODO_TASK_CLOCKED_HISTORY_ADD_V2` | 见“习惯打卡” |
| `TODO_TASK_CLOCKED_HISTORY_UPDATE` | 打卡字段加 `clockedHistoryId` |
| `TODO_ABSORBED_ADD_V2` | `totalTime,mode,startTime,endTime,completeIds,absorbedInfoList` |
| `TODO_ABSORBED_UPDATE` | 上述字段加 `absorbedId` |
| `TODO_ABSORBED_DELETE` | `absorbedId` |
| `RECYCLE_EMPTY_TASK` | `projectId`，清空任务回收站 |

其他方法：`NLP_CHINESE_TIME_RECOGNITION(text)`、`APP_CONFIG_GET_ICONS`、`APP_CONFIG_GET_LIST_BY_KEY(key)`、`APP_CONFIG_GET_ALIYUN_OSS(used)`。

## 核心实体

- Task：`taskId,title,content,taskType,level,projectId,groupId,parentTaskId,startTime,endTime,completeTime,giveUp,isTop,positionWeight,tagIdStrList,addressId,noticeInfo,habitDTO`
- Project：`projectId,projectType,name,parentProjectId,positionWeight,iconUrl,hide,progressMode,remark,permission`
- Habit：`taskId,habitType,habitUnit,habitDayNum,habitOnceNum,autoShowLog,autoAbsorbed`
- ClockedHistory：`clockedHistoryId,taskId,time,completeNum,totalNum,complete,giveUp,clockedMood,clockedLog,clockedDetail`
- Tag：`tagId,tagName,color,positionWeight`
- Group：`groupId,projectId,name,positionWeight`
- Notice：`taskNoticeId,taskId,msg,mode,hour,minute,day,time`

内置项目 ID 通常为：收集箱 `128338`、今天 `10028338`、本周 `-10028338`、本月 `-20028338`、明天 `-30028338`、所有 `-228338`。优先按项目名从同步数据确认。

## 特殊行为

- 完成任务没有独立接口：调用 `TODO_TASK_UPDATE`，传当前毫秒 `completeTime`；取消完成传 `0`。
- 永久删除必须先 `completely=false` 软删，再 `completely=true` 硬删。
- 打卡字段必须齐全：`taskId,taskIdStr,time,clockedMood,clockedLog,completeNum,totalNum,complete,giveUp,updateTime,clockedDetail`。
- `time` 等日期边界字段通常使用本地时区当天零点的毫秒时间戳。
- 密码、绑定邮箱和重置密码接口中的密码字段先计算 MD5。
- `USER_RESET_PASSWORD_BY_EMAIL` 等公开调用发送到 `/api/v/atop/public`。
- 高影响方法包括 `USER_DESTROY`、`USER_UPDATE_PASSWORD`、`USER_UNBIND_EMAIL`、`TODO_PROJECT_DELETE`、`RECYCLE_EMPTY_TASK` 和永久删除。
