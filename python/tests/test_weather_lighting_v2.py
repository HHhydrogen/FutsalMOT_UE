"""新天气目录兼容原协议，且各类天气保留明确视觉控制。"""
from grf_ue_bridge.environment import (ENVIRONMENT_CATALOG_ID, VISUAL_WEATHER_CATALOG_ID,
    ENVIRONMENT_PRESET_IDS, build_environment_parameters, environment_catalog_fingerprint,
    resolve_environment_preset)


def test_weather_visual_catalog_is_separate_and_keeps_seed_selection():
    assert environment_catalog_fingerprint() == '48a095a31efd17443a82e255cc2175330d7df3321c09b1880821c2f8516285c2'
    assert environment_catalog_fingerprint(VISUAL_WEATHER_CATALOG_ID) != environment_catalog_fingerprint()
    assert resolve_environment_preset(1048,'auto') == 'overcast_soft_v1'
    old=build_environment_parameters(1048,ENVIRONMENT_CATALOG_ID,'overcast_soft_v1')
    assert old['venue_spot_lighting']['intensity']==8.0
    values={k:build_environment_parameters(1048,VISUAL_WEATHER_CATALOG_ID,k) for k in ENVIRONMENT_PRESET_IDS}
    assert values['overcast_soft_v1']['directional_light']['cast_shadows'] is False
    assert values['night_floodlit_v1']['directional_light']['intensity']==0
    assert values['night_floodlit_v1']['sky_light']['intensity']==0
    assert values['light_haze_v1']['exponential_height_fog']['fog_density'] > 10*values['daylight_clear_v1']['exponential_height_fog']['fog_density']
    assert values['warm_evening_v1']['post_process']['white_balance_temperature'] > values['cool_evening_v1']['post_process']['white_balance_temperature']
