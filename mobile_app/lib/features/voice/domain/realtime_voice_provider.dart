import 'dart:async';

class RealtimeVoiceEvent {
  const RealtimeVoiceEvent({
    required this.type,
    required this.payload,
  });

  final String type;
  final Map<String, dynamic> payload;
}

abstract class RealtimeVoiceProvider {
  String get providerName;
  Stream<RealtimeVoiceEvent> get events;

  Future<void> startSession();
  Future<void> sendUserText(String text);
  Future<void> close();
}
