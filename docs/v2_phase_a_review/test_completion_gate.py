"""Synthetic lifecycle tests; metadata only."""
import copy
import unittest
from completion_gate import reconcile_selection


def plateau():
    rows=[]
    for ep in range(1,10):
        value=.5 if ep==1 else .49995
        rows.append({'epoch':ep,'validation':{'global_val_core_loss':value},
            'decision':{'checkpoint_selected':ep<=2,'early_stop_improvement':ep==1,'stop':ep==9},
            'selection':{'best_checkpoint_value':value,'selected_checkpoint_epoch':1 if ep==1 else 2,
                         'early_stop_best':.5,'non_improvement_count':ep-1,'completed_epoch':ep}})
    return rows


class CompletionTests(unittest.TestCase):
    def test_best_and_es_are_distinct(self):
        r=reconcile_selection(plateau())
        self.assertEqual(r['best_checkpoint_epoch'],2);self.assertEqual(r['best_es_epoch'],1)
        self.assertEqual(r['final_early_stop_counter'],8);self.assertEqual(r['termination_reason'],'EARLY_STOP_PATIENCE_8')

    def test_incomplete_is_not_complete(self):
        self.assertEqual(reconcile_selection(plateau()[:8])['termination_reason'],'NOT_TERMINATED')

    def test_no_epoch_after_patience(self):
        rows=plateau();extra=copy.deepcopy(rows[-1]);extra['epoch']=10;rows.append(extra)
        with self.assertRaisesRegex(ValueError,'termination'):reconcile_selection(rows)

    def test_changed_best_and_nonfinite_rejected(self):
        rows=plateau();rows[-1]['decision']['checkpoint_selected']=True
        with self.assertRaisesRegex(ValueError,'Decision'):reconcile_selection(rows)
        rows=plateau();rows[0]['validation']['global_val_core_loss']=float('nan')
        with self.assertRaisesRegex(ValueError,'Nonfinite'):reconcile_selection(rows)

if __name__=='__main__':unittest.main(verbosity=2)
