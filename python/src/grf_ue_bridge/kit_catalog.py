"""球衣候选集合版本；扩大新目录，不改历史五套目录的随机结果。"""
EXPANDED_CATALOG_ID = 'mpfb_players_003_009_kits15_v1'
LEGACY_KIT_IDS = tuple('%02d'%i for i in range(1,6))
EXPANDED_KIT_IDS = tuple('%02d'%i for i in range(1,16))


def kit_ids_for_catalog(catalog_id):
    return EXPANDED_KIT_IDS if catalog_id==EXPANDED_CATALOG_ID else LEGACY_KIT_IDS
