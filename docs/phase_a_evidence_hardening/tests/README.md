# 实际执行记录

audit_attempt_001：24 pass/1 fail，完整异常/traceback 保存于 audit_results.json；原报告约 20.24 与源 float32 20.2399997711 精度误比较。修正为严格比较 float32 来源值；没有修改原统计。

audit_attempt_002：25 pass/0 fail。synthetic_attempt_001.xml：37 pass/1 fail，解析平面起伏度 100.00000000000001 与 100 的 exact assertion 不合；修为 abs=1e-12 的解析数值断言。synthetic_attempt_002.xml：48 pass/0 fail，增加实际 v2 tiny CPU 数值接口与配准拒绝测试。无 backward/optimizer 更新。

早期状态发现还出现：cwd 不是仓库（随后定位主仓库）；rg 遇旧 temp 目录权限错误；CIM 进程命令行权限拒绝（使用只读 Get-Process，未杀进程）；一次 Python 默认 GBK 解码历史 UTF-8 JSON 失败（改显式 UTF-8）；Git 网络代理沙箱连接失败，沙箱外经批准的 ls-remote 确认 main。未把失败当成通过或删除相关旧文件。发现阶段工具输出保留于本对话；核心实验和合成失败的完整日志在本目录。

不执行旧训练 full suite、optimizer/backward fixture、真实 pixel 测试、private checkpoint reopen、正式 v2 Phase-B 预检、真实事件/地形评价。PDF 和交付验证另有记录，不能把历史 28/770 checks 加入本轮通过数。

PDF 首次生成因 Python 字符串转义及表格列拼接产生非法 preamble；原 source/generator 保存在 pdf_attempt_001，首轮编译错误在本对话，关键错误为 Illegal pream-token (e)。第二次编译的完整失败日志 pdf_compile_attempt_002.json 指明 dimexpr 乘法单位非法；修正后桌面编译成功。首版导出仍有缺失 θ/≤ 字形及长标识符越界，改用 LaTeX 数学字形和显式可断行点后导出最终 11 页；两版完整本地导出日志和 PDF 均保留，最终页图全部实际查看。

delivery_verification_attempt_001.json 保留首轮交付 13 pass/1 error，原因是科研 Python 环境未安装 pypdf；未安装新依赖，切换到 Codex 已提供 pypdf 的 bundled Python 后，delivery_verification.json 实际为 14 pass/0 fail/0 error。当前总计 25+48+14=87，不把历史失败或旧检查混入当前通过数。

公开副本仅移除设备名、绝对 checkout/runtime 路径等本机标识；所有原始未脱敏日志留在本地 .local/，不上传 GitHub。科学数值、异常内容和状态未改。渲染 PNG、重复中间 PDF 和本地 publication allowlist 也不上传，最终 PDF、LaTeX、失败 source、编译日志和审核 JSON 可公开审查。
