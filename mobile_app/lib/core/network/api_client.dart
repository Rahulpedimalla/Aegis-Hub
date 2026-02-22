import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:http_parser/http_parser.dart';

import 'blob_bytes_loader.dart' as blob_loader;
import '../../config/app_config.dart';
import '../../features/chat/domain/entities/chat_message.dart';
import '../../features/tickets/domain/entities/ticket_payload.dart';
import '../../features/tickets/domain/entities/ticket_submission_result.dart';
import '../../shared/models/media_attachment.dart';
import '../errors/app_exception.dart';

class ApiClient {
  ApiClient(this._config)
      : _dio = Dio(
          BaseOptions(
            baseUrl: _config.apiBaseUrl,
            connectTimeout: Duration(milliseconds: _config.connectTimeoutMs),
            receiveTimeout: Duration(milliseconds: _config.receiveTimeoutMs),
          ),
        ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if ((_config.bearerToken ?? '').isNotEmpty) {
            options.headers['Authorization'] = 'Bearer ${_config.bearerToken}';
          }
          handler.next(options);
        },
      ),
    );
  }

  final AppConfig _config;
  final Dio _dio;

  Future<TicketSubmissionResult> submitTicket(TicketPayload payload) async {
    final captureMode = payload.ticketType.name == 'sos' ? 'sos_auto_voice' : 'normal_ticket';
    final formData = FormData.fromMap({
      'metadata': jsonEncode(
        payload.toMetadataJson(
          captureMode: captureMode,
          connectivityState: 'online',
        ),
      ),
    });

    for (final image in payload.images) {
      formData.files.add(
        MapEntry(
          'images',
          await _buildMultipart(image),
        ),
      );
    }

    for (final video in payload.videos) {
      formData.files.add(
        MapEntry(
          'videos',
          await _buildMultipart(video),
        ),
      );
    }

    if (payload.audioFile != null) {
      final audio = payload.audioFile!;
      formData.files.add(
        MapEntry(
          'audio_file',
          await _buildMultipart(audio),
        ),
      );
    }

    try {
      final endpoint = payload.ticketType.name == 'sos'
          ? _config.sosEndpointPath
          : _config.ticketsEndpointPath;
      final response = await _dio.post<dynamic>(endpoint, data: formData);
      final body = _asMap(response.data);

      // Supports both normalized response and current backend /api/sos/intake response.
      final ticketId = (body['ticket_id'] ?? body['sos_id'] ?? payload.externalId).toString();
      final status = (body['status'] ?? body['message'] ?? 'received').toString();
      final chatSessionId = body['chat_session_id']?.toString();
      final reassurance = body['reassurance_message']?.toString();
      return TicketSubmissionResult(
        ticketId: ticketId,
        status: status,
        chatSessionId: chatSessionId,
        reassuranceMessage: reassurance,
      );
    } on DioException catch (error) {
      if (_isRecoverable(error)) {
        throw RecoverableNetworkException('Ticket submission deferred', cause: error);
      }
      throw AppException('Ticket submission failed', cause: error);
    }
  }

  Future<String> sendChatMessage({
    required String chatSessionId,
    required ChatMessage message,
  }) async {
    final path = '${_config.chatEndpointPath}/$chatSessionId/messages';
    try {
      final response = await _dio.post<dynamic>(
        path,
        data: {
          'role': message.role.name,
          'text': message.text,
          'timestamp': message.timestampUtc.toIso8601String(),
        },
      );
      final body = _asMap(response.data);
      return (body['reply_text'] ?? body['message'] ?? '').toString();
    } on DioException catch (error) {
      throw AppException('Chat request failed', cause: error);
    }
  }

  Future<Map<String, String>> sendVoiceChatMessage({
    required String chatSessionId,
    String? audioPath,
    String? audioMimeType,
    String? audioFileName,
    String? textHint,
  }) async {
    const path = '/api/mobile/ai/voice-agent';
    final formData = FormData.fromMap({
      'chat_session_id': chatSessionId,
      if ((textHint ?? '').trim().isNotEmpty) 'text_hint': textHint!.trim(),
    });

    if ((audioPath ?? '').trim().isNotEmpty) {
      formData.files.add(
        MapEntry(
          'audio_file',
          await _buildAudioMultipartFromPath(
            audioPath!,
            preferredMimeType: audioMimeType,
            preferredFileName: audioFileName,
          ),
        ),
      );
    }

    try {
      final response = await _dio.post<dynamic>(path, data: formData);
      final body = _asMap(response.data);
      return {
        'transcript': (body['transcript'] ?? '').toString(),
        'reply_text': (body['reply_text'] ?? '').toString(),
      };
    } on DioException catch (error) {
      throw AppException('Voice chat request failed', cause: error);
    }
  }

  Future<Map<String, String>> transcribeAudio({
    required String audioPath,
    String languageCode = 'en-IN',
    String? audioMimeType,
    String? audioFileName,
  }) async {
    final formData = FormData.fromMap({
      'language_hint': languageCode,
    });
    formData.files.add(
      MapEntry(
        'audio_file',
        await _buildAudioMultipartFromPath(
          audioPath,
          preferredMimeType: audioMimeType,
          preferredFileName: audioFileName,
        ),
      ),
    );

    try {
      final response = await _dio.post<dynamic>(_config.transcribeEndpointPath, data: formData);
      final body = _asMap(response.data);
      return {
        'transcript': (body['transcript'] ?? '').toString(),
        'provider': (body['provider'] ?? 'gemini').toString(),
        'language': (body['language'] ?? languageCode).toString(),
      };
    } on DioException catch (error) {
      throw AppException('Audio transcription failed', cause: error);
    }
  }

  bool _isRecoverable(DioException error) {
    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout) {
      return true;
    }
    final status = error.response?.statusCode ?? 0;
    return status >= 500 || status == 0;
  }

  Future<MultipartFile> _buildMultipart(MediaAttachment attachment) async {
    final bytes = attachment.bytes;
    final fileName = attachment.fileName;
    final mimeType = attachment.mimeType;
    final path = attachment.path;
    if (bytes != null) {
      return MultipartFile.fromBytes(
        bytes,
        filename: fileName,
        contentType: MediaType.parse(mimeType),
      );
    }
    if (attachment.kind == MediaKind.audio) {
      return _buildAudioMultipartFromPath(
        path,
        preferredFileName: fileName,
        preferredMimeType: mimeType,
      );
    }
    return MultipartFile.fromFile(
      path,
      filename: fileName,
      contentType: MediaType.parse(mimeType),
    );
  }

  Future<MultipartFile> _buildAudioMultipartFromPath(
    String audioPath, {
    String? preferredFileName,
    String? preferredMimeType,
  }) async {
    final path = audioPath.trim();
    if (path.isEmpty) {
      throw AppException('Audio path is empty');
    }

    final inferredMime = _inferAudioMimeType(path);
    final providedMime = (preferredMimeType ?? '').trim();
    final mime = providedMime.isNotEmpty ? providedMime : inferredMime;
    final providedFileName = (preferredFileName ?? '').trim();
    final fileName = providedFileName.isNotEmpty
        ? providedFileName
        : _inferFileNameFromPath(path, mime);

    if (kIsWeb && _isWebBlobLikePath(path)) {
      final blobBytes = await blob_loader.readBlobBytes(path);
      if (blobBytes != null && blobBytes.isNotEmpty) {
        return MultipartFile.fromBytes(
          blobBytes,
          filename: fileName,
          contentType: MediaType.parse(mime),
        );
      }

      try {
        final response = await _dio.get<List<int>>(
          path,
          options: Options(responseType: ResponseType.bytes),
        );
        final bytes = response.data ?? const <int>[];
        if (bytes.isNotEmpty) {
          return MultipartFile.fromBytes(
            bytes,
            filename: fileName,
            contentType: MediaType.parse(mime),
          );
        }
      } catch (_) {
        // Continue to regular file handling fallback.
      }
    }

    return MultipartFile.fromFile(
      path,
      filename: fileName,
      contentType: MediaType.parse(mime),
    );
  }

  bool _isWebBlobLikePath(String path) {
    final lower = path.toLowerCase();
    return lower.startsWith('blob:') || lower.startsWith('data:') || lower.startsWith('http');
  }

  String _inferAudioMimeType(String path) {
    final lower = path.toLowerCase();
    if (lower.endsWith('.wav')) {
      return 'audio/wav';
    }
    if (lower.endsWith('.mp3')) {
      return 'audio/mpeg';
    }
    if (lower.endsWith('.webm')) {
      return 'audio/webm';
    }
    if (lower.endsWith('.ogg') || lower.endsWith('.opus')) {
      return 'audio/ogg';
    }
    return 'audio/m4a';
  }

  String _inferFileNameFromPath(String path, String mimeType) {
    final normalized = path.trim();
    if (normalized.isNotEmpty &&
        !normalized.startsWith('blob:') &&
        !normalized.startsWith('data:')) {
      final parsed = Uri.tryParse(normalized);
      final segments = parsed?.pathSegments ?? const <String>[];
      if (segments.isNotEmpty && segments.last.trim().isNotEmpty) {
        return segments.last.trim();
      }
    }

    if (mimeType == 'audio/wav') {
      return 'recording.wav';
    }
    if (mimeType == 'audio/webm') {
      return 'recording.webm';
    }
    if (mimeType == 'audio/ogg') {
      return 'recording.ogg';
    }
    if (mimeType == 'audio/mpeg') {
      return 'recording.mp3';
    }
    return 'recording.m4a';
  }

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) {
      return value;
    }
    if (value is Map) {
      return value.cast<String, dynamic>();
    }
    return <String, dynamic>{};
  }
}

class RecoverableNetworkException extends AppException {
  RecoverableNetworkException(super.message, {super.cause});
}
