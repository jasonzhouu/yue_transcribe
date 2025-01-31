import dashscope
from http import HTTPStatus
import yt_dlp
import os
from dotenv import load_dotenv
import oss2
import time

# Load environment variables
load_dotenv()
dashscope.api_key = os.getenv('ALIYUN_BAILIAN_API_KEY')

def download_youtube_audio(youtube_url, output_path="temp_audio.m4a"):
    """Download audio from YouTube video"""
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
    return output_path  # Simply return the output path since we're using .m4a consistently

def transcribe_with_timestamps(audio_url):
    """Transcribe audio with timing information using DashScope"""
    try:
        # Create async transcription task
        task_response = dashscope.audio.asr.Transcription.async_call(
            model='sensevoice-v1',
            file_urls=[audio_url],
            language_hints=['yue'],  # Cantonese
        )
        
        # Wait for transcription to complete
        transcribe_response = dashscope.audio.asr.Transcription.wait(
            task=task_response.output.task_id
        )
        
        if transcribe_response.status_code == HTTPStatus.OK:
            return transcribe_response.output
        else:
            raise Exception(f"API Error: {transcribe_response.message}")
            
    except Exception as e:
        print(f"Transcription error: {str(e)}")
        return None

def format_transcript(transcription):
    """Format transcript with timestamps and current word highlighting"""
    formatted_output = []
    if not transcription or 'sentences' not in transcription:
        return formatted_output
        
    for sentence in transcription['sentences']:
        start_time = sentence.get('start_time', 0)
        end_time = sentence.get('end_time', 0)
        text = sentence.get('text', '')
        
        formatted_output.append({
            'timestamp': f"[{float(start_time):.2f}s - {float(end_time):.2f}s]",
            'text': text
        })
    return formatted_output

def upload_to_oss(local_file_path):
    """Upload file to Aliyun OSS and return the public URL"""
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
        
        # Generate a unique filename using timestamp
        file_name = f"audio_{int(time.time())}.m4a"
        
        # Upload the file
        bucket.put_object_from_file(file_name, local_file_path)
        
        # Generate the public URL
        file_url = f"https://{os.getenv('OSS_BUCKET_NAME')}.{os.getenv('OSS_ENDPOINT').replace('http://', '')}/{file_name}"
        
        return file_url
    except Exception as e:
        print(f"Error uploading to OSS: {str(e)}")
        return None

def process_youtube_video(youtube_url):
    """Process YouTube video and generate transcript"""
    try:
        # Download audio from YouTube
        audio_path = download_youtube_audio(youtube_url)
        
        # Upload to OSS and get the URL
        file_url = upload_to_oss(audio_path)
        if not file_url:
            raise Exception("Failed to upload file to OSS")
        
        print('file url:', file_url)
        
        # Transcribe with timestamps
        transcription = transcribe_with_timestamps(file_url)
        
        # Format the transcript
        formatted_transcript = format_transcript(transcription)
        
        # Clean up temporary audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return formatted_transcript
        
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