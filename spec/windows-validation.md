# Windows 执行与验证手册

所有 `behavior_lab` 命令为待实现 CLI 契约，不是当前可用脚本。Phase 1 必须提供 --help 与命令清单，后续阶段实现对应命令。本文件是实现后的执行说明，当前结果均为未运行。

## 环境与交接

Mac：编辑方案、实现核心、模拟器与离线测试；不得把 Mac 通过当作 Windows 输入链路通过。

Windows：Python 3.12 64 位作为首版基线，确认目标软件支持的 Windows 版本。GPU 可为 1GB，但游戏运行能力、捕获能力与 CPU 模板匹配必须实测。记录 CPU、RAM、GPU、OS build、DPI、游戏客户区大小、刷新率、目标版本。

优先本机显示器、普通窗口和固定缩放测试；远程桌面、最小化、锁屏列为单独故障场景。不要为数据采集默认安装输入驱动；输入执行适配器与只读采集分开验收。

## 新仓库准备

用户创建仓库后复制本方案目录。开发实现 pyproject、依赖锁、测试、CLI 后，Windows 在仓库根 PowerShell 执行以下约定命令：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/windows.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m behavior_lab --help
.\.venv\Scripts\python.exe -m pytest tests/unit tests/integration
.\.venv\Scripts\python.exe -m behavior_lab doctor --output artifacts/doctor.json
```

锁文件由开发阶段实际解析依赖后交付，需包含测试工具；不要求用户自己猜版本。doctor 列出缺失项并非零退出，不能偷偷安装驱动或改变显示设置。

## 逐级验证

1. **协议与模拟器**：`python -m behavior_lab simulate --scenario fixtures/synthetic/platform.json --policy deterministic --seed 42 --output artifacts/baseline`。输出 manifest、事件与 quality；重复运行规范化轨迹摘要一致。
2. **测试窗口采集**：`python -m behavior_lab record --config configs/recording.yaml`。先打开项目交付的可视反馈测试窗口，短按/长按/组合键/切换焦点/停止录制，回放核对。
3. **检查会话**：`python -m behavior_lab validate-session --session data/sessions/<session-id>`；无完整性错误才能进入拟合。
4. **回放与标注**：`python -m behavior_lab replay --session data/sessions/<session-id>`；显示画面、输入和时间轴，人工标注写独立文件，不能改原始事件。
5. **生成器**：`python -m behavior_lab simulate --scenario fixtures/synthetic/platform.json --policy semi-markov --seed 42 --output artifacts/generator`；检查中断、非法动作、状态驻留。
6. **评测**：`python -m behavior_lab evaluate --config configs/evaluation.yaml --output artifacts/evaluation`。数据不足也生成报告，但不能返回“研究结论通过”。
7. **Windows shadow**：`python -m behavior_lab run --config configs/windows.yaml --mode shadow`；观察真实画面和生成意图，sink 为 trace，验证无真实输出。
8. **受控执行**：`python -m behavior_lab run --config configs/windows-test.yaml --mode execute`；先只向项目测试窗口执行，再按适配器验证清单接入授权目标环境。

以上 python 表示 `.venv\Scripts\python.exe`，占位 session-id 替换为录制器实际输出。CLI 返回码：0=命令级检查通过，1=验证失败，2=配置/依赖错误；研究证据是否充分另写 report.conclusion，不能由退出码替代。

## 故障矩阵

| 注入 | 预期 | 证据 |
|---|---|---|
| 窗口失焦/关闭 | 取消 pending、释放、停止接收新动作 | 回执、按键状态 |
| 抓帧停滞/定位无效 | 达配置时效后 STOP | observation_age 和停止时间 |
| 策略异常/超时 | 调度器不续用旧命令 | watchdog 事件 |
| 重复 tap ID | 只调用一次输出 | spy sink 计数 |
| 系统时间修改 | 单调冷却不受影响 | 虚拟时钟测试 |
| 录制队列满/磁盘不足 | 明确错误/缺失，不输出完整成功标记 | quality、manifest |
| 停止时仍按住方向 | 受控键释放；失败则明确告警 | held_keys_after |
| 分辨率/DPI变化 | 观察失效并要求重新校准 | doctor/运行事件 |
| 可选网络断线/乱序 | 旧响应丢弃，停止，重连不自动恢复 | request/epoch 日志 |

## 性能测量与初始预算

预算是待验证工程目标：小型策略 CPU 推理 p95≤10ms；受控测试窗口的本地停止到释放调用 p95≤100ms；首次观测时效上限配置为 250ms（导航）、500ms（目标检测），不满足时停止该依赖动作，不能沿用过期数据。实际阈值须按测试地图控制误差验证后冻结并记录变更。

上述预算不要求每项感知达到同一帧率。记录捕获、定位、怪物检测、策略、调度的 p50/p95/p99，CPU、进程峰值内存、GPU占用、队列长度、丢帧率；至少运行 10 分钟性能样本。配置 FPS 上限不等于实际 FPS。

若不达标：先定位瓶颈，缩小检测 ROI、限制模板数、采用有时效标记的独立感知更新；重新测量。禁止为了通过测试直接放宽失效时间而不验证控制误差。HSMM/Semi-Markov 迁到远端通常不能改善模板匹配瓶颈。

## 验收包

交付 `artifacts/<run-id>/`：doctor、测试报告、性能报告、故障矩阵、运行 manifest、脱敏短片索引、已知问题。每项标明 passed/failed/not_run。Windows 首次真实采集、真实输出、拟真统计验证分别签收，不互相替代。
