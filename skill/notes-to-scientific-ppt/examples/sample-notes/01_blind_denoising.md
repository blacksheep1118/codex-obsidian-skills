# Blind Image Denoising

## 问题背景

真实图像的噪声分布通常不是固定高斯噪声。盲去噪需要在未知噪声水平下恢复干净图像。

## 方法总览

以 CBDNet 为例，噪声估计子网络先预测噪声水平图，非盲去噪子网络再把该图与噪声图像一起用于恢复。

## 关键公式

$$
y = x + n, \quad n \sim \mathcal{N}(0, \sigma^2)
$$

其中 $y$ 是观测图像，$x$ 是干净图像，$n$ 是噪声，$\sigma$ 表示噪声水平。这是便于说明的加性高斯基线；CBDNet 还用信号相关的异方差高斯噪声与真实噪声数据训练，不能把该基线当成完整的真实噪声模型。

## 实验

| 数据集 | 指标 | 结论 |
| --- | --- | --- |
| DND | PSNR / SSIM | 论文在真实噪声基准上报告了有竞争力的结果；结论只适用于论文的训练与评测设置 |

## 局限

当真实噪声不满足建模假设时，噪声水平图可能误导后续去噪。

参考: [Toward Convolutional Blind Denoising of Real Photographs (CVPR 2019)](https://openaccess.thecvf.com/content_CVPR_2019/html/Guo_Toward_Convolutional_Blind_Denoising_of_Real_Photographs_CVPR_2019_paper.html)
