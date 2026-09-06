// Файл: Services/src/ai/llm.rs
// Описание: Рабочий локальный ИИ — квантованная GGUF-модель через candle/candelabra
//    (чистый Rust, без llama.cpp/C++). Поддерживаемые архитектуры (определяются автоматически
//    по метаданным GGUF): llama/mistral/mixtral/gemma/gemma2/gemma3/phi/phi2/phi3/qwen2/qwen3/glm4/
//    lfm2/smollm3. gemma3n (elastic E2B/E4B) НЕ поддерживается — для неё нужен llama.cpp/llama-cpp-python.
//
//    GGUF-файл НЕ скачивается этим модулем — ожидается уже положенным вручную в App/data/models/.
//    Токенизатор (маленький tokenizer.json) тянется с Hugging Face автоматически через candelabra.

use candelabra::{load_tokenizer_from_repo, run_inference, InferenceConfig, Model};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tokenizers::Tokenizer;

/// Маркеры конца хода у большинства chat-моделей (Phi-3/4 стиль). candelabra не имеет
/// встроенных stop-последовательностей (только stop_on_eos), поэтому режем обрываем вручную.
const STOP_MARKERS: [&str; 3] = ["<|end|>", "<|user|>", "<|system|>"];

pub struct LocalLlm {
    model: Model,
    tokenizer: Tokenizer,
}

impl LocalLlm {
    /// Загружает GGUF из локального файла (без скачивания) + токенизатор с HF репозитория.
    /// `tokenizer_repo` — обычно оригинальный репозиторий модели (не GGUF-репо квантователя) —
    /// например "microsoft/Phi-4-mini-instruct" для ггуф-файлов из bartowski/microsoft_Phi-4-mini-instruct-GGUF.
    pub fn load<P: AsRef<Path>>(model_path: P, tokenizer_repo: &str) -> anyhow::Result<Self> {
        let tokenizer = load_tokenizer_from_repo(tokenizer_repo)?;
        let model = Model::load(model_path.as_ref())?;
        Ok(LocalLlm { model, tokenizer })
    }

    pub fn architecture(&self) -> String {
        self.model.architecture().to_string()
    }

    /// `prompt` должен быть уже отформатирован под шаблон chat-шаблона конкретной модели —
    /// это ответственность вызывающего кода (services/llm.py), не этого модуля.
    pub fn generate(&mut self, prompt: &str, max_tokens: usize) -> anyhow::Result<String> {
        let cancel_token = Arc::new(AtomicBool::new(false));
        let config = InferenceConfig {
            model_id: String::new(),
            filename: String::new(),
            prompt: prompt.to_string(),
            max_tokens,
            temperature: 0.7,
            max_duration_secs: Some(120), // предохранитель от зависшей генерации
            stop_on_eos: true,
        };

        let output = Mutex::new(String::new());
        let stop_flag = cancel_token.clone();

        run_inference(
            &mut self.model,
            &self.tokenizer,
            &config,
            cancel_token,
            |token| {
                let mut buf = output.lock().unwrap();
                buf.push_str(&token);
                if STOP_MARKERS.iter().any(|marker| buf.contains(marker)) {
                    stop_flag.store(true, Ordering::SeqCst);
                }
                Ok(())
            },
        )?;

        let mut text = output.into_inner().unwrap();
        for marker in STOP_MARKERS {
            if let Some(pos) = text.find(marker) {
                text.truncate(pos);
            }
        }
        Ok(text.trim().to_string())
    }
}