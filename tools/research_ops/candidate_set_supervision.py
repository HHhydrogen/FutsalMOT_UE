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

def real_domain_set_loss(model,windows):
    """每窗一次候选集合CE，再对R窗口等权；unknown在原缓存中排除但仍计入全部候选数。"""
    import torch
    if not windows:raise ValueError('R域必须有窗口')
    counts=[];labels=[];features=[]
    for window in windows:
        x=window['x'];y=window['labels']
        if x.ndim!=2 or y.ndim!=1 or x.shape[0]!=y.numel() or x.shape[1]!=194:
            raise ValueError('窗口特征必须是known_pair×194，标签与known行对齐')
        if x.dtype!=torch.float32 or not bool(torch.isfinite(x).all()):
            raise ValueError('R特征必须有限FP32')
        if not bool(torch.isfinite(y).all()) or not bool(((y==0)|(y==1)).all()):
            raise ValueError('known标签必须是有限0/1，不得静默截断')
        if window['known_pairs']!=y.numel() or window['candidate_pairs']<window['known_pairs']:
            raise ValueError('原始全部候选/known计数不一致')
        if y.numel()==0:raise ValueError('冻结R池每窗至少一个known pair')
        counts.append(y.numel());labels.append(y);features.append(x)
    device=next(model.parameters()).device
    x=torch.cat(features,dim=0).to(device=device,dtype=torch.float32)
    logits=model(x).reshape(-1)
    if logits.dtype!=torch.float32 or not bool(torch.isfinite(logits).all()):raise ValueError('R模型logit须有限FP32')
    losses=[];offset=0
    for count,y in zip(counts,labels):
        chunk=logits[offset:offset+count];offset+=count
        # Cache按原规则移除unknown；仅known候选进入集合，固定无匹配logit为0。
        losses.append(real_window_set_loss(chunk,[int(v) for v in y.tolist()]))
    if offset!=logits.numel():raise ValueError('候选logit切分不完整')
    return torch.stack(losses).mean()
