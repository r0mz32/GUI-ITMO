# PSF Calculator

расчет функции рассеяния точки (PSF) и применение к изображениям

## что умеет

- считать PSF с разными параметрами
- показывать графики PSF
- применять размытие к картинкам
- чистый python

## установка

```bash
pip install -r requirements.txt
python3 main.py
```

## скрины

### PSF Calculator
![PSF Tab](imgs/PSF_tab.png)

тут считается PSF с настройкой параметров

### Image Processing
![Processing Tab](imgs/Processing_tab.png)

тут применяем PSF к картинкам

## параметры PSF

- размер выборки
- длина волны
- апертура
- увеличение
- расфокусировка
- астигматизм
- охват зрачка

## зависимости

- PyQt6 - интерфейс
- NumPy - вычисления
- SciPy - свертка
- Matplotlib - графики
- Pillow - картинки

## сборка исполняемого файла \ exe
Необходимо установить библиотеку pyinstaller
```bash
pip install pyinstaller
```

И выполнить одну из команд для систем:

- Linux
```bash
pyinstaller --onefile --windowed --name="PSF_Calculator" \
  --add-data "frontend:frontend" \
  --add-data "backend:backend" \
  --add-data "imgs:imgs" \
  --hidden-import PyQt6.QtCore \
  --hidden-import PyQt6.QtGui \
  --hidden-import PyQt6.QtWidgets \
  --hidden-import matplotlib \
  --hidden-import numpy \
  --hidden-import scipy \
  --hidden-import PIL \
  main.py
  ```
Исполняемй файл для Linux лежит в папке dist

- Windows
```bash
pyinstaller --onefile --windowed --name="PSF_Calculator" ^
  --add-data "frontend;frontend" ^
  --add-data "backend;backend" ^
  --add-data "imgs;imgs" ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtGui ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import matplotlib ^
  --hidden-import numpy ^
  --hidden-import scipy ^
  --hidden-import PIL ^
  main.py
  ```
