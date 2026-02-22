import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:record/record.dart';

import '../../../core/providers.dart';
import '../../../shared/models/location_point.dart';
import '../../../shared/models/media_attachment.dart';
import '../domain/entities/ticket_payload.dart';
import '../domain/entities/ticket_submission_result.dart';
import '../domain/entities/ticket_type.dart';
import '../domain/entities/voice_transcript.dart';

class NormalTicketState {
  const NormalTicketState({
    this.description = '',
    this.images = const [],
    this.videos = const [],
    this.voiceNote,
    this.voiceTranscript,
    this.location,
    this.isRecordingVoiceNote = false,
    this.isSubmitting = false,
    this.lastResult,
    this.errorMessage,
  });

  final String description;
  final List<MediaAttachment> images;
  final List<MediaAttachment> videos;
  final MediaAttachment? voiceNote;
  final VoiceTranscript? voiceTranscript;
  final LocationPoint? location;
  final bool isRecordingVoiceNote;
  final bool isSubmitting;
  final TicketSubmissionResult? lastResult;
  final String? errorMessage;

  NormalTicketState copyWith({
    String? description,
    List<MediaAttachment>? images,
    List<MediaAttachment>? videos,
    MediaAttachment? voiceNote,
    VoiceTranscript? voiceTranscript,
    bool replaceVoice = false,
    LocationPoint? location,
    bool? isRecordingVoiceNote,
    bool? isSubmitting,
    TicketSubmissionResult? lastResult,
    String? errorMessage,
    bool clearError = false,
    bool clearResult = false,
    bool clearVoice = false,
  }) {
    return NormalTicketState(
      description: description ?? this.description,
      images: images ?? this.images,
      videos: videos ?? this.videos,
      voiceNote: clearVoice ? null : (replaceVoice ? voiceNote : (voiceNote ?? this.voiceNote)),
      voiceTranscript:
          clearVoice ? null : (replaceVoice ? voiceTranscript : (voiceTranscript ?? this.voiceTranscript)),
      location: location ?? this.location,
      isRecordingVoiceNote: isRecordingVoiceNote ?? this.isRecordingVoiceNote,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      lastResult: clearResult ? null : (lastResult ?? this.lastResult),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class NormalTicketController extends StateNotifier<NormalTicketState> {
  NormalTicketController(this._ref)
      : _picker = ImagePicker(),
        super(const NormalTicketState()) {
    refreshLocation();
  }

  final Ref _ref;
  final ImagePicker _picker;
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  DateTime? _voiceStartAt;
  DateTime? _lastSpeechAt;
  bool _heardSpeech = false;
  bool _autoStopping = false;

  void setDescription(String description) {
    state = state.copyWith(description: description, clearError: true);
  }

  Future<void> refreshLocation() async {
    try {
      final location = await _ref.read(locationServiceProvider).getCurrentLocation();
      state = state.copyWith(location: location, clearError: true);
    } catch (_) {
      state = state.copyWith(errorMessage: 'Unable to refresh location right now.');
    }
  }

  Future<void> pickImages() async {
    try {
      final files = await _picker.pickMultiImage(imageQuality: 85);
      if (files.isEmpty) {
        return;
      }
      final attachments = <MediaAttachment>[];
      for (final file in files) {
        final bytes = await file.readAsBytes();
        attachments.add(
          await MediaAttachment.fromBytes(
            bytes: bytes,
            path: file.path,
            fileName: file.name,
            mimeType: 'image/jpeg',
            kind: MediaKind.image,
          ),
        );
      }
      state = state.copyWith(images: [...state.images, ...attachments], clearError: true);
    } catch (_) {
      state = state.copyWith(errorMessage: 'Could not access image picker on this device/browser.');
    }
  }

  Future<void> pickVideo() async {
    try {
      final file = await _picker.pickVideo(source: ImageSource.gallery, maxDuration: const Duration(minutes: 2));
      if (file == null) {
        return;
      }
      final bytes = await file.readAsBytes();
      final attachment = await MediaAttachment.fromBytes(
        bytes: bytes,
        path: file.path,
        fileName: file.name,
        mimeType: 'video/mp4',
        kind: MediaKind.video,
      );
      state = state.copyWith(videos: [...state.videos, attachment], clearError: true);
    } catch (_) {
      state = state.copyWith(errorMessage: 'Could not access video picker on this device/browser.');
    }
  }

  void removeImageAt(int index) {
    if (index < 0 || index >= state.images.length) {
      return;
    }
    final next = [...state.images]..removeAt(index);
    state = state.copyWith(images: next, clearError: true);
  }

  void removeVideoAt(int index) {
    if (index < 0 || index >= state.videos.length) {
      return;
    }
    final next = [...state.videos]..removeAt(index);
    state = state.copyWith(videos: next, clearError: true);
  }

  Future<void> startVoiceNote() async {
    if (state.isRecordingVoiceNote) {
      return;
    }
    final ok = await _ref.read(audioCaptureServiceProvider).startRecording();
    if (!ok) {
      state = state.copyWith(errorMessage: 'Unable to start voice note recording.');
      return;
    }
    // Best-effort live STT fallback for browsers where file transcription may fail.
    await _ref.read(liveTranscriptionServiceProvider).start(localeId: 'en_IN');
    _startSilenceMonitor();
    state = state.copyWith(isRecordingVoiceNote: true, clearError: true);
  }

  Future<void> stopVoiceNote() async {
    if (!state.isRecordingVoiceNote) {
      return;
    }
    _stopSilenceMonitor();
    final liveTranscript = await _ref.read(liveTranscriptionServiceProvider).stopAndCollect();
    final recording = await _ref.read(audioCaptureServiceProvider).stopRecording();
    if ((recording?.path ?? '').isEmpty) {
      state = state.copyWith(
        isRecordingVoiceNote: false,
      );
      return;
    }

    try {
      final attachment = await MediaAttachment.fromRecordingPath(
        path: recording!.path,
        fileName: recording.fileName,
        mimeType: recording.mimeType,
        kind: MediaKind.audio,
      );

      VoiceTranscript? transcript;
      String? warningMessage;
      try {
        transcript = await _ref.read(sttProviderProvider).transcribeFile(
              audioPath: recording.path,
              audioMimeType: recording.mimeType,
              audioFileName: recording.fileName,
            );
        if ((transcript.rawText).trim().isEmpty) {
          transcript = null;
          warningMessage = 'Voice note saved, but no transcript was produced.';
        }
      } catch (_) {
        warningMessage = 'Voice note saved, but transcription is unavailable right now.';
      }
      if (transcript == null && liveTranscript.isNotEmpty) {
        transcript = VoiceTranscript(
          rawText: liveTranscript,
          provider: 'browser_live_stt',
          model: 'speech_to_text',
          language: 'en-IN',
        );
        warningMessage = null;
      }

      final mergedDescription = _mergeTranscriptIntoDescription(
        currentText: state.description,
        transcriptText: transcript?.rawText ?? '',
      );

      state = state.copyWith(
        isRecordingVoiceNote: false,
        description: mergedDescription,
        voiceNote: attachment,
        voiceTranscript: transcript,
        replaceVoice: true,
        errorMessage: warningMessage,
        clearError: warningMessage == null,
      );
    } catch (_) {
      state = state.copyWith(
        isRecordingVoiceNote: false,
        errorMessage: 'Could not process voice note on this device/browser.',
      );
    }
  }

  void clearVoiceNote() {
    state = state.copyWith(clearVoice: true);
  }

  Future<void> submitTicket() async {
    if (state.isSubmitting) {
      return;
    }
    if (state.description.trim().isEmpty && state.voiceTranscript == null && state.voiceNote == null) {
      state = state.copyWith(errorMessage: 'Add text or voice note before submitting.');
      return;
    }

    state = state.copyWith(isSubmitting: true, clearError: true, clearResult: true);
    final location = state.location ?? await _ref.read(locationServiceProvider).getCurrentLocation();
    final device = await _ref.read(deviceContextServiceProvider).collect();
    final payload = TicketPayload(
      ticketType: TicketType.normal,
      text: state.description.trim().isNotEmpty
          ? state.description.trim()
          : (state.voiceTranscript?.rawText ?? (state.voiceNote != null ? 'Voice note attached by reporter.' : '')),
      location: location,
      deviceInfo: device,
      timestampUtc: DateTime.now().toUtc(),
      voiceTranscript: state.voiceTranscript,
      audioFile: state.voiceNote,
      images: state.images,
      videos: state.videos,
      metadata: const {
        'permissions': {
          'location': 'granted',
          'microphone': 'granted_or_optional',
          'camera': 'granted_or_optional',
        },
      },
    );

    try {
      final result = await _ref.read(ticketRepositoryProvider).submitTicket(payload);
      _ref.read(activeChatSessionIdProvider.notifier).state = result.chatSessionId;
      _ref.read(latestReassuranceMessageProvider.notifier).state = result.reassuranceMessage ??
          'Ticket received. Stay safe and keep this chat open for follow-up coordination.';
      state = state.copyWith(
        isSubmitting: false,
        lastResult: result,
      );
    } catch (_) {
      state = state.copyWith(
        isSubmitting: false,
        errorMessage: 'Ticket submission failed. Please retry.',
      );
    }
  }

  String _mergeTranscriptIntoDescription({
    required String currentText,
    required String transcriptText,
  }) {
    final normalizedCurrent = currentText.trim();
    final normalizedTranscript = transcriptText.trim();
    if (normalizedTranscript.isEmpty) {
      return currentText;
    }
    if (normalizedCurrent.isEmpty) {
      return normalizedTranscript;
    }
    if (normalizedCurrent.toLowerCase().contains(normalizedTranscript.toLowerCase())) {
      return currentText;
    }
    return '$normalizedCurrent\n$normalizedTranscript';
  }

  void _startSilenceMonitor() {
    _stopSilenceMonitor();
    _voiceStartAt = DateTime.now().toUtc();
    _lastSpeechAt = _voiceStartAt;
    _heardSpeech = false;
    _autoStopping = false;

    _amplitudeSubscription = _ref
        .read(audioCaptureServiceProvider)
        .onAmplitudeChanged(const Duration(milliseconds: 250))
        .listen((amplitude) async {
      if (_autoStopping || !state.isRecordingVoiceNote || state.isSubmitting) {
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

      if (!_heardSpeech || _lastSpeechAt == null || _voiceStartAt == null) {
        return;
      }

      final silenceFor = now.difference(_lastSpeechAt!);
      final recordingFor = now.difference(_voiceStartAt!);
      if (recordingFor >= const Duration(seconds: 2) && silenceFor >= const Duration(seconds: 3)) {
        _autoStopping = true;
        await stopVoiceNote();
      }
    });
  }

  void _stopSilenceMonitor() {
    _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
    _voiceStartAt = null;
    _lastSpeechAt = null;
    _heardSpeech = false;
    _autoStopping = false;
  }

  @override
  void dispose() {
    _stopSilenceMonitor();
    _ref.read(liveTranscriptionServiceProvider).cancel();
    super.dispose();
  }
}

final normalTicketControllerProvider =
    StateNotifierProvider<NormalTicketController, NormalTicketState>(
  (ref) => NormalTicketController(ref),
);
