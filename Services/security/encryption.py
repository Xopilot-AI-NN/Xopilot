"""
Файл: /Services/security/encryption.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __шифрование__
        защита базыданных с сообщениями
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CryptoPayload:
    password: Optional[str] = None
    user: Optional[str] = None
    message: Optional[str] = None
    ai_message: Optional[str] = None

def zero_dimond_encryption(data: CryptoPayload):
    # Здесь ты просто обращаешься к свойствам через точку. IDE будет сама их подсказывать!
    if data.password:
        print(f"Шифруем пароль: {data.password}")

    if data.message:
        print(f"Шифруем текст: {data.message}")
