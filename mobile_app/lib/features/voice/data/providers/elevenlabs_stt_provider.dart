import '../../../tickets/domain/entities/voice_transcript.dart';
import '../../domain/stt_provider.dart';

class ElevenLabsSttProvider implements SttProvider {
  @override
  String get providerName => 'elevenlabs';

  @override
  Future<VoiceTranscript> transcribeFile({
    required String audioPath,
    String languageCode = 'en',
  }) async {
    return const VoiceTranscript(
      rawText: '[raw transcript pending provider integration]',
      provider: 'elevenlabs',
      model: 'scribe_v2',
      language: 'en',
    );
  }
}
