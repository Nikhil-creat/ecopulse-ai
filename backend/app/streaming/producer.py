from aiokafka import AIOKafkaProducer

from app.schemas.sensor import SensorReadingIn

TOPIC = "sensor.readings"
DLQ = "sensor.readings.dlq"


async def publish(brokers: str, readings: list[SensorReadingIn]) -> int:
    """Idempotent producer, keyed by station so each station's readings stay ordered within a partition."""
    p = AIOKafkaProducer(bootstrap_servers=brokers, acks="all", enable_idempotence=True)
    await p.start()
    try:
        for r in readings:
            await p.send(TOPIC, r.model_dump_json().encode(), key=r.station_id.encode())
        await p.flush()
    finally:
        await p.stop()
    return len(readings)
