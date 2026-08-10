"""Check the Expo/FCM push prerequisites for the mobile app.

Run this after each step of docs/push-notifications-setup.md to see what is
already done and what is still missing:

  python tools/check_expo_setup.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "mobile-viewer-app"

OK = "[ OK ]"
MISSING = "[TODO]"


def _load_app_json() -> dict:
  path = APP_DIR / "app.json"
  if not path.exists():
    return {}
  try:
    return json.loads(path.read_text(encoding="utf-8")).get("expo", {})
  except json.JSONDecodeError as error:
    print(f"  !! app.json is not valid JSON: {error}")
    return {}


def step_1_project_id(expo: dict) -> bool:
  project_id = ((expo.get("extra") or {}).get("eas") or {}).get("projectId")
  uuid_re = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
  if isinstance(project_id, str) and uuid_re.match(project_id):
    print(f"{OK} Step 1  EAS projectId: {project_id}")
    return True
  if project_id:
    print(f"{MISSING} Step 1  extra.eas.projectId is present but not a valid UUID: {project_id!r}")
  else:
    print(f"{MISSING} Step 1  No extra.eas.projectId in app.json -> run: npx eas-cli@latest init")
  return False


def step_2_google_services() -> bool:
  path = APP_DIR / "android" / "app" / "google-services.json"
  if not path.exists():
    print(f"{MISSING} Step 2  android/app/google-services.json is missing (download from Firebase)")
    return False
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except json.JSONDecodeError as error:
    print(f"{MISSING} Step 2  google-services.json is not valid JSON: {error}")
    return False

  packages = [
    client.get("client_info", {}).get("android_client_info", {}).get("package_name")
    for client in data.get("client", [])
  ]
  expected = "com.cinevault.mobileviewerapp"
  if expected in packages:
    print(f"{OK} Step 2  google-services.json present for {expected}")
    return True
  print(f"{MISSING} Step 2  google-services.json does not contain {expected} (found: {packages})")
  return False


def step_3_gradle() -> bool:
  root = APP_DIR / "android" / "build.gradle"
  app = APP_DIR / "android" / "app" / "build.gradle"
  root_text = root.read_text(encoding="utf-8") if root.exists() else ""
  app_text = app.read_text(encoding="utf-8") if app.exists() else ""

  has_classpath = "com.google.gms:google-services" in root_text
  has_plugin = "com.google.gms.google-services" in app_text
  if has_classpath and has_plugin:
    print(f"{OK} Step 3  Google Services Gradle plugin wired up")
    return True
  missing = []
  if not has_classpath:
    missing.append("classpath in android/build.gradle")
  if not has_plugin:
    missing.append("apply plugin in android/app/build.gradle")
  print(f"{MISSING} Step 3  Gradle not wired: missing {', '.join(missing)}")
  return False


def app_side_checks(expo: dict) -> None:
  print("\nAlready handled in code (no action needed):")

  plugins = expo.get("plugins") or []
  flag = OK if "expo-notifications" in plugins else MISSING
  print(f"{flag} expo-notifications config plugin listed in app.json")

  perms = (expo.get("android") or {}).get("permissions") or []
  flag = OK if "POST_NOTIFICATIONS" in perms else MISSING
  print(f"{flag} POST_NOTIFICATIONS permission declared")

  pkg = APP_DIR / "package.json"
  dep = ""
  if pkg.exists():
    dep = (json.loads(pkg.read_text(encoding="utf-8")).get("dependencies") or {}).get(
      "expo-notifications", ""
    )
  flag = OK if dep else MISSING
  print(f"{flag} expo-notifications dependency ({dep or 'not installed'})")

  installed = APP_DIR / "node_modules" / "expo-notifications" / "package.json"
  flag = OK if installed.exists() else MISSING
  print(f"{flag} expo-notifications installed in node_modules")


def main() -> None:
  if not APP_DIR.exists():
    print(f"Cannot find {APP_DIR}")
    sys.exit(1)

  expo = _load_app_json()

  print("Push notification setup status")
  print("=" * 62)
  done = [step_1_project_id(expo), step_2_google_services(), step_3_gradle()]
  app_side_checks(expo)

  print("=" * 62)
  if all(done):
    print("Steps 1-3 complete. Next: upload the FCM key (Step 4), then build (Step 5).")
  else:
    print(f"{done.count(True)}/3 setup steps complete. See docs/push-notifications-setup.md.")


if __name__ == "__main__":
  main()
