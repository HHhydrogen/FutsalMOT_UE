"""独立天气光照目录：保留原八类及抽样算法，增强场内可见差异。"""
from copy import deepcopy

CATALOG_ID = 'futsalmot_indoor_weather_visual_v2'
VERSION = 1

# 太阳/天空强度沿用UE原单位；场馆十灯为EV；曝光为补偿档位。
# 低角度太阳可能被看台遮挡，因此色温、环境光与雾同时承担天气线索。
PRESETS = {
    'daylight_clear_v1': dict(rotation=(-38,-35,0),sun=12.0,sun_color=(1,.96,.86),sky=1.8,sky_color=(.85,.93,1),spot=8.0,exposure=.40,coverage=.10,density=.12,fog=.001,falloff=.20,contrast=1.05,saturation=1.02,white=6500,tint=0,shadows=True),
    'overcast_soft_v1': dict(rotation=(-55,-20,0),sun=.50,sun_color=(.88,.94,1),sky=4.5,sky_color=(.80,.88,1),spot=10.2,exposure=.60,coverage=.95,density=.85,fog=.006,falloff=.16,contrast=.90,saturation=.90,white=6000,tint=0,shadows=False),
    'warm_evening_v1': dict(rotation=(-24,-55,0),sun=6.0,sun_color=(1,.84,.63),sky=.65,sky_color=(.90,.80,.72),spot=10.0,exposure=.65,coverage=.22,density=.25,fog=.005,falloff=.16,contrast=1.03,saturation=1.05,white=7200,tint=.02,shadows=True),
    'cool_evening_v1': dict(rotation=(-8,35,0),sun=.35,sun_color=(.40,.60,1),sky=.65,sky_color=(.35,.55,1),spot=11.2,exposure=.45,coverage=.45,density=.45,fog=.008,falloff=.14,contrast=1.03,saturation=.95,white=4600,tint=0,shadows=True),
    'light_haze_v1': dict(rotation=(-32,-18,0),sun=4.0,sun_color=(1,.95,.82),sky=2.8,sky_color=(.90,.94,1),spot=9.5,exposure=.90,coverage=.40,density=.40,fog=.060,falloff=.055,contrast=.78,saturation=.82,white=6800,tint=0,shadows=True),
    'cloudy_variation_v1': dict(rotation=(-48,40,0),sun=5.5,sun_color=(.90,.96,1),sky=2.5,sky_color=(.70,.84,1),spot=9.0,exposure=.50,coverage=.65,density=.65,fog=.003,falloff=.18,contrast=1.0,saturation=.98,white=5800,tint=0,shadows=True),
    'dawn_cool_v1': dict(rotation=(-12,125,0),sun=3.0,sun_color=(1,.68,.52),sky=1.0,sky_color=(.65,.78,1),spot=10.0,exposure=.80,coverage=.35,density=.30,fog=.030,falloff=.09,contrast=.88,saturation=.90,white=5600,tint=.08,shadows=True),
    'night_floodlit_v1': dict(rotation=(-20,35,0),sun=0.0,sun_color=(.65,.75,1),sky=0.0,sky_color=(.48,.58,.80),spot=12.2,exposure=.35,coverage=.55,density=.40,fog=.002,falloff=.20,contrast=1.10,saturation=1.0,white=6500,tint=0,shadows=True),
}


def build_presets(legacy):
    """只派生新目录；旧字节契约与原目录保持不变。"""
    result=deepcopy(legacy)
    for key,p in PRESETS.items():
        if not -1 <= p['tint'] <= 1:
            raise ValueError('UE WhiteTint使用-1..1范围: '+key)
        v=result[key]
        v['directional_light'].update(rotation_deg=list(p['rotation']),intensity=p['sun'],
            light_color_rgba=list(p['sun_color'])+[1.0],temperature_enabled=False,
            temperature_kelvin=None,cast_shadows=p['shadows'])
        v['sky_light'].update(intensity=p['sky'],light_color_rgba=list(p['sky_color'])+[1.0])
        v['venue_spot_lighting']['intensity']=p['spot']
        v['volumetric_cloud'].update(cloud_coverage=p['coverage'],cloud_density=p['density'])
        v['exponential_height_fog'].update(fog_density=p['fog'],height_falloff=p['falloff'],fog_height_falloff=p['falloff'])
        v['post_process'].update(exposure_compensation=p['exposure'],white_balance_temperature=p['white'],
            white_balance_tint=p['tint'],color_contrast=[p['contrast']]*3+[1.0],color_saturation=[p['saturation']]*3+[1.0])
    return result
