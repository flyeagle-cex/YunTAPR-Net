"""Pin a completed exact fit in engineering v3, never in scientific numeric values."""
import shutil
import yaml
from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256


def main():
    science, config = load_contract()
    relative = science["normalization"]["phase_a"]["artifact"]
    artifact = REPO_ROOT / relative
    config["normalization_artifact"] = {"path": relative, "sha256": sha256(artifact),
                                         "status": "DEVELOPMENT_DERIVED_PARAMETER"}
    path = REPO_ROOT/"config/b0_engineering_v3.yaml"
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8", newline="\n")
    shutil.copyfile(path, artifact.parent/"engineering_config_snapshot_v3.yaml")
    from yuntapr.data.normalization import PhaseANormalizer
    print(PhaseANormalizer.from_pinned())


if __name__ == "__main__":
    main()
