import asyncio
import http.cookies
import random
from typing import *
from openai import OpenAI

import tracemalloc

tracemalloc.start()

import edge_tts
import os

import aiohttp

import blivedm
import blivedm.models.web as web_models

import pygame
from pydub import AudioSegment  # 添加 pydub 的导入

# 直播间ID的取值看直播间URL
TEST_ROOM_IDS = [
    00000000,
]

# 这里填一个已登录账号的cookie的SESSDATA字段的值。不填也可以连接，但是收到弹幕的用户名会打码，UID会变成0
SESSDATA = ''

session: Optional[aiohttp.ClientSession] = None


def init_session():
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = SESSDATA
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)


async def run_single_client():
    room_id = random.choice(TEST_ROOM_IDS)
    client = blivedm.BLiveClient(room_id, session=session)
    handler = Handler()
    client.set_handler(handler)

    client.start()
    try:
        await client.join()

    finally:
        await client.stop_and_close()


class Handler(blivedm.BaseHandler):
    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        print(f'[{client.room_id}] heartbeat')

    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        print(f'[{client.room_id}] {message.uname}：{message.msg}')

        # 将弹幕消息传递给外部处理函数
        # 如果检测到消息第一位是"$"
        for i in message.msg:
            if i != "$":
                asyncio.create_task(process_danmu(f"{message.uname}说:{message.msg}"))
                break
            if i == "$":
                break

    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        print(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
              f' （{message.coin_type}瓜子x{message.total_coin}）')


def process_danmu(danmu_msg):
    # 处理弹幕消息的函数
    async def process():
        await ai.tts(danmu_msg)  # 使用 await 调用 tts
        ai_response_content = ai.run(danmu_msg)  # 调用 AI 回复
        await ai.tts(ai_response_content)  # 再次使用 await 调用 tts

    return process()


class Ai_Awnsers:
    def __init__(self):
        self.bailian_apikey = ""
        self.edgetts_voice = "zh-CN-XiaoyiNeural"

    def run(self, live_chat_msg):
        self.chat_msg = live_chat_msg
        client = OpenAI(api_key=self.bailian_apikey, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")

        response = client.chat.completions.create(
            model="qwen-turbo-latest",
            messages=[
                {"role": "system",
                 "content": "你的名字叫做星语，是一个对人类有帮助的ai智能助手,请你将每个回答都控制在50字以内"},
                {"role": "user", "content": f"{self.chat_msg}"},
            ],
            max_tokens=1024,
            temperature=0.7,
            stream=False,

        )

        print(response.choices[0].message.content)
        ai_response_content = response.choices[0].message.content
        return ai_response_content  # 返回 AI 回复内容

    async def tts(self, tts_text):
        try:
            # 确保 tts_text 是字符串类型
            tts_text = str(tts_text).strip()
            if not tts_text:
                print("TTS 文本为空，跳过处理")
                return

            pygame.mixer.init()
            communicate = edge_tts.Communicate(tts_text, self.edgetts_voice)
            await communicate.save(r"./responseVoice.wav")

            # 添加音频转换代码
            audio = AudioSegment.from_file("./responseVoice.wav")
            audio = audio.set_frame_rate(44100).set_channels(1)
            audio.export("./responseVoice.wav", format="wav")

            pygame.mixer.music.load("./responseVoice.wav")
            pygame.mixer.music.play()

            # 等待音频播放完成
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)

            # 修改: 增加重试机制以确保文件删除成功
            max_retries = 3
            for retry in range(max_retries):
                try:
                    os.remove("./responseVoice.wav")
                    break  # 删除成功，退出循环
                except Exception as e:
                    print(f"删除文件失败（尝试 {retry + 1}/{max_retries}）: {e}")
                    await asyncio.sleep(0.5)  # 等待一段时间后重试
            else:
                print("无法删除文件，请手动检查或稍后再试。")
        except TypeError as e:
            print(f"TypeError: {e}")
        except Exception as e:
            print(f"EdgeTTS 错误: {e}")
        finally:
            # 确保资源释放
            pygame.mixer.quit()


ai = Ai_Awnsers()


async def main():
    init_session()
    try:
        await run_single_client()
    finally:
        await session.close()
        # 确保所有任务完成后再退出
        await asyncio.sleep(0.5)


if __name__ == '__main__':
    asyncio.run(main())
