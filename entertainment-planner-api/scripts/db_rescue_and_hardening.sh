#!/usr/bin/env bash
set -Eeuo pipefail
shopt -s nullglob

log(){ echo -e "$(date '+%F %T') | $*"; }

PROJ="/Users/user/entertainment planner/entertainment-planner-api"
cd "$PROJ"

# venv (если есть)
VENV="/Users/user/entertainment planner/venv"
[ -f "$VENV/bin/activate" ] && source "$VENV/bin/activate" || true

# 1) Ищем самую "свежую" .db в репозитории
DB="$(python3 - <<'PY'
import os, time
root=os.getcwd()
c=[]
for dp,_,fs in os.walk(root):
    for f in fs:
        if f.endswith('.db'):
            p=os.path.join(dp,f)
            try: c.append((os.path.getmtime(p), os.path.abspath(p)))
            except FileNotFoundError: pass
c.sort(reverse=True)
print(c[0][1] if c else "")
PY
)"
[ -n "$DB" ] || { echo "ERR: .db не найдена. Укажи путь вручную"; exit 1; }
export DB
log "DB = $DB"

# 2) Останавливаем процессы, держащие файл БД
log "Останавливаю процессы, держащие БД..."
pids="$(lsof -t "$DB" 2>/dev/null | sort -u || true)"
if [ -n "${pids}" ]; then
  echo "$pids" | xargs -I{} kill -TERM {} || true
  sleep 2
  pids="$(lsof -t "$DB" 2>/dev/null | sort -u || true)"
  [ -n "${pids}" ] && echo "$pids" | xargs -I{} kill -KILL {} || true
fi

# 3) Бэкап .db и sidecar-файлов
TS="$(date +%F-%H%M%S)"
cp -av "$DB"        "${DB}.bak.$TS" || true
[ -f "${DB}-wal" ] && cp -av "${DB}-wal" "${DB}-wal.bak.$TS"
[ -f "${DB}-shm" ] && cp -av "${DB}-shm" "${DB}-shm.bak.$TS"

# 4) Быстрая проверка
log "PRAGMA integrity_check..."
CHECK="$(sqlite3 "$DB" "PRAGMA integrity_check;")"
echo "$CHECK" | head -n1

if [[ "$CHECK" == "ok" ]]; then
  # База логически целая: делаем "свежую" копию
  log "OK: Пересобираю в свежий файл через VACUUM INTO..."
  sqlite3 "$DB" "PRAGMA wal_checkpoint(FULL);" || true
  FRESH="${DB%.db}.fresh.$TS.db"
  sqlite3 "$DB" "VACUUM INTO '$FRESH';"
  mv "$FRESH" "$DB"
else
  # Порча: полноценное восстановление
  log "CORRUPT: .recover -> новая БД -> импорт INSERT'ов"
  REC="/tmp/recovered.$TS.sql"
  sqlite3 "$DB" ".recover" > "$REC"

  mv "$DB" "${DB}.corrupted.$TS"
  [ -f "${DB}-wal" ] && mv "${DB}-wal" "${DB}-wal.corrupted.$TS" || true
  [ -f "${DB}-shm" ] && mv "${DB}-shm" "${DB}-shm.corrupted.$TS" || true

  # Построим схему новой БД: Alembic или fallback на SQLAlchemy Base
  ABS_URL="$(python3 - <<PY
import os, urllib.parse
p=os.environ['DB']
print('sqlite:///' + urllib.parse.quote(os.path.abspath(p), safe='/'))
PY
)"
  FALLBACK=0
  if [ -f "alembic.ini" ]; then
    cp -av alembic.ini "alembic.ini.bak.$TS"
    python3 - <<PY
import io,os,re
fn='alembic.ini'
url=os.environ['ABS_URL']
with io.open(fn,'r',encoding='utf-8') as f: s=f.read()
if re.search(r'^\s*sqlalchemy\.url\s*=', s, flags=re.M):
    s=re.sub(r'^\s*sqlalchemy\.url\s*=.*$', f"sqlalchemy.url = {url}", s, flags=re.M)
else:
    s+="\nsqlalchemy.url = "+url+"\n"
with io.open(fn,'w',encoding='utf-8') as f: f.write(s)
print("Pinned sqlalchemy.url =", url)
PY
    alembic upgrade head || FALLBACK=1
  else
    FALLBACK=1
  fi

  if [ "$FALLBACK" = "1" ]; then
    python - <<PY
import os
from sqlalchemy import create_engine
from apps.core.db import Base
from apps.places.models import Place  # ensure models import
from apps.core.models import User     # ensure models import
engine = create_engine(os.environ['ABS_URL'], future=True)
Base.metadata.create_all(engine)
print("Schema created via Base.metadata.create_all")
PY
  fi

  # Импортируем только INSERT'ы (без CREATE/PRAGMA)
  DATA="/tmp/data_only.$TS.sql"
  grep -E '^INSERT INTO' "$REC" > "$DATA" || true
  if [ -s "$DATA" ]; then
    log "Импорт INSERT'ов..."
    sqlite3 "$DB" ".read $DATA"
  else
    log "WARNING: В recover не нашлось INSERT'ов."
  fi
fi

# 5) Финишная настройка и проверка
log "PRAGMA (WAL, FULL), REINDEX, ANALYZE, VACUUM..."
sqlite3 "$DB" "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA foreign_keys=ON;"
sqlite3 "$DB" "REINDEX; ANALYZE; VACUUM;"

log "Final integrity_check:"
sqlite3 "$DB" "PRAGMA integrity_check;" | head -n1

log "Готово."
