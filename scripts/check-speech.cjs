// Проверяю границу системного TTS без проигрывания звука и без сетевого голоса.
const fs=require('node:fs'), assert=require('node:assert/strict');
const {test}=require('node:test');
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
async function scenario(mode){
 const events=[],spoken=[];let current,cancelled=0;
 const synthesis={getVoices:()=>[{lang:'ru-RU',localService:mode!=='network'}],
  speak(utterance){current=utterance;spoken.push(utterance.text);queueMicrotask(()=>mode==='cancel'?stop():utterance.onend());},
  cancel(){cancelled++;if(mode==='cancel')current?.onerror();}
 };
 let stop;const command=new Promise(resolve=>{stop=resolve;});
 const script=new AsyncFunction('dioxus','window','document','SpeechSynthesisUtterance',fs.readFileSync('App/services/speech_play.js','utf8').replace('__XOPILOT_TEXT__',JSON.stringify(['Проверка','Готово'])));
 await script({recv:()=>command,send:e=>events.push(e)},{speechSynthesis:mode==='missing'?null:synthesis},{addEventListener(){},removeEventListener(){}},class{constructor(text){this.text=text;}});
 return{events,spoken,cancelled};
}
test('local voice completes chunks in order',async()=>{const r=await scenario('local');assert.deepEqual(r.spoken,['Проверка','Готово']);assert.equal(r.events[0].ok,true);assert.ok(r.cancelled>0);});
test('network voice is not used for private reply',async()=>{const r=await scenario('network');assert.equal(r.spoken.length,0);assert.ok(r.events[0].error.includes('Локальный'));});
test('missing engine returns actual error',async()=>{const r=await scenario('missing');assert.ok(r.events[0].error.includes('недоступно'));});
test('stop cancels the utterance and next chunk',async()=>{const r=await scenario('cancel');assert.equal(r.spoken.length,1);assert.ok(r.events[0].error);assert.ok(r.cancelled>0);});
