const API_BASE = `${window.location.origin}/api`;

/* ---------- State ---------- */
const GOOGLE_MAPS_MAX_WAYPOINTS = 23; // лимит waypoints в ссылках Google Maps

const state = {
  steps: [],             // [{label, query, results:[], selected:null}]
  // Default home location (Bangkok). Can be overridden by Home button or geolocation
  user: { lat:13.744262, lng:100.561473 },
  anchor: null,          // {id, lat, lng, name, stepIndex} — последняя выбранная карточка
  searchMode: 'surprise',  // 'surprise' mode by default
  highExperienceFilter: false,  // фильтр высокого качества
  selectedArea: null,     // selected area name (deprecated)
  selectedPlaces: [],    // массив выбранных мест для маршрута
  googleMap: null,       // экземпляр Google Maps
  googleMapsLoaded: false, // флаг загрузки Google Maps API
  mapMarkers: [],        // массив маркеров на карте
  directionsService: null, // Google DirectionsService
  directionsRenderer: null, // Google DirectionsRenderer
  selectedVibe: null,    // выбранный vibe
  selectedEnergy: null,  // выбранный energy
  vibeCaption: null,     // подпись для vibe результатов
  vibeEmptyState: false  // флаг empty state для vibe
};

// Сохраняем позиции скролла для каждого ряда
const scrollPositions = {};

function saveScrollPositions() {
  const rails = document.querySelectorAll('.rail__scroll');
  rails.forEach((rail, index) => {
    scrollPositions[index] = rail.scrollLeft;
  });
}

function restoreScrollPositions() {
  const rails = document.querySelectorAll('.rail__scroll');
  rails.forEach((rail, index) => {
    if (scrollPositions[index] !== undefined) {
      rail.scrollLeft = scrollPositions[index];
    }
  });
}

/* ---------- Utils ---------- */
const $ = (s,ctx=document)=>ctx.querySelector(s);
const $all = (s,ctx=document)=>[...ctx.querySelectorAll(s)];
const haversineM = (a,b)=>{
  if(!a||!b) return null;
  const R = 6371000;
  const toRad = x => x*Math.PI/180;
  const dLat = toRad(b.lat-a.lat), dLng = toRad(b.lng-a.lng);
  const s1 = Math.sin(dLat/2)**2 + Math.cos(toRad(a.lat))*Math.cos(toRad(b.lat))*Math.sin(dLng/2)**2;
  return 2*R*Math.asin(Math.sqrt(s1));
};
const formatDistance = m => {
  if (m == null) return "—";
  if (m < 1000) return `${Math.round(m)}m`;
  return `${(m/1000).toFixed(1)}km`;
};

// Функция для сортировки мест по близости
function sortPlacesByDistance(places, referencePoint) {
  if (!referencePoint) return places;
  
  return places.map(place => ({
    ...place,
    distance: haversineM(referencePoint, { lat: place.lat, lng: place.lng })
  })).sort((a, b) => (a.distance || Infinity) - (b.distance || Infinity));
}

// Функция для получения средней точки между двумя местами
function getMidpoint(place1, place2) {
  if (!place1 || !place2) return null;
  return {
    lat: (place1.lat + place2.lat) / 2,
    lng: (place1.lng + place2.lng) / 2
  };
}

// Функция для получения референсной точки для категории
function getReferencePointForCategory(stepIndex) {
  console.log(`Getting reference point for step ${stepIndex}:`);
  console.log(`Anchor:`, state.anchor);
  console.log(`User location:`, state.user);
  
  // Если есть якорь и это не его категория → использовать якорь
  if (state.anchor && state.anchor.stepIndex !== stepIndex) {
    const result = { lat: state.anchor.lat, lng: state.anchor.lng };
    console.log(`Using anchor:`, result);
    return result;
  }
  
  // Если нет якоря → использовать геолокацию пользователя
  if (state.user.lat && state.user.lng) {
    const result = { lat: state.user.lat, lng: state.user.lng };
    console.log(`Using user location:`, result);
    return result;
  }
  
  // Fallback: если нет геолокации, используем первое место в текущей категории
  const currentStep = state.steps[stepIndex];
  if (currentStep && currentStep.results && currentStep.results.length > 0) {
    const firstPlace = currentStep.results[0];
    if (firstPlace.lat && firstPlace.lng) {
      const result = { lat: firstPlace.lat, lng: firstPlace.lng };
      console.log(`Fallback to first place:`, result);
      return result;
    }
  }
  
  console.log(`No reference point available`);
  return null;
}

/* ---------- Frontend Filtering ---------- */
function filterPlacesByQuery(places, query) {
  if (!query || !query.trim()) return places;
  
  const searchTerms = query.toLowerCase().split(/\s+/).filter(term => term.length > 0);
  if (searchTerms.length === 0) return places;
  
  return places.filter(place => {
    const searchableText = [
      place.name || '',
      place.summary || '',
      place.tags_csv || '',
      place.category || ''
    ].join(' ').toLowerCase();
    
    // Все поисковые термины должны присутствовать в тексте
    return searchTerms.every(term => searchableText.includes(term));
  }).sort((a, b) => {
    // Сортировка по релевантности (количество совпадений)
    const scoreA = getRelevanceScore(a, searchTerms);
    const scoreB = getRelevanceScore(b, searchTerms);
    return scoreB - scoreA;
  });
}

function getRelevanceScore(place, searchTerms) {
  const searchableText = [
    place.name || '',
    place.summary || '',
    place.tags_csv || '',
    place.category || ''
  ].join(' ').toLowerCase();
  
  let score = 0;
  searchTerms.forEach(term => {
    // Название имеет больший вес
    if (place.name && place.name.toLowerCase().includes(term)) score += 3;
    // Категория имеет средний вес
    if (place.category && place.category.toLowerCase().includes(term)) score += 2;
    // Теги имеют средний вес
    if (place.tags_csv && place.tags_csv.toLowerCase().includes(term)) score += 2;
    // Описание имеет меньший вес
    if (place.summary && place.summary.toLowerCase().includes(term)) score += 1;
  });
  
  return score;
}

/* ---------- API ---------- */
async function searchPlaces(q, limit=12, area=null){
  // Для индивидуальных step'ов используем обычный поиск
  // Netflix-style API предназначен для полного compose pipeline
  return searchPlacesByQuery(q, limit, area);
}

async function searchPlacesNetflixStyle(q, limit=12, area=null){
  try {
    console.log('🌐 Netflix-style search for:', q);
    
    // Сначала парсим запрос
    const parseResponse = await fetch(`${API_BASE}/parse`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: q,
        area: area,
        user_lat: state.user.lat,
        user_lng: state.user.lng
      })
    });
    
    if (!parseResponse.ok) {
      throw new Error("Parse failed");
    }
    
    const parseResult = await parseResponse.json();
    console.log('📝 Parse result:', parseResult);

    // Затем получаем compose результат (продовый путь)
    const composeBody = {
      parse_result: parseResult,
      area: area,
      user_lat: state.user.lat,
      user_lng: state.user.lng,
      session_id: null,
      mode: state.searchMode === 'surprise' ? 'surprise' : 'vibe',
      query: q
    };
    const composeResponse = await fetch(`${API_BASE}/compose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(composeBody)
    });

    if (!composeResponse.ok) {
      throw new Error("Compose failed");
    }

    const composeResult = await composeResponse.json();
    console.log('🎯 Compose result:', composeResult);

    // Преобразуем rails в формат, ожидаемый фронтендом
    const allPlaces = [];
    (composeResult.rails || []).forEach(rail => {
      console.log(`📦 Rail ${rail.step}: ${rail.items.length} items`);
      rail.items.forEach(place => {
        allPlaces.push({
          ...place,
          step: rail.step,
          stepLabel: rail.label
        });
      });
    });
    
    console.log('🏆 Total places found:', allPlaces.length);
    return allPlaces.slice(0, limit);
    
  } catch (error) {
    console.error('Netflix-style search failed:', error);
    // Fallback к старому API
    return searchPlacesByQuery(q, limit, area);
  }
}

async function searchPlacesByQuery(q, limit=12, area=null){
  const p = new URLSearchParams({ 
    q: q, 
    limit: String(limit) 
  });
  
  // В режиме Area НЕ передаем геолокацию для фильтрации
  // Геолокация будет использоваться только для расчета расстояний на фронтенде
  if(state.user.lat && state.user.lng && !area) {
    p.set('lat', state.user.lat);
    p.set('lng', state.user.lng);
  }
  
  if(area) {
    p.set('area', area);
  }
  
  const res = await fetch(`${API_BASE}/places/search?${p.toString()}`);
  if(!res.ok) throw new Error("search failed");
  const data = await res.json();
  
  // Дедупликация результатов по ID и названию
  const results = data.results || [];
  const seen = new Set();
  const uniqueResults = [];
  
  for(const place of results) {
    const key = place.id ? `id_${place.id}` : `name_${place.name.toLowerCase().trim()}`;
    if(!seen.has(key)) {
      seen.add(key);
      uniqueResults.push(place);
    }
  }
  
  return uniqueResults;
}
async function buildRouteApi(stepIds){
  // опционально – можешь связать со своим /api/routes позже
  return { route: { steps: [] }, ok:true };
}

/* ---------- Search Reset ---------- */
function resetSearch() {
  console.log('Resetting search results...');
  state.steps = [];
  state.anchor = null;
  renderRails(); // Показываем пустое состояние
  renderSelectedBar();
}

/* ---------- Mode Management ---------- */
function initModeControls() {
  const highExpBtn = $("#highExpBtn");
  const surpriseBtn = $("#surpriseBtn");
  const driftBtn = $("#driftBtn");

  // High Experience теперь работает как фильтр после поиска
  highExpBtn.onclick = () => {
    state.highExperienceFilter = !state.highExperienceFilter;
    
    if (state.highExperienceFilter) {
    highExpBtn.classList.add('control-btn--active');
    } else {
      highExpBtn.classList.remove('control-btn--active');
    }
    
    // Применяем фильтр к текущим результатам и перерисовываем
    applyHighExperienceFilter();
    renderRails();
  };

  vibeBtn.onclick = () => {
    // Vibe button открывает drawer для выбора vibe и energy
    showVibeDrawer();
  };

  // Кнопка Drift - работает только с выбранными местами
  if (driftBtn) {
    driftBtn.onclick = () => {
      if (state.selectedPlaces.length === 0) {
        alert('Please select at least one place by clicking + button');
        return;
      }

      console.log(`🗺️ Drift: Building route for ${state.selectedPlaces.length} selected places`);

      const mapsUrl = buildGoogleMapsRouteUrl();
      if (!mapsUrl) {
        alert('Selected places need valid coordinates to open Google Maps route.');
        return;
      }

      const popup = window.open(mapsUrl, '_blank', 'noopener');
      if (!popup || popup.closed) {
        console.warn('Не удалось открыть Google Maps во всплывающем окне.');
        alert('Allow pop-ups for this site to open the route in Google Maps.');
        return;
      }
      popup.focus();
    };
  }
  
  // Инициализируем vibe drawer
  initVibeDrawer();
}

/* ---------- High Experience Filter ---------- */
function isHighExperiencePlace(place) {
  // Если есть флаг hq_experience от сервера - используем его
  const signals = place.signals || {};
  if (signals.hq_experience !== undefined) {
    return Boolean(signals.hq_experience);
  }
  
  // Иначе применяем ту же логику что и в _compute_hq_flag
  const qualityScore = parseFloat(signals.quality_score || 0);
  if (qualityScore >= 0.6) return true; // Снижен порог с 0.65 до 0.6
  
  if (signals.editor_pick) return true;
  
  if (signals.local_gem && (signals.dateworthy || signals.vista_view)) return true;
  
  // Расширенные текстовые триггеры для High Experience
  const qualityTriggers = {
    michelin: ["michelin", "bib gourmand", "one star", "1 star", "starred"],
    specialty_coffee: ["specialty coffee", "manual brew", "pour-over", "roastery", "flagship roaster"],
    chef_table: ["omakase", "chef's table", "tasting menu"],
    curated_gallery: ["curated program", "gallery program"],
    
    // Новые категории для лучшего покрытия
    premium_cocktails: ["craft cocktails", "mixology", "signature cocktails", "artisan cocktails", "award-winning bar", "premium spirits", "craft bar", "cocktail lounge"],
    luxury_spa: ["luxury spa", "premium treatments", "award-winning spa", "signature treatments", "world-class spa", "spa resort", "wellness retreat"],
    premium_rooftop: ["panoramic view", "skyline view", "infinity pool", "rooftop infinity", "stunning views", "breathtaking view", "city views", "rooftop terrace"],
    fine_dining: ["fine dining", "chef's selection", "molecular gastronomy", "farm-to-table", "tasting menu", "degustation"],
    luxury_experience: ["luxury", "premium", "exclusive", "boutique", "world-class", "award-winning", "5-star", "upscale"]
  };
  
  const texts = [
    place.name || '',
    place.summary || '',
    place.tags_csv || ''
  ];
  
  if (signals.hooks) texts.push(...signals.hooks);
  if (signals.evidence) texts.push(...signals.evidence);
  
  const searchableText = texts.join(' ').toLowerCase();
  
  for (const [category, needles] of Object.entries(qualityTriggers)) {
    for (const needle of needles) {
      if (searchableText.includes(needle.toLowerCase())) {
        return true;
      }
    }
  }
  
  return false;
}

function applyHighExperienceFilter() {
  if (!state.steps.length) return;
  
  let totalPlaces = 0;
  let hqPlaces = 0;
  
  // Применяем фильтр ко всем step результатам
  state.steps.forEach(step => {
    if (step.results && step.results.length > 0) {
      totalPlaces += step.results.length;
      
      if (state.highExperienceFilter) {
        // Фильтруем только high experience места
        step.filteredResults = step.results.filter(place => {
          const isHQ = isHighExperiencePlace(place);
          if (isHQ) hqPlaces++;
          return isHQ;
        });
      } else {
        // Показываем все результаты
        step.filteredResults = step.results;
        // Подсчитываем HQ места для статистики
        step.results.forEach(place => {
          if (isHighExperiencePlace(place)) hqPlaces++;
        });
      }
    }
  });
  
  // Выводим статистику в консоль
  console.log(`🏆 High Experience Filter Stats:`);
  console.log(`Total places: ${totalPlaces}`);
  console.log(`High Experience places: ${hqPlaces}`);
  console.log(`HQ percentage: ${totalPlaces > 0 ? (hqPlaces/totalPlaces*100).toFixed(1) : 0}%`);
  console.log(`Filter active: ${state.highExperienceFilter}`);
  
  // Не вызываем renderRails() здесь - пусть вызывающая функция это делает
}

/* ---------- Parse query into ordered steps ---------- */
async function parseSteps(input){
  try {
    // Используем API парсер для правильного разбора запроса
    const parseResponse = await fetch(`${API_BASE}/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: input,
        area: state.selectedArea,
        user_lat: state.user.lat,
        user_lng: state.user.lng
      })
    });
    
    if (!parseResponse.ok) {
      throw new Error("Parse failed");
    }
    
    const parseResult = await parseResponse.json();
    
    // Преобразуем результат парсера в формат steps
    return parseResult.steps.map(step => ({
      label: getStepLabel(step.intent),
      query: step.query,
      results: undefined,
      selected: null,
      intent: step.intent
    }));
    
  } catch (error) {
    console.error('Parse failed, falling back to simple split:', error);
    // Fallback к простому разбиению по запятым
    return input.split(",")
      .map(s=>s.trim())
      .filter(Boolean)
      .map((q,i)=>({ label:q, query:q, results:undefined, selected:null }));
  }
}

function getStepLabel(intent) {
  const labels = {
    'restaurant': 'Restaurants',
    'drinks': 'Bars & Nightlife', 
    'activity': 'Activities',
    'wellness': 'Wellness & Spa',
    'culture': 'Culture & Arts',
    'shopping': 'Shopping',
    'general': 'Places'
  };
  return labels[intent] || intent.charAt(0).toUpperCase() + intent.slice(1);
}

/* ---------- Render ---------- */
function renderSelectedBar(){
  const wrap = $("#selectedChips");
  const selectedBar = $("#selectedBar");
  wrap.innerHTML = "";
  
  const hasSelections = state.steps.some(st => st.selected);
  
  if (hasSelections) {
    selectedBar.style.display = "flex";
    state.steps.forEach((st,idx)=>{
      if (st.selected) {
        const chip = document.createElement("button");
        chip.className="chip";
        chip.textContent = `${idx+1}. ${st.selected.name}`;
        chip.title = "Unselect";
        chip.onclick = ()=>{
          st.selected = null;
          if (state.anchor && state.anchor.stepIndex === idx) state.anchor = null;
          updateAllDistances();
          renderSelectedBar();
        };
        wrap.appendChild(chip);
      }
    });
  } else {
    selectedBar.style.display = "none";
  }
}

function renderRails(){
  // Сохраняем позиции скролла перед перерисовкой
  saveScrollPositions();
  
  const container = $("#rails");
  container.innerHTML = "";
  
  // Добавляем vibe caption если есть
  if (state.vibeCaption) {
    const caption = document.createElement('div');
    caption.className = 'vibe-caption';
    caption.innerHTML = `
      <div class="vibe-caption__content">
        <span class="vibe-caption__text">${state.vibeCaption}</span>
        ${state.vibeEmptyState ? '<a href="#" class="vibe-caption__link" onclick="showVibeDrawer(); return false;">Try different vibe</a>' : ''}
      </div>
    `;
    container.appendChild(caption);
  }
  
  console.log(`Rendering rails, steps count:`, state.steps.length);
  
  // Показать empty state если нет шагов
  if (!state.steps.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state__icon">🎯</div>
        <h2 class="empty-state__title">Plan your evening</h2>
        <p class="empty-state__description">Enter your plans above to discover amazing places</p>
      </div>
    `;
    return;
  }
  
  const railTpl = $("#railTpl");
  const cardTpl = $("#cardTpl");

  state.steps.forEach((st,stepIndex)=>{
    const displayResults = st.filteredResults || st.results;
    console.log(`Rendering step ${stepIndex}:`, st.label, `results: ${st.results?.length || 0}`, `filtered: ${displayResults?.length || 0}`);
    
    const railNode = railTpl.content.cloneNode(true);
    railNode.querySelector(".rail__title").textContent = st.label;
    railNode.querySelector(".rail__hint").textContent = "Swipe →";

    const content = railNode.querySelector(".rail__content");
    if (st.results === undefined) {
      console.log(`Step ${stepIndex} is loading, showing loading`);
      const empty = document.createElement("div");
      empty.style.cssText="padding:20px;color:#6c757d;text-align:center;width:100%;";
      empty.innerHTML = `
        <div class="loading-placeholder">
          <div class="loading-spinner"></div>
          <p>Searching for ${st.label.toLowerCase()}...</p>
        </div>
      `;
      content.appendChild(empty);
    } else if (Array.isArray(displayResults) && displayResults.length === 0) {
      console.log(`Step ${stepIndex} has empty results, showing no places`);
      const empty = document.createElement("div");
      empty.style.cssText="padding:20px;color:#6c757d;text-align:center;width:100%;";
      empty.innerHTML = `
        <div class="empty-rail">
          <div class="empty-rail__icon">🔍</div>
          <p>No ${st.label.toLowerCase()} found</p>
          <small>Try adjusting your search or location</small>
        </div>
      `;
      content.appendChild(empty);
    } else {
      console.log(`Step ${stepIndex} rendering ${displayResults.length} places`);
      // Места уже отсортированы в recomputeDistancesAndSort()
      displayResults.forEach(place=>{
        const n = cardTpl.content.cloneNode(true);
        const img = n.querySelector(".place-card__img");
        const title = n.querySelector(".place-card__title");
        const badges = n.querySelector(".place-card__badges");
        const summary = n.querySelector(".place-card__summary");
        const why = n.querySelector(".place-card__why");
        const tags = n.querySelector(".place-card__tags");
        const maps = n.querySelector(".place-card__maps");
        const addBtn = n.querySelector(".place-card__add-btn");
        const distEl = n.querySelector("[data-dist]");
        const ratingEl = n.querySelector("[data-rating]");
        const ratingValue = n.querySelector(".rating-value");

        img.src = place.picture_url || "https://picsum.photos/400/300";
        img.alt = place.name || "place";
        title.textContent = place.name;
        
        // Рендеринг badges
        badges.innerHTML = "";
        if (place.badges && place.badges.length > 0) {
          place.badges.slice(0, 2).forEach(badge => { // Показываем максимум 2 badge
            const badgeEl = document.createElement("span");
            badgeEl.className = "badge";
            badgeEl.textContent = badge;
            badges.appendChild(badgeEl);
          });
        }
        
        // Показываем только первое предложение из summary
        const fullSummary = place.summary || "";
        const firstSentence = fullSummary.split('.')[0] + (fullSummary.includes('.') ? '.' : '');
        summary.textContent = firstSentence;
        
        // Рендеринг why (объяснение)
        why.innerHTML = "";
        if (place.why) {
          const whyEl = document.createElement("div");
          whyEl.className = "why-text";
          whyEl.textContent = `💡 ${place.why}`;
          why.appendChild(whyEl);
        }
        
        // Generate Google Maps URL: use name search for best mobile compatibility
        let mapsUrl = "#";
        if (place.name) {
          // Search by name - most reliable across all devices
          const searchQuery = encodeURIComponent(place.name + ' Bangkok');
          mapsUrl = `https://www.google.com/maps/search/?api=1&query=${searchQuery}`;
        } else if (place.gmaps_place_id) {
          // Fallback to Place ID
          mapsUrl = `https://www.google.com/maps/place/?q=place_id:${place.gmaps_place_id}`;
        } else if (place.lat && place.lng) {
          // Last resort - coordinates
          mapsUrl = `https://www.google.com/maps/search/?api=1&query=${place.lat},${place.lng}`;
        }
        maps.href = mapsUrl;
        
        // Показываем компактный рейтинг если есть
        ratingEl.style.display = "flex";
        console.log('Rating raw', place.name, place.rating, typeof place.rating);
        let ratingText = place.rating;
        if (ratingText === undefined || ratingText === null || ratingText === "") {
          ratingText = "—";
        } else {
          let normalized = ratingText;
          if (typeof normalized === "string") {
            normalized = normalized.replace(',', '.').trim();
          }
          const parsed = parseFloat(normalized);
          if (!Number.isNaN(parsed) && Number.isFinite(parsed)) {
            ratingText = parsed.toFixed(1);
          } else {
            ratingText = String(ratingText);
          }
        }
        ratingValue.textContent = ratingText;
        const star = ratingEl.querySelector(".rating-star");
        if (star) {
          star.textContent = "⭐";
        }
        
        // Очистить и добавить теги
        tags.innerHTML = "";
        (place.tags_csv || "").split(",").slice(0,3).map(s=>s.trim()).filter(Boolean)
          .forEach(t=>{ 
            const tag = document.createElement("span"); 
            tag.className = "tag";
            tag.textContent = t; 
            tags.appendChild(tag); 
          });

        // Показываем расстояние согласно новой логике
        console.log(`Rendering place: ${place.name}`);
        console.log(`Place coordinates:`, { lat: place.lat, lng: place.lng });
        console.log(`Step distance label:`, st.distanceLabel);
        
        // Нет координат у карточки → показать —
        if (!place.lat || !place.lng) {
          distEl.textContent = "—";
          return;
        }
        
        // Если это категория якоря - не показываем расстояние
        if (state.anchor && state.anchor.stepIndex === stepIndex) {
          distEl.textContent = "";
          // Не return, продолжаем рендеринг карточки
        }
        
        // Используем предвычисленное расстояние из place.distance
        if (place.distance !== undefined && st.distanceLabel) {
          const finalText = `${formatDistance(place.distance)} ${st.distanceLabel}`;
          console.log(`Final distance text:`, finalText);
          distEl.textContent = finalText;
        } else {
          // Fallback: показываем что-то вместо "—"
          distEl.textContent = "📍 Location needed";
        }

        // состояние кнопки добавления
        const isSelected = state.selectedPlaces.some(p => p.id === place.id);
        addBtn.setAttribute("aria-pressed", isSelected ? "true":"false");
        addBtn.onclick = async ()=>{
          if(isSelected){
            // Удаляем место из выбранных
            state.selectedPlaces = state.selectedPlaces.filter(p => p.id !== place.id);
            console.log(`🗺️ Removed from route: ${place.name}`);
            
            // Снимаем выбор (старая логика)
            st.selected = null;
            console.log(`Deselected: ${place.name} in step ${stepIndex}`);
            
            // Если это был якорь - находим новый якорь из оставшихся выбранных мест
            if (state.anchor && state.anchor.id === place.id) {
              console.log(`Clearing anchor: ${place.name}`);
              let newAnchor = null;
              for (let i = state.steps.length - 1; i >= 0; i--) {
                if (state.steps[i].selected) {
                  newAnchor = {
                    id: state.steps[i].selected.id,
                    lat: state.steps[i].selected.lat,
                    lng: state.steps[i].selected.lng,
                    name: state.steps[i].selected.name,
                    stepIndex: i
                  };
                  break;
                }
              }
              state.anchor = newAnchor;
              console.log(`New anchor:`, state.anchor);
            }
            
            // Обновляем карту или скрываем если нет мест
            if (state.selectedPlaces.length === 0) {
              hideMapContainer();
            } else if (state.googleMap) {
              updateMapWithSelectedPlaces();
            }
            
          } else {
            // Добавляем место в выбранные
            state.selectedPlaces.push(place);
            console.log(`🗺️ Added to route: ${place.name}`);
            
            // Устанавливаем выбор (старая логика)
            st.selected = place;
            
            // Устанавливаем якорь на последний выбранный элемент
            state.anchor = {
              id: place.id,
              lat: place.lat,
              lng: place.lng,
              name: place.name,
              stepIndex: stepIndex
            };
            console.log(`Selected: ${place.name} in step ${stepIndex}`);
            
            // Показываем карту после первого выбора
            if (state.selectedPlaces.length === 1) {
              try {
                console.log('🗺️ Loading Google Maps for first selected place...');
                await loadGoogleMapsAPI();
                showMapContainer();
              } catch (error) {
                console.error('Failed to initialize Google Maps:', error);
              }
            } else if (state.googleMap) {
              // Обновляем карту если уже инициализирована
              updateMapWithSelectedPlaces();
            }
          }
          
          // Пересчитываем расстояния и пересортируем только ряды БЕЗ выбранных мест
          recomputeDistancesAndSortExceptCurrent(stepIndex);
          renderSelectedBar();
          renderRails();
        };

        content.appendChild(n);
      });
    }
    container.appendChild(railNode);
  });
  
  // Восстанавливаем позиции скролла после перерисовки
  setTimeout(() => {
    restoreScrollPositions();
  }, 0);
}

function distanceFromAnchor(place){
  if(!state.anchor || place?.lat==null || place?.lng==null) return null;
  return haversineM(
    {lat:state.anchor.lat,lng:state.anchor.lng},
    {lat:place.lat,lng:place.lng}
  );
}

function distanceFromUser(place){
  if(!state.user.lat || !state.user.lng || place?.lat==null || place?.lng==null) return null;
  return haversineM(
    {lat:state.user.lat,lng:state.user.lng},
    {lat:place.lat,lng:place.lng}
  );
}
function updateAllDistances(){
  // точнее — просто перерисуем rails (дешево при 10–20 карточках/рельс)
  renderRails();
}

// Функция для пересчета расстояний и пересортировки всех категорий
function recomputeDistancesAndSort(){
  console.log(`Recomputing distances and sorting...`);
  console.log(`Current anchor:`, state.anchor);
  console.log(`Steps count:`, state.steps.length);
  
  state.steps.forEach((step, stepIndex) => {
    console.log(`Processing step ${stepIndex}:`, step.label, `results: ${step.results?.length || 0}`);
    
    if (!step.results || step.results.length === 0) {
      console.log(`Step ${stepIndex} has no results, skipping`);
      return;
    }
    
    // Если это категория якоря - не показываем расстояние, но обрабатываем результаты
    if (state.anchor && state.anchor.stepIndex === stepIndex) {
      step.distanceLabel = '';
      console.log(`Step ${stepIndex} is anchor category - no distance, but processing results`);
      // Не return, продолжаем обработку для рендеринга
    }
    
    // Если это категория якоря - не пересчитываем расстояния
    if (state.anchor && state.anchor.stepIndex === stepIndex) {
      console.log(`Step ${stepIndex} is anchor category - keeping original order`);
      // Оставляем результаты как есть, только очищаем расстояния
      step.results.forEach(place => {
        place.distance = undefined;
      });
    } else {
      const referencePoint = getReferencePointForCategory(stepIndex);
      
      if (referencePoint) {
        // Пересчитать расстояния для всех мест в категории
        step.results.forEach(place => {
          place.distance = haversineM(referencePoint, { lat: place.lat, lng: place.lng });
        });
        
        // Пересортировать по расстоянию (ближайшие первыми)
        step.results.sort((a, b) => (a.distance || 0) - (b.distance || 0));
        
        // Обновить подпись расстояния
        if (state.anchor) {
          step.distanceLabel = `from ${state.anchor.name}`;
        } else {
          step.distanceLabel = 'from you';
        }
        
        console.log(`Step ${stepIndex} sorted by distance, label: ${step.distanceLabel}`);
      } else {
        // Нет референсной точки - сортировка по релевантности
        step.results.sort((a, b) => (b.rank || 0) - (a.rank || 0));
        step.distanceLabel = '';
        console.log(`Step ${stepIndex} sorted by relevance, no distance label`);
      }
    }
  });
}

// Функция для пересчета расстояний и пересортировки только рядов БЕЗ выбранных мест
function recomputeDistancesAndSortExceptCurrent(currentStepIndex){
  console.log(`Recomputing distances and sorting except rows with selected places`);
  console.log(`Current anchor:`, state.anchor);
  console.log(`Steps count:`, state.steps.length);
  
  state.steps.forEach((step, stepIndex) => {
    // Пропускаем ряды с выбранными местами (включая текущий)
    if (step.selected) {
      console.log(`Skipping step ${stepIndex} (has selected place):`, step.label);
      return;
    }
    
    console.log(`Processing step ${stepIndex}:`, step.label, `results: ${step.results?.length || 0}`);
    
    if (!step.results || step.results.length === 0) {
      console.log(`Step ${stepIndex} has no results, skipping`);
      return;
    }
    
    const referencePoint = getReferencePointForCategory(stepIndex);
    
    if (referencePoint) {
      // Пересчитать расстояния для всех мест в категории
      step.results.forEach(place => {
        place.distance = haversineM(referencePoint, { lat: place.lat, lng: place.lng });
      });
      
      // Пересортировать по расстоянию (ближайшие первыми)
      step.results.sort((a, b) => (a.distance || 0) - (b.distance || 0));
      
      // Обновить подпись расстояния
      if (state.anchor) {
        step.distanceLabel = `from ${state.anchor.name}`;
      } else {
        step.distanceLabel = 'from you';
      }
      
      console.log(`Step ${stepIndex} sorted by distance, label: ${step.distanceLabel}`);
    } else {
      // Нет референсной точки - сортировка по релевантности
      step.results.sort((a, b) => (b.rank || 0) - (a.rank || 0));
      step.distanceLabel = '';
      console.log(`Step ${stepIndex} sorted by relevance, no distance label`);
    }
  });
}

// Функция для пересортировки всех категорий после выбора (legacy)
function resortAllCategories(){
  recomputeDistancesAndSort();
}

/* ---------- Actions ---------- */
let searchTimeout = null;

async function applyQuery(){
  const input = $("#queryInput").value.trim();
  
  // Очищаем предыдущий таймаут
  if (searchTimeout) {
    clearTimeout(searchTimeout);
  }
  
  // Если нет запроса, показываем пустое состояние
  if (!input) {
    searchTimeout = setTimeout(() => {
      resetSearch();
    }, 300);
    return;
  }
  
  // Устанавливаем новый таймаут для живого поиска
  searchTimeout = setTimeout(async () => {
    await performSearch(input);
  }, 300); // 300ms задержка для живого поиска
}

async function showSurpriseRails() {
  console.log(`🎲 Showing surprise rails`);
  
  // Получаем surprise rails
  const places = await getRailsForMode('surprise');
  
  if (places.length === 0) {
    state.steps = [];
    renderRails();
    return;
  }
  
  // Группируем места по категориям для отображения в рядах
  const railsMap = {};
  places.forEach(place => {
    const step = place.stepLabel || place.step || 'Surprise Me';
    if (!railsMap[step]) {
      railsMap[step] = {
        label: step,
        query: step,
        results: []
      };
    }
    railsMap[step].results.push(place);
  });
  
  state.steps = Object.values(railsMap);
  renderRails();
}

/* ---------- Vibe Drawer ---------- */
function showVibeDrawer() {
  console.log('🎭 Opening vibe drawer');
  
  // Fire analytics event
  if (window.gtag) {
    window.gtag('event', 'ui.vibe_open', {
      event_category: 'ui',
      event_label: 'vibe_drawer'
    });
  }
  
  const drawer = document.getElementById('vibeDrawer');
  drawer.setAttribute('aria-hidden', 'false');
  drawer.style.display = 'block';
  
  // Focus trap
  const firstButton = drawer.querySelector('.vibe-option');
  if (firstButton) {
    firstButton.focus();
  }
  
  // Load saved selection
  loadVibeSelection();
}

function hideVibeDrawer() {
  console.log('🎭 Closing vibe drawer');
  
  const drawer = document.getElementById('vibeDrawer');
  drawer.setAttribute('aria-hidden', 'true');
  drawer.style.display = 'none';
  
  // Fire analytics event
  if (window.gtag) {
    window.gtag('event', 'ui.vibe_cancel', {
      event_category: 'ui',
      event_label: 'vibe_drawer'
    });
  }
}

function initVibeDrawer() {
  const drawer = document.getElementById('vibeDrawer');
  const closeBtn = document.getElementById('closeVibe');
  const cancelBtn = document.getElementById('cancelVibe');
  const applyBtn = document.getElementById('applyVibe');
  const vibeOptions = document.querySelectorAll('.vibe-option');
  const energyOptions = document.querySelectorAll('.energy-option');
  
  // Close buttons
  closeBtn.onclick = hideVibeDrawer;
  cancelBtn.onclick = hideVibeDrawer;
  
  // ESC key to close
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.getAttribute('aria-hidden') === 'false') {
      hideVibeDrawer();
    }
  });
  
  // Vibe selection
  vibeOptions.forEach(btn => {
    btn.onclick = () => {
      // Remove previous selection
      vibeOptions.forEach(b => b.classList.remove('vibe-option--selected'));
      // Select current
      btn.classList.add('vibe-option--selected');
      state.selectedVibe = btn.dataset.vibe;
      updateApplyButton();
    };
  });
  
  // Energy selection
  energyOptions.forEach(btn => {
    btn.onclick = () => {
      // Remove previous selection
      energyOptions.forEach(b => b.classList.remove('energy-option--selected'));
      // Select current
      btn.classList.add('energy-option--selected');
      state.selectedEnergy = btn.dataset.energy;
      updateApplyButton();
    };
  });
  
  // Apply button
  applyBtn.onclick = () => {
    if (state.selectedVibe && state.selectedEnergy) {
      applyVibeSelection();
    }
  };
}

function updateApplyButton() {
  const applyBtn = document.getElementById('applyVibe');
  const canApply = state.selectedVibe && state.selectedEnergy;
  
  applyBtn.disabled = !canApply;
  if (canApply) {
    applyBtn.textContent = `Apply (${state.selectedVibe}, ${state.selectedEnergy})`;
  } else {
    applyBtn.textContent = 'Apply';
  }
}

function loadVibeSelection() {
  // Load from localStorage
  const saved = localStorage.getItem('vibeSelection');
  if (saved) {
    try {
      const { vibe, energy } = JSON.parse(saved);
      if (vibe) {
        const vibeBtn = document.querySelector(`[data-vibe="${vibe}"]`);
        if (vibeBtn) {
          vibeBtn.classList.add('vibe-option--selected');
          state.selectedVibe = vibe;
        }
      }
      if (energy) {
        const energyBtn = document.querySelector(`[data-energy="${energy}"]`);
        if (energyBtn) {
          energyBtn.classList.add('energy-option--selected');
          state.selectedEnergy = energy;
        }
      }
      updateApplyButton();
    } catch (e) {
      console.warn('Failed to load vibe selection:', e);
    }
  }
}

function saveVibeSelection() {
  const selection = {
    vibe: state.selectedVibe,
    energy: state.selectedEnergy,
    timestamp: Date.now()
  };
  localStorage.setItem('vibeSelection', JSON.stringify(selection));
}

async function applyVibeSelection() {
  console.log(`🎭 Applying vibe: ${state.selectedVibe}, energy: ${state.selectedEnergy}`);
  
  // Fire analytics event
  if (window.gtag) {
    window.gtag('event', 'ui.vibe_apply', {
      event_category: 'ui',
      event_label: 'vibe_drawer',
      custom_parameters: {
        vibe: state.selectedVibe,
        energy: state.selectedEnergy
      }
    });
  }
  
  // Save selection
  saveVibeSelection();
  
  // Hide drawer
  hideVibeDrawer();
  
  // Get vibe rails
  const places = await getVibeRails(state.selectedVibe, state.selectedEnergy);
  
  if (places.length === 0) {
    showVibeEmptyState();
    return;
  }
  
  // Group places into rails
  const railsMap = {};
  places.forEach(place => {
    const step = place.stepLabel || place.step || 'Vibe';
    if (!railsMap[step]) {
      railsMap[step] = {
        label: step,
        query: step,
        results: []
      };
    }
    railsMap[step].results.push(place);
  });
  
  state.steps = Object.values(railsMap);
  
  // Add vibe caption
  state.vibeCaption = `Vibe: ${state.selectedVibe}, Energy: ${state.selectedEnergy}`;
  
  renderRails();
}

function showVibeEmptyState() {
  state.steps = [{
    label: 'No matches found',
    query: 'vibe',
    results: []
  }];
  
  state.vibeCaption = `Vibe: ${state.selectedVibe}, Energy: ${state.selectedEnergy}`;
  state.vibeEmptyState = true;
  
  renderRails();
}

async function getVibeRails(vibe, energy) {
  try {
    const params = new URLSearchParams({
      mode: 'vibe',
      vibe: vibe,
      energy: energy,
      user_lat: state.user.lat,
      user_lng: state.user.lng
    });
    
    const response = await fetch(`/api/rails?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    return data.rails || [];
  } catch (error) {
    console.error('Failed to get vibe rails:', error);
    return [];
  }
}

async function showModeRails() {
  console.log(`🎯 Showing ${state.searchMode} rails`);
  
  // Получаем rails для текущего режима
  const places = await getRailsForMode(state.searchMode);
  
  if (places.length === 0) {
    state.steps = [];
    renderRails();
    return;
  }
  
  // Группируем места по stepLabel (rail label)
  const railsMap = {};
  places.forEach(place => {
    const railLabel = place.stepLabel || 'Suggested';
    if (!railsMap[railLabel]) {
      railsMap[railLabel] = {
        label: railLabel,
        query: '',
        results: [],
        selected: null
      };
    }
    railsMap[railLabel].results.push(place);
  });
  
  state.steps = Object.values(railsMap);
  renderRails();
}

/* ---------- Get Rails without query ---------- */
async function getRailsForMode(mode, limit = 36) {
  try {
    const params = new URLSearchParams({
      mode: mode,
      limit: limit.toString()
    });
    
    // Добавляем координаты только если они есть
    if (state.user.lat && state.user.lng) {
      params.append('user_lat', state.user.lat.toString());
      params.append('user_lng', state.user.lng.toString());
    }

    // Добавляем quality=high для high_experience режима
    if (mode === 'high_experience') {
      params.append('quality', 'high');
      params.set('mode', 'vibe'); // используем vibe mode для quality filter
    }

    const response = await fetch(`${API_BASE}/rails?${params}`);
    if (!response.ok) {
      throw new Error("Rails request failed");
    }

    const result = await response.json();
    console.log(`🎯 ${mode} rails result:`, result);

    // Преобразуем rails в формат, ожидаемый фронтендом
    const allPlaces = [];
    (result.rails || []).forEach(rail => {
      console.log(`📦 Rail ${rail.step}: ${rail.items.length} items`);
      rail.items.forEach(place => {
        allPlaces.push({
          ...place,
          step: rail.step,
          stepLabel: rail.label
        });
      });
    });
    
    console.log(`🏆 Total ${mode} places:`, allPlaces.length);
    return allPlaces.slice(0, limit);
    
  } catch (error) {
    console.error(`${mode} rails failed:`, error);
    return [];
  }
}

async function fetchComposeRails(q, lat, lng, limit = 12) {
  const params = new URLSearchParams({ q, limit: String(limit) });
  if (typeof lat === 'number' && typeof lng === 'number') {
    params.set('user_lat', String(lat));
    params.set('user_lng', String(lng));
  }
  const res = await fetch(`/api/rails?${params.toString()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.rails || [];
}

function railsToSteps(rails){
  return (rails || []).map(r => ({
    label: r.label || 'Suggested',
    query: 'compose',
    results: (r.items || []).map(it => ({
      ...it,
      summary: it.summary || '',
      tags_csv: it.tags_csv || '',
      category: it.category || '',
      picture_url: it.picture_url || '',
      distance: it.distance_m ?? it.distance ?? null
    }))
  }));
}

async function showComposeRails(q){
  const lat = (typeof state.user?.lat === 'number') ? state.user.lat : null;
  const lng = (typeof state.user?.lng === 'number') ? state.user.lng : null;
  const rails = await fetchComposeRails(q, lat, lng, 12);
  state.steps = railsToSteps(rails);
  renderRails();
}

async function performSearch(input) {
  console.log('🔍 Starting search for:', input);
  
  // Если свободный текст (есть пробелы/знаки), используем compose slotter
  if (/\s|,/.test(input)) {
    try {
      await showComposeRails(input);
      return;
    } catch (e) {
      console.warn('Compose slotter failed, fallback to legacy steps:', e);
      // продублируем поведение ниже
    }
  }
  
  state.steps = await parseSteps(input);
  console.log('📝 Parsed steps:', state.steps);
  renderSelectedBar();
  renderRails();

  // Показываем loading состояние (results остается undefined)
  renderRails();

  // Загружаем все результаты с небольшой задержкой между запросами
  const promises = state.steps.map(async (step, index) => {
    console.log(`🔎 Searching step ${index}:`, step.query);
    
    // Небольшая задержка между запросами (100ms * индекс)
    await new Promise(resolve => setTimeout(resolve, index * 100));
    try{
      const items = await searchPlaces(step.query, 12, state.selectedArea);
      console.log(`✅ Step ${index} results:`, items.length, 'items');
      step.results = Array.isArray(items) ? items : [];
    }catch(e){ 
      console.error(`❌ Step ${index} error:`, e);
      step.results=[]; 
    }
  });

  // Ждем завершения всех запросов
  await Promise.all(promises);
  
  console.log('🎯 Final steps:', state.steps.map(s => ({ 
    query: s.query, 
    results: s.results?.length || 0 
  })));
  
  // Сортируем все категории по умолчанию
  resortAllCategories();
  
  // Применяем фильтр высокого качества если активен
  applyHighExperienceFilter();
  
  // Перерисовываем все ряды одновременно
  renderRails();
}

/* ---------- Drawer (Route) ---------- */
function openRoute(){ $("#routeDrawer").setAttribute("aria-hidden","false"); drawRouteList(); }
function closeRoute(){ $("#routeDrawer").setAttribute("aria-hidden","true"); }
function drawRouteList(){
  const ol = $("#routeList"); ol.innerHTML="";
  // Используем порядок из state.selectedPlaces
  state.selectedPlaces.forEach((place, index) => {
    const li = document.createElement("li");
    li.className = "route-item";
    li.textContent = `${index + 1}. ${place.name}`;
    li.setAttribute("draggable", "true");
    li.dataset.index = String(index);

    li.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', li.dataset.index);
      li.classList.add('dragging');
    });
    li.addEventListener('dragend', () => {
      li.classList.remove('dragging');
    });
    li.addEventListener('dragover', (e) => {
      e.preventDefault();
      li.classList.add('dragover');
    });
    li.addEventListener('dragleave', () => {
      li.classList.remove('dragover');
    });
    li.addEventListener('drop', (e) => {
      e.preventDefault();
      li.classList.remove('dragover');
      const fromIndex = parseInt(e.dataTransfer.getData('text/plain'), 10);
      const toIndex = parseInt(li.dataset.index || '0', 10);
      if (Number.isInteger(fromIndex) && Number.isInteger(toIndex) && fromIndex !== toIndex) {
        reorderSelectedPlaces(fromIndex, toIndex);
        drawRouteList();
        // Перестроить маршрут на карте
        if (state.googleMap && state.directionsService) {
          buildAndRenderRouteFromHome();
        }
      }
    });

    ol.appendChild(li);
  });
}
async function buildRoute(){
  // Строим маршрут с использованием Google Directions
  if (state.selectedPlaces.length === 0) {
    $("#routeResult").textContent = "Pick at least one place.";
    return;
  }
  $("#routeResult").textContent = "Building route...";
  if (!state.googleMapsLoaded) {
    await loadGoogleMapsAPI();
  }
  showMapContainer();
  ensureDirections();
  buildAndRenderRouteFromHome();
  $("#routeResult").textContent = "Route built.";
}

// Переупорядочить выбранные места
function reorderSelectedPlaces(fromIndex, toIndex) {
  const arr = state.selectedPlaces.slice();
  const [moved] = arr.splice(fromIndex, 1);
  arr.splice(toIndex, 0, moved);
  state.selectedPlaces = arr;
}

/* ---------- Google Maps Functions ---------- */

// Загрузка Google Maps API
async function loadGoogleMapsAPI() {
  if (state.googleMapsLoaded) return true;
  
  try {
    const response = await fetch(`${API_BASE}/config`);
    const config = await response.json();
    const apiKey = config.google_maps_api_key;
    
    if (!apiKey) {
      console.error('Google Maps API key not available');
      return false;
    }
    
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&callback=initGoogleMap`;
      script.async = true;
      script.defer = true;
      
      script.onload = () => {
        state.googleMapsLoaded = true;
        console.log('✅ Google Maps API loaded');
        resolve(true);
      };
      
      script.onerror = (error) => {
        console.error('❌ Failed to load Google Maps API:', error);
        showMapError();
        resolve(false);
      };
      
      document.head.appendChild(script);
    });
  } catch (error) {
    console.error('Failed to load Google Maps config:', error);
    return false;
  }
}

// Инициализация карты (глобальная функция для callback)
window.initGoogleMap = function() {
  const mapContainer = document.getElementById('map');
  if (!mapContainer) {
    console.error('Map container not found');
    return;
  }
  
  try {
    state.googleMap = new google.maps.Map(mapContainer, {
      zoom: 13,
      center: { lat: 13.7563, lng: 100.5018 }, // Бангкок
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false
    });
    
    console.log('✅ Google Map initialized');
    updateMapWithSelectedPlaces();
    ensureDirections();
    
  } catch (error) {
    console.error('Failed to initialize Google Map:', error);
    showMapError();
  }
};

// Показать карту
function showMapContainer() {
  const mapContainer = document.getElementById('mapContainer');
  if (mapContainer) {
    mapContainer.style.display = 'block';
    console.log('📍 Map container shown');
  }
}

// Скрыть карту
function hideMapContainer() {
  const mapContainer = document.getElementById('mapContainer');
  if (mapContainer) {
    mapContainer.style.display = 'none';
    console.log('📍 Map container hidden');
  }
}

// Показать ошибку карты
function showMapError() {
  const mapContainer = document.getElementById('map');
  if (mapContainer) {
    mapContainer.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #e74c3c; text-align: center; padding: 20px;">Map unavailable<br><small>Check API key configuration</small></div>';
  }
}

// Обновить карту с выбранными местами
function updateMapWithSelectedPlaces() {
  if (!state.googleMap) return;
  
  // Очищаем все старые маркеры
  state.mapMarkers.forEach(marker => marker.setMap(null));
  state.mapMarkers = [];
  
  // Если нет выбранных мест - просто очищаем карту
  if (state.selectedPlaces.length === 0) {
    console.log('📍 All markers cleared from map');
    return;
  }
  
  const bounds = new google.maps.LatLngBounds();
  
  // Добавляем маркеры только для выбранных мест
  state.selectedPlaces.forEach((place, index) => {
    if (place.lat && place.lng) {
      const marker = new google.maps.Marker({
        position: { lat: parseFloat(place.lat), lng: parseFloat(place.lng) },
        map: state.googleMap,
        title: place.name,
        label: String(index + 1),
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 16,
          fillColor: '#4285f4',
          fillOpacity: 1,
          strokeColor: 'white',
          strokeWeight: 2,
          labelOrigin: new google.maps.Point(0, 0)
        }
      });
      
      // Добавляем info window
      const infoWindow = new google.maps.InfoWindow({
        content: `<div style="font-weight: bold; margin-bottom: 4px;">${place.name}</div>
                  <div style="font-size: 12px; color: #666;">${place.summary || 'Selected place'}</div>`
      });
      
      marker.addListener('click', () => {
        infoWindow.open(state.googleMap, marker);
      });
      
      state.mapMarkers.push(marker);
      bounds.extend(marker.getPosition());
    }
  });
  
  // Подгоняем карту под все маркеры
  if (state.selectedPlaces.length > 0) {
    state.googleMap.fitBounds(bounds);
    
    // Ограничиваем максимальный zoom для одного места
    if (state.selectedPlaces.length === 1) {
      google.maps.event.addListenerOnce(state.googleMap, 'bounds_changed', () => {
        if (state.googleMap.getZoom() > 16) {
          state.googleMap.setZoom(16);
        }
      });
    }
  }
  
  console.log(`📍 Updated map with ${state.selectedPlaces.length} markers`);
}

// Убедиться, что сервисы Directions инициализированы
function ensureDirections() {
  if (!state.googleMap || !window.google || !google.maps) return;
  if (!state.directionsService) {
    state.directionsService = new google.maps.DirectionsService();
  }
  if (!state.directionsRenderer) {
    state.directionsRenderer = new google.maps.DirectionsRenderer({
      map: state.googleMap,
      suppressMarkers: false,
      preserveViewport: false
    });
  } else if (state.directionsRenderer.getMap() !== state.googleMap) {
    state.directionsRenderer.setMap(state.googleMap);
  }
}

function buildGoogleMapsRouteUrl() {
  const sanitizeLatLng = (lat, lng) => {
    const latNum = Number(lat);
    const lngNum = Number(lng);
    if (!Number.isFinite(latNum) || !Number.isFinite(lngNum)) return null;
    return `${latNum},${lngNum}`;
  };

  const buildPlaceParam = place => {
    if (!place) return null;
    if (place.gmaps_place_id) {
      return `place_id:${place.gmaps_place_id}`;
    }
    const coords = sanitizeLatLng(place.lat, place.lng);
    if (coords) return coords;
    if (place.address) return place.address;
    if (place.name) return place.name;
    return null;
  };

  const placesWithParams = state.selectedPlaces
    .map(place => ({ place, param: buildPlaceParam(place) }))
    .filter(item => item.param);

  if (placesWithParams.length === 0) {
    console.warn('Нет выбранных мест с координатами или place_id для маршрута Google Maps.');
    return null;
  }

  const userOrigin = sanitizeLatLng(state.user?.lat, state.user?.lng);

  if (placesWithParams.length === 1) {
    const singleParam = placesWithParams[0].param;
    const params = new URLSearchParams();
    params.set('api', '1');
    params.set('travelmode', 'walking');
    params.set('destination', singleParam);
    if (userOrigin) {
      params.set('origin', userOrigin);
    }
    return `https://www.google.com/maps/dir/?${params.toString()}`;
  }

  const params = new URLSearchParams();
  params.set('api', '1');
  params.set('travelmode', 'walking');

  let originParam = userOrigin;
  let waypointCandidates = placesWithParams.slice(0, -1);
  const destinationParam = placesWithParams[placesWithParams.length - 1].param;

  if (!originParam) {
    originParam = placesWithParams[0].param;
    waypointCandidates = placesWithParams.slice(1, -1);
  }

  if (!originParam || !destinationParam) {
    console.warn('Не удалось сформировать origin или destination для Google Maps.');
    return null;
  }

  const waypointParams = waypointCandidates.map(item => item.param).filter(Boolean);
  if (waypointParams.length > GOOGLE_MAPS_MAX_WAYPOINTS) {
    console.warn(`Waypoints сокращены с ${waypointParams.length} до ${GOOGLE_MAPS_MAX_WAYPOINTS} для ссылки Google Maps.`);
  }

  params.set('origin', originParam);
  params.set('destination', destinationParam);
  if (waypointParams.length > 0) {
    params.set('waypoints', waypointParams.slice(0, GOOGLE_MAPS_MAX_WAYPOINTS).join('|'));
  }

  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

// Построить маршрут от home (state.user) через выбранные точки по порядку
function buildAndRenderRouteFromHome() {
  if (!state.googleMap || !state.directionsService || !state.directionsRenderer) return;
  if (!state.user.lat || !state.user.lng) {
    // если нет геолокации, используем дефолт, уже задан по умолчанию
    console.warn('No user location; using default home');
  }
  const origin = { lat: parseFloat(state.user.lat), lng: parseFloat(state.user.lng) };
  const points = state.selectedPlaces.filter(p => p.lat && p.lng);
  if (points.length === 0) return;
  const destination = { lat: parseFloat(points[points.length - 1].lat), lng: parseFloat(points[points.length - 1].lng) };
  const waypoints = points.slice(0, -1).map(p => ({ location: { lat: parseFloat(p.lat), lng: parseFloat(p.lng) }, stopover: true }));

  const request = {
    origin,
    destination,
    waypoints,
    travelMode: google.maps.TravelMode.WALKING,
    optimizeWaypoints: false
  };

  state.directionsService.route(request, (result, status) => {
    if (status === google.maps.DirectionsStatus.OK) {
      state.directionsRenderer.setDirections(result);
      renderRouteStats(result);
    } else {
      console.error('Directions request failed due to ' + status);
    }
  });
}

// Отобразить краткую статистику и ссылку «Open in Google Maps»
function renderRouteStats(directionsResult) {
  const info = document.getElementById('mapInfo');
  const stats = document.getElementById('routeStats');
  if (!info || !stats) return;
  try {
    let totalMeters = 0;
    let totalSeconds = 0;
    const legs = directionsResult.routes?.[0]?.legs || [];
    legs.forEach(leg => {
      totalMeters += (leg.distance?.value || 0);
      totalSeconds += (leg.duration?.value || 0);
    });
    const km = (totalMeters / 1000).toFixed(1);
    const mins = Math.round(totalSeconds / 60);

    const mapsLink = buildGoogleMapsRouteUrl();

    stats.innerHTML = `
      <div><strong>Distance:</strong> ${km} km</div>
      <div><strong>ETA:</strong> ${mins} min</div>
      ${mapsLink ? `<div style="margin-top:8px;"><a href="${mapsLink}" target="_blank" rel="noopener">Open in Google Maps ↗</a></div>` : '<div style="margin-top:8px;color:#b00;">Google Maps link unavailable</div>'}
    `;
    info.style.display = 'block';
  } catch (e) {
    console.warn('Failed to render stats', e);
  }
}

/* ---------- Init ---------- */
window.addEventListener("DOMContentLoaded", ()=>{
  // Инициализируем контролы режимов
  initModeControls();
  
  // Инициализируем обработчик закрытия карты
  const closeMapBtn = document.getElementById('closeMap');
  if (closeMapBtn) {
    closeMapBtn.onclick = () => {
      hideMapContainer();
    };
  }
  
  // Живой поиск при вводе
  $("#queryInput").addEventListener("input", applyQuery);
  
  // Показываем пустое состояние при загрузке
  renderRails();
  


    // Home Location button
    $("#homeLoc").onclick = ()=>{
      state.user.lat = 13.744262;
      state.user.lng = 100.561473;
      console.log("✅ Home location set:", state.user.lat, state.user.lng);
      alert(`Home location set: ${state.user.lat}, ${state.user.lng}`);
      
      // Пересортируем категории после установки геолокации
      if (state.steps.length > 0) {
        console.log("Re-sorting categories after home location");
        resortAllCategories();
        renderRails();
      }
    };

  // Auto-get location on page load
  (async () => {
    console.log("Attempting to get user location...");
    try {
      const pos = await new Promise((res,rej)=>navigator.geolocation.getCurrentPosition(res,rej,{enableHighAccuracy:true,timeout:5000}));
      state.user.lat = +pos.coords.latitude.toFixed(6);
      state.user.lng = +pos.coords.longitude.toFixed(6);
      console.log("✅ Location obtained:", state.user.lat, state.user.lng);
      
      // Пересортируем категории после получения геолокации
      if (state.steps.length > 0) {
        console.log("Re-sorting categories after location obtained");
        resortAllCategories();
        renderRails();
      }
    } catch (err) {
      console.log("❌ Location not available:", err.message);
      console.log("Error details:", err);
    }
  })();
  
  // Проверяем существование элементов перед назначением обработчиков
  const openRouteEl = $("#openRoute");
  const closeRouteEl = $("#closeRoute");
  const buildRouteEl = $("#buildRoute");
  
  if (openRouteEl) openRouteEl.onclick = openRoute;
  if (closeRouteEl) closeRouteEl.onclick = closeRoute;
  if (buildRouteEl) buildRouteEl.onclick = buildRoute;

  // демо-пример: можно раскомментировать для тестирования
  // $("#queryInput").value = "tom yum, rooftop, spa";
  // applyQuery();
});
