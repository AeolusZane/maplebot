# 离线优先验证规格 v0.4

## 目标与验收顺序

不开游戏先验证采集协议、决策、调度和日志，再用自建窗口验证原 Interception。游戏内执行为最后的受限集成验证。本文件规定强制门槛，覆盖早先 Windows 手册中可能被误解为可直接进入游戏的顺序。

| 门槛 | 输入与运行方式 | 输出后端 | 必须确认 | 不能据此确认 |
|---|---|---|---|---|
| G0 环境隔离 | 合成输入、离线文件，无游戏进程 | spy/Trace | 不初始化驱动、不枚举或激活游戏、不发键或点击 | Windows 驱动可用 |
| G1 场景与回放 | 合成观察、已有截图/会话 | Trace | 决策、识别回归、动作契约、故障处理 | 动作改变世界后的表现 |
| G2 模拟闭环 | 固定地图简化模拟器，动作改变状态 | SimSink | 可达、停止、卡住、边界、连续决策 | 完整游戏物理与技能效果 |
| G3 自建窗口 | 专用输入反馈窗口 | 原 Interception | 真实按下/释放、时序、组合键、失焦及停止 | 游戏接受输入、真实画面鲁棒性 |
| G4 游戏集成 | 经 G0–G3 的同一模型/配置/执行链 | 原 Interception | 真实识别、移动与技能响应 | 无风控风险或长期稳定性 |

G0–G3 可完全不开游戏完成。已有录制数据可供 G1 使用，无数据时用合成 fixtures；缺少真实样本必须标记真实视觉回归及真人模型未验证。训练 smoke test 可用合成数据，但不得把模型标为真人校准完成。

开发可以并行准备各层，但未通过前层不能签收后一层。G1 的固定录像不会响应模型动作，必须用 G2 补足闭环。G3 可提前用规则动作检查后端，最终模型版本仍需重新验证 G1–G3。

## 离线与真实后端边界

构造运行时先选 backend，再导入平台适配器。离线只加载纯核心、文件感知与 Trace/Sim 后端，禁止间接实例化原 KeyBoardController 所带驱动初始化；可把其纯调度内核提取后注入后端。禁止自动定位窗口、前台激活、截图真实桌面、自动登录鼠标点击、药水/Buff/拾取/回城旁路。

在离线集成测试把 init_interception、key_down、key_up、press_key、点击及窗口激活入口替换成抛异常的哨兵：任一被调用即失败。TraceSink 正常记录虚拟动作，不调用上述入口。不可仅以“没观察到角色动”判断无输出。

G3 使用显式选择的自建窗口句柄与进程身份；失焦即停止，不自动抢焦点。窗口自身记录收到的 keydown/up 和单调时间，和调度回执交叉核对。窗口收到事件不等于游戏会接受，同样不得由驱动调用成功推断收到事件。

## 必测场景与断言

| ID | 场景 | 自动断言 |
|---|---|---|
| O01 | 右移后要求停止 | held 状态最终为空，无多余方向事件 |
| O02 | 目标消失或移到不可达区域 | 无持续使用过期目标；停止或合法新动作 |
| O03 | 同一个 tap 提案重复到达 | 同 event_id 输出调用不超过一次 |
| O04 | 左右/上下矛盾键、未知键、非法时长 | 拒绝且无真实/模拟执行副作用 |
| O05 | 观测延迟、冻结、缺失与低质量 | 达有效期后停止，不能每帧给旧数据刷新期限 |
| O06 | 模型异常、超时、损坏模型包 | STOP、取消 pending、held 清空，失败可见 |
| O07 | 模式切换及 epoch 变化 | 旧提案全部失效，模型历史重置 |
| O08 | 网络乱序/重复/断线/重连 | 不执行旧响应，不重复 tap，不自动恢复缓存动作 |
| O09 | 持续方向 + 一次攻击 | 方向连续保持，攻击按时释放，无重复 keydown |
| O10 | 退出时仍按键，后端释放失败 | 尝试释放；失败明确记录，不假报 completed |
| O11 | 虚拟时钟快进与系统时间调整 | 冷却/期限依赖单调时钟，结果符合时间语义 |
| O12 | 平台边界、缺口、梯子、卡住 | 模拟状态合法；无无限振荡；超时有明确出口 |
| O13 | 录制队列满、磁盘不足、会话中断 | 记录缺失与 incomplete，不输出完整通过 |
| O14 | 自建窗口失焦、关闭、切换目标 | 停止并释放受控键，不把新输入发往其他窗口 |

场景的期望不是强求模型每次按同一个键。对规则策略使用 golden trace；对学习策略检查允许动作集合、时间约束、任务结果和固定环境下重现。阈值写入版本化 suite 配置，不根据测试结果临时放宽。

## 日志契约

机器可读 events.jsonl 和人工 report.md 同时输出。每个事件携带 run_id、scenario_id、session_id、frame_id、proposal_id、action_id、t_ns、source、backend、reason_code；不适用的关联字段为 null。

链路必须能串起 Observation → Proposal → accepted/rejected/modified → Action → Receipt → 下一次观察。Trace 回执标 simulated=true；“模拟执行完成”不得显示成真实发键成功。每个拒绝或修改动作需记录理由与前后差异。

```text
000100 OBS frame=10 player=(100,20) target=(160,20) valid=true
000110 PROPOSE p1 held=[right] tap=[] backend=trace
000111 ACCEPT p1
000112 SIM_KEY_DOWN right action=a1
000200 OBS frame=11 target=null valid=true
000210 PROPOSE p2 held=[] tap=[]
000212 SIM_KEY_UP right action=a2
000220 ASSERT O01.held_empty PASS
```

示例仅演示关联方式，不代表已执行的测试证据。日志排序按事件时间和流序号处理，不能用写入顺序推断因果。

## 验收报告与放行

report.json 至少包含 commit、上游版本、依赖/模型/特征/动作表/场景配置摘要、种子、backend、每个断言、耗时、失败事件索引、not_run 项和 validity_scope。统计重复 tap、非法动作执行、过期动作执行、残留键、规则修改率、停止延迟；零值必须来自实际执行计数，不得缺失填零。

每关仅在必测项全部通过且证据完整时为 passed；依赖或数据缺失为 not_run/incomplete，不能跳过后算通过。输出 gates.json 关联全部 artifact 摘要。模型、键位、感知或调度逻辑变更后对应门槛失效，要求重新跑受影响场景。

G4 前必须核验 G0–G3 同版本报告、Windows 预检和模型数据来源；首次人工真人录制不属于模型执行，可在采集器无输出门禁验证后进行。缺少真人数据不会阻止工程离线开发，但会阻止声明真人模型完整验收。

## 待实现 CLI（当前不可运行）

```powershell
python -m behavior_lab verify --suite configs/validation/offline.yaml --backend trace --output artifacts/g1
python -m behavior_lab verify --suite configs/validation/closed-loop.yaml --backend sim --output artifacts/g2
python -m behavior_lab test-window
python -m behavior_lab verify --suite configs/validation/interception.yaml --backend interception-test-window --output artifacts/g3
python -m behavior_lab gate-check --reports artifacts/g1 artifacts/g2 artifacts/g3 --output artifacts/gates.json
```

G0 哨兵检查包含在 offline suite 中。verify/gate-check 返回 0=该关所有必测通过，1=失败或证据不完整，2=配置/依赖错误。所有命令必须允许本地模型和远端模型变体；远端网络故障可先用可控 stub 注入，再用真实 LAN 在 G3 验证。此处命令是开发验收接口，不宣称已经实现。
