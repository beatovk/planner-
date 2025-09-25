#!/usr/bin/env python3
"""GPT API клиент для нормализации данных мест"""

import json
import logging
from typing import Dict, Any, Optional, List
import openai

logger = logging.getLogger(__name__)


class GPTClient:
    """Клиент для работы с GPT API"""
    
    def __init__(self, api_key: str, timeout: int = 30):
        self.client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self.model = "gpt-4o-mini"
        self.timeout = timeout
    
    def normalize_place_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализация данных места через GPT"""
        try:
            prompt = self._create_prompt(payload)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.6,
                max_tokens=2000,
                presence_penalty=0.6,
                frequency_penalty=0.4
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.info(f"GPT обработал место {payload.get('id')} с confidence {result.get('confidence', 0)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка GPT API: {e}")
            raise e  # Пробрасываем исключение в воркер для обработки умным fallback

    def generate_description_and_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Получить полное описание (6–10 предложений) и саммари (3 предложения) строго из веба.

        Шаги:
        1) Выйти в интернет и собрать текст (1–3 релевантные страницы).
        2) Сжать найденное в 6–10 предложений (description_full) и 3 предложения (summary).
        3) Если веб-контент не найден — НЕ выдумывать, вернуть description_full=None.
        """
        try:
            name = payload.get("name")
            area = payload.get("area") or "Bangkok"
            web_text = self._web_fetch_text(name=name, area=area)
            if not web_text or len(web_text) < 400:
                return {
                    "description_full": None,
                    "summary": None,
                    "confidence": 0.0,
                    "validation_notes": "no_web_content",
                }

            user_prompt = (
                "You are a content condenser.\n"
                "INPUT is aggregated web text about a venue in Bangkok.\n"
                "Return ONLY JSON with keys: description_full (6-10 sentences), summary (3 sentences, ≤250 chars), confidence (0..1), validation_notes.\n"
                "Do NOT invent — only rephrase facts present in INPUT.\n\n"
                f"VENUE: {name} ({area})\nWEB_TEXT:\n{web_text[:6000]}\n"
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return strict JSON. No markdown."},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1200,
            )

            result = json.loads(response.choices[0].message.content)
            if not isinstance(result.get("description_full"), str):
                result["description_full"] = None
            if not isinstance(result.get("summary"), str):
                result["summary"] = None
            return result
        except Exception as e:
            logger.error(f"Ошибка GPT API (desc+summary): {e}")
            return {"description_full": None, "summary": None, "confidence": 0.0, "validation_notes": "error"}

    def _web_fetch_text(self, name: str, area: str) -> str:
        """Простой веб-поиск и извлечение текста. Не требует сторонних ключей.

        Стратегия:
        - Формируем запрос для DuckDuckGo HTML (lite) и Google maps search URL.
        - Берём 1-3 первых результатов, скачиваем страницы, вычищаем HTML, собираем основной текст.
        - Возвращаем конкатенированный текст (до лимита).
        """
        import httpx, re
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        }
        q = f"{name} {area} opening hours menu address review"
        texts: List[str] = []
        try:
            # 1) DuckDuckGo HTML results
            ddg_url = f"https://duckduckgo.com/html/?q={httpx.QueryParams({ 'q': q }).get('q')}"
            with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as cx:
                r = cx.get(ddg_url)
                # Неглубокий парс ссылок
                links = re.findall(r"href=\"(https?://[^\"]+)\"", r.text)[:5]
                for u in links:
                    if any(host in u for host in ["facebook.com", "x.com", "twitter.com", "instagram.com", "tiktok.com"]):
                        continue
                    try:
                        pg = cx.get(u)
                        text = self._strip_html(pg.text)
                        if len(text) > 300:
                            texts.append(text[:8000])
                            if len(texts) >= 3:
                                break
                    except Exception:
                        continue
        except Exception:
            pass

        # 2) Добавим Google Maps search URL как вспомогательное описание
        maps_url = f"https://www.google.com/maps/search/?api=1&query={name.replace(' ', '+')}+{area.replace(' ', '+')}"
        texts.append(f"MapsSearchURL: {maps_url}")

        return "\n\n".join(texts)[:16000]

    @staticmethod
    def _strip_html(html: str) -> str:
        import re
        # Удалить скрипты/стили
        html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
        html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
        # Теги → пробел
        text = re.sub(r"<[^>]+>", " ", html)
        # Конденс пробелы
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    
    def _get_system_prompt(self) -> str:
        """Системный промт для GPT"""
        return """You are a data-and-editorial normalizer for an Entertainment Planner (Bangkok).
Return ONLY valid JSON. No markdown, no prose outside JSON. Be conservative: set a flag only if clearly grounded in INPUT.

GOALS
1) Write a concise 3-sentence summary that sells the vibe and specifics.
2) Produce a wide, grounded tag set using the ontology below (lowercase snake_case, "prefix:value").
3) Detect and score editorial SIGNALS that power "Surprise me" and a "High-quality" filter.
4) Normalize hours and Google Maps URL when possible. Include confidence and brief validation_notes.

STYLE FOR SUMMARY
- Exactly 3 sentences, ≤ 250 chars total.
- Do NOT begin any sentence with "This/It/There is/Here/We/They".
- Vary openings; avoid generic clichés.
- Tone: warm travel/critic blogger, B2 English, no emojis, no exclamation marks.

TAGGING ONTOLOGY (prefix:value; include MANY but ONLY if supported by the input)
- category:*   → cafe | restaurant | bar | club | spa | onsen | park | gallery | museum | cinema | market | mall | karaoke | live_music_venue | aquarium | planetarium | night_market | art_space | workshop_space | arcade | escape_room | climbing_gym | bowling | billiards | karting | vr_arena | water_park | theme_park
- cuisine:*    → thai | japanese | italian | korean | chinese | mexican | indian | french | mediterranean | fusion | seafood | steakhouse | brunch | street_food
- dish:*       → tom_yum | ramen | sushi | pizza | burger | pasta | steak | dim_sum | tacos | dessert
- drink:*      → cocktail_bar | wine_bar | natural_wine | sake | craft_beer | specialty_coffee | tea_room
- vibe:*       → romantic | chill | lively | cozy | premium | artsy | trendy | local | hidden_gem | scenic | instagrammable
- scenario:*   → date | first_date | friends | family | solo | afterwork | birthday | remote_work | rainy_day
- experience:* → rooftop | live_music | tasting | spa | onsen | park_stroll | aquarium | planetarium | cinema_indie | night_market | art_exhibit | workshop | cooking_class | pottery_class | tea_ceremony | muay_thai_gym | boat_cruise | river_cruise | karaoke | board_games | arcade | escape_room | climbing | bowling | billiards | karting | vr_experience | water_park | theme_park
- feature:*    → outdoor | indoor | private_room | counter | reservation_required | queue_often | pet_friendly | kid_friendly | accessibility_ok | late_night | cash_only | dress_code
- view:*       → skyline | riverside | green
- noise:*      → quiet | moderate | loud
- lighting:*   → dim | bright
- seating:*    → terrace | garden | patio | bar_counter | private_dining
- diet:*       → vegan | vegetarian | halal | kosher | gluten_free
- price:*      → $ | $$ | $$$ | $$$$
- area:*       → <district_or_mall_if_clear> (e.g., area:sukhumvit, area:thonglor, area:emporium)

SIGNALS — EDITORIAL CORE (JSON, conservative & grounded)
Purpose: power two axes — "extraordinary" (for Surprise me) and "high-quality" (for connoisseurs).

A) Extraordinary detection (boolean + cluster)
- Set extraordinary=true when INPUT clearly implies a non-everyday activity/format, typically from these CLUSTERS:
  vr_arena, arcade_hybrid, trampoline_park, karting, climbing_gym, archery_range, ice_skating,
  laser_tag, escape_room, bowling_night, billiards, indoor_surf, wakeboarding_cable, skatepark_session,
  planetarium, aquarium, observation_deck, rooftop_viewpoint, boat_cruise, khlong_kayak, sup_lesson,
  night_market_special, street_food_safari, gallery_hop, indie_cinema, workshops, urban_green
- If you set extraordinary, also set extraordinary_cluster to one of the IDs above.
- If the input is unusual but no exact cluster fits, you may still set extraordinary=true and leave extraordinary_cluster=null.
- Do NOT set extraordinary for everyday cafes/restaurants unless they host a clearly non-ordinary program (e.g., "rooftop cinema", "secret supper club", "chef's table AS a show").

B) High-quality (boolean) & quality triggers
- Set hq_experience=true when ANY is true:
  1) quality_score ≥ 0.65; OR 2) editor_pick=true; OR
  3) local_gem=true AND (dateworthy=true OR vista_view=true); OR
  4) clear "quality triggers" in INPUT such as:
     MICHELIN (star/bib), omakase/chef's table/tasting menu, open_kitchen_show,
     craft_cocktail_lab, natural_wine_program, specialty/manual brew (pour-over flights, single-origin),
     flagship roaster, curated gallery program/curator talk, architecture icon/design award.

C) Scores (0.0–1.0, with soft heuristics; be conservative)
- novelty_score: higher for rare formats/clusters (workshops, planetarium, aquarium, karting, VR, boat_cruise, observation_deck, escape_room…), or if INPUT shows unusual features; else low. If not clear → 0.0.
- quality_score: higher for awards/pedigree/program depth (MICHELIN, chef's table, serious specialty coffee program, curated gallery, design-icon); else low. If not clear → 0.0.
- trend_score: signals of current buzz/crowds/hype/limited drops/popular events; else 0.0.
- interest_score: weighted blend for ranking: clamp( 0.5*novelty_score + 0.3*quality_score + 0.2*trend_score , 0..1).

D) Simple editorial flags (booleans; set only if INPUT supports):
- editor_pick, local_gem, dateworthy, vista_view.

E) Evidence & hooks (for UX explanations)
- evidence: list of 1–5 SHORT verbatim fragments (≤120 chars each) that justify your decisions (e.g., "planetarium dome shows", "manual brew flights").
- hooks: list of 1–4 compact marketing hooks (2–6 words), no emojis, e.g., "VR arena + arcade", "Manual brew flights".

HOURS & GMAPS
- hours_json: keep if present and consistent; else try to extract; else null. Format:
  {"Mon":["10:00-18:00"], "Tue":[], "Wed":[], "Thu":[], "Fri":[], "Sat":[], "Sun":[]}
- gmaps_url: If gmaps_place_id exists → "https://www.google.com/maps/place/?q=place_id:PLACE_ID".
  Else: "https://www.google.com/maps/search/?api=1&query=<URLEncode(name + (address or area))>".

VALIDATION
- confidence: 0.0–1.0 (data completeness & clarity).
- validation_notes: short note or null.
- Be conservative. If uncertain, prefer false/null/0.0.

INPUT (example shape):
{
  "id": "place_id",
  "name": "Place Name",
  "description_full": "Full description…",
  "category": "category_if_any",
  "tags_csv": "existing,tags",
  "summary": "existing summary or null",
  "hours_json": "existing hours or null",
  "address": "optional",
  "gmaps_place_id": "optional",
  "gmaps_url": "optional"
}

OUTPUT (strict JSON only):
{
  "summary": "<3-sentence text>",
  "tags": ["category:*", "vibe:*", "experience:*", "drink:*", "feature:*", "area:*", "price:*", "cuisine:*", "dish:*", "scenario:*", "view:*", "noise:*", "lighting:*", "seating:*", "diet:*"],
  "signals": {
    "extraordinary": false,
    "extraordinary_cluster": null,   // or one of the IDs listed above
    "hq_experience": false,
    "novelty_score": 0.0,
    "quality_score": 0.0,
    "trend_score": 0.0,
    "interest_score": 0.0,
    "editor_pick": false,
    "local_gem": false,
    "dateworthy": false,
    "vista_view": false,
    "evidence": [],
    "hooks": []
  },
  "hours_json": {"Mon":[], "Tue":[], "Wed":[], "Thu":[], "Fri":[], "Sat":[], "Sun":[]} | null,
  "gmaps_url": "string",
  "confidence": 0.0,
  "validation_notes": "string or null"
}"""

    def _create_prompt(self, payload: Dict[str, Any]) -> str:
        """Создание промта для GPT"""
        return f"""INPUT:
{json.dumps(payload, indent=2, ensure_ascii=False)}

OUTPUT FORMAT (strict JSON):
{{
  "summary": "<3-sentence text>",
  "tags": ["category:*", "vibe:*", "experience:*", "drink:*", "feature:*", "area:*", "price:*", "cuisine:*", "dish:*", "scenario:*", "view:*", "noise:*", "lighting:*", "seating:*", "diet:*"],
  "interest_signals": {{ "<ALL master keys above as flat booleans; default false unless clearly supported>" }},
  "hours_json": {{"Mon":[], "Tue":[], "Wed":[], "Thu":[], "Fri":[], "Sat":[], "Sun":[]}} | null,
  "gmaps_url": "string",
  "confidence": 0.0,
  "validation_notes": "string or null"
}}"""

    def _get_fallback_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback ответ при ошибке GPT"""
        place_name = payload.get('name', 'Unknown')
        description = payload.get('description_full', '')
        
        # Универсальное определение типа места
        venue_type = self._detect_venue_type(place_name, description)
        
        # Создаем базовое саммари из описания
        if description and len(description) > 50:
            summary = description[:200] + "..." if len(description) > 200 else description
        else:
            summary = f"A {venue_type} in Bangkok offering a unique experience."
        
        # Универсальные теги на основе типа места
        tags = self._generate_fallback_tags(place_name, description, venue_type)
        
        return {
            "summary": summary,
            "tags": tags,
            "interest_signals": {},
            "hours_json": None,
            "gmaps_url": self._generate_fallback_gmaps_url(payload),
            "confidence": 0.3,
            "validation_notes": "GPT API error, using fallback"
        }
    
    def _detect_venue_type(self, name: str, description: str) -> str:
        """Определение типа места на основе названия и описания"""
        text = f"{name} {description}".lower()
        
        # Рестораны и кафе (приоритет по ключевым словам)
        if any(word in text for word in ['cuisine', 'menu', 'dining', 'kitchen', 'restaurant', 'cafe', 'coffee', 'bistro', 'food', 'meal', 'dish', 'chef']):
            return 'restaurant'
        elif any(word in text for word in ['bar', 'pub', 'club', 'lounge', 'cocktail', 'drink', 'wine', 'beer']):
            return 'bar'
        elif any(word in text for word in ['spa', 'massage', 'wellness', 'sauna', 'yoga', 'relaxation', 'treatment']):
            return 'spa'
        elif any(word in text for word in ['cinema', 'theater', 'theatre', 'movie', 'karaoke', 'entertainment', 'show', 'performance']):
            return 'entertainment'
        elif any(word in text for word in ['shop', 'store', 'boutique', 'market', 'mall', 'shopping', 'retail']):
            return 'shopping'
        elif any(word in text for word in ['gallery', 'museum', 'art', 'exhibition', 'culture', 'cultural']):
            return 'culture'
        else:
            return 'entertainment'
    
    def _generate_fallback_tags(self, name: str, description: str, venue_type: str) -> List[str]:
        """Генерация тегов для fallback в новом формате с префиксами"""
        tags = []
        text = f"{name} {description}".lower()
        
        # Добавляем category тег
        if venue_type == 'restaurant':
            tags.append('category:restaurant')
        elif venue_type == 'bar':
            tags.append('category:bar')
        elif venue_type == 'spa':
            tags.append('category:spa')
        elif venue_type == 'entertainment':
            tags.append('category:cinema')
        else:
            tags.append('category:cafe')
        
        # Добавляем теги на основе типа места
        if venue_type == 'restaurant':
            # Определяем кухню
            if any(word in text for word in ['thai', 'pad thai', 'curry', 'tom yum']):
                tags.append('cuisine:thai')
            elif any(word in text for word in ['italian', 'pasta', 'pizza', 'tuscan']):
                tags.append('cuisine:italian')
            elif any(word in text for word in ['japanese', 'sushi', 'ramen', 'tempura']):
                tags.append('cuisine:japanese')
            elif any(word in text for word in ['chinese', 'dim sum', 'wok']):
                tags.append('cuisine:chinese')
            elif any(word in text for word in ['indian', 'curry', 'tandoor']):
                tags.append('cuisine:indian')
            elif any(word in text for word in ['french', 'bistro', 'brasserie']):
                tags.append('cuisine:french')
            else:
                tags.append('cuisine:fusion')
            
            # Определяем стиль
            if any(word in text for word in ['fine dining', 'upscale', 'luxury']):
                tags.append('vibe:premium')
            elif any(word in text for word in ['casual', 'relaxed', 'comfortable']):
                tags.append('vibe:chill')
            elif any(word in text for word in ['street food', 'hawker', 'local']):
                tags.append('vibe:local')
            else:
                tags.append('vibe:chill')
                
        elif venue_type == 'bar':
            if any(word in text for word in ['rooftop', 'sky', 'view']):
                tags.append('category:rooftop_bar')
                tags.append('experience:rooftop')
            elif any(word in text for word in ['speakeasy', 'hidden', 'secret']):
                tags.append('drink:speakeasy')
            elif any(word in text for word in ['dance', 'music', 'party']):
                tags.append('vibe:lively')
            else:
                tags.append('drink:craft_cocktails')
                
        elif venue_type == 'spa':
            if any(word in text for word in ['luxury', 'premium', 'high-end']):
                tags.append('vibe:premium')
            elif any(word in text for word in ['traditional', 'thai', 'ancient']):
                tags.append('vibe:local')
            else:
                tags.append('vibe:chill')
                
        elif venue_type == 'entertainment':
            if any(word in text for word in ['family', 'kids', 'children']):
                tags.append('scenario:family')
            else:
                tags.append('scenario:friends')
                
        elif venue_type == 'shopping':
            if any(word in text for word in ['luxury', 'designer', 'high-end']):
                tags.append('vibe:premium')
            elif any(word in text for word in ['local', 'handmade', 'craft']):
                tags.append('vibe:local')
            else:
                tags.append('vibe:trendy')
        
        # Добавляем общие теги
        if any(word in text for word in ['romantic', 'intimate', 'cozy']):
            tags.append('vibe:romantic')
            tags.append('scenario:date')
        if any(word in text for word in ['outdoor', 'terrace', 'garden']):
            tags.append('feature:outdoor')
        if any(word in text for word in ['view', 'panoramic', 'skyline']):
            tags.append('view:skyline')
        if any(word in text for word in ['expensive', 'luxury', 'premium']):
            tags.append('price:$$$')
        elif any(word in text for word in ['cheap', 'affordable', 'budget']):
            tags.append('price:$')
        else:
            tags.append('price:$$')
        
        # Добавляем базовые теги
        tags.append('energy:medium')
        tags.append('slot:evening')
        
        return tags[:15]  # Ограничиваем количество тегов
    
    def _generate_fallback_gmaps_url(self, payload: Dict[str, Any]) -> str:
        """Генерация fallback Google Maps URL"""
        name = payload.get('name', '')
        
        if name:
            # Используем только название места для поиска
            query = name.replace(' ', '+')
            return f"https://www.google.com/maps/search/?api=1&query={query}"
        else:
            return ""
