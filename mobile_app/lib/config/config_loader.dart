import 'dart:convert';

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
    final rawJson = await rootBundle.loadString('assets/config/runtime_config.json');
    final decoded = jsonDecode(rawJson) as Map<String, dynamic>;
    final fromAsset = AppConfig.fromJson(decoded);

    final envUrl = const String.fromEnvironment('AEGIS_API_BASE_URL');
    final envToken = const String.fromEnvironment('AEGIS_AUTH_BEARER_TOKEN');

    final secureUrl = await _secureStorage.read(key: _apiUrlOverrideKey);
    final secureToken = await _secureStorage.read(key: _tokenOverrideKey);

    final resolvedUrl = (secureUrl?.isNotEmpty ?? false)
        ? secureUrl!
        : (envUrl.isNotEmpty ? envUrl : fromAsset.apiBaseUrl);
    final resolvedToken = (secureToken?.isNotEmpty ?? false)
        ? secureToken
        : (envToken.isNotEmpty ? envToken : fromAsset.bearerToken);

    return fromAsset.copyWith(
      apiBaseUrl: resolvedUrl,
      bearerToken: resolvedToken,
    );
  }
}
