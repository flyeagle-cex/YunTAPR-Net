"""Process-local guards supplement, but do not replace, the durable quota."""
from contextlib import contextmanager, ExitStack
import contextvars
import io
import os
from pathlib import Path
from unittest.mock import patch
import torch

_step=contextvars.ContextVar('smoke_step',default=None)
_backward=contextvars.ContextVar('smoke_backward',default=None)

@contextmanager
def step_permit(optimizer,model,quota):
    token=_step.set((optimizer,model,quota))
    try: yield
    finally: _step.reset(token)

@contextmanager
def backward_permit():
    token=_backward.set({'tensor_called':False,'autograd_called':False})
    try: yield
    finally: _backward.reset(token)

@contextmanager
def guarded_operations(stores):
    # Resolve lazy tracing rules before installing distinct wrapper callables.
    import torch._dynamo.trace_rules as rules
    rules.get_torch_obj_rule_map()
    original_step=torch.optim.AdamW.step
    original_tensor_backward=torch.Tensor.backward
    original_backward=torch.autograd.backward
    original_load,original_save=torch.load,torch.save
    def controlled_step(optimizer,*args,**kwargs):
        permit=_step.get()
        if permit is None or permit[0] is not optimizer or type(optimizer) is not torch.optim.AdamW or args or kwargs:
            raise PermissionError('NO_UNRESERVED_OR_ALTERNATE_OPTIMIZER_STEP')
        _,model,quota=permit
        quota.entered(model)  # durable, before original call; never refunded
        result=original_step(optimizer)
        quota.returned(model)
        return result
    def tensor_backward(tensor,*args,**kwargs):
        permit=_backward.get()
        if permit is None or permit['tensor_called']: raise PermissionError('NO_SECOND_OR_UNRESERVED_BACKWARD')
        permit['tensor_called']=True
        return original_tensor_backward(tensor,*args,**kwargs)
    def autograd_backward(*args,**kwargs):
        permit=_backward.get()
        if permit is None or not permit['tensor_called'] or permit['autograd_called']:
            raise PermissionError('NO_DIRECT_OR_DUPLICATE_AUTOGRAD_BACKWARD')
        permit['autograd_called']=True
        return original_backward(*args,**kwargs)
    def controlled_load(file,*args,**kwargs):
        if not any(s._io_depth for s in stores) or type(file) is not io.BytesIO or kwargs.get('weights_only') is not True:
            raise PermissionError('NO_HISTORICAL_CHECKPOINT_OR_UNSAFE_LOAD')
        return original_load(file,*args,**kwargs)
    def controlled_save(payload,file,*args,**kwargs):
        raw=getattr(file,'name',None)
        if (not isinstance(raw,(str,os.PathLike)) or
            not any(s._io_depth and Path(raw).absolute().parent==s.root for s in stores)):
            raise PermissionError('ONLY_OWN_SMOKE_CHECKPOINT_SERIALIZATION')
        return original_save(payload,file,*args,**kwargs)
    def deny_factory():
        def deny(*args,**kwargs): raise PermissionError('OPERATION_OUTSIDE_REAL_SMOKE_SCOPE')
        return deny
    with ExitStack() as stack:
        for obj,name,fn in ((torch.optim.AdamW,'step',controlled_step),(torch.Tensor,'backward',tensor_backward),
            (torch.autograd,'backward',autograd_backward),(torch.autograd,'grad',deny_factory()),
            (torch,'load',controlled_load),(torch,'save',controlled_save)):
            stack.enter_context(patch.object(obj,name,fn))
        for cls in vars(torch.optim).values():
            if isinstance(cls,type) and issubclass(cls,torch.optim.Optimizer) and cls not in (torch.optim.Optimizer,torch.optim.AdamW):
                stack.enter_context(patch.object(cls,'step',deny_factory()))
        yield
