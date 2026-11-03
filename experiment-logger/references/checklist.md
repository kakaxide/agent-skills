# agent 自检清单：实验日志记录

> 每次实验结束前逐项过一遍。任何一项不满足，先补记录再结束。

## 开跑前

- [ ] 已创建 canonical 记录（`record.json`），包含 experiment_id 与 title
- [ ] 已登记复现目标：哪篇论文（goal.paper）、哪张表/图（goal.target）、期望指标（goal.expected_metrics）
- [ ] 未登记目标时不得开跑；如确需跳过，必须在对话中显式输出跳过声明

## 实验过程中

- [ ] 每次做出非显然选择（换版本、跳步骤、改参数、换数据），立即追加一条 decision，写明"做了什么、为什么、放弃了什么"
- [ ] 每次报错后、重试之前，先追加一条 failed_attempt（含关键报错信息）
- [ ] 长实验每完成一个阶段（epoch / 评测组 / 数据批次），心跳检查一次是否需要补记 event
- [ ] 默认值 / 未偏离论文的配置不写进人版参数表
- [ ] 记录写入失败时不中断实验，打印警告后继续，finalize 时补记

## 实验结束时

- [ ] 已填写 results：核心指标 metrics、与论文/基线的对照 comparison（含偏差与出处）、一句话结论 summary
- [ ] 已填写 artifacts：checkpoint / 日志 / 指标文件 / 配置 / 图的路径
- [ ] 已运行 `scripts/finalize.py`，生成 human.md 与 agent.md
- [ ] finalize 结论为 PASS（或 WARN 项已逐条确认可接受 / 已补全）
- [ ] 人版一屏内可读出主要参数与效果，无命令、无环境细节、无失败过程
- [ ] agent 版包含：环境指纹、完整命令、全量配置、数据溯源、代码 commit、全部失败尝试与决策、产物路径
- [ ] 两份日志均由脚本渲染自同一份 record.json，未手改渲染产物

## 可复现 dry-run（抽查）

- [ ] 另一个 agent 仅凭 agent.md 能列出：模型与版本、数据与预处理、命令序列、关键超参、硬件与随机种子
- [ ] 若无法满足，说明 agent 版缺信息，回填 record.json 后重渲染
