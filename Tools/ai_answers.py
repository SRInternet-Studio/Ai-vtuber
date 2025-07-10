from loguru import logger

import edge_tts
import os

from openai import OpenAI
from pydub import AudioSegment
import pygame
import asyncio


class Ai_Answers:
    _file_counter = 0 # 类变量，用于生成唯一的文件名

    def __init__(self, ai_key, ai_url, model_name, edge_tts_voice):
        self.ai_apikey = ai_key
        self.ai_url = ai_url
        self.edgetts_voice = edge_tts_voice
        self.model_name = model_name



    def run(self, live_chat_msg, messages):
        self.chat_round_num = 0
        self.chat_msg = live_chat_msg
        self.model = self.model_name
        self.client = OpenAI(api_key=self.ai_apikey, base_url=self.ai_url)

        self.chat_round_num += 1
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            stream=False

        )

        logger.info(f"AI回复内容:{response.choices[0].message.content}")
        ai_response_content = response.choices[0].message.content

        return ai_response_content


    async def tts(self, tts_text):
        try:
            # 确保 tts_text 是字符串类型
            tts_text = str(tts_text).strip()
            if not tts_text:
                logger.warning("TTS 文本为空，跳过处理")
                return

            # 生成唯一的文件名
            self._file_counter += 1
            file_name = f"./temp/responseVoice{self._file_counter}.wav"
            file_name_delete = f"./temp/responseVoice{self._file_counter-1}.wav"

            # 调用 EdgeTTS 生成音频文件
            communicate = edge_tts.Communicate(tts_text, self.edgetts_voice)
            await communicate.save(file_name)

            # 检查文件是否存在
            if not os.path.exists(file_name):
                logger.warning("音频文件生成失败，跳过播放")
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
                    logger.error(f"删除文件失败（尝试 {retry + 1}/{max_retries}）: {e}")
                    await asyncio.sleep(1)  # 等待一段时间后重试
            else:
                logger.error("无法删除文件，请手动检查或稍后再试。")

        except edge_tts.exceptions.EdgeTTSException as e:
            logger.error(f"EdgeTTS 错误: {e}")
            # 增加重试机制
            if "Invalid response status" in str(e):
                logger.info("尝试重新生成音频...")
                await self.tts(tts_text)  # 递归调用以重试
        except Exception as e:
            logger.error(f"其他错误: {e}")