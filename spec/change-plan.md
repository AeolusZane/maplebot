# 参考代码改造清单

本文件为静态审阅结论和计划，未执行修复或 Windows 验证。行号以审阅版本为准。

## 固定参考版本

- [MapleStoryAutoLevelUp-CN](https://github.com/Aynamuk/MapleStoryAutoLevelUp-CN)：`94b1d9e44f885b311301c73a46df43a8cff035ec`。
- maplebot 本地研究副本：`320234a21e90c0ee3a811ede71585a1ef627efc9`。迁移前从其 remote 核验来源地址、许可证，不根据同名项目猜测。
- 复用代码必须保留适用的许可证和署名。新库默认通过适配器集成，避免直接复制两套完整运行循环。

## AutoLevelUp 改造点

| 位置 | 已观察到的行为 | 改造方案 | 验证 |
|---|---|---|---|
| engine/MapleStoryAutoLevelUp.py:259 | 顶层 FSM 仅注册 hunting | 提取 Policy 接口，保留原始策略作基线 | 原始场景动作差异审计 |
| states/hunting.py:14 | 路线、终点、怪物逻辑依次改写共享指令 | 各模块提出候选意图，仲裁器统一决定 | 恢复与攻击冲突测试 |
| input/KeyBoardController.py:237 | 字符串拆成三个共享字段 | 不可变 Action、线程安全发布、统一调度 | 并发快照、非法命令测试 |
| input/KeyBoardController.py:437 | 循环持续执行当前指令 | 指令期限、一次性事件去重、按键所有权 | 决策卡顿不重复攻击或持续移动 |
| input/KeyBoardController.py:474 | 拾取与 Buff 在控制线程自行决策 | 纳入统一动作请求与回执 | 模式切换不遗留自动动作 |
| engine/MapleStoryAutoLevelUp.py:4881；utils/potions.py | 引擎/药水存在直接发键路径 | 全部经过 Sink，trace 模式禁止旁路 | spy sink 证明零真实输出 |
| engine/MapleStoryAutoLevelUp.py:4719 | 名字识别失败沿用旧位置 | 添加时效与质量，超时使观察无效 | 遮挡/长时间漏检停止动作 |
| engine/MapleStoryAutoLevelUp.py:4391 | 怪检测可能慢，跳帧复用旧结果 | 标注检测时间，感知和决策解耦 | 观测年龄与延迟测试 |
| states/hunting.py:40 | set_command 后就记为“实际发出” | 区分已提交、实际调用、环境确认 | 拒绝/失焦时不误更新执行状态 |
| input/InterceptionController.py:189 | press_key 通过 sleep 持有按键 | 可取消调度与 finally 释放；统一失败回执 | 取消、异常、释放失败测试 |
| engine/FiniteStateMachine.py:29 | 固定一秒转移节流 | 新策略独立管理驻留与中断，不沿用全局门槛 | 关键事件及时中断 |
| 多处 time.time、帧数计时 | 冷却/转身依赖系统时间或帧率 | 单调时钟与 elapsed duration | 不同 FPS、系统时钟变化测试 |

上表中的 stale-command、线程一致性和释放行为为需要验证的风险，不声称已复现全部故障。原项目 disable_control 初始化顺序和直接发键路径意味着不能未经审计便把它当作可靠 dry-run。

## 复用边界

保留候选：截图与小地图定位、怪物模板匹配、配置 UI、路线解析、回正几何算法。拆出后通过录制帧 golden fixtures 验证输入输出；业务代码应能在没有 Windows/驱动环境时加载核心模块。

maplebot 用作策略/执行分离的参考，不把其时间抖动自动等同于拟真模型。不同时运行两个执行器；不把其固定 waypoint 顺序当作已解决宏观路线重复。

## 迁移顺序

1. 在新库建立核心协议、TraceSink 与模拟器。
2. 包装原策略输出；记录差异，不先改导航参数。
3. 把直接输出全部收口到单一 Sink。
4. 增加观察失效、命令期限、执行回执。
5. 接入行为克隆 ActionProposal 模型并做配对评测，正常走位不再由原路线逻辑覆盖。原导航只保留为规则基线或显式启用的高层模块。
6. Windows 测试窗口通过后再接授权目标适配器。

回滚通过 policy 配置切回规则基线，并清空 pending 意图、增加 epoch、释放按键。不能回滚掉公共的停止/时效保护。第三方代码升级独立 PR 处理，不与拟真参数变更混合。

## v0.2 新增改造

采集模块必须同步记录实际可用的观察和真人按键，不能只导出 F4 路线。新增共享特征构建、训练/导出/模型加载、动作表和隐藏状态生命周期；规则策略输出统一转换为 ActionProposal。远端接口从高层 Intent 改为短期按键提案，本地仍负责时效和执行回执。模型模式禁用原 hunting 正常走位覆盖；所有保护修改必须记录，评测分别分析模型提议与实际动作。

## v0.3 集成优先（取代前述独立应用迁移方式）

按 [集成方案](autolevelup-integration.md) 在原 AutoLevelUp 增量改造。原 UI、截图识别、KeyBoardController 单一输出线程和 Interception 后端明确复用。F4 路线继续供 legacy 使用，新增演示采集才是模型训练数据。根目录 behavior_lab 为纯核心与训练工具包，原 src 包不迁移。

模型时长显式传入，禁止执行层再次随机；旧巡逻和攻击逻辑不得覆盖模型动作。原自动拾取/Buff 在模型模式默认关闭，药水等辅助动作需声明来源并统一仲裁。manual_record/shadow 必须关闭自动登录点击、回城等全部旁路，并禁止初始化真实输出后端。首次录制不依赖完整物理模拟器；以现有感知加原始按键配对先交付。
