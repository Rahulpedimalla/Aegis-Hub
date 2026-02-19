import 'package:uuid/uuid.dart';

import '../../../../shared/models/device_context.dart';
import '../../../../shared/models/location_point.dart';
import '../../../../shared/models/media_attachment.dart';
import 'ticket_type.dart';
import 'voice_transcript.dart';

class TicketPayload {
  static final Uuid _uuid = Uuid();

  TicketPayload({
    required this.ticketType,
    required this.text,
    required this.location,
    required this.deviceInfo,
    required this.timestampUtc,
    String? idempotencyKey,
    String? externalId,
    this.voiceTranscript,
    this.audioFile,
    this.images = const [],
    this.videos = const [],
    this.metadata = const {},
  })  : idempotencyKey = idempotencyKey ?? _uuid.v4(),
        externalId = externalId ?? 'APP-${_uuid.v4().substring(0, 10).toUpperCase()}';

  final TicketType ticketType;
  final String text;
  final LocationPoint location;
  final DeviceContext deviceInfo;
  final DateTime timestampUtc;
  final String idempotencyKey;
  final String externalId;
  final VoiceTranscript? voiceTranscript;
  final MediaAttachment? audioFile;
  final List<MediaAttachment> images;
  final List<MediaAttachment> videos;
  final Map<String, dynamic> metadata;

  factory TicketPayload.fromQueueJson(Map<String, dynamic> json) {
    final imagesRaw = (json['images'] as List<dynamic>? ?? const []);
    final videosRaw = (json['videos'] as List<dynamic>? ?? const []);
    final transcriptRaw = json['voice_transcript'];
    final audioRaw = json['audio_file'];
    final locationRaw = json['location'];
    final deviceRaw = json['device_info'];
    return TicketPayload(
      ticketType: ((json['ticket_type'] ?? 'Normal').toString().toUpperCase() == 'SOS')
          ? TicketType.sos
          : TicketType.normal,
      text: (json['text'] ?? '').toString(),
      location: locationRaw is Map<String, dynamic>
          ? LocationPoint.fromJson(locationRaw)
          : locationRaw is Map
              ? LocationPoint.fromJson(locationRaw.cast<String, dynamic>())
              : const LocationPoint(latitude: 0, longitude: 0, accuracyMeters: 0),
      deviceInfo: deviceRaw is Map<String, dynamic>
          ? DeviceContext.fromJson(deviceRaw)
          : deviceRaw is Map
              ? DeviceContext.fromJson(deviceRaw.cast<String, dynamic>())
              : const DeviceContext(
                  deviceIdHash: '',
                  platform: '',
                  osVersion: '',
                  appVersion: '',
                  model: '',
                  networkType: '',
                  batteryLevel: 0,
                  locale: '',
                  timezone: '',
                ),
      timestampUtc: DateTime.tryParse((json['timestamp'] ?? '').toString()) ?? DateTime.now().toUtc(),
      idempotencyKey: ((json['idempotency_key'] ?? '').toString().isEmpty)
          ? null
          : (json['idempotency_key'] ?? '').toString(),
      externalId: ((json['external_id'] ?? '').toString().isEmpty)
          ? null
          : (json['external_id'] ?? '').toString(),
      voiceTranscript: transcriptRaw is Map<String, dynamic>
          ? VoiceTranscript.fromJson(transcriptRaw)
          : transcriptRaw is Map
              ? VoiceTranscript.fromJson(transcriptRaw.cast<String, dynamic>())
              : null,
      audioFile: audioRaw is Map<String, dynamic>
          ? MediaAttachment.fromJson(audioRaw)
          : audioRaw is Map
              ? MediaAttachment.fromJson(audioRaw.cast<String, dynamic>())
              : null,
      images: imagesRaw
          .whereType<Map>()
          .map((item) => MediaAttachment.fromJson(item.cast<String, dynamic>()))
          .toList(),
      videos: videosRaw
          .whereType<Map>()
          .map((item) => MediaAttachment.fromJson(item.cast<String, dynamic>()))
          .toList(),
      metadata: json['metadata'] is Map<String, dynamic>
          ? json['metadata'] as Map<String, dynamic>
          : json['metadata'] is Map
              ? (json['metadata'] as Map).cast<String, dynamic>()
              : const {},
    );
  }

  Map<String, dynamic> toMetadataJson({
    required String captureMode,
    required String connectivityState,
  }) {
    return {
      'ticket_id_client': externalId,
      'external_id': externalId,
      'ticket_type': ticketType.value,
      'text': text,
      'voice_transcript': voiceTranscript?.toJson(),
      'audio_file_ref': audioFile?.toJson(),
      'image': images.map((item) => item.toJson()).toList(),
      'video': videos.map((item) => item.toJson()).toList(),
      'latitude': location.latitude,
      'longitude': location.longitude,
      'location_accuracy_m': location.accuracyMeters,
      'timestamp': timestampUtc.toIso8601String(),
      'device_info': deviceInfo.toJson(),
      'metadata': {
        'schema_version': '1.0.0',
        'idempotency_key': idempotencyKey,
        'capture_mode': captureMode,
        'connectivity_state': connectivityState,
        ...metadata,
      },
    };
  }

  Map<String, dynamic> toQueueJson() {
    return {
      'ticket_type': ticketType.value,
      'text': text,
      'location': location.toJson(),
      'device_info': deviceInfo.toJson(),
      'timestamp': timestampUtc.toIso8601String(),
      'idempotency_key': idempotencyKey,
      'external_id': externalId,
      'voice_transcript': voiceTranscript?.toJson(),
      'audio_file': audioFile?.toJson(),
      'images': images.map((item) => item.toJson()).toList(),
      'videos': videos.map((item) => item.toJson()).toList(),
      'metadata': metadata,
    };
  }
}
