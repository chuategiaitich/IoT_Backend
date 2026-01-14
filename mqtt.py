import paho.mqtt.client as mqtt
import json
import uuid
from datetime import datetime
import logging
import ssl

from db import SessionLocal, Device, SensorData
from sqlalchemy.exc import IntegrityError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import os
from dotenv import load_dotenv

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = os.getenv("MQTT_PORT")
MQTT_USERNAME = os.getenv("MQTT_USERNAME")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

TOPIC_DATA = "iot/devices/+/data"
TOPIC_COMMAND = "iot/devices/{}/command"

from bridge import data_queue

class MQTTHandler:
    def __init__(self):
        self.loop = None
        unique_id = uuid.uuid4().hex[:6] #unique Backend ID
        client_id = f"fastapi_backend_{unique_id}"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    def connect(self):
        try:
            self.client.tls_set(tls_version=ssl.PROTOCOL_TLS)
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_start()
            logger.info("MQTT connection initiated")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
    
    def disconnect(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Đã ngắt kết nối MQTT Broker")
        except Exception as e:
            logger.error(f"Lỗi khi ngắt kết nối MQTT: {e}")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Kết nối MQTT thành công!")
            client.subscribe(TOPIC_DATA, qos=1)
            logger.info(f"Đã subscribe topic: {TOPIC_DATA}")
        else:
            logger.error(f"Kết nối thất bại, rc={rc}")

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning(f"Mất kết nối bất ngờ... (mã lỗi rc={rc})")
        else:
            logger.info("Đã ngắt kết nối MQTT an toàn.")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload_str = msg.payload.decode('utf-8')
            logger.info(f"Nhận: {topic} → {payload_str}")

            data = json.loads(payload_str)

            if topic.endswith("/data"):
                self.handle_sensor_data(topic, data)

        except json.JSONDecodeError:
            logger.error(f"Payload không phải JSON hợp lệ: {topic}")
        except Exception as e:
            logger.error(f"Lỗi xử lý message: {e}", exc_info=True)

    def handle_sensor_data(self, topic: str, data: dict):
        try:
            # Topic format: iot/devices/<device_id>/data
            parts = topic.split('/')
            device_id_str = parts[2]
            device_uuid = uuid.UUID(device_id_str)
        except (IndexError, ValueError) as e:
            logger.error(f"Topic không đúng định dạng hoặc ID không hợp lệ: {topic} ({e})")
            return

        db = SessionLocal()
        try:
            device = db.get(Device, device_uuid)
            if not device:
                logger.warning(f"Không tìm thấy device với ID: {device_uuid}")
                return

            device.status = "online"
            device.updated_at = datetime.utcnow()

            updated_count = 0
            inserted_count = 0

            for sensor_type, value in data.items():
                value_number = float(value) if isinstance(value, (int, float)) else None
                value_string = str(value) if value_number is None else None

                sensor = db.query(SensorData).filter(
                    SensorData.device_id == device.id,
                    SensorData.type == sensor_type
                ).first()

                if sensor:
                    sensor.value_number = value_number
                    sensor.value_string = value_string
                    sensor.unit = None
                    sensor.timestamp = datetime.utcnow()
                    updated_count += 1
                else:
                    new_sensor = SensorData(
                        device_id=device.id,
                        type=sensor_type,
                        value_number=value_number,
                        value_string=value_string,
                        unit=None,
                        timestamp=datetime.utcnow()
                    )
                    db.add(new_sensor)
                    inserted_count += 1

            db.commit()
            logger.info(f"Đã cập nhật sensor data cho device {device_id_str}")

            if self.loop:
                broadcast_data = {
                    "device_id": device_id_str,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.loop.call_soon_threadsafe(data_queue.put_nowait, broadcast_data)

        except Exception as e:
            db.rollback()
            logger.error(f"Lỗi khi cập nhật sensor data: {e}", exc_info=True)
        finally:
            db.close()

    def publish_command(self, device_id: str, payload: dict):
        """Publish command tới device"""
        topic = TOPIC_COMMAND.format(device_id)
        message = json.dumps(payload)
        result = self.client.publish(topic, message, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Đã publish command tới {topic}: {message}")
        else:
            logger.error(f"Lỗi khi publish command tới {topic}: rc={result.rc}")

mqtt_handler = MQTTHandler()