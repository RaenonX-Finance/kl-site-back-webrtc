import asyncio
import json
import os
import uuid

import aiohttp_cors
from aiohttp import web
from aiortc import RTCDataChannel, RTCPeerConnection, RTCSessionDescription

from tcoreapi_mq.client import TouchanceApiClient
from tcoreapi_mq.message import HistoryData, RealtimeData, SystemTimeData
from tcoreapi_mq.model import SOURCE_SYMBOLS

ROOT = os.path.dirname(__file__)

pcs = set()
chs: set[RTCDataChannel] = set()


class SandboxClient(TouchanceApiClient):
    def on_received_realtime_data(self, data: RealtimeData) -> None:
        if data.security != "NQ":
            return

        for channel in chs:
            channel.send(str(data.close))

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
        print(pc_id + " " + msg)

    log_info(f"Created for {request.remote}")

    @pc.on("datachannel")
    def on_datachannel(channel: RTCDataChannel):
        if channel.label == "marketPx":
            chs.add(channel)

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
    app.on_shutdown.append(on_shutdown)
    app.router.add_post("/offer", offer)

    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })

    # Configure CORS on all routes.
    for route in list(app.router.routes()):
        cors.add(route)

    web.run_app(app, access_log=None, host="localhost", port=8182)
