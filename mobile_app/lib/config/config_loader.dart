import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'app_config.dart';

class ConfigLoader {
  ConfigLoader({FlutterSecureStorage? secureStorage})
      : _secureStorage = secureStorage ?? const FlutterSecureStorage();

  static const _apiUrlOverrideKey = 'api_base_url_override';
  static const _tokenOverrideKey = 'auth_bearer_token_override';

  final FlutterSecureStorage _secureStorage;

  Future<AppConfig> load() async {
    final fromAsset = await _loadAssetConfig();

    final envUrl = const String.fromEnvironment('AEGIS_API_BASE_URL');
    final envToken = const String.fromEnvironment('AEGIS_AUTH_BEARER_TOKEN');

    final secureUrl = kIsWeb ? null : await _safeReadSecure(_apiUrlOverrideKey);
    final secureToken = kIsWeb ? null : await _safeReadSecure(_tokenOverrideKey);

    final resolvedUrl = envUrl.isNotEmpty
        ? envUrl
        : ((secureUrl?.isNotEmpty ?? false) ? secureUrl! : fromAsset.apiBaseUrl);
    final resolvedToken = envToken.isNotEmpty
        ? envToken
        : ((secureToken?.isNotEmpty ?? false) ? secureToken : fromAsset.bearerToken);

    var normalizedUrl = resolvedUrl.trim();
    if (normalizedUrl.isEmpty) {
      normalizedUrl = _defaultConfig.apiBaseUrl;
    }
    // 10.0.2.2 is Android emulator loopback alias and is unreachable from web.
    if (kIsWeb && normalizedUrl.contains('10.0.2.2')) {
      normalizedUrl = normalizedUrl.replaceAll('10.0.2.2', 'localhost');
    }

    return fromAsset.copyWith(
      apiBaseUrl: normalizedUrl,
      bearerToken: resolvedToken,
    );
  }

  Future<AppConfig> _loadAssetConfig() async {
    try {
      final rawJson = await rootBundle.loadString('assets/config/runtime_config.json');
      final decoded = jsonDecode(rawJson) as Map<String, dynamic>;
      return AppConfig.fromJson(decoded);
    } catch (_) {
      return _defaultConfig;
    }
  }

  Future<String?> _safeReadSecure(String key) async {
    try {
      return await _secureStorage.read(key: key);
    } catch (_) {
      return null;
    }
  }

  static const AppConfig _defaultConfig = AppConfig(
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
}
