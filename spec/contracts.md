# 数据与接口约定

所有字段为 v1 契约草案，Phase 1 实现为可校验类型与序列化规则。时间用整数纳秒，坐标注明坐标系，未知用 null，不用 (0,0) 冒充未知。

## 通用记录

每条事件具有 `schema_version`、`session_id`、`event_id`、`stream`、`sequence`、`t_ns`、`source`。t_ns 为相对于会话本机单调起点的时间；UTC 仅写入 manifest 用于人类检索。不同流允许异步到达，保留原始事件时间和写入顺序。

## Observation

字段：`frame_id`、`captured_t_ns`、`produced_t_ns`、`valid`、`invalid_reasons`、`scene_id`、`player`、`targets`、`route`、`resources`。

- player：位置、坐标系（screen/minimap/world）、速度估计、朝向、是否在梯子；每项带 observed_t_ns、质量标记和估计来源。
- targets：会话内 tracking_id、位置、类别、质量、最后观测时间；无法稳定追踪时 ID 为 null，不能假装同一怪。
- route：当前段、可达区域、恢复路径可用性。小地图到世界坐标转换必须带变换版本。
- resources：HP/MP、技能就绪状态；没接入可靠识别的字段为 null。识别分数不是已校准概率，字段名使用 match_score。
- 不向生成器泄露模拟器不可见真值；真值单独用于评测。

## Intent

`intent_id, policy_version, policy_epoch, based_on_frame_id, state, target_id, target_zone, planned_duration_ns, completion_condition, interrupt_conditions, reason_code`。

Intent 描述目标，不含无限按住命令；本地校验后设置有效期限。目标失效时拒绝或结束意图，记录原因；每次重规划不得无条件重置驻留计时。

## Action 与 Receipt

Action：`action_id, intent_id, sequence, based_on_frame_id, issued_t_ns, expires_t_ns, kind, payload`。

- kind=held_state：payload 为期望按住的允许键集合，以新状态替换旧状态。
- kind=tap：payload 为键、最大持续时长，只能执行一次。
- kind=release_all：本地最高优先级，不等待普通队列。

Receipt：`action_id, accepted_t_ns, started_t_ns, ended_t_ns, status, rejection_reason, sink, held_keys_after`。status 取 proposed/rejected/started/completed/cancelled/failed；输出 API 失败不得记录 completed。环境效果为独立事件。

## 接口

```python
class Policy:
    def reset(self, session_config, rng, clock): ...
    def step(self, observation, receipts) -> Intent: ...

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
