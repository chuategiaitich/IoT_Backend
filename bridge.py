import asyncio
from websocket_manager import manager

# Queue to bridge MQTT (sync) and WebSockets (async)
data_queue = asyncio.Queue()

async def broadcast_worker():
    """Background task to broadcast data from the queue to WebSockets"""
    while True:
        data = await data_queue.get()
        if data is None:
            break
        await manager.broadcast(data)
        data_queue.task_done()
