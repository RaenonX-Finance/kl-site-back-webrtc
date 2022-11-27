import asyncio
import json
import os
import threading
import time
import uuid
from datetime import datetime

import aiohttp_cors
from aiohttp import web
from aiortc import RTCDataChannel, RTCPeerConnection, RTCSessionDescription

from tcoreapi_mq.client import TouchanceApiClient
from tcoreapi_mq.message import HistoryData, RealtimeData, SystemTimeData
from tcoreapi_mq.model import SOURCE_SYMBOLS

ROOT = os.path.dirname(__file__)

pcs = set()
chs: set[RTCDataChannel] = set()


def print_log(msg: str):
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"{dt} [{threading.get_ident():>6}]: {msg}")


class SandboxClient(TouchanceApiClient):
    def __init__(self):
        super().__init__()

        threading.Thread(target=self._fake_realtime_data_event).start()

    def _fake_realtime_data_event(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while True:
            for idx in range(1, 100):
                for idx_enum, symbol in enumerate(SOURCE_SYMBOLS, start=1):
                    msg = f"{symbol.security} {idx * idx_enum}"

                    print_log(f"Sending `{msg}` to {len(chs)} channels")

                    for channel in chs:
                        channel.send(msg)

                    time.sleep(0.1)

    def on_received_realtime_data(self, data: RealtimeData) -> None:
        for channel in chs:
            channel.send(f"{data.security} {data.close}")

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

        # FIXME: Currently not in-use
        @channel.on("message")
        def on_message(message):
            if isinstance(message, str) and message.startswith("ping"):
                channel.send("pong" + message[4:])

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
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
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
