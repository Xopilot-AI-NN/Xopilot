/*
Файл: /extensions/flet_xopilot_mobile/android/CanvasWeb.java
Разработчик: DenBroLiik
Версия: 2.0.8
Описание: Интерактивный WebView для сайта Canvas без доступа к сети и файлам устройства.
*/
package ru.xopilot.mobile;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.util.Base64;
import android.view.ViewGroup;
import android.webkit.*;
import android.widget.*;
import io.flutter.plugin.common.MethodChannel;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.util.Map;

/** A dedicated offline WebView, without a JavascriptInterface/file bridge. */
final class CanvasWeb {
    private Dialog dialog;
    private WebView view;
    private String content;
    private String identifier;
    private MethodChannel.Result pending;
    private Map<String,Object> arguments;
    private boolean ready=false;

    void inspect(Activity activity, Map<String,Object> args, MethodChannel.Result result) {
        if (pending != null) { result.error("canvas_busy", "Просмотр сайта занят", null); return; }
        String html=(String)args.get("html"); String id=(String)args.get("id");
        if (html == null || id == null) { result.error("canvas_invalid", "Canvas не найден", null); return; }
        if (view == null || !id.equals(identifier)) {
            close(); identifier=id;
            dialog=new Dialog(activity);
            LinearLayout layout=new LinearLayout(activity); layout.setOrientation(LinearLayout.VERTICAL);
            LinearLayout toolbar=new LinearLayout(activity);
            TextView title=new TextView(activity); title.setText("Canvas · сайт"); title.setTextSize(18); title.setPadding(24,16,8,16);
            toolbar.addView(title,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
            Button done=new Button(activity); done.setText("Закрыть"); done.setOnClickListener(v -> close()); toolbar.addView(done);
            layout.addView(toolbar);
            view=new WebView(activity);
            WebSettings settings=view.getSettings(); settings.setJavaScriptEnabled(true);
            settings.setAllowFileAccess(false); settings.setAllowContentAccess(false); settings.setBlockNetworkLoads(true);
            settings.setJavaScriptCanOpenWindowsAutomatically(false); settings.setSupportMultipleWindows(false);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            settings.setMediaPlaybackRequiresUserGesture(true);
            view.setWebChromeClient(new WebChromeClient(){@Override public void onPermissionRequest(PermissionRequest request){request.deny();}});
            view.setWebViewClient(new WebViewClient(){
                @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest request){return true;}
                @Override public void onPageFinished(WebView v,String url){ready=true;if(pending!=null) evaluate();}
            });
            layout.addView(view,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,1));
            dialog.setContentView(layout); dialog.setOnDismissListener(d -> close()); dialog.show();
            dialog.getWindow().setLayout(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT);
        }
        pending=result; arguments=args;
        if (!html.equals(content)) {
            content=html; ready=false;
            String policy="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'";
            view.loadDataWithBaseURL("https://canvas.xopilot.invalid/", "<meta http-equiv=\"Content-Security-Policy\" content=\""+policy+"\">"+html,"text/html","UTF-8",null);
        } else if (ready) evaluate();
        activity.getWindow().getDecorView().postDelayed(() -> {
            if (pending == result) { pending=null;result.error("canvas_timeout","Просмотр сайта не ответил",null);close(); }
        },10000);
    }
    private void evaluate() {
        final MethodChannel.Result result=pending;
        if (result==null || view==null)return;
        String action=new JSONObject(arguments).toString();
        String script="(()=>{const a="+action+"; const op=a.action; if(op==='click'||op==='fill'){const es=document.querySelectorAll(a.selector);if(es.length!==1)throw Error('Нужен уникальный selector');const e=es[0];if(op==='click')e.click();else{e.value=a.text||'';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}}else if(op==='scroll')window.scrollBy(0,a.dy||300);else if(op==='reload')location.reload();else if(op)throw Error('Действие не поддерживается'); return JSON.stringify({title:document.title,text:document.body?.innerText.slice(0,24000)||'',elements:Array.from(document.querySelectorAll('button,a,input,textarea,select,[role=button]')).slice(0,150).map((e,index)=>{const r=e.getBoundingClientRect();return {index,tag:e.tagName,id:e.id,name:e.name,text:e.innerText?.slice(0,200)||e.getAttribute('aria-label')||'',type:e.type,value:e.type==='password'?'[password]':e.value,x:r.x,y:r.y,width:r.width,height:r.height};})});})()";
        view.evaluateJavascript(script, json -> {
            if(pending!=result)return;
            pending=null;
            try {
                if(json==null || "null".equals(json))throw new IllegalStateException("Не удалось выполнить действие или прочитать страницу");
                String decoded=new org.json.JSONTokener(json).nextValue().toString();
                JSONObject output=new JSONObject(decoded);
                int width=Math.max(1,view.getWidth()),height=Math.max(1,view.getHeight());
                float scale=Math.min(1f,960f/width);
                Bitmap bitmap=Bitmap.createBitmap(Math.max(1,Math.round(width*scale)),Math.max(1,Math.round(height*scale)),Bitmap.Config.ARGB_8888);
                Canvas canvas=new Canvas(bitmap);canvas.scale(scale,scale);view.draw(canvas);
                ByteArrayOutputStream stream=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,90,stream);bitmap.recycle();
                output.put("image",Base64.encodeToString(stream.toByteArray(),Base64.NO_WRAP));
                output.put("width",Math.round(width*scale));output.put("height",Math.round(height*scale));output.put("network","blocked");
                result.success(output.toString());
            } catch(Exception error){result.error("canvas_web",error.getMessage(),null);}
        });
    }
    void close() {
        if(pending!=null){MethodChannel.Result result=pending;pending=null;result.error("canvas_closed","Просмотр закрыт",null);}
        WebView old=view;view=null;content=null;identifier=null;ready=false;
        Dialog previous=dialog;dialog=null;
        if(previous!=null){previous.setOnDismissListener(null);previous.dismiss();}
        if(old!=null){old.stopLoading();old.loadUrl("about:blank");old.destroy();}
    }
}
