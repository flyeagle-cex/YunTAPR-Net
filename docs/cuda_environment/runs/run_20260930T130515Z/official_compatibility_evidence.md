# Official CUDA/PyTorch compatibility gate

Checked 2026-09-30 UTC, before creating the CUDA environment or installing a package. Observed machine: Windows 11 build 26100, Python 3.12.14, NVIDIA GeForce RTX 5060 Laptop GPU, compute capability 12.0, driver 573.24. The CPU reference environment is `F:\pytorch\Research\.venv`; it must remain unchanged.

| Question | Official evidence | Gate result |
|---|---|---|
| Windows and Python | [PyTorch Windows installation prerequisites](https://docs.pytorch.org/get-started/locally/) list Windows and Python 3.9–3.12. [Official CUDA 12.8 wheel index](https://download.pytorch.org/whl/cu128/torch/) explicitly lists `torch-2.11.0+cu128-cp312-cp312-win_amd64.whl`. | PASS for Python 3.12 / Windows x86-64 |
| Blackwell / sm_120 | [PyTorch release 2.11 CUDA support matrix proposal](https://github.com/pytorch/pytorch/issues/172351) explicitly lists CUDA 12.8.1 for Windows x86-64 with Blackwell 12.0; [PyTorch 2.7 release](https://pytorch.org/blog/pytorch-2-7/) introduced Blackwell/CUDA 12.8 support. [NVIDIA compute capability list](https://developer.nvidia.com/cuda-gpus) lists GeForce RTX 5060 at 12.0. Local `nvidia-smi` identifies the laptop variant at 12.0. | SUPPORTED_BINARY_CANDIDATE; execution requires local kernel smoke |
| Driver | [NVIDIA CUDA 12.8 release notes](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-toolkit-release-notes/index.html) list Windows driver >=570.65 for CUDA 12.8 GA; observed 573.24. The `nvidia-smi` "CUDA Version 12.8" field is a driver capability ceiling, not an installed PyTorch runtime. | PASS for CUDA 12.8; CUDA 13.0 excluded |
| Excluded newer wheel | [PyTorch 2.12 release notice](https://pytorch.org/blog/pytorch-2-12-release-blog/) directs Blackwell users to CUDA 13.0+ after cu128 deprecation and states Windows driver >=580.88. Current 573.24 does not meet that requirement. | DO NOT SELECT CUDA 13.x |
| Known exact-GPU risk | A [PyTorch project issue](https://github.com/pytorch/pytorch/issues/174731) reports RTX 5060 on Windows kernel failures with 2.7.0, 2.7.1, and 2.10.0 cu128. It does not establish that 2.11 fails or succeeds on this laptop. Therefore `torch.cuda.is_available()` alone is insufficient; elementwise, matmul, Conv2d, and backward kernels are mandatory gates. | STOP immediately if local kernels fail |

Selected official binary candidate: **PyTorch 2.11.0+cu128** for Windows CPython 3.12 x86-64, from the [official CUDA 12.8 index](https://download.pytorch.org/whl/cu128). The command derived from the [official PyTorch previous-version instructions](https://pytorch.org/get-started/previous-versions/) is:

```powershell
F:\pytorch\Research\.venv-cuda\Scripts\python.exe -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
```

`torchvision` and `torchaudio` are omitted because YunTAPR-Net does not import them. No system CUDA Toolkit or driver change is planned. This is a compatibility candidate established from official packaging evidence, **not** a claim of successful local kernel execution. The separate CUDA environment must pass the explicit smoke before any B0 GPU work.
