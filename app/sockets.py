import json
import asyncio
from datetime import datetime, timezone
from typing import Set, Dict, Optional
from uuid import uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


class WSClient:
    def __init__(self, ws: WebSocket, client_id: str):
        self.ws = ws
        self.client_id = client_id
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=5000)
        self.sender_task: Optional[asyncio.Task] = None

    async def start(self):
        await self.ws.accept()
        self.sender_task = asyncio.create_task(self._sender())

    async def _sender(self):
        try:
            while True:
                msg = await self.queue.get()
                await asyncio.wait_for(self.ws.send_text(msg), timeout=30)
        except Exception:
            pass

    async def recv_forever(self):
        try:
            while True:
                await self.ws.receive_text()
        except WebSocketDisconnect:
            pass

    async def send_dict(self, message: dict):
        message["ts"] = datetime.now(timezone.utc).isoformat()
        try:
            await self.queue.put(json.dumps(message, ensure_ascii=False))
        except asyncio.QueueFull:
            pass

    async def close(self):
        try:
            await self.ws.close()
        except Exception:
            pass
        if self.sender_task:
            self.sender_task.cancel()


class WSHub:
    def __init__(self):
        self.clients: Set[WSClient] = set()
        self.by_id: Dict[str, WSClient] = {}
        self.lock = asyncio.Lock()

    async def register(self, client: WSClient):
        async with self.lock:
            self.clients.add(client)
            self.by_id[client.client_id] = client

    async def unregister(self, client: WSClient):
        async with self.lock:
            self.clients.discard(client)
            self.by_id.pop(client.client_id, None)

    async def broadcast(self, message: dict):
        async with self.lock:
            tasks = [c.send_dict(message) for c in list(self.clients)]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_to(self, client_id: str, message: dict):
        async with self.lock:
            client = self.by_id.get(client_id)
        if client:
            await client.send_dict(message)


class SocketServer:
    def __init__(self):
        self.hub = WSHub()
        self.router = APIRouter()
        self.router.add_api_websocket_route("/ws", self.websocket_endpoint)

    async def websocket_endpoint(self, ws: WebSocket):
        client_id = ws.query_params.get("client_id") or uuid4().hex
        client = WSClient(ws, client_id)
        await client.start()
        await self.hub.register(client)
        await client.send_dict({"type": "hello", "client_id": client_id})
        try:
            await client.recv_forever()
        finally:
            await self.hub.unregister(client)
            await client.close()
