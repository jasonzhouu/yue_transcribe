import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import yt_dlp
import json
import hashlib
import subprocess
from typing import Optional, Dict, List

# Load environment variables
load_dotenv()

def get_video_hash(youtube_url: str) -> str:
    """Generate a hash from YouTube URL"""
    return hashlib.md5(youtube_url.encode()).hexdigest()

def download_youtube_audio(youtube_url: str, file_hash: str) -> Optional[str]:
    """Download audio from YouTube video"""
    output_path = os.path.join('temp', f"original_{file_hash}.wav")
    
    # Check if file already exists
    if os.path.exists(output_path):
        print(f"Audio file already exists: {output_path}")
        return output_path
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'outtmpl': output_path.replace('.wav', ''),
        'nocheckcertificate': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        return output_path
    except Exception as e:
        print(f"Error downloading audio: {str(e)}")
        return None

def download_youtube_video(youtube_url: str, file_hash: str) -> Optional[str]:
    """Download video with audio from YouTube"""
    output_template = os.path.join('temp', f"original_{file_hash}.%(ext)s")
    
    # Try to find existing video file
    for ext in ['mp4', 'mkv', 'webm']:
        existing_file = os.path.join('temp', f"original_{file_hash}.{ext}")
        if os.path.exists(existing_file):
            print(f"Video file already exists: {existing_file}")
            return existing_file
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_template,
        'nocheckcertificate': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            video_path = ydl.prepare_filename(info)
        return video_path
    except Exception as e:
        print(f"Error downloading video: {str(e)}")
        return None

def transcribe_with_azure(audio_file: str, file_hash: str) -> Optional[str]:
    """Transcribe audio using Azure Speech Services"""
    try:
        transcript_file = os.path.join('temp', f'{file_hash}_transcript_raw_azure_speech.json')
        
        # Check if transcript file already exists
        if os.path.exists(transcript_file):
            print(f"Transcript file already exists: {transcript_file}")
            return transcript_file

        # Configure Azure Speech Service
        speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv('AZURE_SPEECH_KEY'),
            region=os.getenv('AZURE_SPEECH_REGION')
        )
        
        # Set the recognition language
        speech_config.speech_recognition_language = "zh-HK"
        
        # Create audio configuration from the WAV file
        audio_config = speechsdk.audio.AudioConfig(filename=audio_file)
        
        # Create speech recognizer
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config
        )

        # Initialize variables for collecting results
        transcription_results = []
        done = False

        def handle_result(evt):
            if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
                result = {
                    'text': evt.result.text,
                    'offset': evt.result.offset,
                    'duration': evt.result.duration
                }
                transcription_results.append(result)

        def stop_cb(evt):
            print('CLOSING on {}'.format(evt))
            nonlocal done
            done = True

        # Connect callbacks
        speech_recognizer.recognized.connect(handle_result)
        speech_recognizer.session_stopped.connect(stop_cb)
        speech_recognizer.canceled.connect(stop_cb)

        # Start continuous recognition
        speech_recognizer.start_continuous_recognition()
        while not done:
            pass
        speech_recognizer.stop_continuous_recognition()

        # Save transcription results
        with open(transcript_file, 'w', encoding='utf-8') as f:
            json.dump({
                'transcripts': [{
                    'text': ' '.join(r['text'] for r in transcription_results),
                    'sentences': [{
                        'text': r['text'],
                        'begin_time': r['offset'] / 10000000,  # Convert from 100-nanosecond units to seconds
                        'end_time': (r['offset'] + r['duration']) / 10000000
                    } for r in transcription_results]
                }]
            }, f, ensure_ascii=False, indent=2)

        return transcript_file

    except Exception as e:
        print(f"Transcription error: {str(e)}")
        return None

def create_srt_from_transcript(transcript_data: Dict) -> str:
    """Convert transcript data to SRT format"""
    srt_content = []
    counter = 1
    
    for sentence in transcript_data.get('sentences', []):
        start_time = float(sentence.get('begin_time', 0))
        end_time = float(sentence.get('end_time', 0))
        text = sentence.get('text', '')
        
        # Convert seconds to SRT time format (HH:MM:SS,mmm)
        start_formatted = f"{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d},{int((start_time*1000)%1000):03d}"
        end_formatted = f"{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d},{int((end_time*1000)%1000):03d}"
        
        srt_entry = f"{counter}\n{start_formatted} --> {end_formatted}\n{text}\n\n"
        srt_content.append(srt_entry)
        counter += 1
    
    return ''.join(srt_content)

def parse_transcription_file(transcript_file: str) -> Optional[Dict]:
    """Read and parse transcript JSON file"""
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'transcripts' in data:
            return {
                'text': data['transcripts'][0].get('text', ''),
                'sentences': data['transcripts'][0].get('sentences', [])
            }
        return None
    except Exception as e:
        print(f"Error reading transcript: {str(e)}")
        return None

def embed_subtitles(source_video_path: str, srt_path: str, file_hash: str) -> Optional[str]:
    """Embed SRT subtitles into video file"""
    try:
        # Get the extension from the original video
        video_ext = os.path.splitext(source_video_path)[1]
        # Determine output path using file hash and original video extension
        output_video = os.path.join('temp', f'output_{file_hash}{video_ext}')
        
        # Check if output file already exists
        if os.path.exists(output_video):
            print(f"Video with subtitles already exists: {output_video}")
            return output_video
            
        print(f"Embedding subtitles into video: {output_video}")
        cmd = [
            'ffmpeg', '-i', source_video_path,
            '-i', srt_path,
            '-c', 'copy',
            '-c:s', 'mov_text',
            output_video
        ]
        subprocess.run(cmd, check=True)
        return output_video
    except subprocess.CalledProcessError as e:
        print(f"Error embedding subtitles: {str(e)}")
        return None

def process_youtube_video(youtube_url: str) -> Optional[str]:
    """Process YouTube video and generate transcript using Azure Speech Services"""
    try:
        # Create temp directory if it doesn't exist
        os.makedirs('temp', exist_ok=True)
        
        # Get hash for consistent naming
        file_hash = get_video_hash(youtube_url)
        
        # Download audio and video
        audio_path = download_youtube_audio(youtube_url, file_hash)
        if not audio_path:
            raise Exception("Failed to download audio")
            
        video_path = download_youtube_video(youtube_url, file_hash)
        if not video_path:
            raise Exception("Failed to download video")
        
        # Transcribe with Azure
        transcription_file = transcribe_with_azure(audio_path, file_hash)
        if not transcription_file:
            raise Exception("Failed to get transcription")
            
        # Parse transcript
        transcript_data = parse_transcription_file(transcription_file)
        if not transcript_data:
            raise Exception("Failed to parse transcript")
        
        # Create SRT file
        srt_content = create_srt_from_transcript(transcript_data)
        srt_path = os.path.join('temp', f'{file_hash}.srt')
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        # Embed subtitles
        output_video = embed_subtitles(video_path, srt_path, file_hash)
        if not output_video:
            raise Exception("Failed to embed subtitles")
            
        # Clean up temporary files
        if os.path.exists(srt_path):
            os.remove(srt_path)
                
        print(f"Video with subtitles saved as: {output_video}")
        print(f"Transcript saved as: {transcription_file}")
        return output_video
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return None

if __name__ == "__main__":
    youtube_url = input("Enter YouTube URL: ")
    if youtube_url.strip():
        output_video = process_youtube_video(youtube_url)
        print('Output video:', output_video)
    else:
        print("No URL provided") 