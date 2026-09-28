# Himawari B13 reader smoke

状态 PASS。读取 16 个真实 B13 源文件，推理阶段另对前 4 个再次读取。主 smoke 未用 synthetic observations。

变量 `tbb_13`；packed dtype `int16`；decoded dtype `float32`；shape `[501, 501]`；dimensions `['latitude', 'longitude']`；units `K`。

本批文件没有显式 `_FillValue`；`missing_value=-32768`。实际 scale_factor=0.009999999776482582、add_offset=273.1499938964844、valid_min=-27315、valid_max=32767。原 metadata 每样本完整保存在 reader_actual_metadata.json，不把实际 float32 存储常数替换成十进制近似值。

复用 Stage-0 `read_himawari.py` 的 decode_packed 和 _time 原函数 AST；快照和原脚本 hash 见 logs/reader_reuse.json。仅增加 tbb_13 变量选择/维度检查封装，不调用七通道读入函数，不加载其他通道。旧 task runner/config 不执行。IMERG 同样复用 P0 decode_values 的原函数体。

valid mask 在 packed domain 排除 sentinel/非有限/超 metadata 范围，再排除解码非有限值；invalid 保留 NaN。原纬度 descending 原样读取。固定坐标 gather 在空间接口中显式记录，不在 reader 内 flip。

16 个实际 crop 输入均 1024/1024 有效；这是本小样本事实，不是全月科学 QC 结论。为避免在 smoke 引入填补规则，本轮模型只接受完全有效输入 crop；遇到不满足的样本须拒绝并记录，不填零。该 eligibility 条件不是正式科研样本剔除政策。本轮未因此拒绝任何已选 raw 样本。
