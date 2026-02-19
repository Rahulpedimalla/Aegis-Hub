import 'dart:async';

import '../../domain/realtime_voice_provider.dart';

class OpenAiRealtimeProvider implements RealtimeVoiceProvider {
  OpenAiRealtimeProvider() : _events = StreamController<RealtimeVoiceEvent>.broadcast();

  final StreamController<RealtimeVoiceEvent> _events;

  @override
  String get providerName => 'openai_realtime';

  @override
  Stream<RealtimeVoiceEvent> get events => _events.stream;

  @override
  Future<void> startSession() async {
    _events.add(
      const RealtimeVoiceEvent(
        type: 'session_started',
        payload: {'provider': 'openai_realtime'},
      ),
    );
  }

  @override
  Future<void> sendUserText(String text) async {
    _events.add(
      RealtimeVoiceEvent(
        type: 'user_text',
        payload: {'text': text},
      ),
    );
  }

  @override
  Future<void> close() async {
    await _events.close();
  }
}
