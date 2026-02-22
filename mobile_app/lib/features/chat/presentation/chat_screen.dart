import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:record/record.dart';

import '../../../core/providers.dart';
import '../domain/entities/chat_message.dart';
import 'chat_controller.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  late final TextEditingController _messageController;
  final _scrollController = ScrollController();
  bool _voiceMode = false;
  bool _recordingVoiceInput = false;
  StreamSubscription<Amplitude>? _amplitudeSubscription;
  DateTime? _voiceStartedAt;
  DateTime? _lastSpeechAt;
  bool _heardSpeech = false;
  bool _autoStopping = false;

  @override
  void initState() {
    super.initState();
    _messageController = TextEditingController();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(chatControllerProvider.notifier).bootstrap();
    });
  }

  @override
  void dispose() {
    _stopAmplitudeWatcher();
    if (_recordingVoiceInput) {
      ref.read(audioCaptureServiceProvider).cancelRecording();
    }
    ref.read(liveTranscriptionServiceProvider).cancel();
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    ref.listen<String?>(activeChatSessionIdProvider, (_, next) {
      ref.read(chatControllerProvider.notifier).applyTicketContext(chatSessionId: next);
    });
    ref.listen<String?>(latestReassuranceMessageProvider, (_, next) {
      ref
          .read(chatControllerProvider.notifier)
          .applyTicketContext(chatSessionId: ref.read(activeChatSessionIdProvider), reassuranceMessage: next);
    });

    final state = ref.watch(chatControllerProvider);
    final controller = ref.read(chatControllerProvider.notifier);

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });

    return SafeArea(
      child: Column(
        children: [
          ListTile(
            title: const Text('Aegis AI Follow-up'),
            subtitle: Text(
              state.chatSessionId == null
                  ? 'Local guidance mode'
                  : 'Session ${state.chatSessionId}',
            ),
            trailing: SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: false, label: Text('Text')),
                ButtonSegment(value: true, label: Text('Voice')),
              ],
              selected: {_voiceMode},
              onSelectionChanged: (values) {
                setState(() => _voiceMode = values.first);
              },
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              itemCount: state.messages.length,
              itemBuilder: (context, index) {
                final message = state.messages[index];
                final isUser = message.role == ChatRole.user;
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    padding: const EdgeInsets.all(12),
                    constraints: const BoxConstraints(maxWidth: 320),
                    decoration: BoxDecoration(
                      color: isUser ? const Color(0xFFB32020) : Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      message.text,
                      style: TextStyle(color: isUser ? Colors.white : Colors.black87),
                    ),
                  ),
                );
              },
            ),
          ),
          if (state.errorMessage != null)
            Padding(
              padding: const EdgeInsets.all(8),
              child: Text(
                state.errorMessage!,
                style: const TextStyle(color: Colors.red),
              ),
            ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _messageController,
                    minLines: 1,
                    maxLines: 4,
                    decoration: InputDecoration(
                      hintText: _voiceMode
                          ? 'Voice mode enabled; type fallback message'
                          : 'Type your update',
                      border: const OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: state.isSending
                      ? null
                      : () async {
                          if (!_voiceMode) {
                            final text = _messageController.text;
                            _messageController.clear();
                            await controller.sendMessage(text);
                            return;
                          }

                          if (!_recordingVoiceInput) {
                            await _startVoiceCapture();
                            return;
                          }

                          await _stopVoiceCaptureAndSend(controller);
                        },
                  child: state.isSending
                      ? const SizedBox.square(
                          dimension: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(
                          _voiceMode
                              ? (_recordingVoiceInput ? Icons.stop_circle_outlined : Icons.mic)
                              : Icons.send,
                        ),
                ),
              ],
            ),
          ),
          if (_voiceMode && _recordingVoiceInput)
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: Text(
                'Recording voice input... auto-sends after speech stops or tap mic to send now.',
                style: TextStyle(color: Colors.red),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _startVoiceCapture() async {
    final messenger = ScaffoldMessenger.of(context);
    final started = await ref.read(audioCaptureServiceProvider).startRecording();
    if (!started) {
      if (mounted) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Unable to start voice recording on this device/browser.')),
        );
      }
      return;
    }

    if (!mounted) return;
    setState(() => _recordingVoiceInput = true);
    await ref.read(liveTranscriptionServiceProvider).start(localeId: 'en_IN');
    _startAmplitudeWatcher();
  }

  Future<void> _stopVoiceCaptureAndSend(ChatController controller) async {
    if (_autoStopping && !mounted) {
      return;
    }
    _stopAmplitudeWatcher();
    final liveTranscript = await ref.read(liveTranscriptionServiceProvider).stopAndCollect();
    final recording = await ref.read(audioCaptureServiceProvider).stopRecording();
    if (!mounted) return;
    setState(() => _recordingVoiceInput = false);

    final typedFallbackText = _messageController.text.trim();
    final fallbackText = typedFallbackText.isNotEmpty ? typedFallbackText : liveTranscript;
    _messageController.clear();
    await controller.sendVoiceMessage(
      audioPath: (recording?.path ?? '').trim().isEmpty ? null : recording!.path,
      audioMimeType: recording?.mimeType,
      audioFileName: recording?.fileName,
      textHint: fallbackText.isEmpty ? null : fallbackText,
    );
  }

  void _startAmplitudeWatcher() {
    _stopAmplitudeWatcher();
    _voiceStartedAt = DateTime.now().toUtc();
    _lastSpeechAt = _voiceStartedAt;
    _heardSpeech = false;
    _autoStopping = false;

    _amplitudeSubscription = ref
        .read(audioCaptureServiceProvider)
        .onAmplitudeChanged(const Duration(milliseconds: 250))
        .listen((amplitude) async {
      if (_autoStopping || !_recordingVoiceInput) {
        return;
      }

      final now = DateTime.now().toUtc();
      final isSpeechFrame = amplitude.current > -45;
      if (isSpeechFrame) {
        _heardSpeech = true;
        _lastSpeechAt = now;
        return;
      }

      if (!_heardSpeech || _voiceStartedAt == null || _lastSpeechAt == null) {
        return;
      }

      final recordingFor = now.difference(_voiceStartedAt!);
      final silenceFor = now.difference(_lastSpeechAt!);
      if (recordingFor >= const Duration(seconds: 2) && silenceFor >= const Duration(seconds: 3)) {
        _autoStopping = true;
        final controller = ref.read(chatControllerProvider.notifier);
        await _stopVoiceCaptureAndSend(controller);
      }
    });
  }

  void _stopAmplitudeWatcher() {
    _amplitudeSubscription?.cancel();
    _amplitudeSubscription = null;
    _voiceStartedAt = null;
    _lastSpeechAt = null;
    _heardSpeech = false;
    _autoStopping = false;
  }
}
