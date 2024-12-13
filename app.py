import os
import subprocess
import wave
import json
import logging
from flask import Flask, request, render_template, send_from_directory
from vosk import Model, KaldiRecognizer

app = Flask(__name__)

model_path = r"#Путь к vosk-model-ru-0.42" 
upload_folder = "uploads"
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)

logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logging.error("Файл не найден в запросе")
        return "Файл не найден", 400

    file = request.files['file']
    if file.filename == '':
        logging.error("Файл не выбран")
        return "Вы не выбрали файл", 400

    input_mp4 = os.path.join(upload_folder, file.filename)
    file.save(input_mp4)
    logging.info(f"Файл {input_mp4} сохранен")

    output_wav = input_mp4.rsplit('.', 1)[0] + '.wav'
    logging.info(f"Конвертированный WAV-файл будет сохранен как {output_wav}")

    try:
        ffmpeg_command = [
            "ffmpeg", "-i", input_mp4, "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", output_wav
        ]
        logging.info(f"Запуск FFmpeg с командой: {' '.join(ffmpeg_command)}")
        subprocess.run(ffmpeg_command, check=True)

        if not os.path.exists(model_path):
            logging.error(f"Модель не найдена по пути: {model_path}")
            return "Модель не найдена", 500
        
        model = Model(model_path)
        with wave.open(output_wav, "rb") as wf:
            logging.info("Начало распознавания речи")
            assert wf.getnchannels() == 1, "Аудио должно быть монофоническим"
            assert wf.getsampwidth() == 2, "Ширина выборки должна быть 16 бит"
            assert wf.getframerate() == 16000, "Частота дискретизации должна быть 16 000 Гц"

            recognizer = KaldiRecognizer(model, wf.getframerate())
            result_text = ''
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    result_text += json.loads(recognizer.Result())['text'] + " "

            final_result = recognizer.FinalResult()
            result_text += json.loads(final_result)['text']

        os.remove(input_mp4)
        os.remove(output_wav)
        logging.info(f"Временные файлы удалены: {input_mp4}, {output_wav}")

        return render_template('result.html', result=result_text)

    except Exception as e:
        logging.error(f"Произошла ошибка: {e}")
        return f"Произошла ошибка: {e}", 500


if __name__ == '__main__':
    app.run(debug=True, port=8080)
