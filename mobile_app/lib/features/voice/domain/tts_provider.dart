abstract class TtsProvider {
  String get providerName;

  Future<void> speak(String text);
}
