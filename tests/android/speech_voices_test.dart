// Файл: /tests/android/speech_voices_test.dart
// Разработчик: DenBroLiik
// Версия: 2.0.9
// Описание: Проверка форматов flutter_tts без установки движка на ПК.
import '../../extensions/flet_xopilot_mobile/src/flutter/flet_xopilot_mobile/lib/src/speech_voices.dart';
void main() {
  final voices = [
    for (final flag in [false, 0, '0', 'false'])
      {'name':'offline-$flag','locale':'ru-RU','network_required':flag},
    for (final flag in [true, 1, '1', 'true', null])
      {'name':'network-$flag','locale':'ru-RU','network_required':flag},
    {'name':'missing','locale':'ru-RU','network_required':'0','features':'notInstalled'},
    {'name':'english','locale':'en_US','network_required':'0'},
    {'name':'different','locale':'rue','network_required':'0'},
  ];
  assert(offlineVoices(voices,'ru').length == 4);
  assert(offlineVoices(voices,'en').single['name'] == 'english');
  assert(offlineVoices(null,'ru').isEmpty);
  print('Offline voice selection: OK');
}
