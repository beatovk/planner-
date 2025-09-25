#!/usr/bin/env python3
"""
Canonical slots for 3-rail targeting
Defines mappings from user queries to structured search parameters
"""

# Canonical slots for 3-rail targeting
# kind: for weighting (category | experience | cuisine | dish | drink | vibe | scenario)
# include_tags: tags your DB already uses: category:*, experience:*, cuisine:*, dish:*, drink:*, vibe:*, view:*
# include_categories: optional hard category filter (matches Place.category / ontology categories)

CANON_SLOTS = {
    # ——— ART / CULTURE ———
    "gallery":        {"kind":"experience","include_tags":["experience:gallery","experience:art_exhibit"],"include_categories":["gallery","art_space","museum"],"exclude_categories":["bar","restaurant","shop","cafe"]},
    "museum":         {"kind":"category","include_tags":["category:museum"],"include_categories":["museum"]},
    "art_space":      {"kind":"category","include_tags":["category:art_space","experience:art_exhibit"],"include_categories":["art_space","gallery"]},
    "design_hub":     {"kind":"experience","include_tags":["vibe:artsy","experience:gallery"]},
    "planetarium":    {"kind":"experience","include_tags":["experience:planetarium"],"include_categories":["planetarium","museum"]},
    "aquarium":       {"kind":"experience","include_tags":["experience:aquarium"],"include_categories":["aquarium","museum"]},
    "cinema_indie":   {"kind":"experience","include_tags":["experience:cinema_indie"],"include_categories":["cinema"]},
    "craft_market":   {"kind":"experience","include_tags":["experience:art_exhibit","night_market"],"include_categories":["market","night_market"]},

    # ——— VIEWS / SETTINGS ———
    "rooftop":        {"kind":"experience","include_tags":["experience:rooftop","view:skyline"],"include_categories":["bar","restaurant","live_music_venue"]},
    "skyline_view":   {"kind":"experience","include_tags":["view:skyline","experience:rooftop"]},
    "riverside":      {"kind":"experience","include_tags":["view:riverside"],"include_categories":["bar","restaurant","live_music_venue"]},
    "green_view":     {"kind":"experience","include_tags":["view:green","experience:park_stroll"]},

    # ——— COFFEE / TEA / DESSERT ———
    "specialty_coffee":{"kind":"drink","include_tags":["drink:specialty_coffee"],"include_categories":["cafe"]},
    "roastery":       {"kind":"drink","include_tags":["drink:specialty_coffee","feature:roastery"],"include_categories":["cafe"]},
    "listening_bar":  {"kind":"experience","include_tags":["experience:live_music","vibe:chill"]},
    "jazz_bar":       {"kind":"experience","include_tags":["experience:live_music","vibe:romantic"],"include_categories":["live_music_venue","bar"]},
    "vinyl_bar":      {"kind":"experience","include_tags":["experience:live_music","vibe:trendy"]},
    "tea_room":       {"kind":"drink","include_tags":["drink:tea_room","scenario:tea_ceremony"],"include_categories":["cafe"]},
    "tea":            {"kind":"drink","include_tags":["drink:tea_room","scenario:tea_ceremony"],"include_categories":["cafe"]},
    "matcha_bar":     {"kind":"drink","include_tags":["drink:tea_room","scenario:tea_ceremony"],"include_categories":["cafe"]},
    "patisserie":     {"kind":"experience","include_tags":["dish:dessert"],"include_categories":["cafe"]},
    "dessert_lab":    {"kind":"experience","include_tags":["dish:dessert","vibe:instagrammable"],"include_categories":["cafe"]},
    "bakery":         {"kind":"experience","include_tags":["dish:dessert"],"include_categories":["cafe"]},
    "chocolate_atelier":{"kind":"experience","include_tags":["dish:dessert"]},
    "gelato":         {"kind":"dish","include_tags":["dish:dessert"],"include_categories":["cafe"]},

    # ——— WINE / COCKTAILS / BEER ———
    "natural_wine":   {"kind":"drink","include_tags":["drink:natural_wine","drink:wine_bar"],"include_categories":["bar","restaurant"]},
    "wine_bar":       {"kind":"drink","include_tags":["drink:wine_bar"],"include_categories":["bar"]},
    "cocktail_bar":   {"kind":"drink","include_tags":["drink:cocktail_bar"],"include_categories":["bar"]},
    "speakeasy":      {"kind":"experience","include_tags":["feature:private_room","drink:cocktail_bar"],"include_categories":["bar"]},
    "tiki_bar":       {"kind":"drink","include_tags":["drink:cocktail_bar","vibe:lively"],"include_categories":["bar"]},
    "craft_beer":     {"kind":"drink","include_tags":["drink:craft_beer"],"include_categories":["bar","taproom","restaurant"]},
    "taproom":        {"kind":"drink","include_tags":["drink:craft_beer"],"include_categories":["bar"]},
    "sake_bar":       {"kind":"drink","include_tags":["drink:sake"],"include_categories":["bar","restaurant"]},
    "whisky_bar":     {"kind":"drink","include_tags":["drink:whisky"],"include_categories":["bar"]},

    # ——— JAPANESE ———
    "omakase":        {"kind":"experience","include_tags":["omakase","dish:sushi","price:$$$","category:restaurant"],"include_categories":["restaurant"]},
    "kaiseki":        {"kind":"experience","include_tags":["tasting_menu","cuisine:japanese","price:$$$"],"include_categories":["restaurant"]},
    "sushi":          {"kind":"dish","include_tags":["dish:sushi","cuisine:japanese"],"include_categories":["restaurant"]},
    "ramen":          {"kind":"dish","include_tags":["dish:ramen","cuisine:japanese"],"include_categories":["restaurant"]},
    "izakaya":        {"kind":"experience","include_tags":["experience:tasting","cuisine:japanese"],"include_categories":["restaurant","bar"]},
    "yakitori":       {"kind":"dish","include_tags":["cuisine:japanese"],"include_categories":["restaurant"]},
    "tempura":        {"kind":"dish","include_tags":["cuisine:japanese"],"include_categories":["restaurant"]},

    # ——— THAI / SEAFOOD / STEAK ———
    "thai_fine_dining":{"kind":"experience","include_tags":["cuisine:thai","price:$$$","tasting_menu"],"include_categories":["restaurant"]},
    "isaan_bbq":      {"kind":"dish","include_tags":["cuisine:thai"],"include_categories":["restaurant","market"]},
    "northern_thai":  {"kind":"cuisine","include_tags":["cuisine:thai"],"include_categories":["restaurant"]},
    "seafood":        {"kind":"cuisine","include_tags":["cuisine:seafood"],"include_categories":["restaurant","market"]},
    "steakhouse":     {"kind":"category","include_tags":["category:restaurant","dish:steak"],"include_categories":["restaurant"]},

    # ——— WORLD CUISINES ———
    "italian":        {"kind":"cuisine","include_tags":["cuisine:italian"],"include_categories":["restaurant"]},
    "pizza":          {"kind":"dish","include_tags":["dish:pizza","cuisine:italian"],"include_categories":["restaurant"]},
    "pasta":          {"kind":"dish","include_tags":["dish:pasta","cuisine:italian"],"include_categories":["restaurant"]},
    "tapas":          {"kind":"dish","include_tags":["cuisine:mediterranean"],"include_categories":["restaurant","bar"]},
    "korean_bbq":     {"kind":"experience","include_tags":["cuisine:korean"],"include_categories":["restaurant"]},
    "hotpot":         {"kind":"experience","include_tags":["dish:hotpot","cuisine:chinese"],"include_categories":["restaurant"]},
    "dim_sum":        {"kind":"dish","include_tags":["dish:dim_sum","cuisine:chinese"],"include_categories":["restaurant"]},
    "sichuan":        {"kind":"cuisine","include_tags":["cuisine:chinese"],"include_categories":["restaurant"]},
    "indian":         {"kind":"cuisine","include_tags":["cuisine:indian"],"include_categories":["restaurant"]},
    "middle_eastern": {"kind":"cuisine","include_tags":["cuisine:mediterranean"],"include_categories":["restaurant"]},
    "mexican":        {"kind":"cuisine","include_tags":["cuisine:mexican"],"include_categories":["restaurant"]},
    "tacos":          {"kind":"dish","include_tags":["dish:tacos","cuisine:mexican"],"include_categories":["restaurant"]},
    "peruvian":       {"kind":"cuisine","include_tags":["cuisine:mediterranean","cuisine:seafood"],"include_categories":["restaurant"]},
    "mediterranean":  {"kind":"cuisine","include_tags":["cuisine:mediterranean"],"include_categories":["restaurant"]},
    "burger":         {"kind":"dish","include_tags":["dish:burger"],"include_categories":["restaurant"]},
    "brunch":         {"kind":"experience","include_tags":["cuisine:brunch"],"include_categories":["restaurant","cafe"]},
    "tasting_menu":   {"kind":"experience","include_tags":["tasting_menu","price:$$$"],"include_categories":["restaurant"]},
    "chef_table":     {"kind":"experience","include_tags":["feature:counter","tasting_menu"],"include_categories":["restaurant"]},

    # ——— DIETS / FLAGS ———
    "vegan":          {"kind":"diet","include_tags":["diet:vegan"],"include_categories":["restaurant","cafe"]},
    "vegetarian":     {"kind":"diet","include_tags":["diet:vegetarian"],"include_categories":["restaurant","cafe"]},
    "halal":          {"kind":"diet","include_tags":["diet:halal"],"include_categories":["restaurant"]},
    "gluten_free":    {"kind":"diet","include_tags":["diet:gluten_free"]},

    # ——— WELLNESS ———
    "spa":            {"kind":"experience","include_tags":["experience:spa"],"include_categories":["spa"]},
    "thai_massage":   {"kind":"experience","include_tags":["experience:spa","wellness:thai_massage"],"include_categories":["spa"]},
    "onsen":          {"kind":"experience","include_tags":["experience:onsen"],"include_categories":["onsen","spa"]},
    "sauna":          {"kind":"experience","include_tags":["feature:indoor","wellness:sauna"],"include_categories":["spa","onsen"]},
    "hammam":         {"kind":"experience","include_tags":["wellness:hammam"],"include_categories":["spa","onsen"]},
    "sound_healing":  {"kind":"experience","include_tags":["wellness:sound_healing"]},
    "yoga":           {"kind":"experience","include_tags":["wellness:yoga"]},

    # ——— ACTIVE / PLAY ———
    "climbing_gym":   {"kind":"experience","include_tags":["experience:climbing"],"include_categories":["climbing_gym"]},
    "bouldering":     {"kind":"experience","include_tags":["experience:climbing"],"include_categories":["climbing_gym"]},
    "karting":        {"kind":"experience","include_tags":["experience:karting"],"include_categories":["karting","theme_park"]},
    "bowling":        {"kind":"experience","include_tags":["experience:bowling"],"include_categories":["bowling"]},
    "billiards":      {"kind":"experience","include_tags":["experience:billiards"],"include_categories":["billiards"]},
    "ice_skating":    {"kind":"experience","include_tags":["experience:ice_skating"],"include_categories":["ice_skating","theme_park"]},
    "trampoline_park":{"kind":"experience","include_tags":["experience:trampoline_park"],"include_categories":["theme_park"]},
    "vr_arcade":      {"kind":"experience","include_tags":["experience:vr_experience"],"include_categories":["vr_arena","arcade"]},
    "arcade":         {"kind":"experience","include_tags":["experience:arcade"],"include_categories":["arcade"]},
    "escape_room":    {"kind":"experience","include_tags":["experience:escape_room"],"include_categories":["escape_room"]},
    "board_game_cafe":{"kind":"experience","include_tags":["experience:board_games"],"include_categories":["cafe"]},
    "karaoke":        {"kind":"experience","include_tags":["experience:karaoke"],"include_categories":["karaoke"]},
    "live_music":     {"kind":"experience","include_tags":["experience:live_music"],"include_categories":["live_music_venue","bar"]},
    "comedy_club":    {"kind":"experience","include_tags":["experience:live_music","vibe:lively"],"include_categories":["live_music_venue","bar"]},

    # ——— NATURE / WALKS / WATER ———
    "park_stroll":    {"kind":"experience","include_tags":["experience:park_stroll"],"include_categories":["park"]},
    "botanical_garden":{"kind":"experience","include_tags":["view:green","experience:park_stroll"],"include_categories":["park"]},
    "bang_krachao_bike":{"kind":"experience","include_tags":["experience:park_stroll","nature:bike_loop"]},
    "river_cruise":   {"kind":"experience","include_tags":["experience:boat_cruise","view:riverside"]},
    "boat_party":     {"kind":"experience","include_tags":["experience:boat_party","view:riverside"]},

    # ——— MARKETS / STREET ———
    "night_market":   {"kind":"experience","include_tags":["experience:night_market"],"include_categories":["night_market","market"]},
    "floating_market":{"kind":"experience","include_tags":["experience:boat_cruise","night_market"],"include_categories":["market"]},
    "street_food_tour":{"kind":"experience","include_tags":["cuisine:street_food","experience:tasting"]},
    "yaowarat_crawl": {"kind":"experience","include_tags":["night_market","cuisine:chinese","street_food"]},

    # ——— FAMILY / KIDS ———
    "theme_park":     {"kind":"category","include_tags":["category:theme_park"],"include_categories":["theme_park"]},
    "water_park":     {"kind":"category","include_tags":["category:water_park"],"include_categories":["water_park"]},
    "zoo":            {"kind":"category","include_tags":["category:zoo"],"include_categories":["zoo"]},
    "kids_museum":    {"kind":"experience","include_tags":["family_kids_play","category:museum"],"include_categories":["museum"]},
    "indoor_playground":{"kind":"experience","include_tags":["family_kids_play"],"include_categories":["theme_park","arcade"]},
    "mini_golf":      {"kind":"experience","include_tags":["experience:board_games"],"include_categories":["theme_park"]},

    # ——— LEARNING / WORKSHOPS ———
    "cooking_class":  {"kind":"experience","include_tags":["experience:cooking_class","workshop_space"],"include_categories":["workshop_space","restaurant"]},
    "pottery_class":  {"kind":"experience","include_tags":["experience:pottery_class","workshop_space"],"include_categories":["workshop_space","art_space"]},
    "mixology_class": {"kind":"experience","include_tags":["experience:mixology_masterclass"],"include_categories":["bar","workshop_space"]},
    "chocolate_workshop":{"kind":"experience","include_tags":["experience:chocolate_workshop"],"include_categories":["workshop_space","cafe"]},
    "photography_walk":{"kind":"experience","include_tags":["experience:photography_walkshop"]},
    "art_workshop":   {"kind":"experience","include_tags":["experience:workshop"],"include_categories":["workshop_space","art_space"]},
    "perfume_lab":    {"kind":"experience","include_tags":["experience:perfume_lab"],"include_categories":["workshop_space"]},

    # ——— NIGHT / UNIQUE ———
    "secret_supper":  {"kind":"experience","include_tags":["experience:secret_supper_club","tasting_menu"]},
    "mystery_dining": {"kind":"experience","include_tags":["experience:mystery_dining"]},
    "rooftop_cinema": {"kind":"experience","include_tags":["experience:rooftop_cinema","view:skyline"]},
}

# (опционально) простые комплементы для авто-добора недостающих слотов
SLOT_COMPLEMENTS = {
    "sushi": ["natural_wine","cocktail_bar","gallery"],
    "gallery": ["tea_room","specialty_coffee","listening_bar"],
    "tea_room": ["sushi","dessert_lab","gallery"],
    "tea": ["sushi","dessert_lab","gallery"],
    "rooftop": ["natural_wine","jazz_bar","secret_supper"],
    "spa": ["tea_room","patisserie","rooftop"],
    "night_market": ["yaowarat_crawl","specialty_coffee","dessert_lab"],
    "_default": ["rooftop","spa","specialty_coffee"]
}
