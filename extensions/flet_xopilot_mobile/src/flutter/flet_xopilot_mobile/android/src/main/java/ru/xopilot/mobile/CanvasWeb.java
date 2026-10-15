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
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
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
    private TextView backButton,forwardButton,address;
    private ProgressBar loading;
    private int foreground,accent,raised;
    private int dp(Activity a,int value){return Math.round(value*a.getResources().getDisplayMetrics().density);}
    private int tone(Map<String,Object> theme,String name,String fallback){
        try{return Color.parseColor(String.valueOf(theme.getOrDefault(name,fallback)));}
        catch(Exception ignored){return Color.parseColor(fallback);}
    }
    private GradientDrawable rounded(int color,int radius){
        GradientDrawable shape=new GradientDrawable();shape.setColor(color);shape.setCornerRadius(radius);return shape;
    }
    private TextView icon(Activity a,String glyph,String label,Runnable click){
        TextView button=new TextView(a);button.setText(glyph);button.setTextSize(26);
        button.setTextColor(foreground);button.setGravity(Gravity.CENTER);button.setContentDescription(label);
        button.setBackground(rounded(raised,dp(a,24)));button.setOnClickListener(v->click.run());
        LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(dp(a,40),dp(a,44));
        params.setMargins(dp(a,2),0,dp(a,2),0);button.setLayoutParams(params);return button;
    }
    private void navigation(){
        if(view==null)return;
        backButton.setEnabled(view.canGoBack());backButton.setAlpha(view.canGoBack()?1f:.35f);
        forwardButton.setEnabled(view.canGoForward());forwardButton.setAlpha(view.canGoForward()?1f:.35f);
        String url=view.getUrl();String fragment=url!=null&&url.contains("#")?url.substring(url.indexOf('#')):"";
        String title=view.getTitle();address.setText((title==null||title.isEmpty()?"Сайт Canvas":title)+fragment);
    }

    void inspect(Activity activity, Map<String,Object> args, MethodChannel.Result result) {
        if (pending != null) { result.error("canvas_busy", "Просмотр сайта занят", null); return; }
        String html=(String)args.get("html"); String id=(String)args.get("id");
        if (html == null || id == null) { result.error("canvas_invalid", "Canvas не найден", null); return; }
        if (view == null || !id.equals(identifier)) {
            close(); identifier=id;
            dialog=new Dialog(activity);
            Map<String,Object> theme=args.get("presentation") instanceof Map?(Map<String,Object>)args.get("presentation"):java.util.Collections.emptyMap();
            int surface=tone(theme,"surface","#eafffa");foreground=tone(theme,"text","#123b43");
            accent=tone(theme,"accent","#087f8c");raised=tone(theme,"raised","#f3fffc");
            LinearLayout layout=new LinearLayout(activity);layout.setOrientation(LinearLayout.VERTICAL);layout.setBackgroundColor(surface);
            TextView brand=new TextView(activity);brand.setText("Xopilot  ·  Canvas");brand.setTextColor(tone(theme,"muted","#47747a"));
            brand.setTextSize(12);brand.setPadding(dp(activity,16),dp(activity,10),dp(activity,16),dp(activity,4));layout.addView(brand);
            LinearLayout toolbar=new LinearLayout(activity);toolbar.setGravity(Gravity.CENTER_VERTICAL);toolbar.setPadding(dp(activity,8),dp(activity,4),dp(activity,8),dp(activity,8));
            backButton=icon(activity,"‹","Назад",()->{if(view!=null&&view.canGoBack())view.goBack();});toolbar.addView(backButton);
            forwardButton=icon(activity,"›","Вперёд",()->{if(view!=null&&view.canGoForward())view.goForward();});toolbar.addView(forwardButton);
            toolbar.addView(icon(activity,"↻","Обновить страницу",()->{if(view!=null)view.reload();}));
            address=new TextView(activity);address.setText(String.valueOf(theme.getOrDefault("title","Сайт Canvas")));address.setTextSize(13);
            address.setTextColor(foreground);address.setSingleLine(true);address.setEllipsize(android.text.TextUtils.TruncateAt.END);
            address.setGravity(Gravity.CENTER_VERTICAL);address.setPadding(dp(activity,12),0,dp(activity,12),0);
            address.setBackground(rounded(raised,dp(activity,24)));address.setContentDescription("Адрес локального сайта Canvas");
            toolbar.addView(address,new LinearLayout.LayoutParams(0,dp(activity,44),1));
            toolbar.addView(icon(activity,"×","Закрыть браузер",()->close()));layout.addView(toolbar);
            loading=new ProgressBar(activity,null,android.R.attr.progressBarStyleHorizontal);loading.setMax(100);
            loading.setProgressTintList(android.content.res.ColorStateList.valueOf(accent));
            layout.addView(loading,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,dp(activity,2)));
            view=new WebView(activity);
            WebSettings settings=view.getSettings(); settings.setJavaScriptEnabled(true);
            settings.setAllowFileAccess(false); settings.setAllowContentAccess(false); settings.setBlockNetworkLoads(true);
            settings.setJavaScriptCanOpenWindowsAutomatically(false); settings.setSupportMultipleWindows(false);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            settings.setMediaPlaybackRequiresUserGesture(true);
            view.setWebChromeClient(new WebChromeClient(){
                @Override public void onPermissionRequest(PermissionRequest request){request.deny();}
                @Override public void onProgressChanged(WebView v,int value){loading.setProgress(value);loading.setVisibility(value==100?View.INVISIBLE:View.VISIBLE);}
                @Override public void onReceivedTitle(WebView v,String title){navigation();}
            });
            view.setWebViewClient(new WebViewClient(){
                @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest request){
                    String url=request.getUrl().toString();
                    return !url.startsWith("https://canvas.xopilot.invalid/#");
                }
                @Override public void doUpdateVisitedHistory(WebView v,String url,boolean reload){navigation();}
                @Override public void onPageFinished(WebView v,String url){ready=true;navigation();if(pending!=null) evaluate();}
            });
            layout.addView(view,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,1));
            dialog.setContentView(layout); dialog.setOnDismissListener(d -> close()); dialog.show();
            dialog.getWindow().setBackgroundDrawableResource(android.R.color.transparent);
            dialog.getWindow().setLayout(ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.MATCH_PARENT);
            dialog.setOnKeyListener((d,key,event)->{
                if(key==android.view.KeyEvent.KEYCODE_BACK&&event.getAction()==android.view.KeyEvent.ACTION_UP&&view!=null&&view.canGoBack()){view.goBack();return true;}return false;
            });
        }
        pending=result; arguments=args;
        if (!html.equals(content)) {
            content=html; ready=false;
            String policy="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'";
            view.loadDataWithBaseURL("https://canvas.xopilot.invalid/", "<meta http-equiv=\"Content-Security-Policy\" content=\""+policy+"\">"+html,"text/html","UTF-8",null);
        } else if (ready) {
            String op=String.valueOf(args.get("action"));
            if(op.equals("back")&&view.canGoBack()){ready=false;view.goBack();}
            else if(op.equals("forward")&&view.canGoForward()){ready=false;view.goForward();}
            else if(op.equals("reload")){ready=false;view.reload();}
            else evaluate();
        }
        activity.getWindow().getDecorView().postDelayed(() -> {
            if (pending == result) { pending=null;result.error("canvas_timeout","Просмотр сайта не ответил",null);close(); }
        },10000);
    }
    private void evaluate() {
        final MethodChannel.Result result=pending;
        if (result==null || view==null)return;
        String action=new JSONObject(arguments).toString();
        String script="(()=>{const a="+action+"; const op=a.action; if(op==='click'||op==='fill'){const es=document.querySelectorAll(a.selector);if(es.length!==1)throw Error('Нужен уникальный selector');const e=es[0];if(op==='click')e.click();else{e.value=a.text||'';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}}else if(op==='scroll')window.scrollBy(0,a.dy||300);else if(op==='reload'||op==='back'||op==='forward'){}else if(op)throw Error('Действие не поддерживается'); return JSON.stringify({title:document.title,text:document.body?.innerText.slice(0,24000)||'',elements:Array.from(document.querySelectorAll('button,a,input,textarea,select,[role=button]')).slice(0,150).map((e,index)=>{const r=e.getBoundingClientRect();return {index,tag:e.tagName,id:e.id,name:e.name,text:e.innerText?.slice(0,200)||e.getAttribute('aria-label')||'',type:e.type,value:e.type==='password'?'[password]':e.value,x:r.x,y:r.y,width:r.width,height:r.height};})});})()";
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
                output.put("can_go_back",view.canGoBack());output.put("can_go_forward",view.canGoForward());
                navigation();
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
