"""候选集合R监督的数值候选；无匹配logit固定0，不改变追踪推理。"""
def real_window_set_loss(logits,labels):
    """labels为0/1/None；unknown不参加分母；空known窗保持零贡献。"""
    import torch
    if logits.ndim!=1 or len(labels)!=logits.numel():raise ValueError('只准一维候选logit与逐项标签')
    if logits.dtype!=torch.float32 or not bool(torch.isfinite(logits).all()):raise ValueError('必须有限FP32')
    if not all(v is None or type(v) is int and v in (0,1) for v in labels):raise ValueError('unknown须None，known只能0或1')
    known=[i for i,v in enumerate(labels) if v is not None];positive=[i for i,v in enumerate(labels) if v==1]
    if len(positive)>1:raise ValueError('冻结互唯一几何标签只准至多一个known正例')
    if not known:return (logits*0).sum()
    index=torch.tensor(known,dtype=torch.long,device=logits.device)
    denominator=torch.logsumexp(torch.cat((logits.new_zeros(1),logits.index_select(0,index))),dim=0)
    return denominator-(logits[positive[0]] if positive else logits.new_zeros(()))
