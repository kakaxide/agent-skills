# 实验记录（agent 版，可复现）｜{{title}}

> 实验 ID：{{experiment_id}} ｜ 状态：{{status}} ｜ 创建：{{created_at}} ｜ 更新：{{updated_at}}

## 复现目标

- 论文：{{goal_paper}}
- 目标位置：{{goal_target}}
- 期望指标：{{expected_metrics}}

## 环境指纹

| 项 | 值 |
|---|---|
| OS | {{env_os}} |
| Python | {{env_python}} |
| CUDA | {{env_cuda}} |
| GPU | {{env_gpu}} |
| 随机种子 | {{env_seed}} |

关键包版本：

{{env_packages}}

## 代码版本

- 仓库：{{code_repo}}
- commit：{{code_commit}}
- 分支：{{code_branch}}
- 未提交改动：{{code_dirty}}

## 完整命令序列

{{commands_list}}

## 全量配置

```json
{{config_json}}
```

## 数据溯源

- 来源：{{data_source}}
- 路径：{{data_path}}
- hash：{{data_hash}}
- 预处理步骤：

{{data_preprocessing}}

## 决策记录

{{decisions_list}}

## 失败尝试

{{failed_attempts_list}}

## 事件时间线

{{events_list}}

## 效果

核心指标：{{metrics_inline}}

与参考对照：

| 指标 | 本实验 | 参考 | 偏差 | 出处 |
|---|---|---|---|---|
{{comparison_rows}}

## 产物

{{artifacts_list}}

---

> 复现验收：另一个 agent 仅凭本文件应能重建实验配置。若发现缺失项，请补全 record.json 后重跑 finalize。
