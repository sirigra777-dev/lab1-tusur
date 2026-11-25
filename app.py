import io
import os
import random
import string
import base64
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import matplotlib
matplotlib.use('Agg')  # Фоновый режим без GUI для работы на сервере
import matplotlib.pyplot as plt
from flask import Flask, render_template, request, session, flash

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Секретный ключ для работы сессий (капча)


def generate_captcha():
    """Генерирует случайный 5-символьный код и возвращает его вместе с картинкой в Base64."""
    chars = string.ascii_uppercase + string.digits
    # Исключаем похожие символы (0, O, 1, I) для удобства пользователя
    chars = chars.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
    code = ''.join(random.choices(chars, k=5))
    session['captcha_code'] = code

    width, height = 160, 50
    image = Image.new('RGB', (width, height), color=(240, 244, 248))
    draw = ImageDraw.Draw(image)

    # Добавляем шумовые линии
    for _ in range(6):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.line(((x1, y1), (x2, y2)), fill=(150, 170, 190), width=1)

    # Добавляем шумовые точки
    for _ in range(120):
        x, y = random.randint(0, width), random.randint(0, height)
        draw.point((x, y), fill=(100, 120, 140))

    # Рисуем текст
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except IOError:
        font = ImageFont.load_default()

    for i, char in enumerate(code):
        x = 18 + i * 26 + random.randint(-3, 3)
        y = 10 + random.randint(-4, 4)
        draw.text((x, y), char, font=font, fill=(30, 50, 80))

    image = image.filter(ImageFilter.SMOOTH)

    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def image_to_base64(img):
    """Конвертирует объект PIL Image в строку Base64."""
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def create_histogram_base64(img_array, title):
    """Строит график распределения цветов (RGB гистограмму) и возвращает в Base64."""
    fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
    colors = ('red', 'green', 'blue')
    labels = ('Красный (R)', 'Зелёный (G)', 'Синий (B)')

    for i, (color, label) in enumerate(zip(colors, labels)):
        hist, bins = np.histogram(img_array[:, :, i].ravel(), bins=256, range=(0, 256))
        ax.plot(bins[:-1], hist, color=color, label=label, linewidth=1.5, alpha=0.85)
        ax.fill_between(bins[:-1], hist, color=color, alpha=0.15)

    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_xlabel('Интенсивность пикселя (0–255)', fontsize=9)
    ax.set_ylabel('Количество пикселей', fontsize=9)
    ax.set_xlim([0, 255])
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', fontsize=8)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='PNG')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


@app.route('/', methods=['GET', 'POST'])
def index():
    result_data = None
    # Значения по умолчанию для формы
    r_factor = 1.0
    g_factor = 1.0
    b_factor = 1.0

    if request.method == 'POST':
        user_captcha = request.form.get('captcha', '').strip().upper()
        saved_captcha = session.get('captcha_code', '')

        # 1. Проверка капчи
        if not user_captcha or user_captcha != saved_captcha:
            flash('Ошибка: Неверный код с картинки (капча)! Попробуйте снова.', 'danger')
        else:
            # 2. Проверка наличия файла
            file = request.files.get('image')
            if not file or file.filename == '':
                flash('Ошибка: Пожалуйста, выберите изображение для загрузки.', 'danger')
            else:
                try:
                    # Считываем коэффициенты интенсивности
                    r_factor = float(request.form.get('r_factor', 1.0))
                    g_factor = float(request.form.get('g_factor', 1.0))
                    b_factor = float(request.form.get('b_factor', 1.0))

                    # Открываем изображение и переводим в RGB
                    orig_img = Image.open(file.stream).convert('RGB')
                    
                    # Ограничиваем размер для быстрой обработки (если картинка огромная)
                    orig_img.thumbnail((800, 800))

                    # Преобразуем в массив NumPy (float32 для расчетов)
                    orig_array = np.array(orig_img, dtype=np.float32)
                    mod_array = orig_array.copy()

                    # Изменяем интенсивность выбранных цветовых карт (каналов)
                    mod_array[:, :, 0] = np.clip(mod_array[:, :, 0] * r_factor, 0, 255)
                    mod_array[:, :, 1] = np.clip(mod_array[:, :, 1] * g_factor, 0, 255)
                    mod_array[:, :, 2] = np.clip(mod_array[:, :, 2] * b_factor, 0, 255)

                    mod_array_uint8 = mod_array.astype(np.uint8)
                    orig_array_uint8 = orig_array.astype(np.uint8)
                    mod_img = Image.fromarray(mod_array_uint8)

                    # Готовим данные для отображения в шаблоне
                    result_data = {
                        'orig_img': image_to_base64(orig_img),
                        'mod_img': image_to_base64(mod_img),
                        'orig_hist': create_histogram_base64(orig_array_uint8, 'Распределение цветов: Исходное'),
                        'mod_hist': create_histogram_base64(mod_array_uint8, 'Распределение цветов: Изменённое'),
                        'r': r_factor,
                        'g': g_factor,
                        'b': b_factor
                    }
                    flash('Изображение успешно обработано!', 'success')
                except Exception as e:
                    flash(f'Ошибка при обработке файла: {str(e)}', 'danger')

    # Генерируем новую капчу при каждой загрузке страницы
    captcha_img = generate_captcha()

    return render_template(
        'index.html',
        captcha_img=captcha_img,
        result=result_data,
        r_factor=r_factor,
        g_factor=g_factor,
        b_factor=b_factor
    )


if __name__ == '__main__':
    app.run(debug=True)
