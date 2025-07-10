import aiohttp
import asyncio


class Weather:
    def __init__(self, city_name, key):
        self.city_name = city_name
        self.api_key = key

    def weather(self):
    # 处理需要进行和风天气查天气的弹幕消息的函数
        self.cityname = self.city_name
        self.key = self.api_key

        async def process():
            try:
                async with aiohttp.ClientSession() as session:
                    cn = self.cityname
                    key = self.key

                    # 查询城市 ID
                    city_data = {
                        "location": cn,
                        "key": key
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

                    # 查询天气信息
                    weather_data = {
                        "location": city_id,
                        "key": "6029a2c0ed9443d1849abe70ef3dae82",
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