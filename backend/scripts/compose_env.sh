# DEV ONLY. Usage, from backend/:  source scripts/compose_env.sh
set -a; source ../.env.compose; set +a
export DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:55432/${POSTGRES_DB}"
export BASE=http://localhost:8080

tok()    { poetry run python -m scripts.dev_token "$1"; }
jid()    { python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"; }
pick()   { python3 -c "import sys,json; k,v=sys.argv[1:3]; print(next((x['id'] for x in json.load(sys.stdin) if x[k]==v), ''))" "$@"; }
post()   { curl -s -X POST "$BASE$1" -H "Authorization: Bearer $2" -H "Content-Type: application/json" -d "$3"; }
dc()     { docker compose -f ../docker-compose.yml --env-file ../.env.compose "$@"; }
say()    { curl -s -o /dev/null -w "%{http_code} " -X POST "$BASE/workspaces/$WS/channels/$CH/messages" -H "Authorization: Bearer $OWNER" -H "Content-Type: application/json" -d "{\"body\":\"$1\"}"; }
sayn()   { for i in $(seq 1 "$1"); do say "$2 $i"; sleep 0.4; done; echo; }
burst()  ( for i in $(seq 1 8); do say "burst $i" & done; wait; echo )
mark()   { MARK=$(date -u +%Y-%m-%dT%H:%M:%SZ); }
spread() { dc logs --no-log-prefix --since "$MARK" proxy | grep -E 'POST /workspaces/[0-9a-f-]+/channels/[0-9a-f-]+/messages' | grep -o 'upstream=[^ ]*' | sort | uniq -c; }

if ! curl -sf "$BASE/health" > /dev/null; then
  echo "nothing answering at $BASE/health: is the stack up?"
  return 1
fi

export OWNER=$(tok owner@compose.dev) BOB=$(tok bob@compose.dev)

export WS=$(curl -s -H "Authorization: Bearer $OWNER" "$BASE/workspaces" | pick slug compose)
if [ -z "$WS" ]; then
  export WS=$(post /workspaces "$OWNER" '{"name":"Compose","slug":"compose"}' | jid)
  post "/workspaces/$WS/members" "$OWNER" '{"email":"bob@compose.dev"}' > /dev/null
fi
export CH=$(curl -s -H "Authorization: Bearer $OWNER" "$BASE/workspaces/$WS/channels" | pick name general)
if [ -z "$CH" ]; then
  export CH=$(post "/workspaces/$WS/channels" "$OWNER" '{"name":"general"}' | jid)
fi
echo "BASE=$BASE WS=$WS CH=$CH"