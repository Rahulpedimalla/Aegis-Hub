// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:async';
import 'dart:js';

import 'live_transcription_service_base.dart';

class _WebLiveTranscriptionService implements LiveTranscriptionService {
  dynamic _recognition;
  bool _isListening = false;
  String _latestTranscript = '';

  @override
  Future<bool> start({String localeId = 'en-IN'}) async {
    final ctor = _speechRecognitionConstructor();
    if (ctor == null) {
      return false;
    }

    await cancel();
    _latestTranscript = '';

    try {
      final recognition = JsObject(ctor);
      recognition['continuous'] = true;
      recognition['interimResults'] = true;
      recognition['maxAlternatives'] = 1;
      recognition['lang'] = localeId.replaceAll('_', '-');

      recognition['onresult'] = JsFunction.withThis((_, dynamic event) {
        final text = _extractTranscript(event);
        if (text.isNotEmpty) {
          _latestTranscript = text;
        }
      });

      recognition['onend'] = JsFunction.withThis((_, dynamic __) {
        _isListening = false;
      });

      recognition.callMethod('start');
      _recognition = recognition;
      _isListening = true;
      return true;
    } catch (_) {
      _recognition = null;
      _isListening = false;
      return false;
    }
  }

  @override
  Future<String> stopAndCollect() async {
    await _stopInternal(abort: false);
    // Allow browser recognition to emit the final onresult callback.
    await Future<void>.delayed(const Duration(milliseconds: 350));
    return _latestTranscript.trim();
  }

  @override
  Future<void> cancel() async {
    _latestTranscript = '';
    await _stopInternal(abort: true);
  }

  Future<void> _stopInternal({required bool abort}) async {
    final recognition = _recognition;
    if (recognition == null) {
      _isListening = false;
      return;
    }
    try {
      if (_isListening) {
        recognition.callMethod(abort ? 'abort' : 'stop');
      }
    } catch (_) {
      // Ignore browser-specific stop errors.
    } finally {
      _isListening = false;
      _recognition = null;
    }
  }

  dynamic _speechRecognitionConstructor() {
    final standard = context['SpeechRecognition'];
    if (standard != null) {
      return standard;
    }
    return context['webkitSpeechRecognition'];
  }

  String _extractTranscript(dynamic event) {
    try {
      final results = event['results'];
      final lengthRaw = results['length'];
      final length = (lengthRaw is num) ? lengthRaw.toInt() : 0;
      if (length <= 0) {
        return '';
      }
      final latest = results[length - 1];
      final alt = latest[0];
      return (alt['transcript'] ?? '').toString().trim();
    } catch (_) {
      return '';
    }
  }
}

LiveTranscriptionService createLiveTranscriptionService() => _WebLiveTranscriptionService();
