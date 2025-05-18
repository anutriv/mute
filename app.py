import os
import subprocess
from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS
from pydub import AudioSegment

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # Allow up to 2GB uploads

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

def process_audio_with_mute(input_video_path, timestamps_file, output_video_path):
    extracted_audio_path = os.path.join(PROCESSED_FOLDER, "extracted_audio.wav")

    # ✅ Fix 1: Extract audio using PCM encoding instead of AAC
    subprocess.run([
        "ffmpeg", "-i", input_video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100",
        "-ac", "2", extracted_audio_path, "-y"
    ])

    # ✅ Fix 2: Verify pydub can read the extracted audio file
    try:
        original_audio = AudioSegment.from_file(extracted_audio_path, format="wav")
    except Exception as e:
        print(f"Error loading audio file: {str(e)}")
        return jsonify({"error": "Audio decoding failed"}), 500

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

    subprocess.run([
        "ffmpeg", "-i", input_video_path, "-i", modified_audio_path, "-c:v", "libx264", "-preset", "ultrafast",
        "-map", "0:v:0", "-map", "1:a:0", "-shortest", output_video_path, "-y"
    ])

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'video' not in request.files or 'timestamps' not in request.files:
        return jsonify({"error": "Missing video or timestamps file"}), 400

    video_file = request.files['video']
    timestamps_file = request.files['timestamps']

    video_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
    timestamps_path = os.path.join(UPLOAD_FOLDER, "timestamps.txt")

    try:
        # Write video file in chunks
        with open(video_path, "wb") as f:
            while True:
                chunk = video_file.stream.read(1024 * 1024)  # Read 1MB chunks
                if not chunk:
                    break
                f.write(chunk)

        # Write timestamps file in chunks
        with open(timestamps_path, "wb") as f:
            while True:
                chunk = timestamps_file.stream.read(1024)
                if not chunk:
                    break
                f.write(chunk)

        if os.path.exists(video_path) and os.path.exists(timestamps_path):
            return jsonify({"success": True, "message": "Upload completed"}), 200
        else:
            return jsonify({"error": "File saving failed"}), 500

    except Exception as e:
        return jsonify({"error": f"Exception during file save: {str(e)}"}), 500

@app.route('/process', methods=['GET'])
def process_video():
    video_path = os.path.join(UPLOAD_FOLDER, "input.mp4")
    timestamps_path = os.path.join(UPLOAD_FOLDER, "timestamps.txt")
    output_path = os.path.join(PROCESSED_FOLDER, "output.mp4")

    if not os.path.exists(video_path) or not os.path.exists(timestamps_path):
        return jsonify({"error": "Files missing, upload first"}), 400

    process_audio_with_mute(video_path, timestamps_path, output_path)

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return send_file(output_path, as_attachment=True)
    else:
        return jsonify({"error": "Processing failed, output file is empty"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
