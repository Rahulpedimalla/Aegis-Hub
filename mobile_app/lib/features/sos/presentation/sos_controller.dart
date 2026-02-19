import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../../../shared/models/location_point.dart';
import '../../../shared/models/media_attachment.dart';
import '../../tickets/domain/entities/ticket_payload.dart';
import '../../tickets/domain/entities/ticket_submission_result.dart';
import '../../tickets/domain/entities/ticket_type.dart';
import '../../tickets/domain/entities/voice_transcript.dart';

class SosState {
  const SosState({
    this.isRecording = false,
    this.isSubmitting = false,
    this.startedAt,
    this.location,
    this.statusText = 'Ready',
    this.previewTranscript = '',
    this.lastResult,
    this.errorMessage,
  });

  final bool isRecording;
  final bool isSubmitting;
  final DateTime? startedAt;
  final LocationPoint? location;
  final String statusText;
  final String previewTranscript;
  final TicketSubmissionResult? lastResult;
  final String? errorMessage;

  SosState copyWith({
    bool? isRecording,
    bool? isSubmitting,
    DateTime? startedAt,
    LocationPoint? location,
    String? statusText,
    String? previewTranscript,
    TicketSubmissionResult? lastResult,
    String? errorMessage,
    bool clearError = false,
    bool clearResult = false,
  }) {
    return SosState(
      isRecording: isRecording ?? this.isRecording,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      startedAt: startedAt ?? this.startedAt,
      location: location ?? this.location,
      statusText: statusText ?? this.statusText,
      previewTranscript: previewTranscript ?? this.previewTranscript,
      lastResult: clearResult ? null : (lastResult ?? this.lastResult),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class SosController extends StateNotifier<SosState> {
  SosController(this._ref) : super(const SosState());

  final Ref _ref;

  Future<void> startSos() async {
    if (state.isRecording || state.isSubmitting) {
      return;
    }

    try {
      final locationFuture = _ref.read(locationServiceProvider).getCurrentLocation();
      final started = await _ref.read(audioCaptureServiceProvider).startRecording();
      if (!started) {
        state = state.copyWith(
          errorMessage: 'Microphone permission denied or recorder unavailable.',
          statusText: 'Mic unavailable',
        );
        return;
      }

      final location = await locationFuture;
      state = state.copyWith(
        isRecording: true,
        startedAt: DateTime.now().toUtc(),
        location: location,
        statusText: 'SOS active: listening',
        clearError: true,
        clearResult: true,
      );
    } catch (_) {
      state = state.copyWith(
        isRecording: false,
        isSubmitting: false,
        statusText: 'SOS start failed',
        errorMessage: 'Unable to start SOS capture on this device/browser.',
      );
    }
  }

  Future<void> cancelSos() async {
    await _ref.read(audioCaptureServiceProvider).cancelRecording();
    state = state.copyWith(
      isRecording: false,
      isSubmitting: false,
      statusText: 'SOS cancelled',
      previewTranscript: '',
    );
  }

  Future<void> endAndSubmit() async {
    if (!state.isRecording || state.isSubmitting) {
      return;
    }

    try {
      state = state.copyWith(isSubmitting: true, statusText: 'Preparing SOS payload');
      final audioPath = await _ref.read(audioCaptureServiceProvider).stopRecording();
      final location = state.location ?? await _ref.read(locationServiceProvider).getCurrentLocation();
      final device = await _ref.read(deviceContextServiceProvider).collect();

      VoiceTranscript transcript = const VoiceTranscript(
        rawText: '',
        provider: 'none',
        model: 'none',
        language: 'en',
      );
      MediaAttachment? audioAttachment;

      if (audioPath != null && audioPath.isNotEmpty) {
        try {
          transcript = await _ref.read(sttProviderProvider).transcribeFile(audioPath: audioPath);
          if (!kIsWeb) {
            audioAttachment = await MediaAttachment.fromPath(
              path: audioPath,
              fileName: 'sos_audio.m4a',
              mimeType: 'audio/m4a',
              kind: MediaKind.audio,
            );
          }
        } catch (_) {
          // Keep SOS flow resilient even if media attachment/transcription fails.
        }
      }

      final payload = TicketPayload(
        ticketType: TicketType.sos,
        text: transcript.rawText.isNotEmpty ? transcript.rawText : 'SOS triggered via mobile app',
        location: location,
        deviceInfo: device,
        timestampUtc: DateTime.now().toUtc(),
        voiceTranscript: transcript,
        audioFile: audioAttachment,
        metadata: const {
          'permissions': {
            'location': 'granted_or_fallback',
            'microphone': 'granted_or_fallback',
          },
        },
      );

      state = state.copyWith(previewTranscript: transcript.rawText, statusText: 'Submitting SOS');
      final result = await _ref.read(ticketRepositoryProvider).submitTicket(payload);
      _ref.read(activeChatSessionIdProvider.notifier).state = result.chatSessionId;
      _ref.read(latestReassuranceMessageProvider.notifier).state = result.reassuranceMessage ??
          'SOS received. Stay in a safe position if possible. Support coordination is in progress.';
      state = state.copyWith(
        isRecording: false,
        isSubmitting: false,
        statusText: result.isQueued ? 'SOS queued safely' : 'SOS submitted',
        lastResult: result,
      );
    } catch (_) {
      state = state.copyWith(
        isRecording: false,
        isSubmitting: false,
        statusText: 'Submission failed',
        errorMessage: 'Could not submit SOS. Please retry.',
      );
    }
  }
}

final sosControllerProvider = StateNotifierProvider<SosController, SosState>(
  (ref) => SosController(ref),
);
