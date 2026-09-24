# Carnet de Dettes - Android Setup

## Prerequisites
- Node.js 18+
- Java JDK 17+
- Android SDK (API 30+)
- Capacitor CLI: `npm install -g @capacitor/cli`

## Build APK

1. Install dependencies:
   ```bash
   npm install
   ```

2. Create Android project:
   ```bash
   npx cap add android
   ```

3. Sync Capacitor:
   ```bash
   npx cap sync
   ```

4. Open in Android Studio:
   ```bash
   npx cap open android
   ```

5. In Android Studio:
   - Build > Build Bundle(s) / APK(s) > Build APK(s)
   - Or use: `./gradlew assembleDebug` from the android folder

## Offline mode

The mobile application stores contacts, debts and repayments locally in SQLite. Internet access and a backend server are not required for normal use.

## Debugging

```bash
# View logs
adb logcat | grep capacitor

# Open DevTools in Android Studio / Chrome DevTools
adb forward tcp:9222 localabstract:chrome_devtools_remote
```

## Production Build

1. Create a keystore:
   ```bash
   keytool -genkey -v -keystore carnet-dettes.keystore -keyalg RSA -keysize 2048 -validity 10000
   ```

2. Update `android/app/build.gradle` with signing config
3. Build signed APK in Android Studio or CLI
