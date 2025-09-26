#!/usr/bin/env python3
"""Rails API endpoint for Netflix-style search system"""

import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session
import hashlib, json
from collections import OrderedDict
from types import SimpleNamespace

from apps.core.db import get_db
from apps.places.schemas.vibes import ComposeResponse, Rail, PlaceCard
from apps.places.schemas.slots import Slot, SlotType
from apps.places.services.heuristic_parser import load_ontology
from sqlalchemy import text
import re
import yaml

from apps.places.services.bitset_service import create_bitset_service
from apps.places.services.ranking_service import create_ranking_service
from apps.places.services.search import SearchService, create_search_service
from apps.places.services.query_builder import create_query_builder
from apps.places.services.session_profiles import SessionProfileService
from apps.core.feature_flags import (
    is_slotter_enabled, is_slotter_shadow_mode, should_use_slotter,
    should_log_slotter, should_ab_test_slotter, get_slotter_config
)

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Module-level simple cache for /api/rails ---
# Shared between vibe and slotter branches in get_rails
if not hasattr(__import__(__name__), "_rails_cache_store"):
    _rails_cache_store = {
        "data": {},   # key -> {"val": obj, "ts": time.time()}
        "ttl": 120,   # seconds
        "max": 300,
    }

def _rcache_get(key: str):
    cache = _rails_cache_store["data"]
    entry = cache.get(key)
    if not entry:
        return None
    if (time.time() - entry["ts"]) > _rails_cache_store["ttl"]:
        cache.pop(key, None)
        return None
    return entry["val"]

def _rcache_set(key: str, val):
    cache = _rails_cache_store["data"]
    cache[key] = {"val": val, "ts": time.time()}
    # simple LRU-ish trim by insertion order
    if len(cache) > _rails_cache_store["max"]:
        # drop oldest approximately
        for k in list(cache.keys())[: len(cache) - _rails_cache_store["max"]]:
            cache.pop(k, None)

def _slotter_rails_cache_key(q: str, area: Optional[str],
                             user_lat: Optional[float], user_lng: Optional[float],
                             quality_only: bool) -> str:
    try:
        payload = {
            "mode": "slotter",
            "q": (q or "").strip().lower(),
            "area": (area or "").strip().lower(),
            "user_lat": round(user_lat or 0.0, 4) if user_lat is not None else None,
            "user_lng": round(user_lng or 0.0, 4) if user_lng is not None else None,
            "quality_only": quality_only,
        }
        s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return "slotter:" + hashlib.md5(s.encode("utf-8")).hexdigest()
    except Exception:
        return f"slotter:{q}:{area}:{user_lat}:{user_lng}:{quality_only}"


def _normalize_text(s: Optional[str]) -> str:
    return (s or "").lower()

def _token_hit(texts: List[str], needles: List[str]) -> bool:
    blob = " ".join([_normalize_text(t) for t in texts if t]) + " "
    return any(needle in blob for needle in needles)

def _detect_extraordinary_cluster(row) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Heuristics: match by tags_csv + summary/name + signals.hooks/evidence.
    Returns: (is_extraordinary, cluster_key, human_label)
    """
    # Load extraordinary clusters from config
    _EXTRA_CONF_PATH = "config/extraordinary.yml"
    _EXTRA_CONF = {}
    try:
        with open(_EXTRA_CONF_PATH, "r", encoding="utf-8") as f:
            _EXTRA_CONF = yaml.safe_load(f) or {}
    except Exception:
        _EXTRA_CONF = {
            "clusters": {
                "vr_arena": {"label": "VR arena", "keywords": ["vr", "vr arena", "virtual reality"]},
                "trampoline_park": {"label": "Trampoline park", "keywords": ["trampoline", "free-jump", "bounce"]},
                "aquarium": {"label": "Aquarium", "keywords": ["aquarium", "sea life"]},
                "planetarium": {"label": "Planetarium", "keywords": ["planetarium", "star show"]},
                "observation_deck": {"label": "Observation deck", "keywords": ["observation deck", "viewpoint"]},
                "rooftop_viewpoint": {"label": "Rooftop viewpoint", "keywords": ["rooftop view", "skyline view"]},
                "karting": {"label": "Karting", "keywords": ["karting", "go-kart", "go kart"]},
                "escape_room": {"label": "Escape room", "keywords": ["escape room", "puzzle room"]},
                "gallery_hop": {"label": "Gallery hop", "keywords": ["gallery hop", "art cluster"]},
                "workshops": {"label": "Workshop", "keywords": ["workshop", "class", "pottery", "mixology", "cooking class"]},
            }
        }

    _EXTRA_CLUSTERS = _EXTRA_CONF.get("clusters", {})
    
    tags = [t.strip().lower() for t in (row.tags_csv or "").split(",") if t.strip()]
    sig = row.signals or {}
    hooks = sig.get("hooks") or []
    evidence = sig.get("evidence") or []
    hay = [row.name, row.summary, " ".join(tags)] + hooks + evidence
    for key, spec in _EXTRA_CLUSTERS.items():
        kws = spec.get("keywords", [])
        if _token_hit(hay, [k.lower() for k in kws]):
            return True, key, spec.get("label") or key
    # fallback: novelty >= 0.45 → still extraordinary without cluster
    try:
        if float(sig.get("novelty_score", 0.0)) >= 0.45:
            return True, None, None
    except Exception:
        pass
    return False, None, None

def _compute_hq_flag(row) -> bool:
    sig = row.signals or {}
    def _f(v, d=0.0):
        try: return float(v)
        except Exception: return d
    if _f(sig.get("quality_score", 0.0)) >= 0.6: 
        return True
    if sig.get("editor_pick"): 
        return True
    if sig.get("local_gem") and (sig.get("dateworthy") or sig.get("vista_view")):
        return True
    # text triggers
    texts = [row.name, row.summary, row.tags_csv] + (sig.get("hooks") or []) + (sig.get("evidence") or [])
    # Load quality triggers from config
    _EXTRA_CONF_PATH = "config/extraordinary.yml"
    _EXTRA_CONF = {}
    try:
        with open(_EXTRA_CONF_PATH, "r", encoding="utf-8") as f:
            _EXTRA_CONF = yaml.safe_load(f) or {}
    except Exception:
        _EXTRA_CONF = {
            "quality_triggers": {
                "michelin": ["michelin", "bib gourmand", "one star", "1 star", "starred"],
                "specialty_coffee": ["specialty coffee", "manual brew", "pour-over", "roastery", "flagship roaster"],
                "chef_table": ["omakase", "chef's table", "tasting menu"],
                "curated_gallery": ["curated program", "gallery program"],
                "premium_cocktails": ["craft cocktails", "mixology", "signature cocktails", "artisan cocktails", "award-winning bar", "premium spirits", "craft bar", "cocktail lounge"],
                "luxury_spa": ["luxury spa", "premium treatments", "award-winning spa", "signature treatments", "world-class spa", "spa resort", "wellness retreat"],
                "premium_rooftop": ["panoramic view", "skyline view", "infinity pool", "rooftop infinity", "stunning views", "breathtaking view", "city views", "rooftop terrace"],
                "fine_dining": ["fine dining", "chef's selection", "molecular gastronomy", "farm-to-table", "tasting menu", "degustation"],
                "luxury_experience": ["luxury", "premium", "exclusive", "boutique", "world-class", "award-winning", "5-star", "upscale"]
            }
        }
    
    _QUALITY_TRIGGERS = _EXTRA_CONF.get("quality_triggers", {})
    for _, needles in _QUALITY_TRIGGERS.items():
        if _token_hit(texts, [n.lower() for n in needles]):
            return True
    return False

def _sig_to_badges_and_why(sig: dict, cluster_label: Optional[str]) -> Tuple[List[str], Optional[str]]:
    if not isinstance(sig, dict):
        sig = {}
    badges = []
    
    # Priority 1: Cluster label (most specific)
    if cluster_label: 
        badges.append(f"🎯 {cluster_label}")
    
    # Priority 2: Quality flags
    if sig.get("editor_pick"): 
        badges.append("👑 Editor Pick")
    if sig.get("local_gem"): 
        badges.append("💎 Local Gem")
    if sig.get("dateworthy"): 
        badges.append("💕 Date Night")
    if sig.get("vista_view"): 
        badges.append("🌅 Great View")
    if sig.get("extraordinary"): 
        badges.append("⭐ Extraordinary")
    
    # Priority 3: Score-derived badges
    try:
        if float(sig.get("trend_score", 0)) >= 0.6: 
            badges.append("🔥 Trending")
        if float(sig.get("quality_score", 0)) >= 0.65: 
            badges.append("✨ Premium")
        if float(sig.get("novelty_score", 0)) >= 0.6: 
            badges.append("🆕 Novel")
    except Exception:
        pass
    
    # Limit to 3 badges max
    badges = badges[:3]
    
    # Generate 'why' explanation
    why = None
    hooks = sig.get("hooks") or []
    ev = sig.get("evidence") or []
    
    if isinstance(hooks, list) and hooks:
        why = hooks[0][:80]  # Use first hook as primary reason
    elif isinstance(ev, list) and ev:
        why = ev[0][:120]  # Use evidence if no hooks
    elif sig.get("editor_pick"):
        why = "Curated by our editors"
    elif sig.get("local_gem"):
        why = "Beloved by locals"
    elif sig.get("dateworthy"):
        why = "Perfect for special occasions"
    elif cluster_label:
        why = f"Unique {cluster_label.lower()} experience"
    elif sig.get("extraordinary"):
        why = "Unusual and memorable experience"
    elif badges:
        # Remove emojis for why text
        clean_badges = [badge.split(' ', 1)[-1] for badge in badges[:2]]
        why = " • ".join(clean_badges)
    else:
        # Fallback based on scores
        novelty = float(sig.get("novelty_score", 0) or 0)
        interest = float(sig.get("interest_score", 0) or 0)
        if novelty > 0.5:
            why = "Novel experience"
        elif interest > 0.5:
            why = "Highly engaging"
        else:
            why = "Recommended"
    
    return badges, why

def _annotate_card_with_signals(card: PlaceCard, row) -> PlaceCard:
    is_extra, cluster_key, cluster_label = _detect_extraordinary_cluster(row)
    sig = dict(row.signals or {})
    sig["extraordinary"] = bool(is_extra)
    if cluster_key:
        sig["extraordinary_cluster"] = cluster_key
    # HQ flag
    sig["hq_experience"] = _compute_hq_flag(row)
    badges, why = _sig_to_badges_and_why(sig, cluster_label)
    card.badges = badges
    card.why = why
    # Сохраняем signals в карточку
    card.signals = sig
    # we do not mutate DB here; we enrich response only
    return card


def _score_query_candidate(place: Dict[str, Any]) -> float:
    signals = place.get("signals") or {}
    score = 0.0
    if signals.get("hq_experience"):
        score += 2.0
    score += float(signals.get("quality_score", 0.0) or 0.0) * 1.2
    score += float(signals.get("interest_score", 0.0) or 0.0) * 0.6
    score += float(signals.get("novelty_score", 0.0) or 0.0) * 0.2
    if signals.get("editor_pick"):
        score += 0.5
    rating = place.get("rating")
    if rating:
        try:
            score += min(1.0, float(rating) / 5.0)
        except (TypeError, ValueError):
            pass
    return score


def _merge_query_primary_with_secondary(primary: List[Rail], secondary: List[Rail], *, max_rails: int = 3) -> List[Rail]:
    merged: List[Rail] = []
    used_ids: set[int] = set()

    def _append(rail: Rail) -> None:
        filtered: List[PlaceCard] = []
        for item in rail.items:
            if item.id in used_ids:
                continue
            used_ids.add(item.id)
            filtered.append(item)
        if filtered:
            merged.append(Rail(step=rail.step, label=rail.label, items=filtered, origin=rail.origin, reason=rail.reason))

    for rail in primary:
        _append(rail)
        if len(merged) >= max_rails:
            return merged[:max_rails]

    for rail in secondary:
        _append(rail)
        if len(merged) >= max_rails:
            break

    return merged[:max_rails]


def _build_query_rail_items(candidates: List[Dict[str, Any]], used_ids: set[int]) -> List[PlaceCard]:
    items: List[PlaceCard] = []
    for place in candidates:
        place_id = place.get("id")
        if place_id in used_ids:
            continue
        lat = place.get("lat")
        lng = place.get("lng")
        if lat is None or lng is None:
            continue
        used_ids.add(place_id)
        card = PlaceCard(
            id=place_id,
            name=place.get("name", ""),
            summary=place.get("summary", ""),
            tags_csv=place.get("tags_csv", ""),
            category=place.get("category", ""),
            lat=lat,
            lng=lng,
            picture_url=place.get("picture_url"),
            rating=place.get("rating"),
            distance_m=place.get("distance_m"),
            search_score=place.get("search_score"),
            vibe_score=0.0,
            novelty_score=float((place.get("signals") or {}).get("novelty_score", 0.0) or 0.0),
            signals=dict(place.get("signals") or {}),
        )
        row = SimpleNamespace(
            signals=place.get("signals"),
            tags_csv=place.get("tags_csv"),
            summary=place.get("summary"),
            rating=place.get("rating"),
            category=place.get("category"),
            name=place.get("name"),
        )
        card = _annotate_card_with_signals(card, row)
        if not card.reason:
            card.reason = "Matches your search"
        if not card.why:
            card.why = "Based on query"
        items.append(card)
    return items


def _augment_slots_from_query(query: str, slots: List[Slot]) -> List[Slot]:
    """Ensure at least three intents by adding heuristic slots when slotter misses obvious tokens."""
    existing_keys = {(getattr(s, "type", None), getattr(s, "canonical", None)) for s in slots}
    lowered = query.lower()

    # quick splits on punctuation and conjunctions
    raw_tokens = re.split(r"[,/&]|\\band\\b|\\bor\\b", lowered)
    tokens = [t.strip() for t in raw_tokens if t and t.strip()]

    # Lightweight heuristics to backfill missing slots when slotter misses simple intents
    _ADHOC_SLOT_HINTS: Dict[str, Tuple[str, str]] = {
        "climb": ("experience", "climbing"),
        "climbing": ("experience", "climbing"),
        "climbing gym": ("experience", "climbing"),
        "bouldering": ("experience", "climbing"),
        "cinema": ("experience", "cinema"),
        "movie theater": ("experience", "cinema"),
        "movie theatre": ("experience", "cinema"),
        "movies": ("experience", "cinema"),
        "date": ("vibe", "romantic"),
        "dating": ("vibe", "romantic"),
        "romantic": ("vibe", "romantic"),
        "anniversary": ("vibe", "romantic"),
    }

    for token in tokens:
        for hint, (kind, canonical) in _ADHOC_SLOT_HINTS.items():
            if hint in token:
                try:
                    slot_type = SlotType(kind)
                except ValueError:
                    continue
                key = (slot_type, canonical)
                if key in existing_keys:
                    continue
                slots.append(
                    Slot(
                        type=slot_type,
                        canonical=canonical,
                        label=canonical.replace("_", " "),
                        confidence=0.35,
                        filters={},
                        matched_text=token,
                        reason="heuristic",
                        context={},
                    )
                )
                existing_keys.add(key)
                if len(slots) >= 3:
                    return slots
                break
    return slots


async def _compose_query_rails(
    query: str,
    area: Optional[str],
    user_lat: Optional[float],
    user_lng: Optional[float],
    quality_only: bool,
    db: Session,
    search_service: Optional[SearchService] = None,
) -> ComposeResponse:
    start = time.time()

    normalized_query = (query or "").strip()
    if not normalized_query:
        return ComposeResponse(rails=[], processing_time_ms=0.0, cache_hit=False)

    service = search_service.bind_db(db) if search_service else SearchService(db)
    slotter = _get_query_builder()

    try:
        slot_result = slotter.build_slots(normalized_query)
        raw_slots = getattr(slot_result, "slots", []) or []
    except Exception:
        raw_slots = []

    def _normalize_phrase(text: str) -> str:
        return (text or "").replace("_", " ").strip().lower()

    lowered_query = normalized_query.lower()
    raw_tokens = re.split(r"[,/&]|\\band\\b|\\bor\\b", lowered_query)
    query_tokens = [t.strip() for t in raw_tokens if t and t.strip()]

    # Deduplicate raw slots while preserving order
    unique_slots: List[Slot] = []
    seen_keys: set[Tuple[SlotType, str]] = set()
    for slot in raw_slots:
        key = (getattr(slot, "type", None), getattr(slot, "canonical", None))
        if None in key or key in seen_keys:
            continue
        seen_keys.add(key)
        unique_slots.append(slot)

    slots = list(unique_slots)
    slots = _augment_slots_from_query(normalized_query, slots)

    def _is_relevant(slot: Slot) -> bool:
        canonical_phrase = _normalize_phrase(getattr(slot, "canonical", ""))
        label_phrase = _normalize_phrase(getattr(slot, "label", ""))
        phrases = [p for p in [canonical_phrase, label_phrase] if p]
        if not phrases:
            return False
        for phrase in phrases:
            if phrase in lowered_query:
                return True
            for token in query_tokens:
                if phrase in token or token in phrase:
                    return True
        return False

    relevant_slots = [slot for slot in slots if _is_relevant(slot)] or slots

    # Final dedupe and cap to 3
    seen_keys.clear()
    deduped_slots: List[Slot] = []
    for slot in relevant_slots:
        key = (getattr(slot, "type", None), getattr(slot, "canonical", None))
        if None in key or key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_slots.append(slot)

    slots = deduped_slots[:3]

    if len(slots) < 3:
        # augment again in case dedupe trimmed entries
        slots = _augment_slots_from_query(normalized_query, slots)
        seen_keys.clear()
        final_slots: List[Slot] = []
        for slot in slots:
            key = (getattr(slot, "type", None), getattr(slot, "canonical", None))
            if None in key or key in seen_keys:
                continue
            seen_keys.add(key)
            final_slots.append(slot)
        slots = final_slots[:3]
    used_ids: set[int] = set()
    rails: List[Rail] = []
    candidate_pool: Dict[int, Dict[str, Any]] = {}
    chunk = 12

    def _merge_candidate(candidate: Dict[str, Any]) -> None:
        pid = candidate.get("id")
        if not pid:
            return
        existing = candidate_pool.get(pid)
        score = candidate.get("search_score") or 0.0
        if existing is None or (existing.get("search_score") or 0.0) < score:
            candidate_pool[pid] = dict(candidate)

    def _quality_sorted(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked_local = sorted(candidates, key=_score_query_candidate, reverse=True)
        if not quality_only:
            return ranked_local
        preferred, others = [], []
        for c in ranked_local:
            sig = c.get("signals") or {}
            rating = c.get("rating") or 0
            if sig.get("hq_experience") or rating >= 4.3:
                preferred.append(c)
            else:
                others.append(c)
        return preferred + others

    def _slot_label(slot) -> str:
        base = (getattr(slot, "label", None) or getattr(slot, "canonical", "")).replace("_", " ").strip()
        if not base:
            return "Matches"
        return base[:1].upper() + base[1:]

    def _slot_reason(slot) -> str:
        base = (getattr(slot, "label", None) or getattr(slot, "canonical", "")).replace("_", " ").strip()
        return f"Based on {base}" if base else "Based on query"

    for slot in slots:
        try:
            slot_candidates = service.search_by_slot(
                slot=slot,
                limit=120,
                offset=0,
                user_lat=user_lat,
                user_lng=user_lng,
                radius_m=None,
                area=area,
            )
        except Exception:
            slot_candidates = []

        if not slot_candidates:
            continue

        deduped: Dict[int, Dict[str, Any]] = {}
        for candidate in slot_candidates:
            pid = candidate.get("id")
            if not pid:
                continue
            existing = deduped.get(pid)
            score = candidate.get("search_score") or 0.0
            if existing is None or (existing.get("search_score") or 0.0) < score:
                deduped[pid] = dict(candidate)

        ranked_slot = _quality_sorted(list(deduped.values()))
        for cand in ranked_slot:
            _merge_candidate(cand)

        items = _build_query_rail_items(ranked_slot, used_ids)
        if not items:
            continue

        slot_type = getattr(getattr(slot, "type", None), "value", "slot")
        step = f"{slot_type}:{getattr(slot, 'canonical', 'slot')}"
        rails.append(
            Rail(
                step=step,
                label=_slot_label(slot),
                items=items[:chunk],
                origin=slot_type,
                reason=_slot_reason(slot),
            )
        )

        if len(rails) >= 3:
            break

    # Если слоттер не дал всех рельс — добираем FTS/общими матчами
    need_fallback = len(rails) < 3
    if need_fallback or not rails:
        try:
            fallback_candidates = service.search_places(
                query=normalized_query,
                limit=180,
                offset=0,
                user_lat=user_lat,
                user_lng=user_lng,
                area=area,
                sort="relevance",
            )
        except Exception:
            fallback_candidates = []

        for cand in fallback_candidates:
            _merge_candidate(cand)

        ranked_pool = _quality_sorted(
            [c for c in candidate_pool.values() if c.get("id") not in used_ids]
        )

        remaining = list(ranked_pool)
        while len(rails) < 3 and remaining:
            slice_ = remaining[:chunk]
            remaining = remaining[chunk:]
            items = _build_query_rail_items(slice_, used_ids)
            if not items:
                continue
            label = "Search results" if not rails else "More matches"
            step = f"query_{len(rails) + 1}"
            rails.append(
                Rail(
                    step=step,
                    label=label,
                    items=items[:chunk],
                    origin="query",
                    reason="Free-text query",
                )
            )

    # Если всё ещё пусто — возвращаем пустой ответ
    if not rails:
        processing_ms = (time.time() - start) * 1000.0
        return ComposeResponse(rails=[], processing_time_ms=processing_ms, cache_hit=False)

    processing_ms = (time.time() - start) * 1000.0
    return ComposeResponse(rails=rails[:3], processing_time_ms=processing_ms, cache_hit=False)


# Global services (singleton pattern)
_query_builder_singleton = None

def _get_query_builder():
    """Lazily instantiate shared query builder for slot extraction."""
    global _query_builder_singleton
    if _query_builder_singleton is None:
        _query_builder_singleton = create_query_builder()
    return _query_builder_singleton


@router.get("/rails", response_model=ComposeResponse)
async def get_rails(
    q: Optional[str] = Query(None, description="Free-text query for slotter"),
    area: Optional[str] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    quality: Optional[str] = None,
    db: Session = Depends(get_db),
    resp: Response = None
):
    """
    GET endpoint for rails: returns exactly 3 rails based on free-text query.
    """
    if not q or not q.strip():
        return ComposeResponse(rails=[], processing_time_ms=0.0, cache_hit=False)

    normalized_q = q.strip()
    search_service = create_search_service(db)

    quality_only = (quality == "high")

    cache_key = _slotter_rails_cache_key(normalized_q, area, user_lat, user_lng, quality_only)
    cached_result = _rcache_get(cache_key)
    if cached_result:
        if resp:
            resp.headers["X-Cache"] = "HIT"
        return cached_result

    fts_response = await _compose_query_rails(
        normalized_q,
        area,
        user_lat,
        user_lng,
        quality_only,
        db,
        search_service=search_service,
    )

    slotter_enabled = should_use_slotter(normalized_q)
    slotter_response: Optional[ComposeResponse] = None

    if slotter_enabled:
        if should_log_slotter(normalized_q):
            logger.info(f"Shadow mode: Processing query '{normalized_q}' with slotter")

        if should_ab_test_slotter(normalized_q):
            logger.info(f"A/B test: Query '{normalized_q}' selected for slotter testing")

        # Use the same _compose_query_rails function for slotter
        slotter_response = await _compose_query_rails(
            normalized_q,
            area,
            user_lat,
            user_lng,
            quality_only,
            db,
            search_service=search_service,
        )

        if should_log_slotter(normalized_q):
            logger.info(
                "Shadow mode: Generated %s rails for query '%s' in %.2fms",
                len(slotter_response.rails),
                normalized_q,
                slotter_response.processing_time_ms,
            )
            for i, rail in enumerate(slotter_response.rails):
                logger.info(
                    "Shadow mode: Rail %s: %s (%s items)",
                    i + 1,
                    rail.label,
                    len(rail.items),
                )

    final_response = fts_response

    if slotter_response and slotter_response.rails:
        if not fts_response.rails:
            final_response = slotter_response
        else:
            merged = _merge_query_primary_with_secondary(fts_response.rails, slotter_response.rails)
            final_response = ComposeResponse(
                rails=merged,
                processing_time_ms=max(
                    fts_response.processing_time_ms or 0.0,
                    slotter_response.processing_time_ms or 0.0,
                ),
                cache_hit=fts_response.cache_hit and slotter_response.cache_hit,
            )
    elif not fts_response.rails and slotter_response:
        final_response = slotter_response

    _rcache_set(cache_key, final_response)
    if resp:
        resp.headers["X-Cache"] = "MISS"
    return final_response
