# 复现命令（PowerShell）

固定解释器：F:\pytorch\Research\.venv\Scripts\python.exe。这些命令不会升级科研环境。

    Set-Location -LiteralPath 'F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & 'F:\pytorch\Research\.venv\Scripts\python.exe' -B -m pytest tests/test_p0.py -q -p no:cacheprovider --rootdir 'F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z' --confcutdir 'F:\pytorch\Research\outputs\stage0_p0_audit\run_20260927T161311_417313Z' --import-mode importlib --basetemp 'F:\pytorch\Research\cache\stage0_p0_audit\run_20260927T161311_417313Z/pytest_new_unique_run'
    & 'F:\pytorch\Research\.venv\Scripts\python.exe' -B src/run_audit.py
    & 'F:\pytorch\Research\.venv\Scripts\python.exe' -B src/finalize_audit.py

当前目录已有结果，不要原地重跑数据入口。全部结果独占创建，禁止静默覆盖。独立重现时，创建新的 outputs/stage0_p0_audit/run_时间戳 目录，仅复制 src/ 和 tests/test_p0.py，并建立 IMERG/、HIMAWARI_202407/、tests/、logs/。config.py 从自身位置识别输出目录，cache 随 run 名称独立，原始目录不变。

精确依赖变更见 logs/dependency_change_record.json 与 pytest_install.log；无需再次安装。新增 pytest 9.1.1、pluggy 1.6.0、colorama 0.4.6、iniconfig 2.3.0、Pygments 2.21.0，没有升级原有包。

固定排序遍历；文件完整性抽检覆盖各库起点、四分位、中点、四分之三及末尾。seed=42。p99 使用 linear 分位数，比较符 >=；std ddof=1。不是科学阈值。没有批准下一阶段。
