package ru.xopilot.mobile;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.content.SharedPreferences;
import android.app.Activity;
import android.app.Application;
import android.os.Bundle;
import android.media.projection.MediaProjectionManager;
import android.media.projection.MediaProjectionConfig;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import android.util.Log;
import com.google.ai.edge.litertlm.*;
import io.flutter.embedding.engine.plugins.FlutterPlugin;
import io.flutter.embedding.engine.plugins.activity.ActivityAware;
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding;
import io.flutter.plugin.common.PluginRegistry;
import io.flutter.plugin.common.MethodCall;
import io.flutter.plugin.common.MethodChannel;
import java.security.KeyStore;
import java.io.File;
import java.security.SecureRandom;
import java.util.*;
import java.util.concurrent.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** Serial inference worker. Cancellation bypasses the inference queue. */
public final class XopilotMobilePlugin implements FlutterPlugin, MethodChannel.MethodCallHandler, ActivityAware, PluginRegistry.ActivityResultListener {
    private Context context;
    private MethodChannel channel;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private volatile Engine engine;
    private final Map<String, Conversation> conversations = new ConcurrentHashMap<>();
    private volatile Conversation active;
    private ActivityPluginBinding activityBinding;
    private MethodChannel.Result screenPending;
    private DocumentPicker documents;
    private LiveOverlay overlay;
    private CameraFrames cameraFrames;
    private final Application.ActivityLifecycleCallbacks lifecycle = new Application.ActivityLifecycleCallbacks() {
        public void onActivityResumed(Activity activity) {
            if (activityBinding != null && activity == activityBinding.getActivity()) overlay.lifecycle(true);
        }
        public void onActivityPaused(Activity activity) {
            if (activityBinding != null && activity == activityBinding.getActivity()) overlay.lifecycle(false);
        }
        public void onActivityCreated(Activity a, Bundle b) {}
        public void onActivityStarted(Activity a) {}
        public void onActivityStopped(Activity a) {}
        public void onActivitySaveInstanceState(Activity a, Bundle b) {}
        public void onActivityDestroyed(Activity a) {}
    };
    private static final int SCREEN_REQUEST = 7319;

    @Override public void onAttachedToEngine(FlutterPluginBinding binding) {
        context = binding.getApplicationContext();
        documents = new DocumentPicker(context);
        cameraFrames = new CameraFrames(context);
        channel = new MethodChannel(binding.getBinaryMessenger(), "ru.xopilot/mobile");
        channel.setMethodCallHandler(this);
        overlay = new LiveOverlay(context, action -> channel.invokeMethod("liveAction", action));
        LiveCaptureService.stopped = () -> overlay.stop(true);
        ((Application)context).registerActivityLifecycleCallbacks(lifecycle);
    }

    @Override public void onMethodCall(MethodCall call, MethodChannel.Result result) {
        // Overlay controls must bypass inference: ending/muting remains immediate.
        try {
            switch (call.method) {
                case "releaseMemory":
                    if (engine != null || active != null || overlay.enabled() || ScreenCaptureService.current != null || activityBinding == null) {
                        result.success(false);return;
                    }
                    Activity memoryActivity = activityBinding.getActivity();
                    // Same engine/framework notification Android delivers on
                    // memory pressure. FlutterFragmentActivity forwards the
                    // public callback to its attached engine and textures.
                    memoryActivity.onTrimMemory(android.content.ComponentCallbacks2.TRIM_MEMORY_RUNNING_LOW);
                    Log.i("XopilotMemory", "Released idle rendering caches");
                    result.success(true);return;
                case "hideKeyboard":
                    if (activityBinding!=null) {
                        Activity currentActivity=activityBinding.getActivity();
                        currentActivity.getWindow().getDecorView().clearFocus();
                        ((android.view.inputmethod.InputMethodManager)context.getSystemService(Context.INPUT_METHOD_SERVICE))
                            .hideSoftInputFromWindow(currentActivity.getWindow().getDecorView().getWindowToken(),0);
                    }
                    result.success(true);return;
                case "deviceInfo":
                    Map<String,Object> deviceInfo=new HashMap<>();
                    deviceInfo.put("name",Build.MODEL);
                    deviceInfo.put("manufacturer",Build.MANUFACTURER);
                    deviceInfo.put("region",Locale.getDefault().getCountry());
                    deviceInfo.put("android",Build.VERSION.RELEASE);
                    result.success(deviceInfo);return;
                case "speechEngines": result.success(SpeechSettings.status(context)); return;
                case "speechSettings": SpeechSettings.open(context); result.success(true); return;
                case "cameraPermission": result.success(cameraFrames.permission()); return;
                case "cameraFrame": cameraFrames.frame(result); return;
                case "cameraClose": cameraFrames.close(); result.success(null); return;
                case "overlayRequest": result.success(overlay.request((Map<String, Object>)call.arguments)); return;
                case "overlayState": overlay.state((Map<String, Object>)call.arguments); result.success(overlay.enabled()); return;
                case "overlayPoll": result.success(overlay.poll()); return;
                case "overlayActive": result.success(overlay.enabled()); return;
                case "overlayFrame": overlay.camera(Base64.decode(call.<String>argument("frame"), Base64.DEFAULT)); result.success(null); return;
                case "overlayStop": overlay.stop(false); result.success(null); return;
                case "minimizeLive": overlay.minimize(); result.success(null); return;
            }
        } catch (RuntimeException error) { result.error("live_overlay", error.getMessage(), null); return; }
        if (call.method.equals("exportDocument")) {
            if (activityBinding == null) result.error("document_picker", "Вернитесь в приложение для сохранения файла", null);
            else documents.startExport(activityBinding.getActivity(), call.argument("token"), result);
            return;
        }
        if (call.method.equals("pickDocuments")) {
            if (activityBinding == null) result.error("document_picker", "Вернитесь в приложение для выбора файлов", null);
            else documents.start(activityBinding.getActivity(), call.argument("tag"), result);
            return;
        }
        if (call.method.equals("screenStart")) {
            if (ScreenCaptureService.current != null && ScreenCaptureService.current.ready()) { result.success(true); return; }
            if (screenPending != null) { result.error("screen_busy", "Ожидаем разрешение на экран", null); return; }
            if (activityBinding == null) { result.error("screen_unavailable", "Вернитесь в приложение для выбора экрана", null); return; }
            screenPending = result;
            try {
                Activity activity = activityBinding.getActivity();
                MediaProjectionManager manager = activity.getSystemService(MediaProjectionManager.class);
                // This control shares the screen. The per-app selector launches
                // Xopilot a second time if users choose the requesting app.
                // Ask explicitly for the display, retaining Android's consent.
                Intent consent = Build.VERSION.SDK_INT >= 34
                    ? manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
                    : manager.createScreenCaptureIntent();
                activity.startActivityForResult(consent, SCREEN_REQUEST);
                main.postDelayed(() -> {
                    if (screenPending == result) {
                        finishScreen("Время выбора экрана истекло. Повторите подключение.");
                        ScreenCaptureService.stop(context);
                    }
                }, 60000);
            } catch (RuntimeException error) { finishScreen("Не удалось открыть выбор экрана"); }
            return;
        }
        if (call.method.equals("screenStop")) {
            ScreenCaptureService.stop(context); finishScreen("Демонстрация экрана остановлена");
            result.success(null); return;
        }
        if (call.method.equals("screenFrame")) {
            try {
                ScreenCaptureService screen = ScreenCaptureService.current;
                if (screen == null) throw new IllegalStateException("Экран отключён. Подключите его заново.");
                result.success(screen.latestFrame());
            } catch (RuntimeException error) { result.error("screen_unavailable", error.getMessage(), null); }
            return;
        }
        if (call.method.equals("openBrowser")) {
            // Launch on the UI thread, independently of a busy inference queue.
            // Google OAuth must use the system browser rather than a WebView.
            main.post(() -> {
                try {
                    Uri uri = Uri.parse(call.<String>argument("url"));
                    if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null)
                        throw new IllegalArgumentException("Неверный адрес браузера");
                    Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                    intent.addCategory(Intent.CATEGORY_BROWSABLE);
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    context.startActivity(intent);
                    result.success(true);
                } catch (Exception error) {
                    result.error("browser_unavailable", "Не удалось открыть системный браузер", null);
                }
            });
            return;
        }
        if (call.method.equals("cancel")) {
            try {
                Conversation running = active;
                if (running != null && running == conversations.get(call.<String>argument("id"))) running.cancelProcess();
                result.success(null);
            } catch (Exception error) { result.error("xopilot_mobile", error.getMessage(), null); }
            return;
        }
        worker.execute(() -> {
            boolean inference = Arrays.asList("load", "openConversation", "send", "closeConversation", "closeAll").contains(call.method);
            try {
                if (inference) Log.i("XopilotInference", "Begin " + call.method +
                    (call.method.equals("load") ? " backend=" + call.<String>argument("backend") : ""));
                Object value = invoke(call);
                if (inference) Log.i("XopilotInference", "Complete " + call.method);
                main.post(() -> result.success(value));
            } catch (Exception error) {
                // Do not log request data, keys or private file paths.
                if (inference) Log.w("XopilotInference", "Failed " + call.method + " type=" + error.getClass().getSimpleName());
                main.post(() -> result.error("xopilot_mobile", error.getMessage(), null));
            }
        });
    }

    private void finishScreen(String error) {
        MethodChannel.Result pending = screenPending; screenPending = null;
        if (pending != null) {
            if (error == null) pending.success(true);
            else pending.error("screen_unavailable", error, null);
        }
    }

    @Override public boolean onActivityResult(int request, int code, Intent data) {
        if (documents.result(request, code, data)) return true;
        if (request != SCREEN_REQUEST) return false;
        if (screenPending == null) return true;
        if (code != Activity.RESULT_OK || data == null) finishScreen("Доступ к экрану отменён");
        else ScreenCaptureService.begin(context, code, data, error -> main.post(() -> finishScreen(error)));
        return true;
    }
    @Override public void onAttachedToActivity(ActivityPluginBinding binding) {
        activityBinding = binding; binding.addActivityResultListener(this);
        overlay.attach(binding.getActivity());
    }
    @Override public void onDetachedFromActivityForConfigChanges() {
        if (activityBinding != null) activityBinding.removeActivityResultListener(this);
        activityBinding = null;
    }
    @Override public void onReattachedToActivityForConfigChanges(ActivityPluginBinding binding) { onAttachedToActivity(binding); }
    @Override public void onDetachedFromActivity() {
        onDetachedFromActivityForConfigChanges(); finishScreen("Приложение закрыто");
        ScreenCaptureService.stop(context);
    }

    private Object invoke(MethodCall call) throws Exception {
        switch (call.method) {
            case "stageExport": return documents.stageExport(call.argument("path"), call.argument("name"));
            case "pendingDocuments": return documents.pending();
            case "ackDocuments": documents.acknowledge(call.argument("token")); return null;
            case "databaseKey": return databaseKey(Boolean.TRUE.equals(call.argument("existing")));
            case "discardPickedFile": {
                File picked = new File(call.<String>argument("path")).getCanonicalFile();
                File cache = new File(context.getCacheDir(), "file_picker").getCanonicalFile();
                // Only the picker's temporary copy can be removed. A caller can
                // never use this method to delete the original document or DB.
                if (!picked.getPath().startsWith(cache.getPath() + File.separator)) return false;
                if (picked.exists() && !picked.delete()) throw new IllegalStateException("Не удалось удалить временную копию файла");
                return true;
            }
            case "capabilities":
                try (ModelInfo info = ModelInfo.from(call.argument("path"))) {
                    SupportedModalities modalities = info.inputModalities();
                    Map<String, Boolean> result = new HashMap<>();
                    result.put("audio", modalities.getAudio()); result.put("vision", modalities.getVision());
                    return result;
                }
            case "load": {
                Engine.Companion.setNativeMinLogSeverity(LogSeverity.ERROR);
                closeAll();
                Backend backend = "gpu".equals(call.argument("backend")) ? new Backend.GPU() : new Backend.CPU();
                Engine created = new Engine(new EngineConfig(call.argument("path"), backend,
                    Boolean.TRUE.equals(call.argument("vision")) ? new Backend.GPU() : null,
                    Boolean.TRUE.equals(call.argument("audio")) ? new Backend.CPU() : null,
                    null, null, call.argument("cache")));
                try { created.initialize(); engine = created; }
                catch (Exception error) { created.close(); throw error; }
                return null;
            }
            case "openConversation": {
                if (engine == null) throw new IllegalStateException("Модель не загружена");
                List<Map<String, Object>> history = call.argument("messages");
                List<Message> initial = new ArrayList<>();
                if (history != null) for (Map<String, Object> item : history) {
                    Contents parts = contents(item.get("content"));
                    initial.add("user".equals(item.get("role")) ? Message.Companion.user(parts)
                        : Message.Companion.model(parts, Collections.emptyList(), Collections.emptyMap()));
                }
                Number temperature = call.argument("temperature");
                Boolean thinking = call.argument("thinking");
                // Full constructor keeps all SDK defaults explicit and avoids
                // compiler-specific Kotlin synthetic constructors.
                ConversationConfig config = new ConversationConfig(
                    Contents.Companion.of(call.<String>argument("system")), initial, Collections.emptyList(),
                    temperature == null ? null : new SamplerConfig(40, 0.95, temperature.doubleValue(), 0),
                    true, Collections.emptyList(), Collections.emptyMap(), null, true, null,
                    thinking == null ? null : new ThinkingConfig(thinking), false, null, null);
                Conversation conversation = engine.createConversation(config);
                String id = UUID.randomUUID().toString();
                conversations.put(id, conversation);
                return id;
            }
            case "send": {
                Conversation conversation = conversations.get(call.<String>argument("id"));
                if (conversation == null) throw new IllegalStateException("Разговор закрыт");
                active = conversation;
                try { return conversation.sendMessage(contents(call.argument("content"))).toString(); }
                finally { active = null; }
            }
            case "closeConversation": {
                Conversation conversation = conversations.remove(call.<String>argument("id"));
                if (conversation != null) conversation.close();
                return null;
            }
            case "closeAll": closeAll(); return null;
            default: throw new IllegalArgumentException("Неизвестный метод платформы");
        }
    }

    private Contents contents(Object raw) {
        if (raw instanceof String) return Contents.Companion.of((String)raw);
        if (!(raw instanceof List)) throw new IllegalArgumentException("Пустое сообщение");
        List<Content> parts = new ArrayList<>();
        for (Object value : (List<?>)raw) {
            Map<?, ?> item = (Map<?, ?>)value;
            switch ((String)item.get("type")) {
                case "text": parts.add(new Content.Text((String)item.get("text"))); break;
                case "image": parts.add(new Content.ImageBytes(Base64.decode((String)item.get("data"), Base64.NO_WRAP))); break;
                case "audio": parts.add(new Content.AudioBytes(Base64.decode((String)item.get("data"), Base64.NO_WRAP))); break;
                default: throw new IllegalArgumentException("Неподдерживаемый тип материала");
            }
        }
        return Contents.Companion.of(parts);
    }

    private String databaseKey(boolean existing) throws Exception {
        SharedPreferences prefs = context.getSharedPreferences("xopilot_keys", Context.MODE_PRIVATE);
        String wrapped = prefs.getString("database", null), iv = prefs.getString("iv", null);
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        String alias = "xopilot.database.v1";
        if ((wrapped == null) != (iv == null)) throw new IllegalStateException("Хранилище ключей повреждено");
        if (existing && wrapped == null) throw new IllegalStateException("Ключ существующей истории недоступен. Данные не изменены.");
        if (wrapped != null && !store.containsAlias(alias)) throw new IllegalStateException("Android Keystore недоступен. Данные не изменены.");
        if (!store.containsAlias(alias)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            generator.generateKey();
        }
        SecretKey key = (SecretKey)store.getKey(alias, null);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        byte[] secret;
        if (wrapped != null) {
            cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)));
            secret = cipher.doFinal(Base64.decode(wrapped, Base64.NO_WRAP));
        } else {
            secret = new byte[32]; new SecureRandom().nextBytes(secret);
            cipher.init(Cipher.ENCRYPT_MODE, key);
            byte[] encrypted = cipher.doFinal(secret);
            if (!prefs.edit().putString("database", Base64.encodeToString(encrypted, Base64.NO_WRAP))
                    .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)).commit())
                throw new IllegalStateException("Не удалось сохранить ключ");
        }
        if (secret.length != 32) throw new IllegalStateException("Некорректный ключ истории");
        StringBuilder hex = new StringBuilder();
        for (byte b : secret) hex.append(String.format(Locale.ROOT, "%02x", b & 255));
        Arrays.fill(secret, (byte)0);
        return hex.toString();
    }

    private void closeAll() {
        for (Conversation conversation : conversations.values()) conversation.close();
        conversations.clear();
        if (engine != null) engine.close();
        engine = null;
    }

    @Override public void onDetachedFromEngine(FlutterPluginBinding binding) {
        ((Application)context).unregisterActivityLifecycleCallbacks(lifecycle);
        overlay.dispose(); LiveCaptureService.stopped = null;
        cameraFrames.close();
        ScreenCaptureService.stop(context);
        finishScreen("Приложение закрыто");
        channel.setMethodCallHandler(null);
        Conversation running = active;
        if (running != null) running.cancelProcess();
        worker.execute(this::closeAll);
        worker.shutdown();
    }
}
