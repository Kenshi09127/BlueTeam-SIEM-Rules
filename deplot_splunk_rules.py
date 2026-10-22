import requests, os, configparser, urllib3
urllib3.disable_warnings()

# Креды берутся из окружения, не из кода:
#   export SPLUNK_HOST=IP
#   export SPLUNK_USER=USER
#   export SPLUNK_PASS=PASS
HOST = os.environ["SPLUNK_HOST"]
PORT = os.environ.get("SPLUNK_PORT", "8089")
USER = os.environ["SPLUNK_USER"]
PASS = os.environ["SPLUNK_PASS"]
APP = os.environ.get("SPLUNK_APP", "search")
AUTH = (USER, PASS)

BASE = f"https://{HOST}:{PORT}/servicesNS/nobody/{APP}/saved/searches"


def sync():
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "splunk-rules")
    conf_files = [f for f in os.listdir(rules_dir) if f.endswith(".conf")]
    print(f"--- SOC Automation: найдено {len(conf_files)} правил ---")

    for fn in conf_files:
        rule_name = fn.replace(".conf", "")
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(os.path.join(rules_dir, fn))

        if rule_name not in cfg:
            print(f"⚠️ {fn}: нет секции [{rule_name}] — пропускаю")
            continue

        section = cfg[rule_name]
        if "search" not in section:
            print(f"⚠️ {fn}: нет ключа 'search' — пропускаю")
            continue

        payload = {
            "search": section["search"],
            "description": section.get("description", ""),
            "is_visible": "true",
            "disabled": "0",
            "dispatch.earliest_time": section.get("earliest", "-24h"),
            "dispatch.latest_time": section.get("latest", "now"),
            # без этого блока правило ничего не алертит, просто лежит как поиск:
            "is_scheduled": "1",
            "cron_schedule": section.get("cron", "*/5 * * * *"),
            "alert_type": "number of events",
            "alert_comparator": "greater than",
            "alert_threshold": section.get("threshold", "0"),
            "alert.severity": section.get("severity", "3"),
            "actions": section.get("actions", ""),
            "action.webhook.param.url": section.get("webhook_url", ""),
        }

        try:
            # пробуем создать; если уже существует — обновляем
            res = requests.post(BASE, data={**payload, "name": rule_name}, auth=AUTH, verify=False, timeout=15)

            if res.status_code in (200, 201):
                print(f"✅ CREATED: {rule_name}")
            elif res.status_code == 400 and "already exists" in res.text.lower():
                res_up = requests.post(f"{BASE}/{rule_name}", data=payload, auth=AUTH, verify=False, timeout=15)
                print(f"🔄 UPDATED: {rule_name}" if res_up.status_code == 200
                      else f"❌ UPDATE FAILED: {rule_name} ({res_up.status_code}) {res_up.text[:150]}")
            else:
                print(f"❌ FAILED: {rule_name} ({res.status_code}) {res.text[:150]}")

        except requests.RequestException as e:
            print(f"⚠️ Ошибка сети для {rule_name}: {e}")


if __name__ == "__main__":
    sync()
