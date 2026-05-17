from bs4 import BeautifulSoup
import os

def extract_js_from_html(html_file, output_txt):
    try:
        # 1. Читаем файл index.html
        if not os.path.exists(html_file):
            print(f"Ошибка: Файл {html_file} не найден.")
            return

        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # 2. Парсим HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 3. Находим все теги <script>
        scripts = soup.find_all('script')
        
        extracted_code = []
        
        for i, script in enumerate(scripts):
            # Проверяем, есть ли внутри тега код (инлайновый JS)
            if script.string:
                content = script.string.strip()
                if content:
                    header = f"/* --- Script Block #{i+1} --- */\n"
                    extracted_code.append(header + content + "\n")
            
            # Если это подключение внешнего файла, можно просто записать его путь
            elif script.get('src'):
                extracted_code.append(f"/* Внешний файл: {script.get('src')} */\n")

        # 4. Записываем результат в файл
        if extracted_code:
            with open(output_txt, 'w', encoding='utf-8') as f:
                f.write("\n".join(extracted_code))
            print(f"Успех! Весь JS код сохранен в файл: {output_txt}")
        else:
            print("В файле index.html не найдено JavaScript кода внутри тегов <script>.")

    except Exception as e:
        print(f"Произошла ошибка: {e}")

# Запуск функции
if __name__ == "__main__":
    extract_js_from_html('index.html', 'extracted_js.txt')