# v2 配对 Phase-A 开发实验决策包

两模型完整终止审计与全量 2024 只读 BEST 评价已通过。
样本集合：2023 Train=10,455；2024 Validation=10,501；2025 不访问；Phase-B 不授权。

|模型|BEST epoch|完整 epoch|global_val_core_loss|Brier|AUROC|AP|conditional pinball|
|---|---:|---:|---:|---:|---:|---:|---:|
|B0_MATCHED_V2|9|17|0.0487596076194|0.0968676263395|0.886357037272|0.567232691216|0.124885458292|
|B1_V2|9|17|0.0478164042666|0.0952534705091|0.893468821807|0.585904924452|0.124113222868|

完整证据见 JSON/CSV；可编辑报告源为同目录 LaTeX。
PDF 排版核验与最终 GitHub 发布仍待独立收尾，不将这些未运行项目标为 PASS。
RESEARCHER_PHASE_A_REVIEW_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false。
