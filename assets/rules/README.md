# 权威规则

本目录保存 Context Atlas 的中文权威规则与机器目录。每条规则的正文只在
[知识治理规则](知识治理规则.md)中维护一次；`catalog.json` 只保存编号、名称、权威链接和最低执行覆盖类型。

Skill、Schema、模板、检查器、标准操作与验收用例必须使用带文件路径的规则链接主动声明依赖。运行
`py scripts/check_rule_coverage.py --print-index` 可生成反向索引；反向索引是临时结果，不提交为第二份权威清单。
