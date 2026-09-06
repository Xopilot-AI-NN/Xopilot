// Файл: Services/src/ai/mod.rs
pub mod llm;

// Описание: Тестовая локальная ИИ-модель (пункт 5 плана) — классификатор тональности
//    сообщения через ONNX (tract-onnx, чистый Rust, без внешней C++ библиотеки).
//
//    Модель НЕ обученная — это проверка пайплайна (загрузка ONNX -> инференс -> ответ),
//    веса заданы вручную в generate_sentiment_model.py в корне репо. Словарь ниже ДОЛЖЕН
//    точно совпадать со словарём в том скрипте — иначе индексы фич разойдутся с весами модели.

use std::path::Path;
use tract_onnx::prelude::*;

/// Порядок СОВПАДАЕТ с VOCAB в generate_sentiment_model.py: 0-7 позитив, 8-15 негатив.
const VOCAB: [&str; 16] = [
    "хорошо", "отлично", "супер", "круто", "нравится", "спасибо", "класс", "рад",
    "плохо", "ужасно", "проблема", "ошибка", "жаль", "грустно", "бесит", "разочарован",
];

/// Индекс класса -> метка (порядок задан в generate_sentiment_model.py: 0=negative, 1=neutral, 2=positive).
const LABELS: [&str; 3] = ["negative", "neutral", "positive"];

type OnnxModel = TypedRunnableModel<TypedModel>;

pub struct SentimentClassifier {
    model: OnnxModel,
}

impl SentimentClassifier {
    /// Загружает ONNX-модель и оптимизирует её под фиксированную форму входа (1, 16).
    pub fn load<P: AsRef<Path>>(model_path: P) -> TractResult<Self> {
        let model = tract_onnx::onnx()
            .model_for_path(model_path)?
            .into_optimized()?
            .into_runnable()?;
        Ok(SentimentClassifier { model })
    }

    /// Простая векторизация: счёт вхождений каждого слова из VOCAB в тексте (подстрока,
    /// без морфологии) — это тест-модель, точная токенизация — задача будущей настоящей модели.
    fn vectorize(text: &str) -> [f32; 16] {
        let lower = text.to_lowercase();
        let mut features = [0.0f32; 16];
        for (i, word) in VOCAB.iter().enumerate() {
            if lower.contains(word) {
                features[i] = 1.0;
            }
        }
        features
    }

    /// Возвращает (метка_класса, уверенность 0..1).
    pub fn classify(&self, text: &str) -> TractResult<(String, f32)> {
        let features = Self::vectorize(text);
        let input: Tensor = tract_ndarray::Array2::from_shape_vec((1, 16), features.to_vec())?.into();

        let outputs = self.model.run(tvec!(input.into()))?;
        let probabilities = outputs[0].to_array_view::<f32>()?;

        let mut best_index = 0usize;
        let mut best_score = f32::MIN;
        for (i, &score) in probabilities.iter().enumerate() {
            if score > best_score {
                best_score = score;
                best_index = i;
            }
        }

        Ok((LABELS[best_index].to_string(), best_score))
    }
}