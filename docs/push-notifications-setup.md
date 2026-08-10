# Push notification setup (Expo + FCM)

One-time account/credential setup so download-date approvals reach viewers
whose app is closed or whose phone is offline.

The app code is already finished. What is missing is external configuration:
an **EAS project id** and **Firebase Cloud Messaging credentials**.

---

## READ THIS FIRST — do not run `expo prebuild` or `eas build`

This project is a **bare workflow**. `mobile-viewer-app/android/` holds
**37 hand-written Kotlin files** (the VCNR player, torrent engine, native
transfer service, crypto). They are **git-ignored and untracked** — they exist
only on this machine and there is no backup anywhere in the repo.

| Command | Result |
|---|---|
| `npx expo prebuild` | **Regenerates `android/` and destroys all 37 Kotlin files.** |
| `npx eas build --platform android` | EAS uploads from **git**. `android/` is git-ignored, so it is **not uploaded**; EAS runs prebuild on its servers and the native modules **silently vanish** from the APK. |
| `cd android && .\gradlew assembleRelease` | **Correct.** Keeps the native code. |

So ignore the `build:android:preview` script in `package.json` for now, and
**build locally**. Before starting, take a safety copy:

```powershell
Copy-Item -Recurse d:\Python\VCNR_Web\mobile-viewer-app\android d:\android-backup-2026-08-10
```

---

## Step 1 — Create an Expo account and get the project id

1. Sign up (free) at <https://expo.dev/signup>.
2. In `d:\Python\VCNR_Web\mobile-viewer-app`:

```powershell
npx eas-cli@latest login
npx eas-cli@latest init
```

`eas init` creates the project on expo.dev and writes the id into `app.json`.
Confirm it landed:

```powershell
Select-String -Path app.json -Pattern projectId
```

`app.json` should now contain:

```json
"extra": {
  "eas": {
    "projectId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

> If `eas init` refuses to modify `app.json`, paste the block above manually
> using the id shown on the project page at expo.dev.

**Why this matters:** outside Expo Go, `getExpoPushTokenAsync()` cannot mint a
token without this id. `src/push.ts` reads it via `resolveEasProjectId()`.

Editing `app.json` is enough — no prebuild required. `expo-constants` runs
`get-app-config-android.gradle` on **every** Gradle build, which regenerates
`assets/app.config` inside the APK from `app.json`. That is how the id reaches
the running app. (Verified: the current APK already embeds an `app.config`; it
just has an empty `extra`, which is exactly what Step 1 fills in.)

---

## Step 2 — Create the Firebase project (gives you FCM)

Android push is delivered by Firebase Cloud Messaging, so a Firebase project
is required even though the app never calls Firebase directly.

1. Go to <https://console.firebase.google.com> → **Add project**
   (name it e.g. `cine-vault`). Google Analytics is not needed.
2. Inside the project click the **Android** icon to add an app.
3. **Android package name** — must match exactly:

   ```
   com.cinevault.mobileviewerapp
   ```

4. Download **`google-services.json`** and save it to:

   ```
   d:\Python\VCNR_Web\mobile-viewer-app\android\app\google-services.json
   ```

   Skip Firebase's own "add the SDK" instructions — Step 3 covers it.

---

## Step 3 — Wire the Google Services Gradle plugin

Normally `expo prebuild` does this. Because we must not run prebuild, apply
these two small edits by hand.

**Only do this after `google-services.json` exists** — the plugin fails the
build if the file is missing.

**A. `mobile-viewer-app\android\build.gradle`** — add the classpath:

```gradle
  dependencies {
    classpath('com.android.tools.build:gradle')
    classpath('com.facebook.react:react-native-gradle-plugin')
    classpath('org.jetbrains.kotlin:kotlin-gradle-plugin')
    classpath('com.google.gms:google-services:4.4.2')   // <-- add
  }
```

**B. `mobile-viewer-app\android\app\build.gradle`** — add the plugin at the
very top, after the existing three `apply plugin` lines:

```gradle
apply plugin: "com.android.application"
apply plugin: "org.jetbrains.kotlin.android"
apply plugin: "com.facebook.react"
apply plugin: "com.google.gms.google-services"   // <-- add
```

Nothing else changes: `expo-notifications` already ships
`com.google.firebase:firebase-messaging:24.0.1` and is **already autolinked**
(verified), so no dependency lines are needed.

---

## Step 4 — Give Expo permission to send through FCM

Expo's server needs credentials to talk to your Firebase project.

1. Firebase console → gear icon → **Project settings** → **Service accounts**.
2. Click **Generate new private key** → confirm → a `.json` file downloads.
   **Treat this like a password.** Do not put it in the repo.
3. Upload it to Expo:

```powershell
cd d:\Python\VCNR_Web\mobile-viewer-app
npx eas-cli@latest credentials
```

Answer the prompts:

| Prompt | Choose |
|---|---|
| Platform | **Android** |
| Build profile | **preview** (any is fine — FCM is shared) |
| What to do | **Push Notifications: Manage your FCM V1 service account key** |
| Action | **Set up a FCM V1 service account key** / **Upload a new key** |
| Path | the `.json` file from step 2 |

Re-running `eas credentials` should then show a configured **FCM V1** key.

---

## Step 5 — Build the APK locally

```powershell
cd d:\Python\VCNR_Web\mobile-viewer-app
npx expo run:android --variant release
```

or, to produce a shareable APK:

```powershell
cd d:\Python\VCNR_Web\mobile-viewer-app\android
.\gradlew assembleRelease
```

Output: `android\app\build\outputs\apk\release\app-release.apk`.

`JAVA_HOME` and `android\local.properties` are already configured on this
machine, so no extra SDK setup is needed.

Install it on a **physical phone** (emulators cannot receive push):

```powershell
adb install -r android\app\build\outputs\apk\release\app-release.apk
```

> Do **not** reuse the old `cinevault-viewer-release.apk` in the project root —
> it predates this work and has no notification module.

---

## Step 6 — Verify it works

1. Launch the app, sign in, and **accept** the notification permission prompt.
2. On the PC, confirm the phone reached the backend:

```powershell
cd d:\Python\VCNR_Web
python tools\send_test_push.py --list
```

You should see an `[active]` row with an `ExponentPushToken[...]`.

3. Send a test alert (copy the token from the list):

```powershell
python tools\send_test_push.py "ExponentPushToken[xxxxxxxxxxxx]"
```

Expect `accepted by Expo: 1` and a banner on the phone.

4. **The real test** — swipe the app away / lock the phone, then approve a
   download date from the admin UI. The alert must still arrive.

---

## Troubleshooting

Every failure path logs a `[VCNR push]` warning. Watch them with:

```powershell
adb logcat -s ReactNativeJS:V | Select-String "VCNR push"
```

| Symptom | Cause / fix |
|---|---|
| `Could not resolve an Expo push token` | Missing `projectId` (Step 1) or missing `google-services.json` (Step 2). |
| `Default FirebaseApp is not initialized` | Gradle plugin not applied — Step 3. |
| `--list` shows nothing | The app never registered: permission denied, or wrong server URL in the app. |
| `--list` shows `[inactive]` | The user signed out on that device. Sign in again. |
| `send_test_push` prints `rejected/dead tokens` | Token retired by Expo (app reinstalled). Sign in again to re-register. |
| Notification arrives in foreground only | Android battery optimisation. Settings → Apps → Cine Vault → Battery → **Unrestricted**. |
| Nothing on Xiaomi / Oppo / Vivo / Realme | Aggressive OEM killers. Enable **Autostart** and lock the app in recents. |

---

## iOS (later)

iOS needs a **paid Apple Developer account** ($99/yr) for APNs keys. Once you
have one, `eas credentials` → iOS → **Push Notifications** will generate and
upload the key. No app code changes are required — `src/push.ts` is already
cross-platform. Android works first and independently.

---

## Optional — `EXPO_ACCESS_TOKEN`

Only needed if you later enable **push security** on the Expo project. Then set
it on the **backend** (`.env`), not in the app:

```
EXPO_ACCESS_TOKEN=your-expo-access-token
```

`backend/core/push.py` sends it automatically when present.
