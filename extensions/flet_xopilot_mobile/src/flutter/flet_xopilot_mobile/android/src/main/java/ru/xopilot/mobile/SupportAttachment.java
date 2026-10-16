/*
Файл: /extensions/flet_xopilot_mobile/android/SupportAttachment.java
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Только чтение диагностического архива через временное разрешение почтовому клиенту.
*/
package ru.xopilot.mobile;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileNotFoundException;

public final class SupportAttachment extends ContentProvider {
    public boolean onCreate() { return true; }
    private File file(Uri uri) throws FileNotFoundException {
        if (!uri.getAuthority().equals(getContext().getPackageName()+".xopilot.support") || uri.getPathSegments().size()!=1)
            throw new FileNotFoundException();
        String name=uri.getLastPathSegment();
        if (name==null || !name.matches("[0-9a-f-]{36}\\.zip")) throw new FileNotFoundException();
        File path=new File(new File(getContext().getCacheDir(),"support"),name);
        if (!path.isFile()) throw new FileNotFoundException();
        return path;
    }
    public String getType(Uri uri) { return "application/zip"; }
    public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
        if (!"r".equals(mode)) throw new FileNotFoundException();
        return ParcelFileDescriptor.open(file(uri),ParcelFileDescriptor.MODE_READ_ONLY);
    }
    public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order) {
        MatrixCursor result=new MatrixCursor(new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE});
        try { result.addRow(new Object[]{"xopilot-support.zip",file(uri).length()}); } catch(FileNotFoundException ignored) {}
        return result;
    }
    public Uri insert(Uri uri,ContentValues values) { throw new UnsupportedOperationException(); }
    public int delete(Uri uri,String where,String[] args) { throw new UnsupportedOperationException(); }
    public int update(Uri uri,ContentValues values,String where,String[] args) { throw new UnsupportedOperationException(); }
}
