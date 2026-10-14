# DEV ONLY. Usage (from backend/, server running): source scripts/dev_env.sh
tok() { poetry run python -m scripts.dev_token "$1"; }
pick() {  # pick <key> <value> <field>: from a JSON list, print <field> of the item where <key> == <value>
  python3 -c "import sys,json; k,v,f=sys.argv[1:4]; print(next(x[f] for x in json.load(sys.stdin) if x[k]==v))" "$@"
}

export OWNER=$(tok arthurshur@gmail.com)
export BOB=$(tok bob@test.dev)
export CAROL=$(tok carol@test.dev)

export ALPHA=$(curl -s -H "Authorization: Bearer $OWNER" localhost:5000/workspaces | pick slug alpha id)
export BETA=$(curl -s -H "Authorization: Bearer $BOB" localhost:5000/workspaces | pick slug beta id)
export CH=$(curl -s -H "Authorization: Bearer $OWNER" localhost:5000/workspaces/$ALPHA/channels | pick name general id)

echo "ALPHA=$ALPHA"; echo "BETA=$BETA"; echo "CH=$CH"