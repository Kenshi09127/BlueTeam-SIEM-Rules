import requests, os, sys, yaml, urllib3
urllib3.disable_warnings()

HOST = os.environ["SPLUNK_HOST"]
PORT = os.environ.get("SPLUNK_PORT", "8089")
USER = os.environ["SPLUNK_USER"]
PASS = os.environ["SPLUNK_PASS"]
APP = os.environ.get("SPLUNK_APP", "search")
AUTH = (USER, PASS)

BASE = "https://{}:{}/servicesNS/nobody/{}/saved/searches".format(HOST, PORT, APP)
LEVEL_TO_SEVERITY = {"informational": "1", "low": "2", "medium": "3", "high": "4", "critical": "5"}
MARKER = "splunk spl query"


def extract_spl_from_comments(raw_text):
    """Достаёт закомментированный SPL-блок вида:
    # --- Splunk SPL Query ---
    # index=web ...
    # (uri_path=... )
    #                       <- пустая строка-комментарий = конец блока
    """
    lines = raw_text.splitlines()
    collecting = False
    spl_lines = []
    for line in lines:
        stripped = line.strip()
        if not collecting:
            if stripped.startswith("#") and MARKER in stripped.lower():
                collecting = True
            continue
        if not stripped.startswith("#"):
            break
        content = stripped.lstrip("#").strip()
        if not content:
            break
        spl_lines.append(content)
    return " ".join(spl_lines) if spl_lines else None


def parens_balanced(spl):
    return spl.count("(") == spl.count(")")


def sync():
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Splunk")

    if not os.path.isdir(rules_dir):
        print("❌ Папка не найдена: {}".format(rules_dir))
        print("Проверь, что скрипт лежит в Scripts/, а правила — в Splunk/ на уровень выше.")
        sys.exit(1)

    yml_files = [f for f in os.listdir(rules_dir) if f.endswith((".yml", ".yaml"))]
    print("--- Splunk Sync: найдено {} правил ---".format(len(yml_files)))

    for fn in yml_files:
        path = os.path.join(rules_dir, fn)
        try:
            raw = open(path, encoding="utf-8").read()
            rule = yaml.safe_load(raw)

            if not rule or "title" not in rule:
                print("⚠️ {}: нет 'title' — пропускаю".format(fn))
                continue

            spl = extract_spl_from_comments(raw)
            if not spl:
                print("⚠️ {}: не нашёл блок '--- Splunk SPL Query ---' — пропускаю".format(fn))
                continue

            if not parens_balanced(spl):
                print("❌ {}: НЕ сбалансированы скобки ( {} vs ) {} — правило НЕ задеплоено".format(
                    fn, spl.count("("), spl.count(")")))
                continue

            rule_name = rule["title"].strip().replace(" ", "_").replace("-", "_")

            payload = {
                "search": spl,
                "description": rule.get("description", ""),
                "is_visible": "true",
                "disabled": "0",
                "dispatch.earliest_time": "-24h",
                "dispatch.latest_time": "now",
                "is_scheduled": "1",
                "cron_schedule": "*/5 * * * *",
                "alert_type": "number of events",
                "alert_comparator": "greater than",
                "alert_threshold": "0",
                "alert.severity": LEVEL_TO_SEVERITY.get(rule.get("level", "medium"), "3"),
            }

            data_create = dict(payload)
            data_create["name"] = rule_name
            res = requests.post(BASE, data=data_create, auth=AUTH, verify=False, timeout=15)

            if res.status_code in (200, 201):
                print("✅ CREATED: {}".format(rule_name))
            elif res.status_code == 400 and "already exists" in res.text.lower():
                update_url = "{}/{}".format(BASE, rule_name)
                res_up = requests.post(update_url, data=payload, auth=AUTH, verify=False, timeout=15)
                if res_up.status_code == 200:
                    print("🔄 UPDATED: {}".format(rule_name))
                else:
                    print("❌ UPDATE FAILED: {} ({}) {}".format(rule_name, res_up.status_code, res_up.text[:150]))
            else:
                print("❌ FAILED: {} ({}) {}".format(rule_name, res.status_code, res.text[:150]))

        except Exception as e:
            print("⚠️ Ошибка в {}: {}".format(fn, e))


if __name__ == "__main__":
    sync()
