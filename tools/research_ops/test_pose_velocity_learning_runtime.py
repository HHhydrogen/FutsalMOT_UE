"""新训练协议与逐步真实预算的独立边界检查。"""
import hashlib
import unittest
import pose_velocity_learning_runtime as rt

class Contract(unittest.TestCase):
    def config(self):return dict(schema='bounded_velocity_recorded_training_protocol_v1',approved_by='root',training_authorized=True,
        tracking_authorized=False,training_matrix=rt.expected_matrix(),parameters=rt.PARAMETERS,test116187_sealed=True)
    def test_matrix_rejects_missing_duplicate_or_budget_change(self):
        rt.validate_matrix(self.config())
        for key,value in [('training_matrix',rt.expected_matrix()[:-1]),('training_matrix',rt.expected_matrix()[:-1]+[rt.expected_matrix()[0]]),
            ('parameters',dict(rt.PARAMETERS,updates=999)),('test116187_sealed',False)]:
            cfg=self.config();cfg[key]=value
            with self.assertRaises(ValueError):rt.validate_matrix(cfg)
    def ledger(self,group):
        real=[dict(window_uid='R'+str(i),epoch=i//1000,candidate_pairs=3,labelled_pairs=2) for i in range(3000)]
        synthetic=[dict(window_uid='S'+str(i),epoch=0,candidate_pairs=4,labelled_pairs=1) for i in range(1000)]
        table=dict(real=real,synthetic=synthetic);logs=[];chain='0'*64
        for i in range(1000):
            row=dict(actual_update=i+1,update_index=i,real=real[3*i:3*i+3],synthetic=synthetic[i:i+1] if group!='T_R' else [],
                R_windows=3,S_windows=int(group!='T_R'),R_pairs=9,R_known_pairs=6,S_pairs=4*int(group!='T_R'),
                S_known_pairs=int(group!='T_R'),learning_rates=[.001],grad_l2=1.,step_wall_seconds=.01)
            chain=hashlib.sha256((chain+rt.canonical(row)).encode()).hexdigest();logs.append(dict(row,chain_sha256=chain))
        return table,logs
    def test_real_and_RS_actual_sequence_and_pair_ledger(self):
        for group in rt.GROUPS:
            table,logs=self.ledger(group);rt.audit_steps(logs,table,group)
            # 即便伪造完整SHA链，错误的原始曝光顺序也不能通过。
            table['real'][0],table['real'][1]=table['real'][1],table['real'][0]
            with self.assertRaises(ValueError):rt.audit_steps(logs,table,group)
    def test_known_pair_not_window_count(self):
        table,logs=self.ledger('T_RS');logs[0]['R_known_pairs']=9
        chain='0'*64
        for log in logs:
            row=dict(log);row.pop('chain_sha256');chain=hashlib.sha256((chain+rt.canonical(row)).encode()).hexdigest();log['chain_sha256']=chain
        with self.assertRaises(ValueError):rt.audit_steps(logs,table,'T_RS')

if __name__=='__main__':unittest.main()
