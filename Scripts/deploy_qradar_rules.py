import requests, os, configparser, urllib3
urllib3.disable_warnings()

# export QRADAR_HOST=IP
# export QRADAR_TOKEN=TOKEN
HOST = os.environ["QRADAR_HOST"]
TOKEN = os.environ["QRADAR_TOKEN"]
BASE = f"https://{HOST}/api/analytics/rules"
HEADERS = {"SEC": TOKEN, "Accept": "application/json"}


def sync():
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qradar-rules")
    conf_files = [f for f in os.listdir(rules_dir) if f.endswith(".conf")]
    print(f"--- QRadar Rule Sync: найдено {len(conf_files)} правил ---")

    for fn in conf_files:
        rule_id_name = fn.replace(".conf", "")
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(os.path.join(rules_dir, fn))

        if rule_id_name not in cfg:
            print(f"⚠️ {fn}: нет секции [{rule_id_name}] — пропускаю")
            continue

        section = cfg[rule_id_name]
        qradar_name = section.get("name", rule_id_name)

        try:
            # ищем правило по имени — оно должно быть один раз создано через GUI
            res = requests.get(BASE, headers=HEADERS, params={"filter": f'name="{qradar_name}"'},
                                verify=False, timeout=15)
            found = res.json() if res.status_code == 200 else []

            if not found:
                print(f"❌ NOT FOUND: '{qradar_name}' — сначала создай правило один раз через GUI "
                      f"(Offenses > Rules), API не умеет собрать логику условий с нуля")
                continue

            rule_id = found[0]["id"]
            payload = {
                "enabled": True,
                "notes": f"[{rule_id_name}] {section.get('description', '')} "
                         f"(mitre={section.get('mitre_id', 'n/a')})",
            }
            res_up = requests.post(f"{BASE}/{rule_id}", headers=HEADERS, json=payload, verify=False, timeout=15)

            print(f"🔄 UPDATED: {qradar_name}" if res_up.status_code in (200, 201)
                  else f"❌ FAILED: {qradar_name} ({res_up.status_code}) {res_up.text[:150]}")

        except requests.RequestException as e:
            print(f"⚠️ Ошибка сети для {qradar_name}: {e}")


if __name__ == "__main__":
    sync()
