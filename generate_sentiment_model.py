"""
Скрипт генерации тестовой ONNX-модели для Xopilot (пункт 5 плана — «ИИ для теста»).
Запускается один раз, чтобы сгенерировать App/assets/models/sentiment.onnx.

ЭТО НЕ обученная модель — веса проставлены вручную, чтобы проверить целиком пайплайн:
текст -> баг-оф-вордс по фиксированному словарю -> линейный слой -> softmax -> класс.
Сама баг-оф-вордс векторизация считается в Rust (Services/src/ai/mod.rs) — модель принимает
готовый вектор из 16 чисел (см. VOCAB ниже, порядок должен совпадать с Rust-версией словаря).

Запуск: python3 generate_sentiment_model.py
"""

import os
import numpy as np
import onnx
from onnx import helper, TensorProto

# ПОРЯДОК ВАЖЕН — тот же список и в том же порядке должен быть в Services/src/ai/mod.rs
POSITIVE_WORDS = ["хорошо", "отлично", "супер", "круто", "нравится", "спасибо", "класс", "рад"]
NEGATIVE_WORDS = ["плохо", "ужасно", "проблема", "ошибка", "жаль", "грустно", "бесит", "разочарован"]
VOCAB = POSITIVE_WORDS + NEGATIVE_WORDS  # 16 слов, индексы 0-7 позитив, 8-15 негатив

# классы: 0 = negative, 1 = neutral, 2 = positive
N_FEATURES = len(VOCAB)
N_CLASSES = 3

W = np.zeros((N_FEATURES, N_CLASSES), dtype=np.float32)
for i in range(len(POSITIVE_WORDS)):
    W[i, 2] = 2.0   # позитивное слово тянет к классу "positive"
    W[i, 0] = -0.3  # и слегка отталкивает от "negative"
for i in range(len(POSITIVE_WORDS), N_FEATURES):
    W[i, 0] = 2.0   # негативное слово тянет к классу "negative"
    W[i, 2] = -0.3

B = np.array([0.0, 0.5, 0.0], dtype=np.float32)  # небольшой сдвиг к "neutral", если слов не найдено

input_tensor = helper.make_tensor_value_info("features", TensorProto.FLOAT, [1, N_FEATURES])
output_tensor = helper.make_tensor_value_info("probabilities", TensorProto.FLOAT, [1, N_CLASSES])

weight_init = helper.make_tensor("W", TensorProto.FLOAT, W.shape, W.flatten().tolist())
bias_init = helper.make_tensor("B", TensorProto.FLOAT, B.shape, B.flatten().tolist())

gemm_node = helper.make_node("Gemm", inputs=["features", "W", "B"], outputs=["logits"], alpha=1.0, beta=1.0)
softmax_node = helper.make_node("Softmax", inputs=["logits"], outputs=["probabilities"], axis=1)

graph = helper.make_graph(
    nodes=[gemm_node, softmax_node],
    name="XopilotSentimentTest",
    inputs=[input_tensor],
    outputs=[output_tensor],
    initializer=[weight_init, bias_init],
)

model = helper.make_model(
    graph,
    producer_name="xopilot-sentiment-test-generator",
    opset_imports=[helper.make_opsetid("", 13)],
)
model.ir_version = 8
onnx.checker.check_model(model)

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "App", "assets", "models")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "sentiment.onnx")
onnx.save(model, out_path)
print(f"saved: {out_path}")
print(f"vocab ({N_FEATURES} words): {VOCAB}")