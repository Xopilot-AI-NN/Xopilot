package ru.xopilot.mobile;

import android.content.Context;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.content.pm.ResolveInfo;
import android.provider.Settings;
import android.speech.tts.TextToSpeech;
import java.util.*;

/** Inspect installed engines without starting or loading a synthesizer. */
final class SpeechSettings {
    static Map<String, Object> status(Context context) {
        List<Map<String, String>> engines = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (ResolveInfo info : context.getPackageManager().queryIntentServices(
                new Intent(TextToSpeech.Engine.INTENT_ACTION_TTS_SERVICE), 0)) {
            String name = info.serviceInfo.packageName;
            if (seen.add(name)) {
                Map<String, String> engine = new HashMap<>();
                engine.put("id", name);
                engine.put("name", info.loadLabel(context.getPackageManager()).toString());
                engines.add(engine);
            }
        }
        String preferred = Settings.Secure.getString(context.getContentResolver(), Settings.Secure.TTS_DEFAULT_SYNTH);
        Map<String, Object> value = new HashMap<>();
        value.put("engines", engines);
        value.put("preferred", preferred == null ? "" : preferred);
        return value;
    }

    static void open(Context context) {
        try {
            context.startActivity(new Intent("com.android.settings.TTS_SETTINGS")
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        } catch (ActivityNotFoundException unavailable) {
            context.startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        }
    }
}
