import asyncio
import logging
from app.db import init_db, procrastinate_app

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    await init_db()
    async with procrastinate_app.open_async():
        await procrastinate_app.run_worker_async(queues=["agents"])

if __name__ == "__main__":
    asyncio.run(main())
