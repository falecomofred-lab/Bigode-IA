import json
from pathlib import Path

base = Path(__file__).parent
for name in ("config.json", "config.example.json", "conexoes.json", "conexoes.example.json"):
    path = base / name
    print(f"[{name}]")
    if not path.exists():
        print("MISSING")
        continue
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print("INVALID_JSON", type(exc).__name__)
        continue
    if name.startswith("config"):
        for key in sorted(data):
            value = data[key]
            if isinstance(value, list):
                print(key, "list", len(value))
            elif isinstance(value, dict):
                print(key, "dict", sorted(value))
            else:
                print(key, type(value).__name__, "<redacted>" if key in {"llm_url", "modelo", "senha", "token"} else value)
    else:
        for key, value in sorted(data.items()):
            if isinstance(value, dict):
                print(key, "dict_keys", sorted(value), "active", value.get("ativa"))
            else:
                print(key, type(value).__name__)
