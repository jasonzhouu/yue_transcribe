import dashscope
from http import HTTPStatus
import yt_dlp
import os
from dotenv import load_dotenv
import oss2
import time
import ssl
import certifi
import requests
import json
import subprocess
import re
import hashlib

# Disable SSL verification warnings and set up SSL context
ssl._create_default_https_context = ssl._create_unverified_context

# Load environment variables
load_dotenv()
dashscope.api_key = os.getenv('ALIYUN_BAILIAN_API_KEY')

# Create temp directory if it doesn't exist
os.makedirs('temp', exist_ok=True)

def get_video_hash(youtube_url):
    """Generate a hash from YouTube URL"""
    return hashlib.md5(youtube_url.encode()).hexdigest()

def download_youtube_audio(youtube_url):
    """Download audio from YouTube video"""
    # Generate hash for filename
    file_hash = get_video_hash(youtube_url)
    output_path = os.path.join('temp', f"{file_hash}.m4a")
    
    # Check if file already exists
    if os.path.exists(output_path):
        print(f"Audio file already exists: {output_path}")
        return output_path
    
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'outtmpl': output_path.replace('.m4a', ''),
        'nocheckcertificate': True,  # Skip SSL certificate verification
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])
    return output_path

def download_youtube_video(youtube_url):
    """Download video with audio from YouTube"""
    # Generate hash for filename
    file_hash = get_video_hash(youtube_url)
    output_template = os.path.join('temp', f"{file_hash}.%(ext)s")
    
    # Try to find existing video file
    for ext in ['mp4', 'mkv', 'webm']:
        existing_file = os.path.join('temp', f"{file_hash}.{ext}")
        if os.path.exists(existing_file):
            print(f"Video file already exists: {existing_file}")
            return existing_file
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_template,
        'nocheckcertificate': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        video_path = ydl.prepare_filename(info)
    return video_path

def transcribe_with_timestamps(audio_url):
    """Transcribe audio with timing information using DashScope"""
    try:
        # Extract hash from audio_url (which contains the hash in the filename)
        file_hash = os.path.basename(audio_url).split('.')[0]
        transcript_file = os.path.join('temp', f'{file_hash}_transcript_raw.json')
        
        # Check if transcript file already exists
        if os.path.exists(transcript_file):
            print(f"Transcript file already exists: {transcript_file}")
            return transcript_file
        
        # Create async transcription task
        task_response = dashscope.audio.asr.Transcription.async_call(
            model='sensevoice-v1',
            file_urls=[audio_url],
            language_hints=['yue', 'zh', 'en'],
        )
        
        # Wait for transcription to complete
        transcribe_response = dashscope.audio.asr.Transcription.wait(
            task=task_response.output.task_id
        )
        
        if transcribe_response.status_code == HTTPStatus.OK and transcribe_response.output.results[0].transcript_url and transcribe_response.output.results[0].subtask_status == 'SUCCEEDED':
            # Download the transcript
            transcript_url = transcribe_response.output.results[0].transcript_url
            response = requests.get(transcript_url)
            response.raise_for_status()
            
            # Save the transcript
            with open(transcript_file, 'w', encoding='utf-8') as f:
                json.dump(response.json(), f, ensure_ascii=False, indent=2)
            
            return transcript_file
        else:
            raise Exception(f"API Error: {transcribe_response.message}")
            
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        return None

def upload_to_oss(local_file_path):
    """Upload file to Aliyun OSS and return a signed URL valid for 1 hour"""
    try:
        # Initialize OSS client
        auth = oss2.Auth(
            os.getenv('OSS_ACCESS_KEY_ID'),
            os.getenv('OSS_ACCESS_KEY_SECRET')
        )
        bucket = oss2.Bucket(
            auth,
            os.getenv('OSS_ENDPOINT'),
            os.getenv('OSS_BUCKET_NAME')
        )
        
        # Get file hash from path
        file_hash = os.path.basename(local_file_path).split('_')[-1].split('.')[0]
        file_name = f"{file_hash}.m4a"
        
        # Upload the file
        bucket.put_object_from_file(file_name, local_file_path)
        
        # Generate a signed URL that's valid for 1 hour (3600 seconds)
        file_url = bucket.sign_url('GET', file_name, 3600)
        
        return file_url
    except Exception as e:
        print(f"Error uploading to OSS: {str(e)}")
        return None

def clean_text(text):
    """Clean text by removing speech and emotion markers"""
    # Remove speech markers
    text = text.replace('<|Speech|>', '').replace('<|/Speech|>', '')
    # Remove emotion tags (any text between <| and |>)
    text = re.sub(r'<\|[^|]+\|>', '', text)
    return text.strip()

def download_transcript(transcript_file):
    """Read and parse transcript JSON file"""
    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle the specific transcript format
        if 'transcripts' in data:
            return {
                'text': clean_text(data['transcripts'].get('text', '')),
                'sentences': [
                    {
                        'start_time': sentence.get('begin_time', 0) / 1000.0,  # Convert ms to seconds
                        'end_time': sentence.get('end_time', 0) / 1000.0,      # Convert ms to seconds
                        'text': clean_text(sentence.get('text', ''))
                    }
                    for sentence in data['transcripts'].get('sentences', [])
                ]
            }
        return None
    except Exception as e:
        print(f"Error reading transcript: {str(e)}")
        return None

def create_srt_from_transcript(transcript_data):
    """Convert transcript data to SRT format"""
    srt_content = []
    counter = 1
    
    for sentence in transcript_data.get('sentences', []):
        start_time = float(sentence.get('start_time', 0))  # Already in seconds from download_transcript
        end_time = float(sentence.get('end_time', 0))      # Already in seconds from download_transcript
        text = sentence.get('text', '')
        
        # Convert seconds to SRT time format (HH:MM:SS,mmm)
        start_formatted = f"{int(start_time//3600):02d}:{int((start_time%3600)//60):02d}:{int(start_time%60):02d},{int((start_time*1000)%1000):03d}"
        end_formatted = f"{int(end_time//3600):02d}:{int((end_time%3600)//60):02d}:{int(end_time%60):02d},{int((end_time*1000)%1000):03d}"
        
        srt_entry = f"{counter}\n{start_formatted} --> {end_formatted}\n{text}\n\n"
        srt_content.append(srt_entry)
        counter += 1
    
    return ''.join(srt_content)

def embed_subtitles(video_path, srt_path, output_path):
    """Embed SRT subtitles into video file"""
    try:
        cmd = [
            'ffmpeg', '-i', video_path,
            '-i', srt_path,
            '-c', 'copy',
            '-c:s', 'mov_text',
            output_path
        ]
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error embedding subtitles: {str(e)}")
        return False

def process_youtube_video(youtube_url):
    """Process YouTube video and generate transcript"""
    try:
        # Get hash once for consistent naming
        file_hash = get_video_hash(youtube_url)
        
        # Download audio from YouTube
        audio_path = download_youtube_audio(youtube_url)
        
        # Download video with audio
        video_path = download_youtube_video(youtube_url)
        
        # Upload audio to OSS and get the URL
        audio_oss_url = upload_to_oss(audio_path)
        if not audio_oss_url:
            raise Exception("Failed to upload file to OSS")
        
        print('audio oss url:', audio_oss_url)
        
        # Transcribe with timestamps
        transcription_file = transcribe_with_timestamps(audio_oss_url)
        if not transcription_file:
            raise Exception("Failed to get transcription file")
            
        # Download and parse transcript
        transcript_data = download_transcript(transcription_file)
        if not transcript_data:
            raise Exception("Failed to download transcript")
        
        # Create SRT file using hash
        srt_content = create_srt_from_transcript(transcript_data)
        srt_path = os.path.join('temp', f'{file_hash}.srt')
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)
            
        # Embed subtitles into video using just the hash
        output_path = os.path.join('temp', f'{file_hash}.{video_path.split(".")[-1]}')
        if not embed_subtitles(video_path, srt_path, output_path):
            raise Exception("Failed to embed subtitles")
            
        # Clean up temporary files
        if os.path.exists(srt_path):
            os.remove(srt_path)
                
        print(f"Video with subtitles saved as: {output_path}")
        print(f"Transcript saved as: {transcription_file}")
        return transcript_data
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return None

if __name__ == "__main__":
    youtube_url = "https://youtu.be/l2JAsuVG_8c"  # Replace with your YouTube URL
    transcript = process_youtube_video(youtube_url)
    
    if transcript:
        print("Transcription with timestamps:")
        for segment in transcript:
            print(f"{segment['timestamp']}: {segment['text']}")