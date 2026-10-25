# B2 本地训练进度页面

复用既有 Stage4 监测器的只读 SQLite、元数据解析、进程身份和本机资源查询；不导入训练模块，不读取气象源、缓存张量或模型权重，不提供启停/重放接口。仅绑定127.0.0.1，页面打开时每15秒请求快照，服务端缓存10秒；隐藏标签暂停自动请求。

```text
python tools/b2_monitor/server.py --experiment <B2本地运行目录> --training-pid <真实训练子进程PID> --service-dir docs/research_readiness/.local/b2_monitor --port 0
```

实际网址写入私有service.json和本地快捷方式。展示真实更新数、九轮Train/Dev/LAST、源读取预算、逐轮数值指标与硬件资源。进度百分比使用已交付源字节/固定预算，不能代替完成收据；进程未知或失败会明确标注。此页面不改变已授权的a353021训练代码或科研协议。
