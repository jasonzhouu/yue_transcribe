import pyaudio
import numpy as np
from openai import OpenAI
import whisper
import threading
from queue import Queue
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置 Qwen AI API
client = OpenAI(
    api_key=os.getenv("ALIYUN_BAILIAN_API_KEY"),
    base_url=os.getenv("ALIYUN_BAILIAN_BASE_URL")
)

# 初始化 Whisper 语音识别模型（中等尺寸）
model = whisper.load_model("base")

# 音频参数
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
SILENCE_THRESHOLD = 200  # 降低静音阈值，使其更容易捕获声音
MIN_AUDIO_LENGTH = 5  # 最少需要收集的音频块数量

# 创建线程安全队列
audio_queue = Queue()

def record_audio():
    """实时录音并存入队列"""
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    print("开始录音，请说话...")
    frames = []
    silence_count = 0
    
    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_np = np.frombuffer(data, dtype=np.int16)
            
            # 检测是否有声音并打印音量级别
            volume_norm = np.abs(audio_np).mean()
            print(f"当前音量: {volume_norm}", end='\r')
            
            # 检测是否有声音
            if volume_norm > SILENCE_THRESHOLD:
                frames.append(data)
                silence_count = 0
            else:
                silence_count += 1
                print(f"Silence count: {silence_count}", end='\r')
            
            # 当收集到足够的音频数据或检测到语音停顿时处理
            if len(frames) >= MIN_AUDIO_LENGTH and silence_count > 2:  # Reduced from 3 to 2, removed len(frames) >= 20
                print(f"\nProcessing audio chunk with {len(frames)} frames after {silence_count} silent chunks")
                if frames:
                    audio_queue.put(b''.join(frames))
                frames = []
                silence_count = 0
                
        except Exception as e:
            print(f"录音错误: {str(e)}")
            continue

def transcribe_and_translate():
    """从队列获取音频并进行转换"""
    while True:
        if not audio_queue.empty():
            audio_data = audio_queue.get()
            
            # Convert bytes to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            try:
                # Whisper 语音识别
                result = model.transcribe(
                    audio_np,
                    language=os.getenv('TRANSCRIPTION_LANGUAGE', 'zh'),
                    fp16=False
                )

                print('==',result["text"])

                # if result["text"].strip():  # 只处理非空文本
                #     # 使用 Qwen AI 进行方言转换
                #     response = client.chat.completions.create(
                #         model="qwen-max",
                #         messages=[{
                #             "role": "system",
                #             "content": "你是一个专业的方言转换助手，请将用户输入的粤语口语文本转换为标准普通话书面文本，保持原意不变。"
                #         }, {
                #             "role": "user",
                #             "content": result["text"]
                #         }],
                #         temperature=0.3
                #     )
                    
                #     print(f"\n粤语原文: {result['text']}")
                #     print(f"普通话转换: {response.choices[0].message.content}")
            except Exception as e:
                print(f"处理错误: {str(e)}")

if __name__ == "__main__":
    # 启动录音线程
    record_thread = threading.Thread(target=record_audio)
    record_thread.daemon = True
    record_thread.start()

    # 启动处理线程
    process_thread = threading.Thread(target=transcribe_and_translate)
    process_thread.daemon = True
    process_thread.start()

    try:
        while True: pass
    except KeyboardInterrupt:
        print("\n转换已停止")