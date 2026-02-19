import '../../tickets/domain/entities/voice_transcript.dart';

abstract class SttProvider {
  String get providerName;

  Future<VoiceTranscript> transcribeFile({
    required String audioPath,
    String languageCode = 'en',
  });
}
