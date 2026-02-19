import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

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
      voiceNote: clearVoice ? null : (voiceNote ?? this.voiceNote),
      voiceTranscript: clearVoice ? null : (voiceTranscript ?? this.voiceTranscript),
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

  void setDescription(String description) {
    state = state.copyWith(description: description, clearError: true);
  }

  Future<void> refreshLocation() async {
    final location = await _ref.read(locationServiceProvider).getCurrentLocation();
    state = state.copyWith(location: location);
  }

  Future<void> pickImages() async {
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
  }

  Future<void> pickVideo() async {
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
    state = state.copyWith(isRecordingVoiceNote: true, clearError: true);
  }

  Future<void> stopVoiceNote() async {
    if (!state.isRecordingVoiceNote) {
      return;
    }
    try {
      final path = await _ref.read(audioCaptureServiceProvider).stopRecording();
      if (path == null || path.isEmpty) {
        state = state.copyWith(isRecordingVoiceNote: false);
        return;
      }

      MediaAttachment? attachment;
      if (!kIsWeb) {
        attachment = await MediaAttachment.fromPath(
          path: path,
          fileName: 'voice_note.m4a',
          mimeType: 'audio/m4a',
          kind: MediaKind.audio,
        );
      }

      final transcript = await _ref.read(sttProviderProvider).transcribeFile(audioPath: path);
      state = state.copyWith(
        isRecordingVoiceNote: false,
        voiceNote: attachment,
        voiceTranscript: transcript,
        clearError: true,
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
    if (state.description.trim().isEmpty && state.voiceTranscript == null) {
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
          : (state.voiceTranscript?.rawText ?? ''),
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
}

final normalTicketControllerProvider =
    StateNotifierProvider<NormalTicketController, NormalTicketState>(
  (ref) => NormalTicketController(ref),
);
