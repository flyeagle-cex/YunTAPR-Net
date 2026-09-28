# 来源链结论

main_provenance_status = SUPPORTED_WITH_CAVEATS
thermo_provenance_status = SUPPORTED_WITH_CAVEATS
main_thermo_source_lineage_status = SUPPORTED_WITH_CAVEATS
compatibility = PARTIALLY_COMPATIBLE
Dataset-layer question = NEEDS_MORE_PROVENANCE

官方产品身份、12960 组原始 source token、20 组当前文件复核共同支持同一 forecast family 和按 init/lead 配对的工程解释。NCAR 是归档/子集服务，NOAA/NCEP 是生成机构，AWS 是分发途径；多字段出现这些名称不自动构成来源冲突。

关键缺口仍为获取源代码/执行版本、上游载荷或中间文件校验和、当前文件内容与历史转换的关联。60 条带大小的所选事件中 54 条与当前文件大小不同，不能直接关联；大小相同的 6 条也不能替代内容哈希。英语历史根目录映射未证实。文件后续标准化是一种可能解释，不作为已证实原因。

旧索引 8820 行两分支大小全部符合当前 inventory，加强该派生索引的对应关系，但不足以追到上游 GRIB。当前结论保留 caveats，不建议自动升级 COMPATIBLE_CANDIDATE，不建议拒绝已通过的结构/时间/变量证据。研究者决定还需要什么 provenance 才能进入组合准备。
