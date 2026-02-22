import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:record/record.dart';

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
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  DateTime? _sosRecordingStartedAt;
  DateTime? _lastSpeechAt;
  bool _heardSpeech = false;
  bool _autoSubmitting = false;

  static const Map<String, int> _wordNumbers = {
    'one': 1,
    'two': 2,
    'three': 3,
    'four': 4,
    'five': 5,
    'six': 6,
    'seven': 7,
    'eight': 8,
    'nine': 9,
    'ten': 10,
    'eleven': 11,
    'twelve': 12,
    'thirteen': 13,
    'fourteen': 14,
    'fifteen': 15,
    'sixteen': 16,
    'seventeen': 17,
    'eighteen': 18,
    'nineteen': 19,
    'twenty': 20,
  };

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
      // Best-effort live STT fallback for browser recording paths.
      await _ref.read(liveTranscriptionServiceProvider).start(localeId: 'en_IN');
      _startSilenceMonitor();
      state = state.copyWith(
        isRecording: true,
        startedAt: DateTime.now().toUtc(),
        location: location,
        statusText: 'SOS active: listening (speak affected count clearly)',
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
    _stopSilenceMonitor();
    await _ref.read(liveTranscriptionServiceProvider).cancel();
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
      _stopSilenceMonitor();
      state = state.copyWith(isSubmitting: true, statusText: 'Preparing SOS payload');
      final liveTranscript = await _ref.read(liveTranscriptionServiceProvider).stopAndCollect();
      final recording = await _ref.read(audioCaptureServiceProvider).stopRecording();
      final location = state.location ?? await _ref.read(locationServiceProvider).getCurrentLocation();
      final device = await _ref.read(deviceContextServiceProvider).collect();

      VoiceTranscript transcript = const VoiceTranscript(
        rawText: '',
        provider: 'none',
        model: 'none',
        language: 'en',
      );
      MediaAttachment? audioAttachment;

      if ((recording?.path ?? '').isNotEmpty) {
        final recordedPath = recording!.path;
        final recordedFileName = recording.fileName;
        final recordedMimeType = recording.mimeType;
        try {
          audioAttachment = await MediaAttachment.fromRecordingPath(
            path: recordedPath,
            fileName: recordedFileName,
            mimeType: recordedMimeType,
            kind: MediaKind.audio,
          );
        } catch (_) {
          // Keep SOS flow resilient even if audio packaging fails.
        }

        try {
          transcript = await _ref.read(sttProviderProvider).transcribeFile(
                audioPath: recordedPath,
                audioMimeType: recordedMimeType,
                audioFileName: recordedFileName,
              );
        } catch (_) {
          // Keep SOS flow resilient even if transcription fails.
        }
      }
      if (transcript.rawText.trim().isEmpty && liveTranscript.isNotEmpty) {
        transcript = VoiceTranscript(
          rawText: liveTranscript,
          provider: 'browser_live_stt',
          model: 'speech_to_text',
          language: 'en-IN',
        );
      }

      final payload = TicketPayload(
        ticketType: TicketType.sos,
        text: transcript.rawText.trim().isNotEmpty
            ? transcript.rawText.trim()
            : (audioAttachment != null ? '' : 'SOS triggered via mobile app'),
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

      final peopleHint = _extractPeopleHint(transcript.rawText);
      state = state.copyWith(
        previewTranscript: transcript.rawText,
        statusText: peopleHint != null ? 'Submitting SOS (detected $peopleHint affected)' : 'Submitting SOS',
      );
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

  int? _extractPeopleHint(String transcript) {
    final text = transcript.toLowerCase();
    final numeric = RegExp(r'\b(\d{1,3})\b').allMatches(text);
    var maxValue = 0;
    for (final match in numeric) {
      final value = int.tryParse(match.group(1) ?? '');
      if (value != null && value > maxValue) {
        maxValue = value;
      }
    }

    for (final token in text.split(RegExp(r'[^a-z0-9]+'))) {
      final value = _wordNumbers[token];
      if (value != null && value > maxValue) {
        maxValue = value;
      }
    }

    if (maxValue <= 0) {
      return null;
    }
    return maxValue;
  }

  void _startSilenceMonitor() {
    _stopSilenceMonitor();
    _sosRecordingStartedAt = DateTime.now().toUtc();
    _lastSpeechAt = _sosRecordingStartedAt;
    _heardSpeech = false;
    _autoSubmitting = false;

    _amplitudeSubscription = _ref
        .read(audioCaptureServiceProvider)
        .onAmplitudeChanged(const Duration(milliseconds: 250))
        .listen((amplitude) async {
      if (_autoSubmitting || !state.isRecording || state.isSubmitting) {
        return;
      }

      final now = DateTime.now().toUtc();
      final dbfs = amplitude.current;
      final isSpeechFrame = dbfs > -45;
      if (isSpeechFrame) {
        _heardSpeech = true;
        _lastSpeechAt = now;
        return;
      }

      if (!_heardSpeech || _lastSpeechAt == null || _sosRecordingStartedAt == null) {
        return;
      }

      final silenceFor = now.difference(_lastSpeechAt!);
      final recordingFor = now.difference(_sosRecordingStartedAt!);
      if (recordingFor >= const Duration(seconds: 2) && silenceFor >= const Duration(seconds: 3)) {
        _autoSubmitting = true;
        await endAndSubmit();
      }
    });
  }

  void _stopSilenceMonitor() {
    _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
    _sosRecordingStartedAt = null;
    _lastSpeechAt = null;
    _heardSpeech = false;
    _autoSubmitting = false;
  }

  @override
  void dispose() {
    _stopSilenceMonitor();
    _ref.read(liveTranscriptionServiceProvider).cancel();
    super.dispose();
  }
}

final sosControllerProvider = StateNotifierProvider<SosController, SosState>(
  (ref) => SosController(ref),
);
