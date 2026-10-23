import requests, os, sys, yaml, urllib3
urllib3.disable_warnings()

HOST = os.environ["QRADAR_HOST"]
TOKEN = os.environ["QRADAR_TOKEN"]
BASE = "https://{}/api/analytics/rules".format(HOST)
HEADERS = {"SEC": TOKEN, "Accept": "application/json"}


def sync():
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "QRadar")

    if not os.path.isdir(rules_dir):
        print("❌ Папка не найдена: {}".format(rules_dir))
        print("Проверь, что скрипт лежит в Scripts/, а правила — в QRadar/ на уровень выше.")
        sys.exit(1)

    yml_files = [f for f in os.listdir(rules_dir) if f.endswith((".yml", ".yaml"))]
    print("--- QRadar Sync: найдено {} правил ---".format(len(yml_files)))

    for fn in yml_files:
        path = os.path.join(rules_dir, fn)
        try:
            with open(path, encoding="utf-8") as f:
                rule = yaml.safe_load(f)

            if not rule or "title" not in rule:
                print("⚠️ {}: нет 'title' — пропускаю".format(fn))
                continue

            qradar_name = rule["title"].strip()

            # ВАЖНО: QRadar API не создаёт логику условий правила с нуля —
            # правило должно быть один раз собрано в GUI (Rule Wizard) под этим же именем.
            res = requests.get(BASE, headers=HEADERS, params={"filter": 'name="{}"'.format(qradar_name)},
                                verify=False, timeout=15)
            if res.status_code != 200:
                print("❌ {}: ошибка поиска правила ({}) {}".format(fn, res.status_code, res.text[:150]))
                continue

            found = res.json()
            if not found:
                print("❌ NOT FOUND: '{}' — сначала создай это правило один раз через GUI (Offenses > Rules)".format(
                    qradar_name))
                continue

            rule_id = found[0]["id"]
            payload = {
                "enabled": True,
                "notes": "[{}] {} (level={})".format(
                    fn, rule.get("description", "").strip(), rule.get("level", "n/a")),
            }
            res_up = requests.post("{}/{}".format(BASE, rule_id), headers=HEADERS, json=payload,
                                    verify=False, timeout=15)

            if res_up.status_code in (200, 201):
                print("🔄 UPDATED: {} (id={})".format(qradar_name, rule_id))
            else:
                print("❌ UPDATE FAILED: {} ({}) {}".format(qradar_name, res_up.status_code, res_up.text[:150]))

        except Exception as e:
            print("⚠️ Ошибка в {}: {}".format(fn, e))


if __name__ == "__main__":
    sync()
