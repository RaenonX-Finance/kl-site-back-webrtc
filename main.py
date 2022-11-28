import asyncio
import json
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Coroutine, ParamSpec

import aiohttp_cors
from aiohttp import web
from aiortc import RTCDataChannel, RTCPeerConnection, RTCSessionDescription

from tcoreapi_mq.client import TouchanceApiClient
from tcoreapi_mq.message import HistoryData, RealtimeData, SystemTimeData
from tcoreapi_mq.model import SOURCE_SYMBOLS


pcs = set()
chs: set[RTCDataChannel] = set()


P = ParamSpec("P")

Func = Callable[P, Coroutine[Any, Any, None]]

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def execute_async_function(async_func: Func, *args: P.args, **kwargs: P.kwargs):
    async def async_func_wrapper():
        await async_func(*args, **kwargs)

    asyncio.run(async_func_wrapper())


def print_log(msg: str):
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"{dt} [{threading.get_ident():>6}]: {msg}")


async def send_data_to_channels(msg: str):
    global chs

    print_log(f"Sending `{msg}` to {len(chs)} channels")

    closed_ch = set()

    for channel in chs:
        if channel.readyState != "open":
            print_log(f"Channel ({channel.id}) closed (state: {channel.readyState})")
            channel.close()
            closed_ch.add(channel)
            continue

        channel.send(msg)

        # https://github.com/aiortc/aiortc/issues/547
        await channel.transport._data_channel_flush()
        await channel.transport._transmit()

    chs -= closed_ch


class SandboxClient(TouchanceApiClient):
    def __init__(self):
        super().__init__()

    def on_received_realtime_data(self, data: RealtimeData) -> None:
        execute_async_function(send_data_to_channels, f"{data.security} {data.last_px}")

    def on_received_history_data(self, data: HistoryData) -> None:
        pass

    def on_system_time_min_change(self, data: SystemTimeData) -> None:
        pass

    def on_error(self, message: str) -> None:
        pass


client = SandboxClient()


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pc_id = "PeerConnection(%s)" % uuid.uuid4()
    pcs.add(pc)

    def log_info(msg):
        print_log(pc_id + " " + msg)

    log_info(f"Peer connection created for {request.remote}")

    @pc.on("datachannel")
    def on_datachannel(channel: RTCDataChannel):
        log_info(f"Channel created: {channel.label} ({channel.id})")

        if channel.label == "marketPx":
            log_info(f"Add market px channel ({channel.id})")
            chs.add(channel)

        @channel.on("message")
        def on_message(message):
            print_log(f"Received message from channel ({channel.id}) - {message}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        log_info(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    @pc.on("track")
    def on_track(track):
        log_info(f"Track {track.kind} received")

    # handle offer
    await pc.setRemoteDescription(offer)

    # send answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }),
    )


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    client.start()
    for symbol in SOURCE_SYMBOLS:
        client.subscribe_realtime(symbol)

    app = web.Application()

    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    cors.add(app.router.add_post("/offer", offer))

    app.on_shutdown.append(on_shutdown)

    web.run_app(app, access_log=None, host="localhost", port=8182)
