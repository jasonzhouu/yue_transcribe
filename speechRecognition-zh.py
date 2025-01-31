import speech_recognition as sr

def recognize_speech_from_mic():
    # 创建Recognizer对象
    recognizer = sr.Recognizer()

    # 使用麦克风作为音频源
    with sr.Microphone() as source:
        print("请说话...")

        # 调整麦克风的噪声水平
        recognizer.adjust_for_ambient_noise(source)

        # 捕获音频
        audio = recognizer.listen(source)

        try:
            print("正在识别...")
            # 使用Google Web Speech API进行语音识别
            text = recognizer.recognize_google(audio, language="zh-CN")
            print(f"你说的是: {text}")
        except sr.UnknownValueError:
            print("抱歉，无法理解你说的话。")
        except sr.RequestError as e:
            print(f"无法请求结果；{e}")

if __name__ == "__main__":
    while True:
        recognize_speech_from_mic()