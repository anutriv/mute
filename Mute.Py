import subprocess
from pydub import AudioSegment

def process_audio_with_mute(input_video_path, timestamps_file, output_video_path):
    # Step 1: Extract audio from the input video
    extracted_audio_path = "extracted_audio.wav"
    subprocess.run([
        "ffmpeg", "-i", input_video_path, "-q:a", "0", "-map", "a", extracted_audio_path, "-y"
    ])

    # Step 2: Process the original audio to mute specified time ranges
    original_audio = AudioSegment.from_file(extracted_audio_path)

    with open(timestamps_file, "r") as file:
        timestamps = file.readlines()

    for line in timestamps:
        try:
            # Parse start and end times
            start_time, end_time = line.strip().split(" to ")
            start_time_ms = sum(float(x) * t for x, t in zip(start_time.split(":"), [60 * 1000, 1000, 1]))
            end_time_ms = sum(float(x) * t for x, t in zip(end_time.split(":"), [60 * 1000, 1000, 1]))

            # Apply silence to the specified range
            original_audio = original_audio[:start_time_ms] + \
                             AudioSegment.silent(duration=end_time_ms - start_time_ms) + \
                             original_audio[end_time_ms:]
        except ValueError:
            print(f"Skipping invalid line: {line.strip()}")

    # Step 3: Save the modified audio
    modified_audio_path = "modified_audio.wav"
    original_audio.export(modified_audio_path, format="wav")

    # Step 4: Merge the new audio with the original video
    subprocess.run([
        "ffmpeg", "-i", input_video_path, "-i", modified_audio_path, "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", output_video_path, "-y"
    ])

# Inputs
input_video_path = "input.mp4"           # Path to your input video
timestamps_file = "timestamps.txt"       # Path to your timestamps file
output_video_path = "output.mp4"         # Path to save the output video

# Run the function
process_audio_with_mute(input_video_path, timestamps_file, output_video_path)
