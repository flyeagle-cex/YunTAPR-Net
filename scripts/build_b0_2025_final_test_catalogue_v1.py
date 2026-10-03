"""Catalogue-only runner. This release authorizes preflight fixtures, not raw QC."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'scripts')]
from yuntapr.evaluation import catalogue_gate_b0 as gate

def catalogue(args):
    # Mandatory authorization is checked before backend import/construction,
    # discovery, existence/size checks, hashing and output directory creation.
    authority=gate.CatalogueAuthority.load(args.authorization,args.authorization_sha256)
    authority.require_catalogue();protocol=gate.load_protocol()
    source_guard=gate.CatalogueSourceGuard(authority);backend=None;owned_output=False
    output=gate.safe_artifact_path(args.output)
    gate.safe_artifact_path(args.staging_root)
    try:
        with gate.CatalogueOnlyGuard(),source_guard:
            output.mkdir(parents=True,exist_ok=False);owned_output=True
            from yuntapr.evaluation.catalogue_backend_b0 import RealCatalogueBackend
            backend=RealCatalogueBackend(protocol,authority,args.staging_root)
            return gate.build_catalogue(authority,backend,output,_output_seal=gate._SEAL)
    except Exception as error:
        # Never log raw arrays, arbitrary exception messages, attrs or outcomes.
        if owned_output and not (output/'failure.json').exists():
            telemetry_invalid=False
            try:telemetry=gate.sanitized_telemetry(dict(getattr(backend,'telemetry',{})))
            except (TypeError,ValueError):telemetry={};telemetry_invalid=True
            gate.save(output/'failure.json',{'status':'CATALOGUE_STOPPED','error_type':type(error).__name__,
                '2025_CATALOGUE_QC_ACCESS':source_guard.qc_access,
                'raw_source_open_events':source_guard.raw_open_events,'raw_access_telemetry':telemetry,
                'telemetry_sanitization_failed':telemetry_invalid,
                '2025_FINAL_TEST_EXECUTED':False,'2025_MODEL_INFERENCE_SCENES':0,
                '2025_FINAL_TEST_METRICS_COMPUTED':False,'2025_TARGET_OUTCOME_SUMMARIES_EXPOSED':False,
                'failed_utc':gate.now()})
        raise

def preflight():
    from preflight_b0_catalogue_v1_1 import preflight
    return preflight()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','catalogue'])
    parser.add_argument('--authorization',type=Path);parser.add_argument('--authorization-sha256')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--staging-root',type=Path)
    args=parser.parse_args()
    if args.action=='preflight':preflight()
    else:
        if args.output is None or args.staging_root is None:
            parser.error('Future authorized catalogue requires explicit output and bounded English staging root')
        try:catalogue(args)
        except Exception as error:
            import json
            print(json.dumps({'status':'CATALOGUE_STOPPED','error_type':type(error).__name__}),file=sys.stderr)
            raise SystemExit(1) from None
