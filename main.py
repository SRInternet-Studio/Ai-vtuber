import asyncio
import http.cookies

from typing import *
from Tools.weather import Weather

import aiohttp
import pygame

import blivedm
import blivedm.models.web as web_models

from Tools.ai_answers import Ai_Answers
from loguru import logger
import tqdm

import json

with open("config.json", "r", encoding = "utf-8") as f:
    config = json.load(f)

chat_round_num = 0

BILIBILI_ROOM_ID = config["blive_room_id"]
SESSDATA = config["sessdata"]
reminder = config["reminder"]
ai_model = config["ai_settings"][0]["model"]
ai_key = config["ai_settings"][0]["api_key"]
ai_endpoint = config["ai_settings"][0]["api_endpoint"]
edge_tts_voice = config["edgetts_voice"]
weather_api_key = config["weather_api_key"]
character_set = config["character_set"]

session: Optional[aiohttp.ClientSession] = None


messages = [
    {"role": "system", "content": f"{character_set}"},
]

def init_session():
    cookies = http.cookies.SimpleCookie()
    cookies['SESSDATA'] = SESSDATA
    cookies['SESSDATA']['domain'] = 'bilibili.com'

    global session
    session = aiohttp.ClientSession()
    session.cookie_jar.update_cookies(cookies)
    logger.success("session initialized successfully")


async def run_single_client():
    room_id = BILIBILI_ROOM_ID
    client = blivedm.BLiveClient(room_id, session=session)
    handler = Handler()
    client.set_handler(handler)

    client.start()
    logger.success("成功加入房间")
    try:
        await client.join()


    finally:
        await client.stop_and_close()


class Handler(blivedm.BaseHandler):
    def _on_heartbeat(self, client: blivedm.BLiveClient, message: web_models.HeartbeatMessage):
        logger.info(f'[{client.room_id}] heartbeat')

    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        logger.info(f'[{client.room_id}] {message.uname}：{message.msg}')
        asyncio.create_task(process_danmu(f"{message.uname}:{message.msg}"))


    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        logger.info(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}'
              f' （{message.coin_type}瓜子x{message.total_coin}）')


async def process_danmu(danmu_msg):
    await danmu_queue.put(danmu_msg)  # 将弹幕消息放入队列

ai = Ai_Answers(ai_key ,ai_endpoint ,ai_model ,edge_tts_voice)

danmu_queue = asyncio.Queue()
async def danmu_task_handler():
    global messages
    global chat_round_num
    while True:
        try:
            danmu_msg = await danmu_queue.get()
            danmu_msg_splited = danmu_msg.split(":")
            if "查天气" in danmu_msg_splited[1]:
                logger.info(danmu_msg_splited)
                await ai.tts(f"{danmu_msg_splited[0]}说:{danmu_msg_splited[1]}")
                danmu_weather_list = danmu_msg_splited[1].split(" ")
                city_name = danmu_weather_list[1]
                await asyncio.create_task(weather(city_name))

            elif reminder in danmu_msg:
                pass
            # 没有匹配到任何一个，进入ai回复
            else:
                await ai.tts(f"{danmu_msg_splited[0]}说:{danmu_msg_splited[1]}")
                ai_chat_msg = ai.run(f"{danmu_msg_splited[0]}说:{danmu_msg_splited[1]}", messages)
                await ai.tts(ai_chat_msg)
                messages.append({"role": "assistant", "content": f"{ai_chat_msg}"})
                chat_round_num += 1

                if chat_round_num >= 20:
                    self.chat_round_num = 0
                    messages = [
                        {"role": "system", "content": f"{character_set}"},
                    ]

        finally:
                danmu_queue.task_done()


async def main():
    init_session()
    try:
        pygame.mixer.init()

        asyncio.create_task(danmu_task_handler())

        await run_single_client()
    finally:
        await session.close()

        await asyncio.sleep(0.5)

        pygame.mixer.quit()

if __name__ == '__main__':
    asyncio.run(main())
