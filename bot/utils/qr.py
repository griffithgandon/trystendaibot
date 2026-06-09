"""Генерация QR-кодов для подписок."""

from io import BytesIO

import qrcode
from aiogram.types import BufferedInputFile


def generate_qr(data: str, filename: str = "qr.png") -> BufferedInputFile:
    """
    Возвращает PNG QR-кода как BufferedInputFile, готовый к отправке
    через message.answer_photo(...).
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    bio = BytesIO()
    img.save(bio, "PNG")
    return BufferedInputFile(bio.getvalue(), filename=filename)
