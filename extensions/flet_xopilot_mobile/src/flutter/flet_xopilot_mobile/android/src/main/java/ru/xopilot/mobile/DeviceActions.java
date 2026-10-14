/*
Файл: /extensions/flet_xopilot_mobile/android/DeviceActions.java
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Список запускаемых приложений, открытие приложения и стандартные команды медиаплеера.
*/
package ru.xopilot.mobile;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.media.AudioManager;
import android.view.KeyEvent;
import java.util.*;

/** Only launcher activities and standard media keys; no arbitrary Intent extras. */
final class DeviceActions {
    static List<Map<String,Object>> apps(Context context) {
        Intent query = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        Map<String,Map<String,Object>> unique = new TreeMap<>();
        for (ResolveInfo item : context.getPackageManager().queryIntentActivities(query, 0)) {
            if (item.activityInfo == null || !item.activityInfo.enabled) continue;
            String pkg = item.activityInfo.packageName;
            Map<String,Object> row = new HashMap<>();
            row.put("package", pkg);
            row.put("name", item.loadLabel(context.getPackageManager()).toString());
            unique.put(pkg, row);
        }
        List<Map<String,Object>> result = new ArrayList<>(unique.values());
        result.sort(Comparator.comparing(item -> item.get("name").toString(), String.CASE_INSENSITIVE_ORDER));
        return result;
    }
    static Map<String,Object> launch(Context context, String pkg) {
        if (pkg == null || apps(context).stream().noneMatch(item -> pkg.equals(item.get("package"))))
            throw new IllegalArgumentException("Приложение не найдено в списке запускаемых приложений");
        Intent intent = context.getPackageManager().getLaunchIntentForPackage(pkg);
        if (intent == null) throw new IllegalArgumentException("У приложения нет окна запуска");
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        context.startActivity(intent);
        Map<String,Object> result = new HashMap<>(); result.put("launched", true); result.put("package", pkg); return result;
    }
    static Map<String,Object> media(Context context, String action) {
        int key;
        switch (action == null ? "" : action) {
            case "next": key=KeyEvent.KEYCODE_MEDIA_NEXT; break;
            case "previous": key=KeyEvent.KEYCODE_MEDIA_PREVIOUS; break;
            case "pause": key=KeyEvent.KEYCODE_MEDIA_PAUSE; break;
            case "play": key=KeyEvent.KEYCODE_MEDIA_PLAY; break;
            case "play_pause": key=KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE; break;
            case "stop": key=KeyEvent.KEYCODE_MEDIA_STOP; break;
            default: throw new IllegalArgumentException("Неизвестная команда медиаплеера");
        }
        AudioManager audio = (AudioManager)context.getSystemService(Context.AUDIO_SERVICE);
        audio.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_DOWN, key));
        audio.dispatchMediaKeyEvent(new KeyEvent(KeyEvent.ACTION_UP, key));
        Map<String,Object> result = new HashMap<>(); result.put("dispatched", true); result.put("action", action);
        result.put("note", "Команда передана активной медиасессии; плеер сам определяет её поддержку"); return result;
    }
}
