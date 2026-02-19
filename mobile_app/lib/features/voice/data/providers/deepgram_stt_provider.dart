import '../../../tickets/domain/entities/voice_transcript.dart';
import '../../domain/stt_provider.dart';

class DeepgramSttProvider implements SttProvider {
  @override
  String get providerName => 'deepgram';

  @override
  Future<VoiceTranscript> transcribeFile({
    required String audioPath,
    String languageCode = 'en',
  }) async {
    // Integration point: replace with Deepgram speech-to-text API call.
    return const VoiceTranscript(
      rawText: '[raw transcript pending provider integration]',
      provider: 'deepgram',
      model: 'flux-general-en',
      language: 'en',
    );
  }
}
