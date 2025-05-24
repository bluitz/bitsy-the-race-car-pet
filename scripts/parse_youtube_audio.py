import yt_dlp
import librosa
import numpy as np
import whisper
import os

# pip install yt-dlp librosa numpy soundfile openai-whisper
# And make sure FFmpeg is installed:

# macOS: brew install ffmpeg
# STEP 1: Download audio from YouTube
def download_audio(youtube_url, output_filename="downloaded_audio.mp3"):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_filename,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

# STEP 2: Analyze audio with Librosa
def analyze_audio(audio_path):
    y, sr = librosa.load(audio_path, duration=180)

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    chroma = librosa.feature.chroma_stft(y=y, sr=sr)

    analysis_summary = f"""
Song Analysis:
- Tempo: approx {round(tempo)} BPM
- Total Beats: {len(beat_times)}
- First 10 Beat Timestamps: {np.round(beat_times[:10], 2).tolist()}
- First 10 Onset Timestamps: {np.round(onset_times[:10], 2).tolist()}
- Chroma Shape: {chroma.shape} (12 pitch classes x time)
"""
    return analysis_summary

# STEP 3: Transcribe vocals using Whisper
def transcribe_audio(audio_path):
    model = whisper.load_model("base")  # Choose base, small, medium, large
    result = model.transcribe(audio_path)
    return result['text'], result['segments']

# STEP 4: Combine into GPT-ready summary
def generate_gpt_prompt(audio_summary, transcription, segments):
    prompt = f"""
Analyze the structure of the song based on the following:

🎵 Audio Summary:
{audio_summary}

🗣️ Transcribed Lyrics:
{transcription[:1000]}{'...' if len(transcription) > 1000 else ''}

🕒 Timestamped Transcript Segments:
"""
    for seg in segments[:5]:
        prompt += f"- [{seg['start']:.2f}s - {seg['end']:.2f}s]: {seg['text']}\n"

    prompt += "\nLabel likely song sections (intro, verse, chorus, bridge), and explain your reasoning."

    return prompt

# MAIN EXECUTION
if __name__ == "__main__":
    youtube_url = input("Enter a YouTube video URL: ")
    audio_file = "downloaded_audio.mp3"

    print("🔽 Downloading audio...")
    download_audio(youtube_url, audio_file)

    print("🎼 Analyzing audio structure...")
    audio_summary = analyze_audio(audio_file)

    print("🗣️ Transcribing lyrics with Whisper...")
    transcription, segments = transcribe_audio(audio_file)

    print("\n🧠 GPT Prompt:\n")
    gpt_prompt = generate_gpt_prompt(audio_summary, transcription, segments)
    print(gpt_prompt)
