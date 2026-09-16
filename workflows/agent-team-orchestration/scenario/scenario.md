# Agent 团队编排

该工作流把复杂协作需求整理为一份可执行的多 Agent 编排方案。它只设计团队、任务流和质量
控制，不会声称已经创建或运行 Agent，也不会替用户执行方案中的外部操作。

执行路径：

`define_scope → design_team → define_handoffs → design_quality_gates → assemble_plan → end`

## define_scope：目标与约束

从用户请求中提取最终目标、范围、不做事项、输入、交付物、时限、风险和假设，产出
`scope_brief`。该步骤只建立共同任务边界，不提前分配角色。

## design_team：角色与任务图

读取 `scope_brief`，设计最小充分团队、单一主责角色、任务所有权、依赖和并行批次，产出
`team_blueprint`。Orchestrator 负责路由和最终决策，每项交付物必须有唯一负责人。

## define_handoffs：生命周期与交接

读取目标简报和团队蓝图，定义任务状态流、状态负责人、共享产物约定、进度更新和阻塞上报，
产出 `handoff_protocol`。每次交接包含完成内容、产物位置、验证方式、已知问题和下一动作。

## design_quality_gates：审查与恢复

读取前三项产物，为关键交付物设置独立审查、证据标准、验收门禁、停止条件、升级路径和失败
恢复，产出 `quality_plan`。构建者不得批准自己的产物。

## assemble_plan：编排方案

汇总所有中间产物并检查约束一致性，产出 `orchestration_plan`。最终方案包含团队表、执行阶段、
并行批次、输入输出契约、交接模板、审查与恢复机制、验收清单和负责人矩阵。
