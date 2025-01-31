from aliyunSenseVoice import process_youtube_video

def main():
    print("Welcome to YouTube Video Processor!")
    youtube_url = input("Please enter a YouTube URL: ")
    
    if youtube_url.strip():
        print("Processing video, please wait...")
        result = process_youtube_video(youtube_url)
        if result:
            print("Processing completed successfully!")
        else:
            print("Failed to process the video. Please check the error messages above.")
    else:
        print("No URL provided. Please try again with a valid YouTube URL.")

if __name__ == "__main__":
    main()
