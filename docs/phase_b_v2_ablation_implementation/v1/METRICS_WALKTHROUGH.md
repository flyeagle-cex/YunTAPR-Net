# 未加权评价接口解读

metrics.py没有Brier/AUROC/AP实现、没有模型推理，也没有读取样本。它只把调用者已经提供的分子与计数按冻结口径整理。正式数据是否允许传入由未来执行gate控制；本轮所有调用都是合成张量。

ReportingSums(s_occ,s_qr,n_valid,n_rain)是frozen dataclass。__post_init__检查两个分子为真正Python数且finite/非负，计数是真正int、N_valid>0、0<=N_rain<=N_valid；bool不接受。对象保存的是unweighted sums，不能放lambda*S_qr进去冒充原S_qr。接口语义由from_candidate与测试确保，任意外部人手输入float则仍需来源审查。

from_candidate(result)是@classmethod，首参cls代表当前类，不是对象self；它用float(result.s_occ.detach())和s_qr生成汇总。detach不改变数值，而是切断本报告分支的梯度图。GPU到Python scalar会同步，因此不能把汇总接口时间当纯训练吞吐。

conditional_pinball是@property，使用者写report.conditional_pinball而不是函数括号；返回S_qr/N_rain，N_rain=0返回None。pooled(other)先加分子及计数，再创建经过同样检查的新对象，避免平均两个batch比例。它不合并seed模型预测，也不把seed×像元当独立重复。

common_validation_sums(logit,qlog,rate,imerg_valid,yunnan_mask)被@torch.no_grad()修饰，这些运算不建训练梯度图。它将logit.double()，显式get_config('E0')后调用同一受保护算术入口，得到gamma2/lambda1的FP64 common core分子。训练E1的gamma0或E2的lambda2绝不能从训练result直接替换共同core。

例T2：S_qr3、N_rain2，CPB1.5；把这个对象与自己pooled后6/4仍1.5。若两个batch雨数不等，则应使用总S_qr/总N_rain，不是两个CPB简单平均。所有示例均为合成教学数值。未来指标还须绑定年份、域、样本身份、missingness及原科学审查规则，当前接口不是完整科学observer。
