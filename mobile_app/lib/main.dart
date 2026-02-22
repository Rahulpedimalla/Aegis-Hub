import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'config/app_config.dart';
import 'config/config_loader.dart';
import 'config/config_providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  AppConfig config;
  try {
    config = await ConfigLoader().load();
  } catch (error, stackTrace) {
    FlutterError.reportError(
      FlutterErrorDetails(
        exception: error,
        stack: stackTrace,
        library: 'aegis_mobile_bootstrap',
        informationCollector: () sync* {
          yield ErrorDescription('Falling back to default app config after startup failure.');
        },
      ),
    );
    config = _fallbackAppConfig;
  }

  runApp(
    ProviderScope(
      overrides: [appConfigProvider.overrideWithValue(config)],
      child: const AegisHubApp(),
    ),
  );
}

const _fallbackAppConfig = AppConfig(
  apiBaseUrl: 'http://localhost:8001',
  ticketsEndpointPath: '/api/mobile/tickets',
  sosEndpointPath: '/api/mobile/tickets',
  chatEndpointPath: '/api/mobile/chat',
  transcribeEndpointPath: '/api/mobile/ai/transcribe',
  sttProvider: 'backend_gemini',
  ttsProvider: 'system',
  realtimeProvider: 'openai_realtime',
  connectTimeoutMs: 15000,
  receiveTimeoutMs: 20000,
);
