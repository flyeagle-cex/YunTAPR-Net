"""CPU-only boundary checks: no weather files, weights, GPU or optimizer steps."""
import inspect,unittest
import torch
from yuntapr.experimental.research_readiness.dote_without_mee import DoteResidual,DoteWithoutMee


class DoteOnlyTests(unittest.TestCase):
    def setUp(self):torch.set_num_threads(2)
    def region(self):
        r=torch.zeros(1,1,100,100,dtype=torch.bool);r.flatten()[:3430]=True;return r
    def test_zero_output_preserves_the_satellite_feature(self):
        m=DoteResidual();x=torch.randn(2,8,100,100);v=torch.ones_like(x,dtype=torch.bool)
        a,used=m(x,v,self.region(),output_dtype=torch.bfloat16)
        self.assertTrue(torch.equal(a,torch.zeros_like(a)))
        f=torch.randn(2,48,100,100).to(torch.bfloat16)
        self.assertTrue(torch.equal(f+a,f));self.assertEqual(int(used.sum()),6860)
        a.float().square().sum().backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters()))
    def test_invalid_dynamic_input_cannot_make_a_residual(self):
        m=DoteResidual()
        with torch.no_grad():m.output.weight.fill_(.01);m.output.bias.fill_(1.)
        x=torch.full((1,8,100,100),float('nan'));v=torch.zeros_like(x,dtype=torch.bool)
        a,used=m(x,v,self.region(),output_dtype=torch.float32)
        self.assertTrue(torch.equal(a,torch.zeros_like(a)));self.assertFalse(used.any())
    def test_dynamic_values_have_an_active_path_after_zero_output_warmup(self):
        m=DoteResidual()
        with torch.no_grad():m.input.weight.fill_(.01);m.input.bias.zero_();m.output.weight.fill_(.01)
        v=torch.ones(1,8,100,100,dtype=torch.bool)
        a,_=m(torch.zeros_like(v,dtype=torch.float32),v,self.region(),output_dtype=torch.float32)
        b,_=m(torch.ones_like(v,dtype=torch.float32),v,self.region(),output_dtype=torch.float32)
        self.assertFalse(torch.equal(a,b));self.assertFalse(b[:,:,40:,:].any())
    def test_direct_environment_and_static_branches_are_absent(self):
        arguments=inspect.signature(DoteWithoutMee.forward).parameters
        self.assertNotIn('environment',arguments);self.assertNotIn('environment_valid',arguments)
        self.assertNotIn('static',arguments);self.assertIn('dynamic',arguments)
    def test_frozen_channel_shape_is_enforced(self):
        with self.assertRaises(ValueError):DoteResidual(8)
        with self.assertRaises(ValueError):DoteResidual()(torch.zeros(1,7,100,100),torch.ones(1,7,100,100,dtype=torch.bool),self.region(),output_dtype=torch.float32)


if __name__=='__main__':unittest.main()
