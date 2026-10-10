# 测试与首轮失败记录

- cpu_attempt_001：45 passed、1 failed。流式累计的手工q首值0.05低于冻结log1p(0.1)支撑下界，原始guard正确拒绝。修复仅把夹具首值设为0.2；没有修改model、tau、epsilon、loss或容差。
- cpu_repair_attempt_001：仅重跑上述两个streaming测试，2 passed、45 deselected。
- checkpoint_attempt_001：32 passed；新完整epoch schema、故障注入及恢复计数。
- cuda_attempt_001：6 passed；30实际optimizer steps，一次固定预算campaign完成，未重跑成功组合。
- stop_attempt_001：2 passed；实际架构NaN参考异常停止，0 steps。

唯一最终检查79 CPU + 8 CUDA全部有通过记录；初次1失败保留，当前未解决0。tests/attempt_summary.json按testcase身份去重，重复修复不增加唯一数。新namespace实际source SHA与六个CUDA记录一致；没有测试后改变引擎源码再声称同版本通过。

完整机器日志留在.local/raw_test_logs；公开log/XML仅替换机器路径，不改变测试输出或失败原因。旧loss、隔离、批次、短程Runner测试未重跑。先前12次合成更新保持历史事实，本轮独立固定30次，正式更新仍0。
