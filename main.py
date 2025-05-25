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
from pydub import AudioSegment
import requests

import json

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
        asyncio.create_task(process_danmu(f"{message.uname}:{message.msg}"))

    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        print(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
              f' （{message.coin_type}瓜子x{message.total_coin}）')


async def process_danmu(danmu_msg):
    await danmu_queue.put(danmu_msg)  # 将弹幕消息放入队列


class Ai_Awnsers:
    _file_counter = 0  # 类变量，用于生成唯一的文件名

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

            # 生成唯一的文件名
            self._file_counter += 1
            file_name = f"./temp/responseVoice{self._file_counter}.wav"
            file_name_delete = f"./temp/responseVoice{self._file_counter - 1}.wav"

            # 调用 EdgeTTS 生成音频文件
            communicate = edge_tts.Communicate(tts_text, self.edgetts_voice)
            await communicate.save(file_name)

            # 检查文件是否存在
            if not os.path.exists(file_name):
                print("音频文件生成失败，跳过播放")
                return

            # 转换音频格式
            audio = AudioSegment.from_file(file_name)
            audio = audio.set_frame_rate(44100).set_channels(1)
            audio.export(file_name, format="wav")

            # 播放音频
            pygame.mixer.music.load(file_name)
            pygame.mixer.music.play()

            # 等待音频播放完成
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.5)

            # 等待一段时间后再删除文件

            max_retries = 3
            for retry in range(max_retries):
                try:
                    os.remove(file_name_delete)
                    break  # 删除成功，退出循环
                except Exception as e:
                    print(f"删除文件失败（尝试 {retry + 1}/{max_retries}）: {e}")
                    await asyncio.sleep(1)  # 等待一段时间后重试
            else:
                print("无法删除文件，请手动检查或稍后再试。")

        except edge_tts.exceptions.EdgeTTSException as e:
            print(f"EdgeTTS 错误: {e}")
            # 增加重试机制
            if "Invalid response status" in str(e):
                print("尝试重新生成音频...")
                await self.tts(tts_text)  # 递归调用以重试
        except Exception as e:
            print(f"其他错误: {e}")


ai = Ai_Awnsers()

# 新增任务队列
danmu_queue = asyncio.Queue()


def weather(city_name):
    # 处理需要进行和风天气查天气的弹幕消息的函数
    cityname = city_name

    async def process():
        try:
            async with aiohttp.ClientSession() as session:
                cn = cityname

                # 查询城市 ID
                city_data = {
                    "location": cn,
                    "key": ""
                }
                async with session.get('https://geoapi.qweather.com/v2/city/lookup', params=city_data) as city_response:
                    city_dict = await city_response.json()
                    city_location = city_dict.get("location")
                    if city_location:
                        city_info = city_location[0]
                    else:
                        city_info = None

                if city_info:
                    city_id = city_info.get("id")
                    city_name = city_info.get("name")
                else:
                    city_id = "101010100"
                    city_name = "北京"

                # 查询天气信息
                weather_data = {
                    "location": city_id,
                    "key": "",
                    "lang": "zh"
                }
                async with session.get('https://devapi.qweather.com/v7/weather/now?',
                                       params=weather_data) as weather_response:
                    weather_dict = await weather_response.json()
                    weather_dict_now = weather_dict["now"]
                    weather_condition = weather_dict_now["text"]
                    temperature = weather_dict_now["temp"]
                    feel_temperature = weather_dict_now["feelsLike"]
                    humidity = weather_dict_now["humidity"]
                    wind_direction = weather_dict_now["windDir"]
                    wind_speed = weather_dict_now["windSpeed"]
                    wind_scale = weather_dict_now["windScale"]
                    weather_icon = weather_dict_now["icon"]

                final_weather_info = f" {city_name}目前天气{weather_condition}，温度为{temperature}°C"
                final_weather_data = f"当前体感温度为{feel_temperature}°C，湿度为{humidity}，风向为{wind_direction}，风级为{wind_scale}级，风速为{wind_speed}."
                print(f"{final_weather_info},{final_weather_data}")

                await ai.tts(f"{final_weather_info},{final_weather_data}")

        except Exception as e:
            print(f"处理天气信息时发生错误: {e}")
            await ai.tts("抱歉，未能获取到天气信息，请稍后再试。")

    return process()


async def danmu_task_handler():
    while True:
        try:
            danmu_msg = await danmu_queue.get()
            danmu_msg_splited = danmu_msg.split(":")
            if "查天气" in danmu_msg_splited[1]:
                print(danmu_msg_splited)
                await ai.tts(f"{danmu_msg_splited[0]}说:{danmu_msg_splited[1]}")
                danmu_weather_list = danmu_msg_splited[1].split(".")
                city_name = danmu_weather_list[1] if len(danmu_weather_list) > 1 else "北京"  # 确保 city_name 有默认值
                await asyncio.create_task(weather(city_name))

            elif "$" in danmu_msg:
                pass
            elif "$" not in danmu_msg:
                await ai.tts(f"{danmu_msg_splited[0]}说:{danmu_msg_splited[1]}")
                ai_chat_msg = ai.run(f"{danmu_msg_splited[0]}说:{danmu_msg_splited[1]}")
                await ai.tts(ai_chat_msg)

        finally:
            danmu_queue.task_done()


async def main():
    init_session()
    try:
        # 初始化 pygame.mixer
        pygame.mixer.init()

        # 启动任务处理器
        asyncio.create_task(danmu_task_handler())

        await run_single_client()
    finally:
        await session.close()
        # 确保所有任务完成后再退出
        await asyncio.sleep(0.5)
        # 释放 pygame.mixer 资源
        pygame.mixer.quit()


if __name__ == '__main__':
    asyncio.run(main())
