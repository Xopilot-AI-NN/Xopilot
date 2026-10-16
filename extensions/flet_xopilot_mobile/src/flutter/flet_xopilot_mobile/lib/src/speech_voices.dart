// Файл: /extensions/flet_xopilot_mobile/lib/src/speech_voices.dart
// Разработчик: DenBroLiik
// Версия: 2.0.9
// Описание: Совместимый выбор установленного офлайн-голоса Android.
List<Map> offlineVoices(dynamic voices, String language) {
  if (voices is! List) return [];
  return voices.whereType<Map>().where((voice) {
    final locale = voice['locale'].toString().toLowerCase().replaceAll('_', '-');
    final network = voice['network_required'];
    final offline = network == false || network == 0 || network == '0' || network == 'false';
    final installed = !voice['features'].toString().contains('notInstalled');
    return (locale == language || locale.startsWith('$language-')) && offline && installed &&
        voice['name'] is String && (voice['name'] as String).isNotEmpty;
  }).toList();
}
