# B0 2025 catalogue-only authorization v1.1

研究者仅授权真实 2025 March–September catalogue QC 与资格样本清单冻结。本文件不授权 FINAL 加载、模型实例化、推理、训练或任何结果统计。

独立能力文件：`config/evaluation/b0_2025_catalogue_only_authorization_v1.1.json`。授权文件 SHA256：`00ed1e1de442832e2197d71ee5412aafa95496b144cae73781adfeb3e13ac1c0`。

研究者补充批准只绑定既有 completion manifest 的独立适配器。原 v1.1 代码、协议、28 列 candidate schema、12 列 identity projection 和资格规则均保持原字节。此路径批准只用于 manifest 元数据，不扩大 raw source 范围。

FINAL 完整性按研究者明确决定，只核验冻结 identity 记录。实际 FINAL 文件未打开，实际文件 SHA256 未重新计算；登记的 SHA 值不能解释为本轮重新验签。

本授权绑定以下元数据：

```json
{
  "version": "v1.1",
  "AUTHORIZED_BY": "RESEARCHER",
  "scope": "B0_2025_FINAL_TEST_CATALOGUE_ONLY",
  "baseline_commit": "c661d8a31dbd8cc205624716d8a2d0fcd0867023",
  "FINAL_TEST_CATALOGUE_AUTHORIZED": true,
  "FINAL_TEST_2025_AUTHORIZED": false,
  "protocol_sha256": "b1be82d5bc03293c35ddc793faa1187e97fa48c537039181c0eb68a689f15eb8",
  "implementation_sha256": {
    "src/yuntapr/__init__.py": "2d4dae85df531298acab4ae4da33907d968e57235429fc219ac04623d4de5bdd",
    "src/yuntapr/contracts/__init__.py": "1ecb7fb4f558e7e8139a774374db54f98096871d9979b8fccee253b7dd28f645",
    "src/yuntapr/contracts/loader.py": "776d1aa774342e955eba9ff28809477e0f357a5d60eec7819ba55d3351b06964",
    "src/yuntapr/data/__init__.py": "ec826cc0faeb4a373ff65877fdc980032baad23e0a2525d006ffda2b2e0912a7",
    "src/yuntapr/data/dataset_b0.py": "19e5ef7c16c2ce1fdd0df2a16acc44bf740b9d4b5400001c406136879c8762e3",
    "src/yuntapr/data/development_audit.py": "ed65703ded7e6db6e14ebc5fcd9b772ebc76486e5e8b6a476b66dfba1dd7fe8b",
    "src/yuntapr/data/formal_policy.py": "3c0a0b97dc25b3ae0f942ec2cef367217fc981c01d1f09501d9f957adab2f490",
    "src/yuntapr/data/himawari_b13.py": "4ce00bd7dc44839cbb5feb6e36e404931fc547ba5cc726a577be5120926a4857",
    "src/yuntapr/data/imerg_v07.py": "eff89d4a2fb21473288b90f892799866ff839b7119901886e2ea358183b8d7b2",
    "src/yuntapr/data/masks.py": "c397a5866af834098fd5f36e4acd23a26dfa607058ad298f8781a9766d5a8542",
    "src/yuntapr/data/normalization.py": "cc10f0fc37e9fc2ac3e163025881c02ccbb805a35b884bc86702f6a72b7e6afb",
    "src/yuntapr/data/sample_schema.py": "371a051b2aa7b5b2ac193df513a4ecc27850e923a371a4ec5cb3fe59a9d61b99",
    "src/yuntapr/data/staging.py": "f84c55bfba9b998b2ee3486ee08b5857a2a1f48f76c68245dc7a06f31adebbe4",
    "src/yuntapr/losses/__init__.py": "40206e500ba1cb5df1a4858f754fcdf83e49a108d0ec73cab31dafc9152aac1e",
    "src/yuntapr/losses/focal.py": "7cd5042f88856c37889bee86f1f340e0e93373486620ee4a7a4d1f61df380e58",
    "src/yuntapr/losses/pinball.py": "b3ebd505238fe881039f143fe9c73462735782ecfa0dee1e63b5463c3cb49b78",
    "src/yuntapr/losses/total_loss.py": "8e52d3422ec2e8b727c696d470a3d21910c7f1137f901cd5afc1201b9dd9e2d0",
    "src/yuntapr/metrics/__init__.py": "350f75bcc8be415c283773a339d442a62cc2192d0bb84b62576cc54f4f074cf2",
    "src/yuntapr/metrics/deterministic.py": "43db58494627a6f83fee72241a394937fb144f481f580d40fe1018b5e1a91793",
    "src/yuntapr/metrics/probabilistic.py": "310147262c0090e805d45bba36d7f992f157da8e52939a4361e18e4e4d8da110",
    "src/yuntapr/models/__init__.py": "1e98d33cb0665c9eb26b67921b8ef55ab1b76958f25240bf1ebd376e5218a26e",
    "src/yuntapr/models/b0.py": "6b9b8c28c8b12b7948d9658deedc68e0e54df42a956850d357d4f15d06c6227d",
    "src/yuntapr/models/backbone_b0.py": "79f35a29349eae9dcba705b7e127899972d0bcea723773043547f0d7f341819f",
    "src/yuntapr/models/blocks.py": "925ed0246258d4f709f4279f22e3829cf5aff89ce44dbe67f93ab1cb7c40bfd6",
    "src/yuntapr/models/monotonic_quantiles.py": "d0b26433b986d5ce89a3eec92ee88cdf47d33d09809eba5a8bf11b5a2152c532",
    "src/yuntapr/models/probability_heads.py": "6d807ff03c4a458b0406dd295df774c98e859d62125df9fc289176deb61eba50",
    "src/yuntapr/spatial/__init__.py": "811e5f8e967d25595aa30c5976ded23d1d9ed35334c34fb19fc06fe86376ae5c",
    "src/yuntapr/spatial/projection.py": "88661698d642e1f2e350d819452bdedd075f42da17bfe18e0ab5efde0e34662c",
    "src/yuntapr/spatial/sp04_mapping.py": "a4a4d0c8744acd6754588f01c7d1976ccd109b7c9224ba362a4bc474cdc35202",
    "src/yuntapr/training/__init__.py": "1d9d8338a97125e175d456f4260be66331a28f4949f62d1cacbade34089b8258",
    "src/yuntapr/training/batch_contract.py": "e5089ce2a51a9ce0eb7e0b06b0ccf12f655a946b807443e7adcfb17fc336224e",
    "src/yuntapr/training/formal_phase_a.py": "61061d245f1f614211d1418eec7d01cd80039dd37e58fb9650d37b05887b3c99",
    "src/yuntapr/training/formal_phase_b.py": "9f9e8fb203334a4195c982181553daa11fb95f327fccfa2f626cf1dab91a2b55",
    "src/yuntapr/training/forward_step.py": "a0d3f52ece5d383c2f8016c1d0245f963fa637dbe253414a7907131381d7170c",
    "src/yuntapr/training/phase_a_protocol.py": "95ed5a182590a8a84ee7659720a89ea7e36687800cb7e7441f60d30d795a8b19",
    "src/yuntapr/training/phase_a_validation.py": "9b654748879d22d10805728f6b25ef40f2042a0ef8121e588d4a3769995d7a1c",
    "src/yuntapr/training/phase_b_preparation.py": "789338ea040e4999fa2e420d14ef402e37a4f5208cb0dbbe7f5c89739ddc410e",
    "src/yuntapr/training/scientific_review.py": "303bf6b6f181bb9147d22ed970dd3bc6c1b233052d1952ec2c9ac8d8531c3b01",
    "scripts/train_b0_phase_b_finalfit_v1.py": "1bddb634909ff6786e69e67becd4052e6829e6619e3d6513bccf97709f44c3b8",
    "src/yuntapr/evaluation/__init__.py": "129e5b9fc26dafd3b7c5e7d5b0bd676dced59e2cd6d2b134ee9742a56d19fddc",
    "src/yuntapr/evaluation/final_test_b0.py": "ac73a66d202964da465ca79abb3e24ad439febe37fec72f6c8ef83ae62bc4b8a",
    "scripts/test_b0_2025_final_v1.py": "3e11c2f969b82d442d96de85388cdaac59998399edbcc697c4345e41a35bc4d1",
    "src/yuntapr/evaluation/catalogue_gate_b0.py": "881e587ba7ebcb217645d5906f623ce6c455c9c6479d0fc98d43f5c1d63dcd07",
    "src/yuntapr/evaluation/catalogue_backend_b0.py": "3fb2a6246aa8589f2a990f84e9547e04ab73f25816929999d19fe6d69efff375",
    "src/yuntapr/evaluation/final_test_b0_v1_1.py": "0eb2f72feca6f568751dcf7a64319a9aadf8637bfa5061ba97fd77512487a045",
    "scripts/build_b0_2025_final_test_catalogue_v1.py": "245a84bcbec011c2d7735db9cc549797b3489865a22f79b59f65196e2621d421",
    "scripts/test_b0_2025_final_v1_1.py": "859e6f2cebc5a0b919580d44a596598bdc4dcd66062d34099c98903fa58b2963",
    "scripts/preflight_b0_catalogue_v1_1.py": "425ffffad87034e69960691a7f976f91c4c6be1a4178bf3626d1cd9ad924541d",
    "tests/final_test_catalogue/test_catalogue_gate.py": "e19abc6429122bb3f7f69e381ca011732a41991639806e3ce96af05378ec6947",
    "tests/final_test_b0/test_catalogue_backend_v1_1.py": "cf2103bd5a1003e7f70e7c738c98a82b4d07826e21d3152896cbf6a05e405095"
  },
  "execution_implementation_sha256": {
    "src/yuntapr/evaluation/catalogue_execution_v1_1.py": "fda661f07056da8276db97f7576b7b765c6514f98498fcf97ec9d4fb0d1035c6",
    "scripts/execute_b0_2025_catalogue_only_v1_1.py": "93a20731ad5e2a0e0957b94d84b9be9ee489ecd9899efce60ef16016ea816f30",
    "tests/final_test_catalogue/test_catalogue_execution_v1_1.py": "467a5d3b52d5156df23bf5d72312771d683ea9559af8e8abfc83eec15d1aa47b"
  },
  "catalogue_implementation_sha256": "881e587ba7ebcb217645d5906f623ce6c455c9c6479d0fc98d43f5c1d63dcd07",
  "backend_implementation_sha256": "3fb2a6246aa8589f2a990f84e9547e04ab73f25816929999d19fe6d69efff375",
  "FINAL_sha256": "05359d2fee2ae61daf654ae5a59b7977cb65247fd46d97a69a690a0133da7f65",
  "FINAL_identity_record_sha256": "d88bc7ec861ffcfd654ba339ea519f5fc061adb6ebcaf7477d052230b4b5899a",
  "normalization_sha256": "c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327",
  "candidate_count": 10272,
  "source_roots": {
    "Himawari": "H:\\葵花202303_202510",
    "IMERG": "F:\\云南极端降水数据\\raw\\IMERG"
  },
  "imerg_completion_manifest_path": "F:\\云南极端降水数据\\manifests\\imerg_manifest.jsonl",
  "imerg_completion_manifest_sha256": "7efef36f05545ac6b9482e5d8fd68367aea875bc59145606a1bf45b5848968c1",
  "completion_manifest_metadata_path_exception_approved": true,
  "FINAL_verification_mode": "FROZEN_IDENTITY_RECORD_ONLY_RESEARCHER_APPROVED",
  "created_utc": "2026-10-03T02:13:16.730984+00:00",
  "researcher_request_sha256": "475e23572c07bc5b0174cab03172c4d3f5e0602a7c8f04326b8a6db0f8f2ba5d"
}
```

适配器源码与测试 SHA 由本授权锁定；catalogue freeze record 保持原冻结 schema，其 `catalogue_authorization_sha256` 绑定本授权，因而递归绑定新适配器。旧 `implementation_sha256` 仍是原 v1.1 bundle，未被静默替换。

固定范围为 [2025-03-01 00:00 UTC, 2025-10-01 00:00 UTC)，10272 个半小时槽位。只记录源身份、有效性 QC、时间/网格 provenance 与固定资格枚举；不使用降雨强度决定资格。基础设施/复制 SHA/清理/身份异常必须 STOP，固定样本拒绝原因按原规则写入。

完成 catalogue freeze 后 STOP。真正 Final Test 必须另获第二阶段研究者授权。
