# Context margins — engineering evidence only

各来源与共同候选的西/东/南/北余量见context_margins.csv。距离以云南polygon包络到source数值包络edge计算，是最大包络余量，不能跳过footprint holes或时变NoData。负数表示对应方向不足。

共同候选的 west/east/south/north = 0.5341° / 0.8058° / 1.1394° / 0.7489°。以polygon中纬度计算东西方向、以中经度计算南北方向的WGS84测地近似距离约53.83 / 81.22 / 126.14 / 83.01 km。不是沿复杂省界处处等宽的buffer，也不是天气系统所需context的科学估计。

不选择0.5°/1°/2°或其他margin，不冻结bbox。对于SRTM大包络仍有外部3tile缺口，不能直接把所有包络余量认作无缝context。
