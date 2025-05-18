import os
import subprocess
from flask import Flask, request, send_file, render_template
from pydub import AudioSegment

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return render_template('index.html')  # Serve the home page

def process_audio_with_mute(input_video_path, timestamps_file, output_video_path):
    # Step 1: Extract audio from the input video
    extracted_audio_path = os.path.join(PROCESSED_FOLDER, "extracted_audio.wav")
    subprocess.run([
        "ffmpeg", "-i", input_video_path, "-q:a", "0", "-map", "a", extracted_audio_path, "-y"
    ])

    # Step 2: Process the original audio to mute specified time ranges
    original_audio = AudioSegment.from_file(extracted_audio_path)

    with open(timestamps_file, "r") as file:
        timestamps = file.readlines()

    for line in timestamps:
        try:
            start_time, end_time = line.strip().split(" to ")
            start_time_ms = sum(float(x) * t for x, t in zip(start_time.split(":"), [60 * 1000, 1000, 1]))
            end_time_ms = sum(float(x) * t for x, t in zip(end_time.split(":"), [60 * 1000, 1000, 1]))

            original_audio = original_audio[:start_time_ms] + AudioSegment.silent(duration=end_time_ms - start_time_ms) + original_audio[end_time_ms:]
        except ValueError:
            print(f"Skipping invalid line: {line.strip()}")

    modified_audio_path = os.path.join(PROCESSED_FOLDER, "modified_audio.wav")
    original_audio.export(modified_audio_path, format="wav")

    # Step 4: Merge new audio with original video
    subprocess.run([
        "ffmpeg", "-i", input_video_path, "-i", modified_audio_path, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", output_video_path, "-y"
    ])

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'video' not in request.files or 'timestamps' not in request.files:
        return {"error": "Missing video or timestamps file"}, 400

    video_file = request.files['video']
    timestamps_file = request.files['timestamps']

    video_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
    timestamps_path = os.path.join(UPLOAD_FOLDER, "timestamps.txt")
    output_path = os.path.join(PROCESSED_FOLDER, "output.mp4")

    video_file.save(video_path)
    timestamps_file.save(timestamps_path)

    process_audio_with_mute(video_path, timestamps_path, output_path)

    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
