import copy,json,unittest
from metadata_fix_candidate import validate_history_metrics

class Tests(unittest.TestCase):
    def setUp(self):
        self.payload=dict(train=dict(scenes=10455,loss=.1),validation=dict(scene_blocks=[('synthetic',0),('synthetic2',1)],summary=dict(brier=.2)))
        self.history=json.loads(json.dumps(dict(train=self.payload['train'],development=self.payload['validation'])))
    def test_serialization_container_roundtrip(self):validate_history_metrics(self.history,self.payload)
    def test_changed_metric_rejected(self):
        self.history['development']['summary']['brier']+=.001
        with self.assertRaises(ValueError):validate_history_metrics(self.history,self.payload)
    def test_changed_train_rejected(self):
        self.history['train']['scenes']=10454
        with self.assertRaises(ValueError):validate_history_metrics(self.history,self.payload)
    def test_scene_order_rejected(self):
        self.history['development']['scene_blocks'].reverse()
        with self.assertRaises(ValueError):validate_history_metrics(self.history,self.payload)
    def test_missing_scene_rejected(self):
        self.history['development']['scene_blocks'].pop()
        with self.assertRaises(ValueError):validate_history_metrics(self.history,self.payload)
    def test_duplicate_scene_rejected(self):
        self.history['development']['scene_blocks'].append(['synthetic2',1])
        with self.assertRaises(ValueError):validate_history_metrics(self.history,self.payload)
    def test_nonfinite_rejected(self):
        self.history['train']['loss']=float('nan');self.payload['train']['loss']=float('nan')
        with self.assertRaises(ValueError):validate_history_metrics(self.history,self.payload)
    def test_scalar_types_not_coerced(self):
        self.history['development']['scene_blocks'][0][1]=False
        with self.assertRaises(ValueError):validate_history_metrics(self.history,self.payload)
if __name__=='__main__':unittest.main(verbosity=2)
