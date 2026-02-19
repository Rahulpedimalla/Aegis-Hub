import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'normal_ticket_controller.dart';

class NormalTicketScreen extends ConsumerStatefulWidget {
  const NormalTicketScreen({super.key});

  @override
  ConsumerState<NormalTicketScreen> createState() => _NormalTicketScreenState();
}

class _NormalTicketScreenState extends ConsumerState<NormalTicketScreen> {
  late final TextEditingController _descriptionController;

  @override
  void initState() {
    super.initState();
    _descriptionController = TextEditingController();
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(normalTicketControllerProvider);
    final controller = ref.read(normalTicketControllerProvider.notifier);

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Create Ticket', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 12),
            TextField(
              controller: _descriptionController,
              minLines: 4,
              maxLines: 8,
              decoration: const InputDecoration(
                labelText: 'Describe the situation',
                border: OutlineInputBorder(),
              ),
              onChanged: controller.setDescription,
            ),
            const SizedBox(height: 12),
            Card(
              child: ListTile(
                leading: const Icon(Icons.my_location),
                title: const Text('Auto location'),
                subtitle: Text(
                  state.location == null
                      ? 'Detecting...'
                      : '${state.location!.latitude.toStringAsFixed(5)}, ${state.location!.longitude.toStringAsFixed(5)}',
                ),
                trailing: IconButton(
                  onPressed: controller.refreshLocation,
                  icon: const Icon(Icons.refresh),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ElevatedButton.icon(
                  onPressed: state.isSubmitting ? null : controller.pickImages,
                  icon: const Icon(Icons.image_outlined),
                  label: const Text('Add Images'),
                ),
                ElevatedButton.icon(
                  onPressed: state.isSubmitting ? null : controller.pickVideo,
                  icon: const Icon(Icons.videocam_outlined),
                  label: const Text('Add Video'),
                ),
                ElevatedButton.icon(
                  onPressed: state.isSubmitting
                      ? null
                      : () {
                          if (!state.isRecordingVoiceNote) {
                            controller.startVoiceNote();
                          } else {
                            controller.stopVoiceNote();
                          }
                        },
                  icon: Icon(state.isRecordingVoiceNote ? Icons.stop_circle : Icons.mic_none),
                  label: Text(state.isRecordingVoiceNote ? 'Stop Voice Note' : 'Voice Note'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (state.images.isNotEmpty)
              Text(
                'Images (${state.images.length})',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            if (state.images.isNotEmpty)
              ...state.images.map(
                (image) => ListTile(
                  dense: true,
                  leading: const Icon(Icons.image),
                  title: Text(image.fileName),
                  subtitle: Text('${image.sizeBytes} bytes'),
                ),
              ),
            if (state.videos.isNotEmpty)
              Text(
                'Videos (${state.videos.length})',
                style: Theme.of(context).textTheme.titleSmall,
              ),
            if (state.videos.isNotEmpty)
              ...state.videos.map(
                (video) => ListTile(
                  dense: true,
                  leading: const Icon(Icons.video_file),
                  title: Text(video.fileName),
                  subtitle: Text('${video.sizeBytes} bytes'),
                ),
              ),
            if (state.voiceNote != null)
              Card(
                child: ListTile(
                  leading: const Icon(Icons.graphic_eq),
                  title: Text(state.voiceNote!.fileName),
                  subtitle: Text(
                    state.voiceTranscript?.rawText.isNotEmpty == true
                        ? 'Raw transcript: ${state.voiceTranscript!.rawText}'
                        : 'Voice note captured',
                  ),
                  trailing: IconButton(
                    onPressed: state.isSubmitting ? null : controller.clearVoiceNote,
                    icon: const Icon(Icons.delete_outline),
                  ),
                ),
              ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: state.isSubmitting ? null : controller.submitTicket,
              icon: state.isSubmitting
                  ? const SizedBox.square(
                      dimension: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.send),
              label: Text(state.isSubmitting ? 'Submitting...' : 'Submit Ticket'),
            ),
            const SizedBox(height: 8),
            if (state.lastResult != null)
              Card(
                color: state.lastResult!.isQueued
                    ? const Color(0xFFFFF3E0)
                    : const Color(0xFFE8F5E9),
                child: ListTile(
                  leading: Icon(
                    state.lastResult!.isQueued ? Icons.schedule_send : Icons.check_circle,
                    color: state.lastResult!.isQueued ? Colors.orange : Colors.green,
                  ),
                  title: Text('Ticket ${state.lastResult!.ticketId}'),
                  subtitle: Text(
                    state.lastResult!.reassuranceMessage ??
                        (state.lastResult!.isQueued ? 'Queued for upload.' : 'Submitted successfully.'),
                  ),
                ),
              ),
            if (state.errorMessage != null)
              Card(
                color: const Color(0xFFFFEBEE),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    state.errorMessage!,
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
