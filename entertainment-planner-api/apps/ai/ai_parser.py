# apps/ai/ai_parser.py
from __future__ import annotations
import re
import unicodedata
import hashlib
import json
import time
from typing import List, Dict, Any, Tuple, Optional
try:
    from rapidfuzz import process, fuzz  # pip install rapidfuzz
    HAVE_FUZZ = True
except Exception:
    import difflib
    HAVE_FUZZ = False

SEPS = [",", ";", " then ", " and then ", " -> ", " → ", " after "]

LEXICON = {
    "intents": {
        "eat": ["eat","food","dinner","lunch","breakfast","brunch","restaurant","thai","tom_yum","tom-yum","tom yam"],
        "drink": ["drink","bar","rooftop","skybar","sky bar","speakeasy","wine","cocktail","beer","craft beer","coffee","cafe","café"],
        "relax": ["relax","spa","massage","onsen","sauna"],
        "walk": ["walk","stroll","park","promenade","riverwalk"]
    },
    "phrases": {
        "tom yum": "tom_yum",
        "first date": "first_date",
        "date with girlfriend": "date",
        "date with boyfriend": "date",
        "sky bar": "rooftop",
        "skybar": "rooftop"
    },
    "typos": {
        "coffe": "coffee",
        "cofee": "coffee",
        "cofeee": "coffee",
        "restaraunt": "restaurant",
        "resturant": "restaurant",
        "cafee": "cafe",
        "café": "cafe",
        "tomyum": "tom_yum",
        "tom-yum": "tom_yum"
    },
    "scenarios": {
        "date": ["date","girlfriend","boyfriend","romantic","couple"],
        "first_date": ["first_date","first-date","firstdate"]
    },
    "vibes": {
        "romantic": ["romantic","intimate","cozy","candle","sunset"],
        "chill": ["chill","laid-back","calm","relaxed","cozy"],
        "lively": ["lively","party","vibe","music","dj"]
    },
    "category_map": {
        "tom_yum": ["thai","restaurant"],
        "rooftop": ["bar","rooftop"],
        "coffee": ["cafe"],
        "cafe": ["cafe"],
        "massage": ["spa"],
        "spa": ["spa"]
    },
    "tag_hints": {
        "rooftop": ["view","sunset","skyline"],
        "coffee": ["specialty","beans","aromatic"],
        "tom_yum": ["spicy","soup","thai"]
    }
}

def fold(s: str) -> str:
    """Normalize text: lowercase, remove diacritics"""
    s = s.lower().strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s

def protect_phrases(text: str) -> str:
    """Protect multi-word phrases from being split"""
    t = " " + fold(text) + " "
    for k, v in LEXICON["phrases"].items():
        kf = " " + fold(k) + " "
        t = t.replace(kf, " " + v + " ")
    return t.strip()

def tokenize(text: str) -> List[str]:
    """Split text into segments, handling separators and normalizing"""
    t = protect_phrases(text)
    # replace separators with comma
    for sep in SEPS:
        t = t.replace(sep, ",")
    # remove garbage characters
    t = re.sub(r"[^\w\s,.-]+", " ", t)
    # normalize spaces/commas
    t = re.sub(r"\s+", " ", t)
    parts = [p.strip() for p in t.split(",") if p.strip()]
    return parts

def fuzzy_fix(token: str, candidates: List[str], score_cutoff=85) -> str:
    """Fix typos using fuzzy matching"""
    if token in candidates: 
        return token
    if HAVE_FUZZ:
        match = process.extractOne(token, candidates, scorer=fuzz.ratio, score_cutoff=score_cutoff)
        return match[0] if match else token
    # fallback: difflib
    close = difflib.get_close_matches(token, candidates, n=1, cutoff=0.85)
    return close[0] if close else token

def classify_segment(seg: str) -> Dict[str, Any]:
    """Classify a segment into intent, categories, tags, etc."""
    raw_terms = re.findall(r"[a-zA-Z0-9_+-]+", seg)
    terms = []
    for t in raw_terms:
        t = LEXICON["typos"].get(t, t)
        terms.append(t)

    # determine intent by highest match count
    intent_scores = {k:0 for k in LEXICON["intents"].keys()}
    must_have, cats, tags, scenarios, vibes = [], [], [], [], []

    # fix typos for keywords
    vocab = sorted(set(sum(LEXICON["intents"].values(), [])))
    terms = [fuzzy_fix(t, vocab) for t in terms]

    for t in terms:
        # intent score
        for intent, words in LEXICON["intents"].items():
            if t in words:
                intent_scores[intent] += 1
        # category hints
        if t in LEXICON["category_map"]:
            for c in LEXICON["category_map"][t]:
                if c not in cats: cats.append(c)
        # must_have
        if t == "tom_yum":
            must_have.append("tom yum")
        # tag hints
        if t in LEXICON["tag_hints"]:
            for tg in LEXICON["tag_hints"][t]:
                if tg not in tags: tags.append(tg)
        # scenario/vibe
        for sc, words in LEXICON["scenarios"].items():
            if t in words:
                if sc not in scenarios: scenarios.append(sc)
        for vb, words in LEXICON["vibes"].items():
            if t in words:
                if vb not in vibes: vibes.append(vb)

    # best intent
    intent = max(intent_scores.items(), key=lambda kv: kv[1])[0] if any(intent_scores.values()) else None

    # fallback intent by categories/keys
    if not intent:
        if any(x in ["bar","rooftop","cafe","coffee"] for x in cats+terms): intent="drink"
        elif any(x in ["thai","restaurant","tom_yum"] for x in cats+terms): intent="eat"
        elif any(x in ["spa","massage","onsen","sauna"] for x in cats+terms): intent="relax"
        elif any(x in ["park","walk","stroll","promenade"] for x in cats+terms): intent="walk"

    return {
        "intent": intent,
        "must_have": must_have,
        "category": cats,
        "tags": tags,
        "scenarios": scenarios,
        "vibes": vibes,
        "raw_terms": terms
    }

def segment_into_steps(q: str) -> List[Dict[str, Any]]:
    """Segment query into ordered steps"""
    segs = tokenize(q)
    steps: List[Dict[str, Any]] = []
    last_major = None

    for seg in segs:
        cls = classify_segment(seg)
        major = cls["intent"] or ("eat" if "restaurant" in cls["category"] else None)

        if not steps:
            steps.append(cls)
            last_major = major
            continue

        # if no explicit separators, split by major category/intent change
        if len(segs) == 1:
            # single section - possibly mixed: split by known keys
            pass
        if major and last_major and major != last_major:
            steps.append(cls)
            last_major = major
        else:
            # same intent - merge terms
            s = steps[-1]
            for k in ["must_have","category","tags","scenarios","vibes","raw_terms"]:
                for v in cls[k]:
                    if v not in s[k]: s[k].append(v)
            if not s["intent"] and cls["intent"]:
                s["intent"] = cls["intent"]

    # if after pass intents < 2 and text has many terms - force split by known markers
    if len(steps) == 1:
        t = " ".join(steps[0]["raw_terms"])
        forced = []
        for key in ("rooftop","bar","coffee","cafe","tom_yum","thai","spa","massage","walk","park"):
            if key in t: forced.append(key)
        
        # Improved splitting logic for mixed queries
        if len(forced) >= 2:
            # Define order of intents
            intent_order = [
                ("rooftop", "drink"),
                ("tom_yum", "eat"), 
                ("coffee", "drink"),
                ("spa", "relax"),
                ("massage", "relax"),
                ("bar", "drink"),
                ("restaurant", "eat"),
                ("park", "walk")
            ]
            
            new_steps = []
            for key, intent in intent_order:
                if key in forced:
                    # Create step for this key
                    step = classify_segment(key.replace("_", " "))
                    step["intent"] = intent
                    new_steps.append(step)
            
            if len(new_steps) >= 2:
                steps = new_steps

    # normalize lengths
    for s in steps:
        if not s["category"]:
            # map intent -> default category
            if s["intent"] == "drink": s["category"] = ["bar"]
            if s["intent"] == "eat": s["category"] = ["restaurant"]
            if s["intent"] == "relax": s["category"] = ["spa"]
            if s["intent"] == "walk": s["category"] = ["park"]

    return steps

def parse(q: str, area: Optional[str]=None) -> Dict[str, Any]:
    """Main parse function"""
    steps = segment_into_steps(q)
    all_terms = sum((s["raw_terms"] for s in steps), [])
    recognized = sum(1 for s in steps for k in (s["intent"],) if k) + len([t for t in all_terms if t in LEXICON["category_map"] or t in LEXICON["phrases"].values()])
    confidence = min(0.95, 0.4 + 0.6 * (recognized / (len(all_terms) + 1)))

    # scenarios/vibes from total segments
    scenarios = sorted({sc for s in steps for sc in s.get("scenarios", [])})
    vibes = sorted({vb for s in steps for vb in s.get("vibes", [])})
    
    # If no scenarios detected but query suggests dating, add default scenarios
    if not scenarios and any(word in q.lower() for word in ["date", "girlfriend", "boyfriend", "romantic", "couple"]):
        scenarios = ["date"]
        vibes = ["romantic"]
    
    # If no vibes detected but query suggests romantic, add default vibes
    if not vibes and any(word in q.lower() for word in ["romantic", "intimate", "cozy", "candle", "sunset"]):
        vibes = ["romantic"]
    
    # If no valid steps but we have scenarios, create default steps based on scenario
    valid_steps = [s for s in steps if s.get('intent')]
    if not valid_steps and scenarios:
        if "date" in scenarios or "first_date" in scenarios:
            # Create default date steps: eat -> walk/relax -> drink
            steps = [
                {
                    "intent": "eat",
                    "must_have": [],
                    "category": ["restaurant"],
                    "tags": ["romantic", "intimate", "cozy"],
                    "scenarios": scenarios,
                    "vibes": vibes,
                    "raw_terms": ["date", "dinner"]
                },
                {
                    "intent": "walk",
                    "must_have": [],
                    "category": ["park"],
                    "tags": ["romantic", "peaceful", "scenic"],
                    "scenarios": scenarios,
                    "vibes": vibes,
                    "raw_terms": ["walk", "stroll"]
                },
                {
                    "intent": "drink",
                    "must_have": [],
                    "category": ["bar"],
                    "tags": ["romantic", "intimate", "cozy"],
                    "scenarios": scenarios,
                    "vibes": vibes,
                    "raw_terms": ["drink", "cocktail"]
                }
            ]
        elif "business" in scenarios:
            # Create default business steps: eat -> drink
            steps = [
                {
                    "intent": "eat",
                    "must_have": [],
                    "category": ["restaurant"],
                    "tags": ["professional", "formal", "quiet"],
                    "scenarios": scenarios,
                    "vibes": vibes,
                    "raw_terms": ["business", "meeting"]
                },
                {
                    "intent": "drink",
                    "must_have": [],
                    "category": ["bar"],
                    "tags": ["professional", "quiet", "formal"],
                    "scenarios": scenarios,
                    "vibes": vibes,
                    "raw_terms": ["drink", "business"]
                }
            ]
        elif "family" in scenarios:
            # Create default family steps: eat -> walk
            steps = [
                {
                    "intent": "eat",
                    "must_have": [],
                    "category": ["restaurant"],
                    "tags": ["family", "friendly", "casual"],
                    "scenarios": scenarios,
                    "vibes": vibes,
                    "raw_terms": ["family", "dinner"]
                },
                {
                    "intent": "walk",
                    "must_have": [],
                    "category": ["park"],
                    "tags": ["family", "outdoor", "fun"],
                    "scenarios": scenarios,
                    "vibes": vibes,
                    "raw_terms": ["walk", "family"]
                }
            ]
    
    novelty_preference = 0.6 if ("interesting" in all_terms or "new" in all_terms or "surprise" in all_terms) else 0.3
    
    return {
        "steps": [{"intent":s["intent"],"must_have":s["must_have"],"category":s["category"],"tags":s["tags"][:6],"scenarios":s.get("scenarios",[]),"vibes":s.get("vibes",[])} for s in steps if s["intent"]],
        "filters": {"area": area or "", "radius_m": 1500, "open_now": False, "budget": "", "time_of_day": ""},
        "vibes": vibes,
        "scenarios": scenarios,
        "novelty_preference": novelty_preference,
        "confidence": round(confidence, 2)
    }
