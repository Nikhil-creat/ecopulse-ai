"""Streaming ingestion worker: Kafka/Redpanda -> validate -> idempotent upsert into TimescaleDB.
At-least-once delivery (commit after a successful write); invalid messages go to a dead-letter topic.
Run: python -m app.streaming.consumer   (compose profile `streaming`)"""
import asyncio
import logging

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import ValidationError

from app.core.config import get_settings
from app.db.worker_session import worker_session
from app.schemas.sensor import SensorReadingIn
from app.services.ingestion import store_readings
from app.streaming.producer import DLQ, TOPIC

log = logging.getLogger("stream-consumer")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    brokers = get_settings().kafka_brokers
    consumer = AIOKafkaConsumer(TOPIC, bootstrap_servers=brokers, group_id="ecopulse-ingest",
                                enable_auto_commit=False, auto_offset_reset="earliest")
    dlq = AIOKafkaProducer(bootstrap_servers=brokers)
    await consumer.start()
    await dlq.start()
    log.info("consuming %s from %s", TOPIC, brokers)
    try:
        while True:
            batches = await consumer.getmany(timeout_ms=1000, max_records=500)
            msgs = [m for ms in batches.values() for m in ms]
            if not msgs:
                continue
            good: list[SensorReadingIn] = []
            for m in msgs:
                try:
                    good.append(SensorReadingIn.model_validate_json(m.value))
                except ValidationError:
                    await dlq.send_and_wait(DLQ, m.value)
            if good:
                async with worker_session() as session:
                    res = await store_readings(session, good)
                log.info("stored %s (suspect=%s, dlq=%s)", res.stored, res.suspect, len(msgs) - len(good))
            await consumer.commit()  # a crash before this line re-delivers the batch; upserts make that safe
    finally:
        await consumer.stop()
        await dlq.stop()


if __name__ == "__main__":
    asyncio.run(main())
