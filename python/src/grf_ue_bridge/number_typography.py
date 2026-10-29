"""号码字体候选目录；旧图集保持独立，不修改历史外观或号码分配。"""
from copy import deepcopy

ATLAS_ID = 'bahnschrift_bold_condensed_v2'
ATLAS_PROFILE = {
    'id':ATLAS_ID,
    'texture':'/Game/FutsalMOT/Characters/MPFB/Materials/JerseyNumbersUV_v2/T_NumberAtlas_BahnschriftBoldCondensed_v2',
    'font_family':'Bahnschrift Bold Condensed',
    'font_sha256':'eaad201da94cb323401fdb8cc760650803ddf8fd704cb9fa56317e6c69bc6fd6',
    'font_axes':[700,75],
    'grid':[16,8],'cell_px':256,'padding_px':24,
}

INK_PROFILE = 'kit_contrast_v2'
# 白和黄为亮色球衣；其余三套使用白字，规则固定且不参与随机抽样。
KIT_INK = {'01':[1.0,1.0,1.0],'02':[0.0,0.0,0.0],'03':[1.0,1.0,1.0],
           '04':[1.0,1.0,1.0],'05':[0.0,0.0,0.0],
           '06':[1.0,1.0,1.0],'07':[1.0,1.0,1.0],'08':[1.0,1.0,1.0],
           '09':[1.0,1.0,1.0],'10':[0.0,0.0,0.0],'11':[0.0,0.0,0.0],
           '12':[1.0,1.0,1.0],'13':[0.0,0.0,0.0],'14':[0.0,0.0,0.0],
           '15':[1.0,1.0,1.0]}


def ink_for_kit(kit_id):
    if kit_id not in KIT_INK:raise ValueError('未知球衣套装: '+str(kit_id))
    return list(KIT_INK[kit_id])


def atlas_profile(atlas_id):
    if atlas_id != ATLAS_ID:
        raise ValueError('未知UV号码字体图集: '+str(atlas_id))
    return deepcopy(ATLAS_PROFILE)
