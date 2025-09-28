#!/usr/bin/env python3
"""Compose API for Netflix-style search system"""

import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Response, Query
from sqlalchemy.orm import Session
import hashlib, json
from collections import OrderedDict
from types import SimpleNamespace

from apps.core.db import get_db
from apps.places.schemas.vibes import ComposeRequest, ComposeResponse, Rail, PlaceCard
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

# --- Load extraordinary clusters (YAML). Fallback to in-code defaults if file missing.
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
        },
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

_EXTRA_CLUSTERS = _EXTRA_CONF.get("clusters", {})
_QUALITY_TRIGGERS = _EXTRA_CONF.get("quality_triggers", {})

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

def _vibe_rails_cache_key(vibe: str, energy: str, area: Optional[str],
                          user_lat: Optional[float], user_lng: Optional[float],
                          quality_only: bool) -> str:
    try:
        payload = {
            "mode": "vibe",
            "vibe": vibe,
            "energy": energy,
            "area": (area or "").strip().lower(),
            "user_lat": round(user_lat or 0.0, 4) if user_lat is not None else None,
            "user_lng": round(user_lng or 0.0, 4) if user_lng is not None else None,
            "quality_only": quality_only,
        }
        s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return "vibe:" + hashlib.md5(s.encode("utf-8")).hexdigest()
    except Exception:
        return f"vibe:{vibe}:{energy}:{area}:{user_lat}:{user_lng}:{quality_only}"

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



def _pick_by_clusters(rows: List[Any], per_cluster: int = 12) -> Dict[str, List[Any]]:
    """Group rows into clusters; take up to per_cluster per cluster in order of interest_score desc then rating."""
    grouped: Dict[str, List[Any]] = {}
    def score_key(r):
        sig = r.signals or {}
        try: 
            return (float(sig.get("interest_score", 0.0)), r.rating or 0.0)
        except Exception:
            return (0.0, r.rating or 0.0)
    rows_sorted = sorted(rows, key=score_key, reverse=True)
    for r in rows_sorted:
        is_extra, cluster_key, _label = _detect_extraordinary_cluster(r)
        if not is_extra or not cluster_key:
            continue
        bucket = grouped.setdefault(cluster_key, [])
        if len(bucket) < per_cluster:
            bucket.append(r)
    return grouped

def _pick_by_clusters_enhanced(rows: List[Any], per_cluster: int = 12) -> Dict[str, List[Any]]:
    """Enhanced clustering with fallback for places without explicit clusters."""
    grouped: Dict[str, List[Any]] = {}
    
    # First pass: group by explicit clusters
    for r in rows:
        is_extra, cluster_key, _label = _detect_extraordinary_cluster(r)
        if is_extra and cluster_key:
            bucket = grouped.setdefault(cluster_key, [])
            if len(bucket) < per_cluster:
                bucket.append(r)
                continue
    
    # Second pass: create fallback clusters from tags for unclustered extraordinary places
    unclustered = []
    for r in rows:
        is_extra, cluster_key, _label = _detect_extraordinary_cluster(r)
        if is_extra and not cluster_key:
            unclustered.append(r)
        elif not is_extra:
            # Check for surprise tags as fallback
            tags_lower = (r.tags_csv or "").lower()
            if any(tag in tags_lower for tag in ['experience:', 'feature:rooftop', 'category:theme_park']):
                unclustered.append(r)
    
    # Create fallback clusters
    fallback_clusters = {
        'unique_experiences': [],
        'adventure_sports': [],
        'creative_spaces': []
    }
    
    for r in unclustered:
        tags_lower = (r.tags_csv or "").lower()
        
        # Categorize into fallback clusters
        if any(tag in tags_lower for tag in ['experience:ice_skating', 'experience:trampoline', 'experience:arcade']):
            if len(fallback_clusters['unique_experiences']) < per_cluster:
                fallback_clusters['unique_experiences'].append(r)
        elif any(tag in tags_lower for tag in ['experience:climbing', 'experience:karting', 'experience:bowling']):
            if len(fallback_clusters['adventure_sports']) < per_cluster:
                fallback_clusters['adventure_sports'].append(r)
        elif any(tag in tags_lower for tag in ['workshop', 'gallery', 'art']):
            if len(fallback_clusters['creative_spaces']) < per_cluster:
                fallback_clusters['creative_spaces'].append(r)
        else:
            # Default to unique experiences
            if len(fallback_clusters['unique_experiences']) < per_cluster:
                fallback_clusters['unique_experiences'].append(r)
    
    # Merge fallback clusters with main grouped results
    for cluster_name, places in fallback_clusters.items():
        if places and cluster_name not in grouped:
            grouped[cluster_name] = places
    
    return grouped


# Global services (singleton pattern)
_ontology = None
_bitset_service = None
_search_service = None
_ranking_service = None
_profile_service = None
_query_builder_singleton = None


def get_services():
    """Get or create global services"""
    global _ontology, _bitset_service, _search_service, _ranking_service, _profile_service
    
    if _ontology is None:
        _ontology = load_ontology()
    
    if _bitset_service is None:
        _bitset_service = create_bitset_service(_ontology)
    
    if _search_service is None:
        _search_service = SearchService(None)  # Will be initialized with db in compose_rails
    
    if _ranking_service is None:
        _ranking_service = create_ranking_service(_bitset_service, _search_service)
    
    if _profile_service is None:
        _profile_service = SessionProfileService()

    # Always return after ensuring all singletons are initialized
    return _ontology, _bitset_service, _search_service, _ranking_service, _profile_service


def _get_query_builder():
    """Lazily instantiate shared query builder for slot extraction."""
    global _query_builder_singleton
    if _query_builder_singleton is None:
        _query_builder_singleton = create_query_builder()
    return _query_builder_singleton


def _get_rail_label(step: str) -> str:
    """Get human-readable label for a rail step"""
    labels = {
        'restaurant': 'Restaurants',
        'drinks': 'Bars & Nightlife',
        'activity': 'Activities',
        'wellness': 'Wellness & Spa',
        'culture': 'Culture & Arts',
        'shopping': 'Shopping',
        'general': 'Places'
    }
    return labels.get(step, step.title())


@router.post("/compose", response_model=ComposeResponse)
async def compose_rails(
    request: ComposeRequest,
    db: Session = Depends(get_db),
    resp: Response = None
):
    """
    Compose search results into rails with 3-stage ranking.
    
    This endpoint takes a parsed query and returns organized rails of places:
    1. Base ranking: search_score + vibe_score + novelty
    2. Proximity sorting: re-sort by distance from user/anchor
    3. Diversity (MMR): ensure variety in results
    
    Each rail represents a different intent (restaurant, activity, drinks, etc.)
    and contains up to 12 place cards with scores and metadata.
    """
    start_time = time.time()
    
    # --- simple LRU cache for rails ---
    # key: mode + parse_result + geo + area (TTL 120s)
    if not hasattr(compose_rails, "_rails_cache"):
        compose_rails._rails_cache = OrderedDict()
        compose_rails._ttl = 120
        compose_rails._max = 200

    def _rails_cache_key(req: ComposeRequest) -> str:
        try:
            payload = {
                "mode": (req.mode or "light"),
                "area": (req.area or "").strip().lower(),
                "user_lat": round(req.user_lat or 0.0, 4) if req.user_lat is not None else None,
                "user_lng": round(req.user_lng or 0.0, 4) if req.user_lng is not None else None,
                "parse_result": req.dict().get("parse_result", {})
            }
            s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(s.encode("utf-8")).hexdigest()
        except Exception:
            # fallback
            return hashlib.md5(str(req).encode("utf-8")).hexdigest()

    def _vibe_rails_cache_key(vibe: str, energy: str, area: Optional[str], 
                             user_lat: Optional[float], user_lng: Optional[float], 
                             quality_only: bool) -> str:
        """Generate cache key for vibe rails requests."""
        try:
            payload = {
                "mode": "vibe",
                "vibe": vibe,
                "energy": energy,
                "area": (area or "").strip().lower(),
                "user_lat": round(user_lat or 0.0, 4) if user_lat is not None else None,
                "user_lng": round(user_lng or 0.0, 4) if user_lng is not None else None,
                "quality_only": quality_only
            }
            s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(s.encode("utf-8")).hexdigest()
        except Exception:
            # fallback
            return hashlib.md5(f"vibe:{vibe}:{energy}:{area}:{user_lat}:{user_lng}:{quality_only}".encode("utf-8")).hexdigest()

    def _slotter_rails_cache_key(q: str, area: Optional[str], 
                                user_lat: Optional[float], user_lng: Optional[float], 
                                quality_only: bool) -> str:
        """Generate cache key for slotter rails requests."""
        try:
            payload = {
                "mode": "slotter",
                "q": q.strip().lower(),
                "area": (area or "").strip().lower(),
                "user_lat": round(user_lat or 0.0, 4) if user_lat is not None else None,
                "user_lng": round(user_lng or 0.0, 4) if user_lng is not None else None,
                "quality_only": quality_only
            }
            s = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(s.encode("utf-8")).hexdigest()
        except Exception:
            # fallback
            return hashlib.md5(f"slotter:{q}:{area}:{user_lat}:{user_lng}:{quality_only}".encode("utf-8")).hexdigest()

    def _rcache_get(key: str):
        cache = compose_rails._rails_cache
        entry = cache.get(key)
        if not entry:
            return None
        if (time.time() - entry["ts"]) > compose_rails._ttl:
            cache.pop(key, None)
            return None
        cache.move_to_end(key, last=True)
        return entry["val"]

    def _rcache_set(key: str, val):
        cache = compose_rails._rails_cache
        cache[key] = {"val": val, "ts": time.time()}
        while len(cache) > compose_rails._max:
            cache.popitem(last=False)

    try:
        cache_key = _rails_cache_key(request)
        cached = _rcache_get(cache_key)
        if cached:
            if resp:
                try:
                    labels = [f"{r.label}:{r.origin or 'query'}" for r in (cached.rails or [])]
                    if resp:
                        resp.headers["X-Mode"] = request.mode or "light"
                        resp.headers["X-Rails"] = "; ".join(labels)
                        resp.headers["X-Rails-Cache"] = "HIT"
                except Exception:
                    pass
            return cached
        # Get services
        ontology, bitset_service, search_service, ranking_service, profile_service = get_services()
        
        # Get or create user profile
        profile = None
        if request.session_id:
            profile = profile_service.get_profile(request.session_id)
            if not profile:
                profile = profile_service.create_profile(request.session_id)
        
        # --- SLOTTING: всегда готовим до 3 слотов ---
        def _slot_intent(slot: str) -> str:
            if slot.startswith("dish:"):
                return "feature"
            if slot.startswith("experience:"):
                return "vibe"
            return "default"

        def _ensure_three_slots(req: ComposeRequest) -> list:
            # Берём из parse_result, если там уже есть осмысленные шаги
            steps = []
            try:
                raw_steps = (req.parse_result or {}).get("steps", []) if isinstance(req.parse_result, dict) else (req.parse_result.steps or [])
                for s in (raw_steps or []):
                    sl = s.get("slot") or s.get("token") or s.get("term")
                    if sl:
                        steps.append(str(sl).strip().lower())
            except Exception:
                pass
            # Если слотов нет/меньше 3 — достраиваем из свободного текста
            if len(steps) < 3 and req.query:
                builder = _get_query_builder()
                try:
                    slotter_res = builder.build_slots(req.query)
                except Exception:
                    slotter_res = None
                if slotter_res:
                    for slot in getattr(slotter_res, "slots", []) or []:
                        canonical = f"{slot.type.value}:{slot.canonical}"
                        if canonical not in steps:
                            steps.append(canonical)
                            if len(steps) == 3:
                                break
            # Если всё ещё <3 — добираем co-occurrence
            if len(steps) < 3:
                need = 3 - len(steps)
                for sl in _suggest_complementary_slots(db, steps, need):
                    if sl not in steps:
                        steps.append(sl)
                        if len(steps) == 3:
                            break
            return steps[:3]

        def _suggest_complementary_slots(db: Session, have: list, need: int) -> list:
            """
            Добор комплементарных слотов через co-occurrence по MV:
            - Берём все места, где встречается хотя бы один из текущих слотов (по части после префикса).
            - Сплитим tags_csv на атомы, считаем частоты, исключаем уже имеющиеся.
            - Отбираем только теги, которые можно отмаппить в канонические слоты (experience/dish).
            """
            if need <= 0:
                return []
            seeds = []
            for s in (have or []):
                try:
                    seeds.append(s.split(":", 1)[1])
                except Exception:
                    pass
            seeds = [x for x in seeds if x]
            if not seeds:
                return []

            # Строим ILIKE условия безопасно через параметры
            ilike_conditions = []
            params = {}
            for i, x in enumerate(seeds):
                key = f"pat_{i}"
                ilike_conditions.append(f"tags_csv ILIKE :{key}")
                params[key] = f"%{x}%"
            
            sql = text(f"""
                WITH hits AS (
                  SELECT tags_csv
                  FROM epx.places_search_mv
                  WHERE processing_status IN ('summarized','published')
                    AND ({' OR '.join(ilike_conditions)})
                ),
                exploded AS (
                  SELECT lower(trim(both ' ' from t)) AS tag
                  FROM hits, regexp_split_to_table(hits.tags_csv, ',') AS t
                )
                SELECT tag, count(*) AS cnt
                FROM exploded
                WHERE tag <> '' 
                GROUP BY tag
                ORDER BY cnt DESC
                LIMIT 50
            """)
            rows = db.execute(sql, params).fetchall()

            # Try to use SLOT_COMPLEMENTS first
            try:
                from config.canon_slots import SLOT_COMPLEMENTS, CANON_SLOTS
                
                suggestions = []
                have_set = set(have or [])
                
                # Extract slot names from have list (e.g., "dish:sushi" -> "sushi")
                have_names = []
                for slot in have:
                    try:
                        slot_name = slot.split(":", 1)[1] if ":" in slot else slot
                        have_names.append(slot_name)
                    except:
                        pass
                
                # Get complements for each slot we have
                for slot_name in have_names:
                    if slot_name in SLOT_COMPLEMENTS:
                        complements = SLOT_COMPLEMENTS[slot_name]
                        for complement in complements:
                            # Create full slot key with correct kind
                            if complement in CANON_SLOTS:
                                kind = CANON_SLOTS[complement]['kind']
                                complement_slot = f"{kind}:{complement}"
                            else:
                                complement_slot = f"experience:{complement}"  # Default to experience
                            
                            if complement_slot not in have_set and complement_slot not in suggestions:
                                suggestions.append(complement_slot)
                                if len(suggestions) >= need:
                                    break
                    if len(suggestions) >= need:
                        break
                
                # If we still need more, use _default
                if len(suggestions) < need and "_default" in SLOT_COMPLEMENTS:
                    for complement in SLOT_COMPLEMENTS["_default"]:
                        if complement in CANON_SLOTS:
                            kind = CANON_SLOTS[complement]['kind']
                            complement_slot = f"{kind}:{complement}"
                        else:
                            complement_slot = f"experience:{complement}"
                        
                        if complement_slot not in have_set and complement_slot not in suggestions:
                            suggestions.append(complement_slot)
                            if len(suggestions) >= need:
                                break
                
                return suggestions[:need]
                
            except ImportError:
                # Fallback to old tag mapping logic
                def _map_tag_to_slot(tag: str) -> str:
                    t = tag.strip().lower()
                    # минимальный маппинг в канонические слоты
                    if "tom_yum" in t or "tom yum" in t or "tom-yum" in t:
                        return "dish:tom_yum"
                    if "rooftop" in t or "skyline" in t or "skybar" in t:
                        return "experience:rooftop"
                    if "park" in t or "promenade" in t or "riverside" in t or "waterfront" in t or "garden" in t:
                        return "experience:park_stroll"
                    if "live_music" in t or "jazz" in t:
                        return "experience:live_music"
                    if "night_market" in t or "market" in t:
                        return "experience:night_market"
                    if "spa" in t or "onsen" in t:
                        return "experience:spa"
                    if "craft_beer" in t or "taproom" in t or "ipa" in t:
                        return "experience:tasting"
                    return ""

                out = []
                have_set = set(have or [])
                for r in rows:
                    slot = _map_tag_to_slot(r.tag or "")
                    if slot and slot not in have_set and slot not in out:
                        out.append(slot)
                        if len(out) == need:
                            break
                return out

        # Нормализуем до трёх слотов и подменяем parse_result.steps
        slots = _ensure_three_slots(request)
        if slots:
            norm_steps = [{"intent": _slot_intent(s), "slot": s} for s in slots]
            # Создаем новый ParseResult с нормализованными шагами
            from apps.places.schemas.vibes import ParseResult
            new_parse_result = ParseResult(
                steps=norm_steps,
                vibes=getattr(request.parse_result, 'vibes', []) if hasattr(request.parse_result, 'vibes') else [],
                scenarios=getattr(request.parse_result, 'scenarios', []) if hasattr(request.parse_result, 'scenarios') else [],
                experiences=getattr(request.parse_result, 'experiences', []) if hasattr(request.parse_result, 'experiences') else [],
                filters=getattr(request.parse_result, 'filters', {}) if hasattr(request.parse_result, 'filters') else {},
                novelty_preference=getattr(request.parse_result, 'novelty_preference', 0.0) if hasattr(request.parse_result, 'novelty_preference') else 0.0,
                confidence=getattr(request.parse_result, 'confidence', 0.0) if hasattr(request.parse_result, 'confidence') else 0.0,
                used_llm=getattr(request.parse_result, 'used_llm', False) if hasattr(request.parse_result, 'used_llm') else False,
                processing_time_ms=getattr(request.parse_result, 'processing_time_ms', 0.0) if hasattr(request.parse_result, 'processing_time_ms') else 0.0,
                cache_hit=getattr(request.parse_result, 'cache_hit', False) if hasattr(request.parse_result, 'cache_hit') else False
            )
            request.parse_result = new_parse_result

        # Пробрасываем режим внутрь ранжирования
        setattr(ranking_service, "_mode", (request.mode or "light"))
        payload = ranking_service.compose_rails(request, db, profile)

        query_text = (request.query or "").strip()
        if query_text:
            fts_response = await _compose_query_rails(
                query_text,
                request.area,
                request.user_lat,
                request.user_lng,
                False,
                db,
                search_service=search_service,
            )
            if fts_response.rails:
                payload.rails = _merge_query_primary_with_secondary(fts_response.rails, payload.rails)
        
        # Гарантируем РОВНО 3 рельсы: если меньше — добираем рекомендационными
        def _suggest_rail(label: str, lat: Optional[float], lng: Optional[float]) -> Rail:
            # 1) пытаемся по signals != '{}'
            sql_signals = text("""
                SELECT id, name, summary, tags_csv, COALESCE(category,'') AS category,
                       lat, lng, picture_url, rating, signals
                FROM epx.places_search_mv
                WHERE processing_status IN ('summarized','published')
                  AND signals <> '{}'::jsonb
                ORDER BY rating DESC NULLS LAST
                LIMIT 120
            """)
            rows = db.execute(sql_signals).fetchall()
            # 2) если пусто — подстраховка по «сильным» тегам
            if not rows:
                sql_tags = text("""
                    SELECT id, name, summary, tags_csv, COALESCE(category,'') AS category,
                           lat, lng, picture_url, rating, signals
                    FROM epx.places_search_mv
                    WHERE processing_status IN ('summarized','published')
                      AND (
                           tags_csv ILIKE ANY (ARRAY['%rooftop%','%gallery%','%park%','%spa%','%vr%','%market%'])
                          )
                    ORDER BY rating DESC NULLS LAST
                    LIMIT 120
                """)
                rows = db.execute(sql_tags).fetchall()
            
            # простая гео-сортировка в приложении (без PostGIS)
            def _dist_km(r):
                if not lat or not lng or r.lat is None or r.lng is None:
                    return float('inf')
                import math
                R = 6371.0
                la1, lo1, la2, lo2 = map(math.radians, [lat, lng, r.lat, r.lng])
                d = 2*math.asin(math.sqrt(math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2))
                return R*d
            rows_sorted = sorted(rows, key=_dist_km)
            # anti-dup: если в payload уже есть карточки, не повторяем
            existing_ids = set()
            try:
                for rr in (payload.rails or []):
                    for it in rr.items:
                        existing_ids.add(it.id)
            except Exception:
                pass
            picked = []
            for r in rows_sorted:
                if r.id in existing_ids: 
                    continue
                picked.append(r)
                if len(picked) == 12:
                    break
            items = [PlaceCard(
                id=r.id, name=r.name, summary=r.summary or "", tags_csv=r.tags_csv or "",
                category=r.category or "", lat=r.lat, lng=r.lng, address=None,
                picture_url=r.picture_url, rating=r.rating, website=None, phone=None,
                price_level=None, distance_m=None, walk_time_min=None
            ) for r in picked]
            
            return Rail(step="suggested", label=label, items=items, origin="signals", reason="Top picks near you (no duplicates)")

        if len(payload.rails) < 3:
            missing = 3 - len(payload.rails)
            for i in range(missing):
                payload.rails.append(_suggest_rail(label=f"Suggested #{i+1}", lat=request.user_lat, lng=request.user_lng))
        else:
            # помечаем рельсы, пришедшие из парсера, как origin="query"
            for r in payload.rails[:3]:
                if not r.origin:
                    r.origin = "query"
        if len(payload.rails) > 3:
            payload.rails = payload.rails[:3]
        
        # пометим существующие рельсы, пришедшие из запроса, если у них не задан origin/reason
        for r in payload.rails:
            if not getattr(r, "origin", None):
                r.origin = "query"
            if not getattr(r, "reason", None):
                r.reason = "Based on your query"
        
        # Update profile with search signals
        if profile and request.session_id:
            profile_service.update_search_signal(
                request.session_id, 
                request.parse_result.steps,
                request.parse_result.vibes
            )
        
        processing_time = (time.time() - start_time) * 1000
        payload.processing_time_ms = processing_time
        
        # debug headers через FastAPI Response отсутствуют здесь — добавим лёгкую телеметрию в лог
        # debug логирование с acceptance markers и slots
        try:
            labels = [f"{r.label}:{r.origin or 'query'}" for r in (payload.rails or [])]
            # acceptance markers
            n_items = sum(len(r.items) for r in payload.rails or [])
            first_labels = ", ".join([r.label for r in payload.rails[:3]])
            logger.info(
                f"RailsDebug mode={request.mode} slots={','.join(slots or [])} "
                f"rails={'; '.join(labels)} items={n_items} first3={first_labels} t={processing_time:.2f}ms"
            )
        except Exception:
            logger.info(f"Composed {len(payload.rails)} rails in {processing_time:.2f}ms")

        # HTTP debug headers
        if resp:
            try:
                labels = [f"{r.label}:{r.origin or 'query'}" for r in (payload.rails or [])]
                if resp:
                    resp.headers["X-Mode"] = request.mode or "light"
                    resp.headers["X-Rails"] = "; ".join(labels)
                    resp.headers["X-Rails-Cache"] = "MISS"
            except Exception:
                pass

        # cache store
        _rcache_set(cache_key, payload)
        return payload
        
    except Exception as e:
        logger.error(f"Failed to compose rails: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compose rails: {str(e)}")


@router.get("/compose/stats")
async def get_compose_stats(db: Session = Depends(get_db)):
    """Get composition statistics for monitoring"""
    try:
        ontology, bitset_service, search_service, ranking_service, profile_service = get_services()
        
        # Get bitset stats
        bitset_stats = bitset_service.get_stats(db)
        
        # Get profile stats
        profile_stats = profile_service.get_stats()
        
        return {
            "bitset_stats": bitset_stats,
            "profile_stats": profile_stats,
            "ontology_stats": {
                "total_tags": len(ontology.get_alias_map()),
                "vibes_count": len(ontology.vibes),
                "scenarios_count": len(ontology.scenarios),
                "experiences_count": len(ontology.experiences)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get compose stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/compose/rebuild-bitsets")
async def rebuild_bitsets(db: Session = Depends(get_db)):
    """Rebuild all bitsets for places (admin endpoint)"""
    try:
        ontology, bitset_service, search_service, ranking_service, profile_service = get_services()
        
        # Update all places bitsets
        updated_count = bitset_service.update_all_places_bitsets(db)
        
        logger.info(f"Rebuilt bitsets for {updated_count} places")
        
        return {
            "message": f"Rebuilt bitsets for {updated_count} places",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Failed to rebuild bitsets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rebuild bitsets: {str(e)}")


@router.get("/compose/test")
async def test_compose(
    query: str = "tom yum, rooftop, spa",
    area: Optional[str] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Test endpoint for composing rails without full request validation"""
    try:
        # Parse query first using AI parser
        from apps.ai.ai_parser import parse as ai_parse
        
        ontology, bitset_service, search_service, ranking_service, profile_service = get_services()
        
        # Parse query using AI parser
        ai_result = ai_parse(query, area)
        
        # Convert AI parser result to ParseResult format
        from apps.places.schemas.vibes import ParseResult
        parse_result = ParseResult(
            steps=ai_result['steps'],
            vibes=ai_result['vibes'],
            scenarios=ai_result['scenarios'],
            experiences=ai_result.get('experiences', []),
            filters=ai_result['filters'],
            novelty_preference=ai_result['novelty_preference'],
            confidence=ai_result['confidence'],
            used_llm=False,
            processing_time_ms=0.0,
            cache_hit=False
        )
        
        # Create compose request
        compose_request = ComposeRequest(
            parse_result=parse_result,
            area=area,
            user_lat=user_lat,
            user_lng=user_lng,
            session_id=session_id
        )
        
        # Compose rails
        response = ranking_service.compose_rails(compose_request, db)
        
        return {
            "query": query,
            "parse_result": parse_result.model_dump(),
            "compose_response": response.model_dump(),
            "stats": {
                "rails_count": len(response.rails),
                "total_places": sum(len(rail.items) for rail in response.rails),
                "processing_time_ms": response.processing_time_ms
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to test compose: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to test compose: {str(e)}")


@router.get("/rails", response_model=ComposeResponse)
async def get_rails(
    mode: Optional[str] = "light",
    vibe: Optional[str] = Query(None, description="Vibe type: chill, romantic, active, artsy, classy, scenic, nightlife, family, trendy, cozy"),
    energy: Optional[str] = Query(None, description="Energy level: low, medium, high"),
    area: Optional[str] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
    session_id: Optional[str] = None,
    query: Optional[str] = None,
    q: Optional[str] = Query(None, description="Free-text query for slotter"),
    time_slot: Optional[str] = None,
    limit: int = 12,
    quality: Optional[str] = None,
    db: Session = Depends(get_db),
    resp: Response = None
):
    """
    GET alias for compose: returns exactly 3 rails.
    Supports mode=surprise for extraordinary cluster-based rails and quality=high filter.
    Supports mode=vibe with vibe and energy parameters for vibe-based recommendations.
    """
    # Allow legacy clients sending `query=` instead of `q=`
    if (not q or not q.strip()) and query and query.strip():
        q = query

    # Валидация параметров vibe и energy
    valid_vibes = ["chill", "romantic", "active", "artsy", "classy", "scenic", "nightlife", "family", "trendy", "cozy"]
    valid_energies = ["low", "medium", "high"]
    
    if vibe and vibe not in valid_vibes:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid vibe '{vibe}'. Must be one of: {', '.join(valid_vibes)}"
        )
    
    if energy and energy not in valid_energies:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid energy '{energy}'. Must be one of: {', '.join(valid_energies)}"
        )
    
    # QUALITY filter flag
    quality_only = (quality == "high")

    # Surprise mode → build from extraordinary clusters, 3 distinct rails
    if mode == "surprise":
        # fetch broad candidate pool with enhanced scoring
        sql = text("""
            SELECT *
            FROM epx.places_search_mv
            WHERE processing_status IN ('summarized','published')
              AND (
                signals <> '{}'::jsonb OR 
                tags_csv ILIKE ANY (ARRAY['%experience:trampoline%','%experience:ice_skating%','%experience:planetarium%',
                                          '%experience:aquarium%','%experience:vr_experience%','%experience:karting%',
                                          '%experience:climbing%','%experience:bowling%','%experience:arcade%',
                                          '%feature:rooftop%','%category:theme_park%'])
              )
            LIMIT 500
        """)
        rows = db.execute(sql).fetchall()
        
        # Enhanced scoring: 0.4*novelty + 0.3*interest + 0.15*trend + 0.15*rating_norm
        def _compute_surprise_score(r):
            sig = r.signals or {}
            novelty = float(sig.get("novelty_score", 0.0) or 0.0)
            interest = float(sig.get("interest_score", 0.0) or 0.0)
            trend = float(sig.get("trend_score", 0.0) or 0.0)
            rating_norm = min(1.0, (r.rating or 0.0) / 5.0)  # normalize rating to 0-1
            
            # Core scoring formula
            score = 0.4 * novelty + 0.3 * interest + 0.15 * trend + 0.15 * rating_norm
            
            # Bonus for extraordinary flag
            if sig.get("extraordinary"):
                score += 0.05
                
            # Fallback scoring for places without signals but with surprise tags
            if not sig and r.tags_csv:
                tags_lower = (r.tags_csv or "").lower()
                surprise_indicators = [
                    'experience:trampoline', 'experience:ice_skating', 'experience:planetarium',
                    'experience:aquarium', 'experience:vr_experience', 'experience:karting',
                    'experience:climbing', 'experience:bowling', 'experience:arcade',
                    'feature:rooftop', 'category:theme_park'
                ]
                if any(indicator in tags_lower for indicator in surprise_indicators):
                    score = 0.3 + 0.15 * rating_norm  # base surprise score + rating
                    
            return score
        
        # Sort by surprise score
        rows_scored = [(r, _compute_surprise_score(r)) for r in rows]
        rows_scored.sort(key=lambda x: x[1], reverse=True)
        
        # optional quality filter (client asks for connoisseur picks)
        if quality_only:
            rows_scored = [(r, score) for r, score in rows_scored if _compute_hq_flag(r)]
            
        # Extract rows for clustering
        scored_rows = [r for r, score in rows_scored]
        grouped = _pick_by_clusters_enhanced(scored_rows, per_cluster=limit)

        rails: List[Rail] = []
        # pick 3 best distinct clusters
        cluster_keys_sorted = sorted(grouped.keys(), key=lambda k: (
            sum([_compute_surprise_score(r) for r in grouped[k]]) / max(1, len(grouped[k]))
        ), reverse=True)
        
        for i, key in enumerate(cluster_keys_sorted[:3]):
            items = []
            for r in grouped[key][:limit]:
                surprise_score = _compute_surprise_score(r)
                card = PlaceCard(
                    id=r.id, name=r.name, summary=r.summary or "", tags_csv=r.tags_csv or "",
                    category=r.category or "", lat=r.lat, lng=r.lng, address=None,
                    picture_url=r.picture_url, rating=r.rating, website=None, phone=None,
                    price_level=None, distance_m=None, walk_time_min=None,
                    search_score=surprise_score, vibe_score=0.0, 
                    novelty_score=float((r.signals or {}).get("novelty_score", 0.0) or 0.0),
                )
                card = _annotate_card_with_signals(card, r)
                items.append(card)
            
            # Better rail labels
            cluster_label = _EXTRA_CLUSTERS.get(key, {}).get("label", key.replace("_", " ").title())
            rails.append(Rail(step=f"surprise_{i+1}", label=cluster_label, items=items))
            
        return ComposeResponse(rails=rails, processing_time_ms=0.0, cache_hit=False)

    # High Experience mode or default suggested rails with enhanced quality scoring
    if quality_only:
        # Enhanced High Experience scoring: 0.5*quality + 0.2*rating_norm + 0.2*flags + 0.1*interest
        base_sql = """
            SELECT *
            FROM epx.places_search_mv
            WHERE processing_status IN ('summarized','published')
              AND (
                signals <> '{}'::jsonb OR 
                rating >= 4.0 OR
                tags_csv ILIKE ANY (ARRAY['%price:$$$%','%price:$$$$%','%cuisine:michelin%','%cuisine:fine_dining%',
                                          '%experience:tasting%','%drink:specialty_coffee%','%vibe:upscale%'])
              )
            LIMIT :limit
        """
        rows = db.execute(text(base_sql), {"limit": limit*6}).fetchall()
        
        def _compute_quality_score(r):
            sig = r.signals or {}
            quality = float(sig.get("quality_score", 0.0) or 0.0)
            interest = float(sig.get("interest_score", 0.0) or 0.0)
            rating_norm = min(1.0, (r.rating or 0.0) / 5.0)  # normalize rating to 0-1
            
            # Flags scoring
            flags_score = 0.0
            if sig.get("editor_pick"):
                flags_score += 0.4
            if sig.get("local_gem"):
                flags_score += 0.3
            if sig.get("dateworthy"):
                flags_score += 0.3
            if sig.get("hq_experience"):
                flags_score += 0.2
            flags_score = min(1.0, flags_score)  # cap at 1.0
            
            # Core scoring formula
            score = 0.5 * quality + 0.2 * rating_norm + 0.2 * flags_score + 0.1 * interest
            
            # Fallback scoring for places without signals but with premium indicators
            if not sig and r.tags_csv:
                tags_lower = (r.tags_csv or "").lower()
                premium_indicators = [
                    'price:$$$', 'price:$$$$', 'cuisine:michelin', 'cuisine:fine_dining',
                    'experience:tasting', 'drink:specialty_coffee', 'vibe:upscale'
                ]
                if any(indicator in tags_lower for indicator in premium_indicators):
                    score = 0.3 + 0.4 * rating_norm  # base quality score + heavy rating weight
                elif r.rating and r.rating >= 4.3:
                    score = 0.2 + 0.5 * rating_norm  # high rating fallback
                    
            return score
        
        # Sort by quality score
        rows_scored = [(r, _compute_quality_score(r)) for r in rows]
        rows_scored.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by actual quality criteria
        quality_rows = [(r, score) for r, score in rows_scored 
                       if _compute_hq_flag(r) or score >= 0.4]
        
        # Group into 3 quality-focused rails
        rails: List[Rail] = []
        rail_labels = ["Premium Experiences", "Editor's Picks", "Local Gems"]
        
        # Distribute quality places across 3 rails
        for i in range(3):
            rail_places = quality_rows[i*limit:(i+1)*limit]
            items = []
            for r, quality_score in rail_places:
                card = PlaceCard(
                    id=r.id, name=r.name, summary=r.summary or "", tags_csv=r.tags_csv or "",
                    category=r.category or "", lat=r.lat, lng=r.lng, address=None,
                    picture_url=r.picture_url, rating=r.rating, website=None, phone=None,
                    price_level=None, distance_m=None, walk_time_min=None,
                    search_score=quality_score, vibe_score=0.0, 
                    novelty_score=float((r.signals or {}).get("novelty_score", 0.0) or 0.0),
                )
                card = _annotate_card_with_signals(card, r)
                items.append(card)
            
            rail_label = rail_labels[i] if i < len(rail_labels) else "High Quality"
            rails.append(Rail(step=f"quality_{i+1}", label=rail_label, items=items))
            
        return ComposeResponse(rails=rails, processing_time_ms=0.0, cache_hit=False)
    
    # Vibe mode → build from vibe_packs, 3 distinct rails
    if mode == "vibe" and vibe and energy:
        # Check cache first
        cache_key = _vibe_rails_cache_key(vibe, energy, area, user_lat, user_lng, quality_only)
        cached_result = _rcache_get(cache_key)
        if cached_result:
            if resp:
                resp.headers["X-Cache"] = "HIT"
            return cached_result
        
        # Generate new result
        result = await _compose_vibe_rails(vibe, energy, area, user_lat, user_lng, quality_only, db)
        _rcache_set(cache_key, result)
        if resp:
            resp.headers["X-Cache"] = "MISS"
        return result
    
    # Free-text query mode (slotter / FTS)
    elif q and q.strip():
        normalized_q = q.strip()
        search_service = create_search_service(db)

        cache_key = _slotter_rails_cache_key(normalized_q, area, user_lat, user_lng, quality_only)
        cached_result = _rcache_get(cache_key)
        if cached_result:
            if resp:
                resp.headers["X-Cache"] = "HIT"
            if should_log_slotter(normalized_q):
                logger.info(f"Shadow mode: Cache hit for query '{normalized_q}'")
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

            slotter_response = await _compose_slotter_rails(normalized_q, area, user_lat, user_lng, quality_only, db)

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
    
    # default suggested rails (light/vibe mode)
    base_sql = """
        SELECT *
        FROM epx.places_search_mv
        WHERE processing_status IN ('summarized','published')
          AND signals <> '{}'::jsonb
        ORDER BY COALESCE( (signals->>'interest_score')::float, 0 ) DESC,
                 rating DESC NULLS LAST
        LIMIT :limit
    """
    rows = db.execute(text(base_sql), {"limit": limit*3}).fetchall()

    # split into 3 rails of equal size (or as many as available)
    rails: List[Rail] = []
    for i in range(3):
        picked = rows[i*limit:(i+1)*limit]
        items = []
        for r in picked:
            card = PlaceCard(
                id=r.id, name=r.name, summary=r.summary or "", tags_csv=r.tags_csv or "",
                category=r.category or "", lat=r.lat, lng=r.lng, address=None,
                picture_url=r.picture_url, rating=r.rating, website=None, phone=None,
                price_level=None, distance_m=None, walk_time_min=None,
                search_score=0.0, vibe_score=0.0, novelty_score=float((r.signals or {}).get("novelty_score", 0.0) or 0.0),
            )
            card = _annotate_card_with_signals(card, r)
            items.append(card)
        rails.append(Rail(step=f"suggested_{i+1}", label="Suggested", items=items))
    return ComposeResponse(rails=rails, processing_time_ms=0.0, cache_hit=False)


async def _compose_vibe_rails(vibe: str, energy: str, area: Optional[str], 
                             user_lat: Optional[float], user_lng: Optional[float], 
                             quality_only: bool, db: Session) -> ComposeResponse:
    """
    Compose vibe-based rails using vibe_packs configuration.
    Returns 3 rails: Core, Signature, Curveball.
    """
    import yaml
    import os
    from apps.places.services.search import create_search_service
    from apps.places.services.ranking_service import create_ranking_service
    from apps.places.schemas.vibes import VibesOntology
    
    # Load vibe configuration
    config_path = os.path.join(os.getcwd(), "config", "vibes.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    vibe_packs = config.get("vibe_packs", {})
    energy_map = config.get("energy_map", {})
    
    if vibe not in vibe_packs:
        raise HTTPException(status_code=400, detail=f"Unknown vibe: {vibe}")
    
    if energy not in energy_map:
        raise HTTPException(status_code=400, detail=f"Unknown energy: {energy}")
    
    pack = vibe_packs[vibe]
    energy_config = energy_map[energy]
    noise_max = energy_config.get("noise_max", 0.5)
    
    # Get services
    search_service = create_search_service(db)
    ontology = VibesOntology.model_validate(config)
    from apps.places.services.bitset_service import BitsetService
    bitset_service = BitsetService(ontology)
    ranking_service = create_ranking_service(bitset_service, search_service)
    
    # Build search queries for each rail
    must_any_tags = pack.get("must_any", [])
    prefer_tags = pack.get("prefer", [])
    avoid_tags = pack.get("avoid", [])
    curveball_tags = pack.get("curveball", [])
    
    # Create search queries
    core_query = " OR ".join(must_any_tags) if must_any_tags else ""
    signature_query = " OR ".join(must_any_tags + prefer_tags) if (must_any_tags + prefer_tags) else ""
    curveball_query = " OR ".join(curveball_tags) if curveball_tags else ""
    
    rails = []
    used_ids = set()
    
    # Rail 1: Core (must_any + proximity)
    if core_query:
        core_candidates = search_service.search_places(
            query=core_query,
            limit=50,
            offset=0,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=2000,  # 2km radius
            sort="relevance",
            area=area
        )
        
        # Apply noise filter
        core_candidates = _apply_noise_filter(core_candidates, noise_max)
        
        # Rank and select top 12
        core_ranked = ranking_service._stage1_base_ranking(
            core_candidates, [vibe], [], [], None
        )
        # Apply vibe alignment
        core_ranked = ranking_service._apply_vibe_alignment(core_ranked, pack)
        core_ranked = ranking_service._stage2_proximity_sorting(
            core_ranked, type('Request', (), {
                'user_lat': user_lat, 'user_lng': user_lng, 'area': area
            })()
        )
        
        # Select top 12, avoiding used IDs
        core_items = []
        for place, scores in core_ranked:
            if place.get("id") not in used_ids and len(core_items) < 12:
                used_ids.add(place.get("id"))
                card = _create_place_card(place, scores, "vibe:core")
                core_items.append(card)
        
        rails.append(Rail(
            step="vibe:core",
            label="Core picks near you",
            items=core_items
        ))
    
    # Rail 2: Signature (prefer + signals)
    if signature_query:
        sig_candidates = search_service.search_places(
            query=signature_query,
            limit=50,
            offset=0,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=5000,  # 5km radius
            sort="relevance",
            area=area
        )
        
        # Apply noise filter
        sig_candidates = _apply_noise_filter(sig_candidates, noise_max)
        
        # Rank and select top 12
        sig_ranked = ranking_service._stage1_base_ranking(
            sig_candidates, [vibe], [], [], None
        )
        # Apply vibe alignment
        sig_ranked = ranking_service._apply_vibe_alignment(sig_ranked, pack)
        sig_ranked = ranking_service._stage2_proximity_sorting(
            sig_ranked, type('Request', (), {
                'user_lat': user_lat, 'user_lng': user_lng, 'area': area
            })()
        )
        
        # Select top 12, avoiding used IDs
        sig_items = []
        for place, scores in sig_ranked:
            if place.get("id") not in used_ids and len(sig_items) < 12:
                used_ids.add(place.get("id"))
                card = _create_place_card(place, scores, "vibe:signature")
                card.reason = _build_reason(place, "signature")
                sig_items.append(card)
        
        rails.append(Rail(
            step="vibe:signature",
            label="Signature & quality",
            items=sig_items
        ))
    
    # Rail 3: Curveball (curveball_tags + diversity)
    if curveball_query:
        cb_candidates = search_service.search_places(
            query=curveball_query,
            limit=50,
            offset=0,
            user_lat=user_lat,
            user_lng=user_lng,
            radius_m=10000,  # 10km radius
            sort="relevance",
            area=area
        )
        
        # Apply noise filter
        cb_candidates = _apply_noise_filter(cb_candidates, noise_max)
        
        # Rank and select top 12
        cb_ranked = ranking_service._stage1_base_ranking(
            cb_candidates, [vibe], [], [], None
        )
        # Apply vibe alignment
        cb_ranked = ranking_service._apply_vibe_alignment(cb_ranked, pack)
        cb_ranked = ranking_service._stage2_proximity_sorting(
            cb_ranked, type('Request', (), {
                'user_lat': user_lat, 'user_lng': user_lng, 'area': area
            })()
        )
        
        # Select top 12, avoiding used IDs
        cb_items = []
        for place, scores in cb_ranked:
            if place.get("id") not in used_ids and len(cb_items) < 12:
                used_ids.add(place.get("id"))
                card = _create_place_card(place, scores, "vibe:curveball")
                card.reason = _build_reason(place, "curveball")
                cb_items.append(card)
        
        rails.append(Rail(
            step="vibe:curveball",
            label="Curveballs to explore",
            items=cb_items
        ))
    
        return ComposeResponse(
            rails=rails,
            processing_time_ms=0.0,
            cache_hit=False
        )


async def _compose_slotter_rails(q: str, area: Optional[str],
                                user_lat: Optional[float], user_lng: Optional[float],
                                quality_only: bool, db: Session) -> ComposeResponse:
    """
    Compose slotter-based rails using free-text query.
    Returns 3 rails based on extracted slots.
    """
    from apps.places.services.search import create_search_service
    from apps.places.services.ranking_service import create_ranking_service
    from apps.places.services.bitset_service import create_bitset_service
    from apps.places.schemas.vibes import VibesOntology
    import yaml
    import os
    
    def _str_low(x):
        try:
            return (x or "").lower()
        except Exception:
            return ""
    
    def _has_any(text: str, needles: list[str]) -> bool:
        t = _str_low(text)
        return any(n in t for n in needles)
    
    def _dish_phrase_candidates(canonical: str) -> list[str]:
        # tom_yum -> ["tom yum", "tom-yum"]
        if not canonical:
            return []
        s = canonical.replace('_', ' ').strip()
        parts = [s]
        if ' ' in s:
            parts.append(s.replace(' ', '-'))
        return parts
    
    def _slottype_adjust_scores(slot, ranked: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
        out = []
        for place, scores in ranked:
            name = _str_low(place.get('name'))
            summary = _str_low(place.get('summary'))
            tags = _str_low(place.get('tags_csv'))
            boost = 0.0
            penalty = 0.0
            if slot.type.value == 'dish':
                # strong dish phrase boost
                phrases = _dish_phrase_candidates(slot.canonical)
                if any(_has_any(name, [p]) or _has_any(summary, [p]) for p in phrases):
                    boost += 0.35
                # dish tag/cuisine bridge boost
                if f"dish:{slot.canonical}" in tags:
                    boost += 0.30
                if "cuisine:thai" in tags and any(p in summary for p in phrases):
                    boost += 0.20
                # pizza-only penalty when looking for tom_yum
                if slot.canonical == 'tom_yum' and 'pizza' in name:
                    penalty += 0.45
            elif slot.type.value == 'vibe':
                # chill soft signals
                if slot.canonical == 'chill':
                    if _has_any(tags, ['quiet','tea_room','specialty_coffee','cozy','lighting:dim']):
                        boost += 0.25
                    if _has_any(tags, ['rooftop','club','edm','party','live_music','loud']):
                        penalty += 0.30
            elif slot.type.value == 'experience':
                if slot.canonical == 'rooftop':
                    if _has_any(name+summary+tags, ['rooftop','sky bar','view:skyline','feature:rooftop']):
                        boost += 0.25
            scores['base_score'] = scores.get('base_score', 0.0) + boost - penalty
            out.append((place, scores))
        # keep order roughly by new base_score
        out.sort(key=lambda x: x[1].get('base_score', 0.0), reverse=True)
        return out
    
    def _enforce_top3_constraints(slot, ranked: list[tuple[dict, dict]]) -> list[tuple[dict, dict]]:
        # Hard rules for top-3
        top = []
        tail = []
        for i, (place, scores) in enumerate(ranked):
            if len(top) < 3:
                name = _str_low(place.get('name'))
                summary = _str_low(place.get('summary'))
                tags = _str_low(place.get('tags_csv'))
                ok = True
                if slot.type.value == 'vibe' and slot.canonical == 'chill':
                    if _has_any(tags, ['rooftop','club','edm','party','live_music','loud']):
                        ok = False
                if slot.type.value == 'dish' and slot.canonical == 'tom_yum':
                    phrases = _dish_phrase_candidates('tom_yum')
                    has_strong = any(p in name or p in summary for p in phrases) or ('dish:tom_yum' in tags)
                    if not has_strong:
                        ok = False
                    # exclude obvious pizza-only in top-3
                    if 'pizza' in name and not has_strong:
                        ok = False
                (top if ok else tail).append((place, scores))
            else:
                tail.append((place, scores))
        return top + tail
    
    start_time = time.time()
    
    try:
        # Load vibe configuration
        config_path = os.path.join(os.getcwd(), "config", "vibes.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        ontology = VibesOntology.model_validate(config)
        
        # Get services
        search_service = create_search_service(db)
        bitset_service = create_bitset_service(ontology)
        ranking_service = create_ranking_service(bitset_service, search_service)
        query_builder = _get_query_builder()
        
        # Extract slots from query
        slotter_result = query_builder.build_slots(q)
        slots = slotter_result.slots
        
        if not slots:
            logger.warning(f"No slots extracted from query: {q}")
            return ComposeResponse(
                rails=[],
                processing_time_ms=(time.time() - start_time) * 1000,
                cache_hit=False
            )
        
        # Create rails from slots
        rails = []
        used_ids = set()
        
        for i, slot in enumerate(slots[:3]):  # Max 3 rails
            # Search by slot
            candidates = search_service.search_by_slot(
                slot=slot,
                limit=120,
                user_lat=user_lat,
                user_lng=user_lng,
                radius_m=8000,
                area=area
            )
            
            if not candidates:
                candidates = search_service.search_by_slots_fallback(
                    limit=120,
                    user_lat=user_lat,
                    user_lng=user_lng,
                    radius_m=12000,
                    area=area
                )
            if not candidates:
                continue
            
            if quality_only:
                candidates = [c for c in candidates if c.get('signals', {}).get('hq_experience', False)]
            
            # Rank candidates
            ranked = ranking_service._stage1_base_ranking(
                candidates, [slot.canonical], [], [], None
            )
            # Slot-type aware adjustments
            ranked = _slottype_adjust_scores(slot, ranked)
            # Enforce hard top-3 rules
            ranked = _enforce_top3_constraints(slot, ranked)
            # Proximity sorting
            ranked = ranking_service._stage2_proximity_sorting(
                ranked, type('Request', (), {
                    'user_lat': user_lat, 'user_lng': user_lng, 'area': area
                })()
            )
            
            # Select top 12, avoiding used IDs
            items = []
            for place, scores in ranked:
                if place.get("id") not in used_ids and len(items) < 12:
                    used_ids.add(place.get("id"))
                    card = PlaceCard(
                        id=place.get("id"),
                        name=place.get("name", ""),
                        summary=place.get("summary", ""),
                        category=place.get("category", ""),
                        tags_csv=place.get("tags_csv", ""),
                        lat=place.get("lat"),
                        lng=place.get("lng"),
                        picture_url=place.get("picture_url"),
                        gmaps_place_id=place.get("gmaps_place_id"),
                        gmaps_url=place.get("gmaps_url"),
                        rating=place.get("rating"),
                        distance_m=place.get("distance_m"),
                        search_score=place.get("search_score", 0.0),
                        signals=place.get("signals"),
                        reason=f"Matched {slot.type}:{slot.canonical}"
                    )
                    items.append(card)
            
            if items:
                # Применяем простую квоту для chill: не более 1 из каждой корзины (если доступны)
                if slot.type.value == "vibe" and slot.canonical == "chill":
                    try:
                        import os, yaml
                        policy_path = os.path.join(os.getcwd(), "config", "rail_policy.yml")
                        buckets = None
                        if os.path.exists(policy_path):
                            cfg = yaml.safe_load(open(policy_path, "r", encoding="utf-8")) or {}
                            rp = ((cfg.get("rail_policy") or {}).get("vibe") or {}).get("chill", {})
                            buckets = rp.get("category_quota", {}) or {}
                        if buckets:
                            picked = []
                            used_bucket = set()
                            def _belongs(card, tags):
                                t = (card.tags_csv or "").lower()
                                n = (card.name or "").lower()
                                return any(tt.lower() in t or tt.lower() in n for tt in (tags or []))
                            # один проход: взять по одному из каждого ведра, затем добор
                            for bname, tags in buckets.items():
                                for card in items:
                                    if card.id in [c.id for c in picked]:
                                        continue
                                    if _belongs(card, tags):
                                        picked.append(card)
                                        used_bucket.add(bname)
                                        break
                            # добрать до 12 любыми оставшимися
                            for card in items:
                                if len(picked) >= 12:
                                    break
                                if card.id in [c.id for c in picked]:
                                    continue
                                picked.append(card)
                            items = picked
                    except Exception:
                        pass
                rail_label = f"{slot.label} spots"
                if slot.type.value == "vibe":
                    rail_label = f"{slot.label} vibes"
                elif slot.type.value == "dish":
                    rail_label = f"{slot.label} food"
                elif slot.type.value == "experience":
                    rail_label = f"{slot.label} experiences"
                elif slot.type.value == "area":
                    rail_label = f"Places in {slot.label}"
                elif slot.type.value == "cuisine":
                    rail_label = f"{slot.label} cuisine"
                elif slot.type.value == "drink":
                    rail_label = f"{slot.label} drinks"
                
                rails.append(Rail(
                    step=f"slot_{i+1}",
                    label=rail_label,
                    items=items
                ))
        
        # Fill remaining rails with fallback if needed
        while len(rails) < 3:
            fallback_candidates = search_service.search_by_slots_fallback(
                limit=120,
                user_lat=user_lat,
                user_lng=user_lng,
                radius_m=15000,
                area=area
            )
            if not fallback_candidates:
                break
            if quality_only:
                fallback_candidates = [c for c in fallback_candidates if c.get('signals', {}).get('hq_experience', False)]
            ranked = ranking_service._stage1_base_ranking(
                fallback_candidates, [], [], [], None
            )
            ranked = ranking_service._stage2_proximity_sorting(
                ranked, type('Request', (), {
                    'user_lat': user_lat, 'user_lng': user_lng, 'area': area
                })()
            )
            items = []
            for place, scores in ranked:
                if place.get("id") not in used_ids and len(items) < 12:
                    used_ids.add(place.get("id"))
                    card = PlaceCard(
                        id=place.get("id"),
                        name=place.get("name", ""),
                        summary=place.get("summary", ""),
                        category=place.get("category", ""),
                        tags_csv=place.get("tags_csv", ""),
                        lat=place.get("lat"),
                        lng=place.get("lng"),
                        picture_url=place.get("picture_url"),
                        gmaps_place_id=place.get("gmaps_place_id"),
                        gmaps_url=place.get("gmaps_url"),
                        rating=place.get("rating"),
                        distance_m=place.get("distance_m"),
                        search_score=place.get("search_score", 0.0),
                        signals=place.get("signals"),
                        reason="Editorial pick"
                    )
                    items.append(card)
            if items:
                rails.append(Rail(
                    step=f"fallback_{len(rails)+1}",
                    label="Editorial picks",
                    items=items
                ))
        
        processing_time = (time.time() - start_time) * 1000
        
        return ComposeResponse(
            rails=rails,
            processing_time_ms=processing_time,
            cache_hit=False
        )
        
    except Exception as e:
        logger.error(f"Failed to compose slotter rails: {e}")
        return ComposeResponse(
            rails=[],
            processing_time_ms=(time.time() - start_time) * 1000,
            cache_hit=False
        )


def _apply_noise_filter(candidates: List[Dict[str, Any]], noise_max: float) -> List[Dict[str, Any]]:
    """Apply noise filter based on signals.noise_level or heuristic fallback."""
    filtered = []
    for place in candidates:
        signals = place.get("signals", {})
        noise_level = signals.get("noise_level")
        
        if noise_level is not None:
            try:
                if float(noise_level) <= noise_max:
                    filtered.append(place)
            except (ValueError, TypeError):
                # Fallback to heuristic
                if _heuristic_noise_level(place) <= noise_max:
                    filtered.append(place)
        else:
            # Use heuristic
            if _heuristic_noise_level(place) <= noise_max:
                filtered.append(place)
    
    return filtered


def _heuristic_noise_level(place: Dict[str, Any]) -> float:
    """Heuristic noise level based on tags."""
    tags = (place.get("tags_csv") or "").lower()
    
    # High noise indicators
    if any(tag in tags for tag in ["club", "edm", "live_music", "party", "loud"]):
        return 0.8
    # Low noise indicators  
    elif any(tag in tags for tag in ["spa", "tea_room", "onsen", "quiet", "library"]):
        return 0.2
    # Default
    else:
        return 0.5


def _create_place_card(place: Dict[str, Any], scores: Dict[str, float], origin: str) -> PlaceCard:
    """Create PlaceCard from place data."""
    return PlaceCard(
        id=place.get("id"),
        name=place.get("name", ""),
        summary=place.get("summary", ""),
        tags_csv=place.get("tags_csv", ""),
        category=place.get("category", ""),
        lat=place.get("lat"),
        lng=place.get("lng"),
        address=place.get("address"),
        picture_url=place.get("picture_url"),
        website=place.get("website"),
        phone=place.get("phone"),
        price_level=place.get("price_level"),
        rating=place.get("rating"),
        distance_m=place.get("distance_m"),
        walk_time_min=place.get("walk_time_min"),
        search_score=scores.get("search_score", 0.0),
        vibe_score=scores.get("vibe_score", 0.0),
        novelty_score=scores.get("novelty_score", 0.0),
        origin=origin,
        reason=""
    )


def _build_reason(place: Dict[str, Any], rail_type: str) -> str:
    """Build reason string for place card."""
    reason_parts = []
    
    if rail_type == "signature":
        signals = place.get("signals", {})
        if signals.get("dateworthy"):
            reason_parts.append("dateworthy")
        if signals.get("vista_view"):
            reason_parts.append("view")
        if signals.get("hq_experience"):
            reason_parts.append("high-quality")
    
    # Add distance if available
    distance_m = place.get("distance_m")
    if distance_m is not None:
        km = max(0.1, distance_m / 1000.0)
        reason_parts.append(f"{km:.1f} km")
    
    return " • ".join(reason_parts[:3]) if reason_parts else "Recommended"
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
