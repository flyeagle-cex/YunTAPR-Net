"""Pure metadata/firewall tests: no real data, model or optimizer."""
from pathlib import Path
import hashlib
import json
import tempfile
from unittest.mock import patch

import numpy as np
import pytest

from yuntapr.experimental.phase_b_v2_real_data_preflight import audit as a


def rows(n, year=2023, month=3):
    return [{"index":str(i),"sample_id":f"SCENE_{year}_{month}_{i}",
             "window_start":f"{year}-{month:02d}-01T00:00:00+00:00",
             "analysis_time":f"{year}-{month:02d}-01T00:30:00+00:00"} for i in range(n)]


@pytest.mark.parametrize("n,expected",[(3,[0,1,2]),(4,[0,2,3]),(5,[0,2,4]),(10,[0,5,9])])
def test_prelabel_positions(n,expected):
    selection,monthly=a.select_monthly(rows(n),2023)
    assert [r["index"] for r in selection]==expected
    assert monthly[0]["positions"]==tuple(expected)


@pytest.mark.parametrize("n",[0,1,2])
def test_no_replacement_for_insufficient_month(n):
    selection,monthly=a.select_monthly(rows(n),2023)
    assert not selection
    assert monthly[0]["status"]=="STOPPED_MONTH_INSUFFICIENT_SCENES"


def test_no_2025_or_outside_frozen_month_selection():
    selection,_=a.select_monthly(rows(3,2023,2)+rows(3,2023,11),2023)
    assert not selection


@pytest.mark.parametrize("kind",["CHECKPOINT","MODEL","OTHER"])
def test_closed_file_roles(kind,tmp_path):
    ledger=a.ReadLedger(tmp_path)
    with pytest.raises(ValueError): ledger.register(tmp_path/"x.json",kind,"0"*64)
    assert not ledger.events


@pytest.mark.parametrize("suffix",[".pt",".pth",".ckpt"])
def test_private_checkpoint_rejected(suffix,tmp_path):
    ledger=a.ReadLedger(tmp_path)
    with pytest.raises(PermissionError): ledger.register(a.OUT/(".local/x"+suffix),"SCALER","0"*64)


def test_unregistered_read(tmp_path):
    ledger=a.ReadLedger(tmp_path)
    with pytest.raises(PermissionError): ledger.read(tmp_path/"missing")
    assert not ledger.events


@pytest.mark.parametrize("kind",["B13","IMERG"])
def test_2025_registration_rejected(kind,tmp_path):
    from yuntapr.data import dataset_b1 as frozen
    p=frozen.H_ROOT/"202503/01/NC_H09_20250301_0000_R21_FLDK.06001_06001.nc" if kind=="B13" else frozen.IMERG_ROOT/"2025/imerg_20250301.nc"
    ledger=a.ReadLedger(tmp_path)
    with pytest.raises((PermissionError,ValueError)): ledger.register(p,kind,"0"*64,year=2025)
    assert not ledger.allowed


def test_public_metadata_cannot_relabel_raw_file(tmp_path):
    ledger=a.ReadLedger(tmp_path)
    with pytest.raises(PermissionError): ledger.register(a.OUT/"x.nc","PUBLIC_METADATA","0"*64)


def test_exact_bytes_and_sha_failure_retained():
    private=a.OUT/".local/unit_fixtures"
    private.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private) as directory:
        p=Path(directory)/"fixture.json"; p.write_bytes(b'{"a":1}\r\n')
        ledger=a.ReadLedger(Path(directory))
        ledger.register(p,"PUBLIC_METADATA",hashlib.sha256(p.read_bytes()).hexdigest())
        assert ledger.read(p)==b'{"a":1}\r\n'
        assert ledger.total_metadata_bytes==9
        p.write_bytes(b'{"a":2}\r\n')
        with pytest.raises(ValueError,match="SHA mismatch"): ledger.read(p)
        assert ledger.events[-1]["status"]=="FAILED"
        assert ledger.events[-1]["bytes_returned"]==9


def test_size_mismatch_no_read():
    private=a.OUT/".local/unit_fixtures"
    private.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private) as directory:
        p=Path(directory)/"fixture.json"; p.write_bytes(b"abc")
        ledger=a.ReadLedger(Path(directory))
        ledger.register(p,"PUBLIC_METADATA",hashlib.sha256(b"abc").hexdigest(),size=4)
        with pytest.raises(ValueError,match="size mismatch"): ledger.read(p)
        assert not ledger.events


@pytest.mark.parametrize("mode",["w","a","r+"])
def test_netcdf_write_mode_never_reads(mode,tmp_path):
    ledger=a.ReadLedger(tmp_path)
    with pytest.raises(PermissionError):
        with ledger.dataset(tmp_path/"missing",mode): pass
    assert not ledger.events


def test_frozen_normalization_dtype_formula():
    x=np.array([[250.,275.,300.]],dtype=np.float32)
    scaler={"mean_K":271.60515414265217,"std_K":19.93959597783802}
    expected=((x.astype(np.float64)-scaler["mean_K"])/scaler["std_K"]).astype(np.float32)
    assert np.array_equal(a.normalize_frozen(x,scaler),expected)


@pytest.mark.parametrize("bad",[np.nan,np.inf,-np.inf])
def test_normalization_nonfinite_rejected(bad):
    with pytest.raises(ValueError): a.normalize_frozen(np.array([bad],np.float32),{"mean_K":1.,"std_K":1.})


@pytest.mark.parametrize("dtype",[np.float64,np.float16,np.int32])
def test_normalization_wrong_dtype(dtype):
    with pytest.raises(ValueError): a.normalize_frozen(np.array([1],dtype),{"mean_K":1.,"std_K":1.})


@pytest.mark.parametrize("std",[0.,-1.,np.inf,np.nan])
def test_scaler_invalid_std(std):
    with pytest.raises(ValueError): a.normalize_frozen(np.ones(1,np.float32),{"mean_K":1.,"std_K":std})


def test_resources_measured_without_psutil():
    result=a.memory()
    assert 0<result["working_set_bytes"]<=result["peak_working_set_bytes"]


def test_real_data_not_a_training_authorization():
    assert a.FLAGS["FORMAL_OPTIMIZER_STEPS"]==0
    assert not a.FLAGS["V2_PHASE_B_AUTHORIZED"]
    assert not a.FLAGS["FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED"]
    assert a.FLAGS["2025_RAW_ACCESS"]==0


@pytest.mark.parametrize("kind,declared_year",[(k,y) for k in ("B13","IMERG") for y in (2025,2023)])
def test_forbidden_date_rejected_before_resolution(kind,declared_year,tmp_path):
    from yuntapr.data import dataset_b1 as frozen
    # The resolver is replaced by an exception: this test cannot inspect a file.
    p=frozen.H_ROOT/"202503/99/SYNTHETIC_20250399.nc" if kind=="B13" else frozen.IMERG_ROOT/"2025/SYNTHETIC_20250399.nc"
    ledger=a.ReadLedger(tmp_path)
    with patch.object(Path,"resolve",side_effect=AssertionError("Filesystem resolution forbidden")):
        with pytest.raises(PermissionError): ledger.register(p,kind,"0"*64,year=declared_year)
    assert not ledger.events and not ledger.allowed


@pytest.mark.parametrize("kind",["B13","IMERG"])
def test_outside_root_rejected_before_resolution(kind,tmp_path):
    ledger=a.ReadLedger(tmp_path)
    p=Path("Q:/SYNTHETIC_ONLY/202303/fixture.nc")
    with patch.object(Path,"resolve",side_effect=AssertionError("Filesystem resolution forbidden")):
        with pytest.raises(PermissionError): ledger.register(p,kind,"0"*64,year=2023)
    assert not ledger.events


@pytest.mark.parametrize("kind",["B13","IMERG"])
def test_allowed_registration_with_synthetic_filesystem_only(kind,tmp_path):
    from yuntapr.data import dataset_b1 as frozen
    p=frozen.H_ROOT/"202303/99/SYNTHETIC_20230399.nc" if kind=="B13" else frozen.IMERG_ROOT/"2023/SYNTHETIC_20230399.nc"
    ledger=a.ReadLedger(tmp_path)
    with patch.object(Path,"resolve",lambda self,*args,**kwargs:self), patch.object(frozen,"guard_source",lambda path,role:path):
        assert ledger.register(p,kind,"0"*64,year=2023)==p
    assert not ledger.events

