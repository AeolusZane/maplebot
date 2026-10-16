# Phase 1：工程与协议

上级：[requirements](../requirements.md)。依赖：无。

## 目标与范围

建立可在 Mac/Windows 导入和测试的纯 CPU 核心，落实 R01–R03、R13。此阶段不操作真实窗口。

## 实现

- 创建 pyproject、src 布局、开发锁文件、平台可选依赖与 CLI --help。
- 实现 contracts 中的类型、JSONL 编解码与版本检查；注入 Clock、RNG。
- 实现 ActionProposal、action_schema 和模型包版本契约；测试合法多键组合、空集合释放、矛盾键拒绝和重复 tap 去重。
- 实现 TraceSink、模拟时钟、基本 manifest 与数据目录规则。
- 提供 .gitignore：data/、artifacts/、凭据与本地配置不进库；fixtures 仅包含人工合成数据。
- 测试核心在没有 pywin32/输入驱动时可导入；配置清晰区分录制、shadow、execute。

## 验收

- [ ] 非法字段、版本、时间和动作被拒绝，错误可定位。
- [ ] 同 seed/配置/输入的纯核心输出一致。
- [ ] Windows 依赖不泄漏到纯核心导入；两系统测试分别记录。
- [ ] 新库按 README 安装后 --help 可用；未实现命令明确提示，不产生假结果。

证据：测试报告、示例 manifest、合成事件往返结果。通过后进入 Phase 2；协议变更必须更新契约和版本。
