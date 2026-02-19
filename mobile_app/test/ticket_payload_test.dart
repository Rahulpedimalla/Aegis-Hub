import 'package:flutter_test/flutter_test.dart';

import 'package:aegis_hub_mobile/features/tickets/domain/entities/ticket_payload.dart';
import 'package:aegis_hub_mobile/features/tickets/domain/entities/ticket_type.dart';
import 'package:aegis_hub_mobile/features/tickets/domain/entities/voice_transcript.dart';
import 'package:aegis_hub_mobile/shared/models/device_context.dart';
import 'package:aegis_hub_mobile/shared/models/location_point.dart';
import 'package:aegis_hub_mobile/shared/models/media_attachment.dart';

void main() {
  test('TicketPayload queue serialization round-trip keeps required fields', () {
    final payload = TicketPayload(
      ticketType: TicketType.sos,
      text: 'Test emergency',
      location: const LocationPoint(latitude: 17.385, longitude: 78.4867, accuracyMeters: 10),
      deviceInfo: const DeviceContext(
        deviceIdHash: 'hash',
        platform: 'android',
        osVersion: '14',
        appVersion: '1.0.0+1',
        model: 'Pixel',
        networkType: 'wifi',
        batteryLevel: 0.8,
        locale: 'en_US',
        timezone: 'IST',
      ),
      timestampUtc: DateTime.parse('2026-02-19T12:00:00Z'),
      voiceTranscript: const VoiceTranscript(
        rawText: 'help needed',
        provider: 'deepgram',
        model: 'flux',
        language: 'en',
      ),
      audioFile: const MediaAttachment(
        path: '/tmp/a.m4a',
        fileName: 'a.m4a',
        mimeType: 'audio/m4a',
        sizeBytes: 1,
        sha256: 'abc',
        kind: MediaKind.audio,
      ),
      metadata: const {'schema_version': '1.0.0'},
    );

    final roundTrip = TicketPayload.fromQueueJson(payload.toQueueJson());
    expect(roundTrip.ticketType, TicketType.sos);
    expect(roundTrip.text, 'Test emergency');
    expect(roundTrip.location.latitude, 17.385);
    expect(roundTrip.voiceTranscript?.rawText, 'help needed');
    expect(roundTrip.audioFile?.fileName, 'a.m4a');
  });
}
