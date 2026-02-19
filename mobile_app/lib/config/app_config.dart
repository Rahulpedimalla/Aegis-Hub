class AppConfig {
  const AppConfig({
    required this.apiBaseUrl,
    required this.ticketsEndpointPath,
    required this.sosEndpointPath,
    required this.chatEndpointPath,
    required this.sttProvider,
    required this.ttsProvider,
    required this.realtimeProvider,
    required this.connectTimeoutMs,
    required this.receiveTimeoutMs,
    this.bearerToken,
  });

  final String apiBaseUrl;
  final String ticketsEndpointPath;
  final String sosEndpointPath;
  final String chatEndpointPath;
  final String sttProvider;
  final String ttsProvider;
  final String realtimeProvider;
  final int connectTimeoutMs;
  final int receiveTimeoutMs;
  final String? bearerToken;

  AppConfig copyWith({
    String? apiBaseUrl,
    String? ticketsEndpointPath,
    String? sosEndpointPath,
    String? chatEndpointPath,
    String? sttProvider,
    String? ttsProvider,
    String? realtimeProvider,
    int? connectTimeoutMs,
    int? receiveTimeoutMs,
    String? bearerToken,
  }) {
    return AppConfig(
      apiBaseUrl: apiBaseUrl ?? this.apiBaseUrl,
      ticketsEndpointPath: ticketsEndpointPath ?? this.ticketsEndpointPath,
      sosEndpointPath: sosEndpointPath ?? this.sosEndpointPath,
      chatEndpointPath: chatEndpointPath ?? this.chatEndpointPath,
      sttProvider: sttProvider ?? this.sttProvider,
      ttsProvider: ttsProvider ?? this.ttsProvider,
      realtimeProvider: realtimeProvider ?? this.realtimeProvider,
      connectTimeoutMs: connectTimeoutMs ?? this.connectTimeoutMs,
      receiveTimeoutMs: receiveTimeoutMs ?? this.receiveTimeoutMs,
      bearerToken: bearerToken ?? this.bearerToken,
    );
  }

  factory AppConfig.fromJson(Map<String, dynamic> json) {
    return AppConfig(
      apiBaseUrl: (json['apiBaseUrl'] ?? '').toString(),
      ticketsEndpointPath: (json['ticketsEndpointPath'] ?? '/api/mobile/tickets').toString(),
      sosEndpointPath: (json['sosEndpointPath'] ?? '/api/mobile/tickets').toString(),
      chatEndpointPath: (json['chatEndpointPath'] ?? '/api/mobile/chat').toString(),
      sttProvider: (json['sttProvider'] ?? 'deepgram').toString(),
      ttsProvider: (json['ttsProvider'] ?? 'cartesia').toString(),
      realtimeProvider: (json['realtimeProvider'] ?? 'openai_realtime').toString(),
      connectTimeoutMs: int.tryParse((json['connectTimeoutMs'] ?? '15000').toString()) ?? 15000,
      receiveTimeoutMs: int.tryParse((json['receiveTimeoutMs'] ?? '20000').toString()) ?? 20000,
      bearerToken: json['bearerToken']?.toString(),
    );
  }
}
