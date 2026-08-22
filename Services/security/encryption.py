"""
Файл: /Services/security/encryption.py
Разработчик: DenBroLiik
Версия: 2.0.0
Описание: __шифрование__
        защита базыданных с сообщениями
"""

# from dataclasses import dataclass
# from typing import Optional


# @dataclass
# class CryptoPayload:
#     password: Optional[str] = None
#     user: Optional[str] = None
#     message: Optional[str] = None
#     ai_message: Optional[str] = None

# def zero_dimond_encryption(data: CryptoPayload):
#     # Здесь ты просто обращаешься к свойствам через точку. IDE будет сама их подсказывать!
#     if data.password:
#         print(f"Шифруем пароль: {data.password}")

#     if data.message:
#         print(f"Шифруем текст: {data.message}")


class CryptoPayload:
    def __init__(
        self,
        password: str | None = None,
        user: str | None = None,
        message: str | None = None,
        ai_message: str | None = None,
    ):
        self.password = password
        self.user = user
        self.message = message
        self.ai_message = ai_message

    def __repr__(self):
        return (
            f"CryptoPayload(password={self.password!r}, user={self.user!r}, "
            f"message={self.message!r}, ai_message={self.ai_message!r})"
        )


def zero_dimond_encryption(data: CryptoPayload):
    # Доступ через точку работает абсолютно так же, подсказки IDE сохраняются
    if data.password:
        print(f"Шифруем пароль: {data.password}")

    if data.message:
        print(f"Шифруем текст: {data.message}")