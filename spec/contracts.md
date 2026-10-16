# 数据与接口约定

所有字段为 v1 契约草案，Phase 1 实现为可校验类型与序列化规则。时间用整数纳秒，坐标注明坐标系，未知用 null，不用 (0,0) 冒充未知。

## 通用记录

每条事件具有 `schema_version`、`session_id`、`event_id`、`stream`、`sequence`、`t_ns`、`source`。t_ns 为相对于会话本机单调起点的时间；UTC 仅写入 manifest 用于人类检索。不同流允许异步到达，保留原始事件时间和写入顺序。

## Observation

字段：`frame_id`、`captured_t_ns`、`produced_t_ns`、`valid`、`invalid_reasons`、`scene_id`、`map_version`、`terrain`、`player`、`targets`、`route`、`resources`、`held_keys`、`recent_actions`。

- player：位置、坐标系（screen/minimap/world）、速度估计、朝向、是否在梯子；每项带 observed_t_ns、质量标记和估计来源。
- targets：会话内 tracking_id、位置、类别、质量、最后观测时间；无法稳定追踪时 ID 为 null，不能假装同一怪。
- route：当前段、可达区域、恢复路径可用性。小地图到世界坐标转换必须带变换版本。
- resources：HP/MP、技能就绪状态；没接入可靠识别的字段为 null。识别分数不是已校准概率，字段名使用 match_score。
- 不向生成器泄露模拟器不可见真值；真值单独用于评测。
- terrain：静态平台、梯子、缺口和可达边按 map_version 缓存，动态变化单独发布；不同坐标系须先转换，不能直接相减。
- held_keys/recent_actions：真人录制来自输入监听，模型运行来自执行回执；都带时间及来源，不能把提议但未执行的动作写成实际动作。

## ActionProposal（主策略输出）

`proposal_id, session_id, request_id, policy_epoch, model_version, based_on_frame_id, held_keys, tap_events, valid_for_ns, next_update_after_ns`。

held_keys 为完整期望集合，空集合代表释放所有持续键；tap_events 每项包含稳定 event_id、允许键和 bounded hold_duration_ns。同一未完成 tap 不能每帧生成新 ID；训练侧从按下边沿构建事件，连续保持攻击键不得转换成无数新点击。键行为由 action_schema 配置声明，键不能同时出现在 held 和 tap；不允许左+右、上+下等矛盾集合。

valid_for 是本机授权的最长有效期，不代表期间屏蔽环境反馈；next_update_after 是建议重评估间隔。模型预测时长必须裁剪到版本化的工程限额。本地以触发请求的时刻计算期限，收到超期响应直接拒绝。示例数值仅用于协议演示，不代表已验证控制参数。

```json
{"proposal_id":"p1","session_id":"s1","request_id":"r1","policy_epoch":1,"model_version":"bc-v1","based_on_frame_id":42,"held_keys":["right"],"tap_events":[{"event_id":"tap1","key":"attack","hold_duration_ns":50000000}],"valid_for_ns":100000000,"next_update_after_ns":50000000}
```

记录 proposal → accepted/rejected/modified → Action → Receipt。人工演示标签保持原始值，规则过滤不能静默改写训练真值。

## Intent（可选高层模块）

`intent_id, policy_version, policy_epoch, based_on_frame_id, state, target_id, target_zone, planned_duration_ns, completion_condition, interrupt_conditions, reason_code`。

Intent 描述目标，不含无限按住命令；本地校验后设置有效期限。目标失效时拒绝或结束意图，记录原因；每次重规划不得无条件重置驻留计时。

## Action 与 Receipt

Action：`action_id, proposal_id, intent_id?, sequence, based_on_frame_id, issued_t_ns, expires_t_ns, kind, payload`。

- kind=held_state：payload 为期望按住的允许键集合，以新状态替换旧状态。
- kind=tap：payload 为键、最大持续时长，只能执行一次。
- kind=release_all：本地最高优先级，不等待普通队列。

Receipt：`action_id, accepted_t_ns, started_t_ns, ended_t_ns, status, rejection_reason, sink, held_keys_after`。status 取 proposed/rejected/started/completed/cancelled/failed；输出 API 失败不得记录 completed。环境效果为独立事件。

## 接口

```python
class Policy:
    def reset(self, session_config, rng, clock): ...
    def step(self, observation, receipts) -> ActionProposal: ...

class Sink:
    def apply(self, action) -> Receipt: ...
    def release_all(self, reason) -> Receipt: ...
```

策略不依赖窗口、网络或真实 sleep。RemotePolicyClient 是接口适配器；异步结果由运行时检查，不允许阻塞本机急停。

## 会话目录

```text
data/sessions/<session_id>/
  manifest.json
  input.jsonl
  observations.jsonl
  proposals.jsonl
  intents.jsonl
  actions.jsonl
  receipts.jsonl
  frame_index.jsonl
  annotations.jsonl
  video/segment-0001.mp4
  quality.json
```

manifest 包含硬件/OS、程序 commit、依赖锁摘要、窗口/分辨率/DPI、地图/职业配置、允许键、数据来源 human/synthetic/bot、匿名参与者 ID、种子、录制完整性、文件摘要。写入采用临时文件到原子完成标记；异常中断的会话标记 incomplete，可修复但不能默认为完整。

frame_index 记录实际捕获时间、帧 ID、视频段/帧映射和丢帧标记；不能靠“帧号÷目标 FPS”重建真实时间。annotation 包含起止时间、标签、标注者、来源、可信度；unknown 为合法标签。

## 校验规则

拒绝版本不支持、重复事件 ID、非法按键、负时长、非有限坐标、跨会话动作和未来帧引用。每条流序号单调；数据集检查跨流时间映射、未闭合按键与缺失区间。重复 keydown 的系统自动重复标记为 repeat，不误算多次点击。

## 训练样本与模型包

样本包含 `sample_id/session_id/decision_t_ns/history/action_label/label_window/quality_mask`。history 中每个观察的 produced_t_ns 必须不晚于 decision_t_ns。离线补算视觉时记录 offline 来源与处理延迟假设，不得默认在捕获瞬间已得到识别结果。截断的按键持续时间标记右删失，未来按键只作为标签，不能进入输入特征。

model manifest 包含训练 split 摘要、权重摘要、特征版本、action_schema、归一化参数、历史长度、状态重置规则、采样/解码模式、时长限额及运行依赖。运行时任一版本不匹配拒绝加载。位级重现只要求固定受支持运行环境；不同硬件以输出数值容差和动作一致性报告，不承诺所有神经运行时逐位一致。
