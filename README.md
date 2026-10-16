# Maplebot：AutoLevelUp 源码与行为模型开发方案

状态：已在本地导入 AutoLevelUp 上游源码与历史；v0.3 方案明确复用原 Interception 执行层，行为模型尚未实现，Windows 实机验证尚未进行。

## 上游来源与运行入口

基于 [Aynamuk/MapleStoryAutoLevelUp-CN](https://github.com/Aynamuk/MapleStoryAutoLevelUp-CN)，导入基准为 `94b1d9e44f885b311301c73a46df43a8cff035ec`，保留上游 Git 历史和 [MIT 许可证及署名](LICENSE)。这是现有独立仓库的源码合并，GitHub 页面不一定显示 Fork 关系。

- [上游开发与安装说明](README_UPSTREAM.md)
- [上游用户说明](README_用户版.md)
- 现有入口：`run_gui.py`、`src/`、`tools/`、`requirements.txt`。
- `spec/` 中的 `behavior_lab` 是待开发架构，不是现有源码已提供的命令。
- 上游 CI 仍按原配置监听 `master`，本仓库主分支为 `main`；本次导入不代表 CI 或 Windows 测试已通过，后续实现时再适配工作流及其历史标签依赖。

目标：在 AutoLevelUp 上建立实时“环境状态 → 模型按键提案 → 原 Interception 执行 → 环境反馈”闭环。先保留规则基线，再用真人配对数据训练动作模型；支持本地 CPU 或局域网推理。Windows 负责采集和实测，Mac 可开发与运行纯核心测试。当前规格为 v0.3。

本仓库已包含上游跟踪的源码和资源，文档使用相对链接，不依赖当前 Mac 路径。个人配置、真人数据、构建产物和凭据不应提交。

## 阅读顺序

优先阅读 [AutoLevelUp 集成方案 v0.3](spec/autolevelup-integration.md)：保留原 UI、感知、F4 和 Interception，新增演示录制及模型动作决策，明确四种模式的输出边界。

1. [需求与阶段导航](spec/requirements.md)
2. [设计与开发架构](spec/architecture.md)
3. [数据与接口约定](spec/contracts.md)
4. [现有代码改造清单](spec/change-plan.md)
5. [Windows 执行和验证手册](spec/windows-validation.md)
6. [采集与评测方案](spec/evaluation.md)
7. [决策与待验证事项](spec/history.md)

开发时按 `spec/phases/` 顺序完成各阶段。每一阶段须交付可运行代码、对应测试、运行证据，再更新状态。文档中的命令是未来 CLI 的验收契约，目前执行会因程序不存在而失败。

## 用户需要准备

- 使用已创建的 AeolusZane/maplebot 仓库；拉取包含源码和最新 spec 的 main。
- Windows 测试机：记录 Windows 版本、CPU、内存、GPU/显存、显示缩放、分辨率和目标程序版本。
- 选定一个固定地图、角色/职业、技能配置；在运行清单中填写，不需要阻塞 Mac 上的核心开发。
- Phase 2 完成后，正常操作录制几段短样本并检查质量；采集流程通过后再扩大样本。
- 回看少量典型片段，为停顿、放弃目标和恢复等行为补充意图标签。
- Windows 每阶段产出报告和脱敏诊断信息；原始视频默认留在本机。

## 完成定义

核心交付为 Phase 1–6，通过 Windows 回放、采集、模型训练、模拟执行和实验报告验证。先验收本地，再验收局域网部署；没有第二台机器时远端项标记未运行。没有真人数据时只能交付规则基线和技术接口，行为克隆阶段保持未完成；没有足够真人负样本时，不能声称达到低误报检测指标。
