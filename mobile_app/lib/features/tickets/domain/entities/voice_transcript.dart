class TranscriptSegment {
  const TranscriptSegment({
    required this.startMs,
    required this.endMs,
    required this.text,
    this.confidence,
    this.speaker,
  });

  final int startMs;
  final int endMs;
  final String text;
  final double? confidence;
  final String? speaker;

  factory TranscriptSegment.fromJson(Map<String, dynamic> json) {
    return TranscriptSegment(
      startMs: int.tryParse((json['start_ms'] ?? '0').toString()) ?? 0,
      endMs: int.tryParse((json['end_ms'] ?? '0').toString()) ?? 0,
      text: (json['text'] ?? '').toString(),
      confidence: double.tryParse((json['confidence'] ?? '').toString()),
      speaker: json['speaker']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'start_ms': startMs,
      'end_ms': endMs,
      'text': text,
      'confidence': confidence,
      'speaker': speaker,
    };
  }
}

class VoiceTranscript {
  const VoiceTranscript({
    required this.rawText,
    required this.provider,
    required this.model,
    required this.language,
    this.segments = const [],
  });

  final String rawText;
  final String provider;
  final String model;
  final String language;
  final List<TranscriptSegment> segments;

  factory VoiceTranscript.fromJson(Map<String, dynamic> json) {
    final rawSegments = (json['segments'] as List<dynamic>? ?? const []);
    return VoiceTranscript(
      rawText: (json['raw_text'] ?? '').toString(),
      provider: (json['provider'] ?? '').toString(),
      model: (json['model'] ?? '').toString(),
      language: (json['language'] ?? '').toString(),
      segments: rawSegments
          .whereType<Map>()
          .map((segment) => TranscriptSegment.fromJson(segment.cast<String, dynamic>()))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'raw_text': rawText,
      'segments': segments.map((segment) => segment.toJson()).toList(),
      'provider': provider,
      'model': model,
      'language': language,
    };
  }
}
