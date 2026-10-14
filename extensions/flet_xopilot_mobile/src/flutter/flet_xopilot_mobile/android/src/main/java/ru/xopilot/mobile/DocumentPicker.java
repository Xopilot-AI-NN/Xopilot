/*
Файл: /extensions/flet_xopilot_mobile/.../DocumentPicker.java
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Восстановление выбора файлов Android после замены Activity или процесса.
*/
package ru.xopilot.mobile;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import io.flutter.plugin.common.MethodChannel;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.util.*;
import java.util.concurrent.Executors;

/** Journals ordinary-chat selections before leaving the Activity. */
final class DocumentPicker {
    static final int REQUEST = 7320;
    static final int EXPORT_REQUEST = 7321;
    private final Context context;
    private final SharedPreferences preferences;
    private final Handler main = new Handler(Looper.getMainLooper());
    private MethodChannel.Result callback;
    private static final int FIRST_DYNAMIC_REQUEST = 10000;
    private static final int LAST_DYNAMIC_REQUEST = 60000;

    DocumentPicker(Context context) {
        this.context = context;
        preferences = context.getSharedPreferences("xopilot_document_picker", Context.MODE_PRIVATE);
        // A copy worker cannot survive process death. Do not wait forever for
        // that abandoned state or silently pretend its partial file is valid.
        try {
            JSONObject previous = new JSONObject(preferences.getString("operation", "{}"));
            if ("copying".equals(previous.optString("state"))) {
                previous.put("state", "error").put("error", "Копирование прервано Android. Выберите файл повторно.");
                preferences.edit().putString("operation", previous.toString()).commit();
            } else if ("staged".equals(previous.optString("state"))) {
                previous.put("state", "ready").put("exported", false);
                preferences.edit().putString("operation", previous.toString()).commit();
            }
        } catch (Exception ignored) { }
    }

    void start(Activity activity, String tag, MethodChannel.Result result) {
        try { releaseAbandonedWaiting(); }
        catch (Exception error) { result.error("document_picker", error.getMessage(), null); return; }
        if (preferences.contains("operation")) {
            result.error("document_picker", "Сначала завершите предыдущий выбор файлов", null);
            return;
        }
        try {
            if (tag == null || !(tag.matches("chat:[1-9][0-9]*") || tag.matches("workspace:[0-9a-f-]{32,36}") || tag.equals("avatar")))
                throw new IllegalArgumentException("Неверное назначение выбранных файлов");
            JSONObject operation = new JSONObject();
            operation.put("token", UUID.randomUUID().toString());
            operation.put("tag", tag);
            operation.put("state", "waiting");
            int request = nextRequest();
            operation.put("request", request);
            if (!preferences.edit().putString("operation", operation.toString()).commit())
                throw new IOException("Не удалось сохранить выбор файлов");
            callback = result;
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType(tag.equals("avatar") ? "image/*" : "*/*");
            intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, !tag.equals("avatar"));
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            activity.startActivityForResult(intent, request);
        } catch (Exception error) {
            preferences.edit().remove("operation").commit();
            callback = null;
            result.error("document_picker", error.getMessage(), null);
        }
    }

    boolean result(int request, int code, Intent data) {
        if (request != REQUEST && request != EXPORT_REQUEST &&
            (request < FIRST_DYNAMIC_REQUEST || request > LAST_DYNAMIC_REQUEST)) return false;
        // A new plugin instance still receives this result after Android kills
        // the original process. The persisted tag retains the destination chat.
        if (!preferences.contains("operation")) return false;
        try {
            JSONObject operation = new JSONObject(preferences.getString("operation", "{}"));
            int expected = operation.optInt("request", "export".equals(operation.optString("tag")) ? EXPORT_REQUEST : REQUEST);
            // A cancelled/restored picker must never deliver its late result
            // into a newer request or into a different chat/workspace.
            if (request != expected) return false;
            if (!"waiting".equals(operation.optString("state"))) return true;
            operation.put("state", "copying");
            preferences.edit().putString("operation", operation.toString()).commit();
            List<Uri> uris = new ArrayList<>();
            if (code == Activity.RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    for (int i = 0; i < data.getClipData().getItemCount(); i++)
                        uris.add(data.getClipData().getItemAt(i).getUri());
                } else if (data.getData() != null) uris.add(data.getData());
            }
            // One bounded-copy worker; no base64 or complete file in memory.
            java.util.concurrent.ExecutorService copy = Executors.newSingleThreadExecutor();
            copy.execute(() -> {
                try {
                    JSONArray files = new JSONArray();
                    File root = new File(context.getFilesDir(), "pending_documents/" + operation.getString("token"));
                    if (!uris.isEmpty() && !root.mkdirs() && !root.isDirectory()) throw new IOException("Нет места для файлов");
                    if ("export".equals(operation.optString("tag"))) {
                        if (!uris.isEmpty()) {
                            try (InputStream input = new FileInputStream(new File(root, "export"));
                                 OutputStream output = context.getContentResolver().openOutputStream(uris.get(0), "wt")) {
                                if (output == null) throw new IOException("Не удалось открыть место сохранения");
                                transfer(input, output);
                            }
                        }
                        operation.put("exported", !uris.isEmpty());
                    } else {
                    int index = 0;
                    for (Uri uri : uris) {
                        String name = "document";
                        try (Cursor cursor = context.getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                            if (cursor != null && cursor.moveToFirst()) name = cursor.getString(0);
                        }
                        File destination = new File(root, Integer.toString(index++));
                        try (InputStream input = context.getContentResolver().openInputStream(uri);
                             OutputStream output = new FileOutputStream(destination)) {
                            if (input == null) throw new IOException("Не удалось открыть документ");
                            transfer(input, output);
                        }
                        files.put(new JSONObject().put("name", name).put("path", destination.getAbsolutePath()));
                    }
                    }
                    operation.put("files", files).put("state", "ready");
                } catch (Exception error) {
                    try { operation.put("state", "error").put("error", "Не удалось скопировать выбранные файлы. Повторите выбор."); }
                    catch (Exception ignored) { }
                } finally {
                    boolean current = operation.optString("token").equals(currentToken());
                    boolean saved = current && preferences.edit().putString("operation", operation.toString()).commit();
                    main.post(() -> {
                        MethodChannel.Result waiting = callback;
                        callback = null;
                        if (waiting != null) {
                            if (saved) waiting.success(pending());
                            else waiting.error("document_picker", "Не удалось сохранить выбранные файлы", null);
                        }
                    });
                    copy.shutdown();
                }
            });
        } catch (Exception error) {
            MethodChannel.Result waiting = callback;
            callback = null;
            if (waiting != null) waiting.error("document_picker", "Не удалось восстановить выбор файлов", null);
        }
        return true;
    }

    Map<String, Object> pending() {
        try {
            if (!preferences.contains("operation")) return null;
            JSONObject operation = new JSONObject(preferences.getString("operation", "{}"));
            Map<String, Object> value = new HashMap<>();
            for (String key : new String[]{"token", "tag", "state", "error"})
                if (operation.has(key)) value.put(key, operation.getString(key));
            if (operation.has("exported")) value.put("exported", operation.getBoolean("exported"));
            List<Map<String, String>> files = new ArrayList<>();
            JSONArray entries = operation.optJSONArray("files");
            if (entries != null) for (int i = 0; i < entries.length(); i++) {
                JSONObject item = entries.getJSONObject(i);
                Map<String, String> file = new HashMap<>();
                file.put("name", item.getString("name")); file.put("path", item.getString("path"));
                files.add(file);
            }
            value.put("files", files);
            return value;
        } catch (Exception error) { throw new IllegalStateException("Повреждены данные выбора файлов"); }
    }

    private static void transfer(InputStream input, OutputStream output) throws IOException {
        byte[] buffer = new byte[64 * 1024];
        int read;
        while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
    }

    String stageExport(String path, String name) throws Exception {
        releaseAbandonedWaiting();
        if (preferences.contains("operation")) throw new IllegalStateException("Сначала завершите предыдущий выбор файлов");
        File source = new File(path).getCanonicalFile();
        String privateRoot = context.getFilesDir().getCanonicalPath() + File.separator;
        if (!source.getPath().startsWith(privateRoot)) throw new IllegalArgumentException("Файл должен быть во внутреннем хранилище Xopilot");
        String token = UUID.randomUUID().toString();
        File root = new File(context.getFilesDir(), "pending_documents/" + token);
        if (!root.mkdirs()) throw new IOException("Не удалось подготовить экспорт");
        try (InputStream input = new FileInputStream(source);
             OutputStream output = new FileOutputStream(new File(root, "export"))) {
            transfer(input, output);
        } catch (Exception error) {
            new File(root, "export").delete(); root.delete(); throw error;
        }
        JSONObject operation = new JSONObject().put("token", token).put("tag", "export")
            .put("name", name).put("state", "staged");
        if (!preferences.edit().putString("operation", operation.toString()).commit())
            throw new IOException("Не удалось сохранить подготовленный экспорт");
        return token;
    }

    void startExport(Activity activity, String token, MethodChannel.Result result) {
        try {
            JSONObject operation = new JSONObject(preferences.getString("operation", "{}"));
            if (!token.equals(operation.optString("token")) || !"staged".equals(operation.optString("state")))
                throw new IllegalStateException("Экспорт не подготовлен");
            operation.put("state", "waiting");
            int request = nextRequest();
            operation.put("request", request);
            if (!preferences.edit().putString("operation", operation.toString()).commit())
                throw new IOException("Не удалось сохранить экспорт");
            callback = result;
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("application/octet-stream");
            intent.putExtra(Intent.EXTRA_TITLE, operation.getString("name"));
            intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
            activity.startActivityForResult(intent, request);
        } catch (Exception error) {
            callback = null;
            try { acknowledge(token); } catch (Exception ignored) { }
            result.error("document_picker", error.getMessage(), null);
        }
    }

    void acknowledge(String token) throws Exception {
        Map<String, Object> operation = pending();
        if (operation == null || !Objects.equals(token, operation.get("token"))) return;
        if (!token.matches("[0-9a-f-]{36}")) throw new IllegalArgumentException("Неверный идентификатор выбора");
        File root = new File(context.getFilesDir(), "pending_documents/" + token);
        File[] files = root.listFiles();
        if (files != null) for (File file : files) if (!file.delete()) throw new IOException("Не удалось убрать временный файл");
        if (root.exists() && !root.delete()) throw new IOException("Не удалось убрать временную папку");
        preferences.edit().remove("operation").commit();
    }

    private String currentToken() {
        try { return new JSONObject(preferences.getString("operation", "{}")).optString("token"); }
        catch (Exception ignored) { return ""; }
    }

    private int nextRequest() throws IOException {
        int previous = preferences.getInt("request_sequence", FIRST_DYNAMIC_REQUEST - 1);
        int next = previous >= LAST_DYNAMIC_REQUEST ? FIRST_DYNAMIC_REQUEST : previous + 1;
        if (!preferences.edit().putInt("request_sequence", next).commit())
            throw new IOException("Не удалось подготовить выбор файлов");
        return next;
    }

    private void releaseAbandonedWaiting() throws Exception {
        if (callback != null || !preferences.contains("operation")) return;
        JSONObject operation = new JSONObject(preferences.getString("operation", "{}"));
        // Only a fresh explicit selection/export supersedes a waiting request
        // with no live callback. Never discard ready files or a running copy.
        if ("waiting".equals(operation.optString("state"))) acknowledge(operation.getString("token"));
    }
}
