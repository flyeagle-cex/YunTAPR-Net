from pathlib import Path
import numpy as np
import pytest
import torch
from data.b0_smoke_dataset import AuditedReaders,check_causality,nearest_alignment,BoundedStaging
from models.b0_smoke import B0SmokeUNet
from losses.b0_smoke_loss import masked_mse
RUN=Path(__file__).resolve().parents[1]

def test_b13_reused_packed_decoder():
 r=AuditedReaders(RUN/'src/vendor')
 a=np.array([[100,-9999],[200,300]],dtype=np.int16)
 attrs=dict(scale_factor=0.1,add_offset=200.,valid_min=0,valid_max=500,_FillValue=-9999)
 x,m=r.decode_b13(a,attrs)
 assert x.dtype==np.float32 and m.dtype==bool
 assert x[0,0]==210 and np.isnan(x[0,1]) and not m[0,1]

def test_imerg_reused_decoder_missing_not_zero():
 r=AuditedReaders(RUN/'src/vendor')
 x,m,_,_=r.decode_imerg(np.array([0.,np.nan,-9999.,2.]),{'_FillValue':-9999.})
 assert m.tolist()==[True,False,False,True]
 assert x[0]==0 and np.isnan(x[1:3]).all()

def test_zero_rain_valid_and_included_in_loss():
 p=torch.tensor([2.,10.],requires_grad=True);t=torch.tensor([0.,float('nan')]);m=torch.tensor([True,False])
 loss=masked_mse(p,t,m);assert loss.item()==4
 loss.backward();assert p.grad.tolist()==[4.,0.]

def test_masked_pixel_excluded_even_if_prediction_nan():
 p=torch.tensor([3.,float('nan')],requires_grad=True);t=torch.tensor([1.,float('nan')]);m=torch.tensor([True,False])
 loss=masked_mse(p,t,m);assert loss.item()==4
 loss.backward();assert p.grad[1]==0

def test_empty_valid_target_rejected():
 with pytest.raises(ValueError):masked_mse(torch.ones(2),torch.ones(2),torch.zeros(2,dtype=torch.bool))

def test_causality_valid():
 assert check_causality(dict(analysis_time='2024-07-01T00:30:00Z',nominal_time='2024-07-01T00:20:00Z',obs_start='2024-07-01T00:20:40Z',obs_end='2024-07-01T00:29:40Z'))

@pytest.mark.parametrize('nom,end',[('00:20:00','00:30:01'),('00:40:00','00:49:40')])
def test_future_frame_or_observation_rejected(nom,end):
 with pytest.raises(ValueError,match='Future'):
  check_causality(dict(analysis_time='2024-07-01T00:30:00Z',nominal_time='2024-07-01T'+nom+'Z',obs_start='2024-07-01T00:20:40Z',obs_end='2024-07-01T'+end+'Z'))

def test_coordinate_gather_explicit_orientation():
 lat=np.array([3.,2.,1.]);lon=np.array([10.,11.,12.]);x=lat[:,None]+lon[None,:]
 out,m,info=nearest_alignment(x,np.ones_like(x,dtype=bool),lat,lon,np.array([1.,2.]),np.array([10.,12.]))
 assert np.array_equal(out,np.array([[11.,13.],[12.,14.]]))
 assert info['source_row_indices']==[2,1] and info['source_lat_direction']=='descending'
 assert info['output_lat_direction']=='ascending'

def test_alignment_preserves_invalid_nan():
 x=np.array([[1.,np.nan],[3.,4.]])
 y,m,_=nearest_alignment(x,np.isfinite(x),np.array([0.,1.]),np.array([0.,1.]),np.array([0.,1.]),np.array([0.,1.]))
 assert np.isnan(y[0,1]) and not m[0,1]

def test_alignment_outside_coverage_rejected():
 with pytest.raises(ValueError,match='extrapolation'):
  nearest_alignment(np.ones((2,2)),np.ones((2,2),bool),np.array([0.,1.]),np.array([0.,1.]),np.array([-1.,0.]),np.array([0.,1.]))

@pytest.mark.parametrize('batch',[1,4])
def test_model_forward_output_shape(batch):
 torch.manual_seed(42);m=B0SmokeUNet();x=torch.full((batch,1,32,32),250.)
 y=m(x);assert y.shape==x.shape and torch.isfinite(y).all() and (y>=0).all()

def test_missing_model_input_not_filled():
 x=torch.full((1,1,32,32),250.);x[0,0,0,0]=float('nan')
 with pytest.raises(ValueError,match='missing fill'):B0SmokeUNet()(x)

def test_multichannel_rejected():
 with pytest.raises(ValueError):B0SmokeUNet()(torch.ones((1,7,32,32)))

def test_backward_finite_gradients_optimizer_changes_parameters():
 torch.manual_seed(42);model=B0SmokeUNet();opt=torch.optim.Adam(model.parameters(),lr=.001)
 pred=model(torch.full((2,1,16,16),250.));target=torch.ones_like(pred)
 loss=masked_mse(pred,target,torch.ones_like(target,dtype=torch.bool));assert torch.isfinite(loss)
 loss.backward();params=list(model.parameters());assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in params)
 before=[p.detach().clone() for p in params];opt.step();assert any(not torch.equal(a,p) for a,p in zip(before,params))

def test_checkpoint_safe_reload_new_instance(tmp_path):
 model=B0SmokeUNet().eval();x=torch.full((1,1,16,16),250.)
 with torch.no_grad():a=model(x)
 p=tmp_path/'unit_smoke_checkpoint.pt';torch.save({'model_state_dict':model.state_dict()},p)
 other=B0SmokeUNet().eval();other.load_state_dict(torch.load(p,weights_only=True)['model_state_dict'])
 with torch.no_grad():b=other(x)
 assert torch.equal(a,b)

def test_staging_cannot_read_outside_allowlist(tmp_path):
 (tmp_path/'logs').mkdir();st=BoundedStaging(tmp_path,[])
 p=tmp_path/'other.nc';p.write_bytes(b'not-raw')
 with pytest.raises(ValueError,match='allowlist'):
  with st.local(p):pass

def test_staging_copy_hash_cleanup_owned_only(tmp_path):
 (tmp_path/'logs').mkdir();src=tmp_path/'fixture.nc';src.write_bytes(b'fixture only')
 st=BoundedStaging(tmp_path,[src]);before=src.read_bytes()
 with st.local(src) as copy:assert copy.read_bytes()==before and copy!=src
 assert src.read_bytes()==before and not st.created and st.summary()['all_size_hash_verified']
 assert st.summary()['cleanup_failures']==0

def test_prepare_from_archived_snapshot_does_not_double_copy_vendor(tmp_path):
 from scripts.run_b0_smoke import copy_python_sources,write
 source=tmp_path/'archived';target=tmp_path/'new_run'
 (source/'src/vendor').mkdir(parents=True);(source/'tests').mkdir()
 (source/'src/main.py').write_text('value = 1\n')
 (source/'src/vendor/reader.py').write_text('old = True\n')
 (source/'tests/test_example.py').write_text('def test_ok(): pass\n')
 (source/'tests/tmp_old').mkdir()
 (source/'tests/tmp_old/test_fixture.py').write_text('def test_fixture(): pass\n')
 copy_python_sources(source,target)
 assert (target/'src/main.py').is_file() and (target/'tests/test_example.py').is_file()
 assert not (target/'src/vendor/reader.py').exists()
 assert not (target/'tests/tmp_old').exists()
 write(target,'src/vendor/reader.py','audited = True\n')
 assert (target/'src/vendor/reader.py').read_text()=='audited = True\n'
