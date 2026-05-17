from flask import Flask, send_from_directory
import os

app = Flask(__name__)

# Путь к папке, где лежит этот скрипт
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    # Отдаем index.html из корня папки
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    # Позволяет подгружать .css, .js или картинки, если они лежат рядом
    return send_from_directory(BASE_DIR, path)

if __name__ == '__main__':
    print("Frontend started: http://localhost:8080")
    print("Make sure site_api.py is also running on port 5000")
    # Запускаем на порту 8080, чтобы не конфликтовать с API (порт 5000)
    app.run(host='0.0.0.0', port=8080)