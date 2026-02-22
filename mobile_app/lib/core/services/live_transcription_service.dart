import 'live_transcription_service_base.dart';
import 'live_transcription_service_stub.dart'
    if (dart.library.html) 'live_transcription_service_web.dart' as impl;

export 'live_transcription_service_base.dart';

LiveTranscriptionService createLiveTranscriptionService() => impl.createLiveTranscriptionService();
