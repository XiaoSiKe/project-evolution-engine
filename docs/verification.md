# 验证记录

本文件记录确定性检查与独立代理行为评测。CI 徽章只代表自动化测试状态，不代表外部 MCP 集成已经验证。

## v0.1.0 本地结果 · 2026-09-03

- 技能包与工具测试：Python 3.12 下 **39 项通过**。
- 官方 skill-creator 格式校验及本仓库包校验：通过。
- 独立代理案例：**7/7 达到预期结果**；主评测者另行运行了行为验收并对账真实差异。
- 七个示例项目更新后的测试合计 37 项，通过情况如下；它们不计入上面的 39 项工具测试。

| 案例 | 更新后项目测试 | 独立验收 | 净修改文件 |
| --- | ---: | --- | ---: |
| 批量导出与公共规则复用 | 8 | 通过 | 3 |
| 已授权行为变化 | 4 | 通过 | 3 |
| 保留用户未提交修改 | 7 | 通过 | 2 |
| 生成链与规范源 | 3 | 通过 | 4 |
| 过期说明与实际职责定位 | 8 | 通过 | 5 |
| 无 Serena 的独立更新 | 4 | 通过 | 2 |
| 完成独立工作并提出业务冲突 | 3 | 通过 | 2 |

业务冲突案例的预期结果是完成邮箱规范化、保留旧订单计算，并准确提出服务费 2 与 3 的冲突；它没有擅自实施未确定的收费行为。

第五个案例首次报告校验遇到评测器约束问题：新增的领域测试文件未列入允许清单，且完整测试套件标签未被视为覆盖相关测试。主评测者阅读实际差异和执行结果后修正了这两项约束，并复核通过；Skill 和该案例实现均未因此修改。

可查看[机器可读结果与实际补丁](../evals/results/v0.1.0/results.json)。检查器、字段对账和行为执行分别记录，避免用单一的“通过”掩盖覆盖差异。

## 验证方法

独立代理只拿到安装包内的 Skill、原始开发请求、临时项目和中立结果格式。案例中的预期结果与验收程序由主评测者保留。

主评测者将报告与真实净文件变化对账，再执行代理未读取的行为检查。所有原始夹具都能运行基线测试；所有未实现的夹具都会被相应行为检查拒绝。

## 本地复现基础设施

```bash
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_skill.py
python3 -m unittest discover -s tests -v
python3 scripts/eval_cases.py validate-cases
```

独立运行一个案例时，先在新的临时目录物化原始项目：

```bash
python3 scripts/eval_cases.py materialize --case batch-export --output /tmp/evolution-example
python3 scripts/eval_cases.py result-contract
```

向代理提供物化输出中的原始请求、技能路径与中立结果约定。代理结果应写到夹具外，且不允许读取本仓库的 evals 目录。完成后由评测者运行：

```bash
python3 scripts/eval_cases.py validate-result --case batch-export --workspace /tmp/evolution-example --result /tmp/evolution-result.json
python3 scripts/eval_cases.py verify-behavior --case batch-export --workspace /tmp/evolution-example
```

`validate-result` 核对结果字段和真实改动；`verify-behavior` 检查功能与保留行为。仅通过前者不足以证明新功能完成。

## 可选集成

本次环境没有可用的 Serena MCP 工具，因此验证的是缺少 Serena 时的核心独立路径。Serena 的真实连接、语言后端与符号查询需要在接入环境中另行验证。

旧 Skill 的相关修复路由已定义，但首发独立行为评测未调用外部专项 Skill。评测使用小型 Python 项目，不等于覆盖所有语言、框架、数据库迁移或生产环境。
