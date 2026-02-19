# Platform Setup

This repository contains the application code (`lib/`, `pubspec.yaml`) and expects a Flutter SDK project shell.

If platform folders are missing, run in `mobile_app/`:

```bash
flutter create .
```

Re-apply `pubspec.yaml` dependencies if `flutter create` overwrites them.

## Android permissions (`android/app/src/main/AndroidManifest.xml`)

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.RECORD_AUDIO" />
<uses-permission android:name="android.permission.CAMERA" />
```

## iOS permissions (`ios/Runner/Info.plist`)

```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>Aegis Hub needs your location to route emergency response.</string>
<key>NSMicrophoneUsageDescription</key>
<string>Aegis Hub needs microphone access for SOS voice capture.</string>
<key>NSCameraUsageDescription</key>
<string>Aegis Hub needs camera access for incident evidence.</string>
<key>NSPhotoLibraryUsageDescription</key>
<string>Aegis Hub needs photo library access for ticket media uploads.</string>
```

## Runtime configuration

Default runtime config file:

- `assets/config/runtime_config.json`

Override base URL without rebuild:

```bash
flutter run --dart-define=AEGIS_API_BASE_URL=http://10.0.2.2:8001
```

Optional bearer token:

```bash
flutter run --dart-define=AEGIS_AUTH_BEARER_TOKEN=<token>
```
