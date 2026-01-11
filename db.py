from sqlalchemy import create_engine, Column, String, Numeric, Text, Boolean, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Cấu hình kết nối PostgreSQL local
DATABASE_URL = os.getenv("DATABASE_URL")

# Tạo engine
engine = create_engine(DATABASE_URL, echo=False)  # echo=True nếu muốn debug SQL

# Tạo session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class cho tất cả các model
Base = declarative_base()


# =================== MODELS ===================

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Quan hệ (nếu cần)
    devices = relationship("Device", back_populates="user")
    commands = relationship("Command", back_populates="performer")
    schedules = relationship("Schedule", back_populates="performer")


class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String, default="feeder")
    status = Column(String, default="offline")  # online / offline
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Quan hệ
    user = relationship("User", back_populates="devices")
    sensor_data = relationship("SensorData", back_populates="device")
    commands = relationship("Command", back_populates="device")
    schedules = relationship("Schedule", back_populates="device")


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)  # weight, temperature, ...
    value_number = Column(Numeric, nullable=True)
    value_string = Column(Text, nullable=True)
    unit = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    # Quan hệ
    device = relationship("Device", back_populates="sensor_data")


class Command(Base):
    __tablename__ = "commands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    performer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # người thực hiện lệnh
    action = Column(String, nullable=False)
    params = Column(JSONB, default=dict, server_default='{}')
    status = Column(String, default="pending")  # pending, executed, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # Quan hệ
    device = relationship("Device", back_populates="commands")
    performer = relationship("User", back_populates="commands")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    performer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String, nullable=False)
    params = Column(JSONB, default=dict, server_default='{}')
    cron = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Quan hệ
    device = relationship("Device", back_populates="schedules")
    performer = relationship("User", back_populates="schedules")


class History(Base):
    __tablename__ = "history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=True)
    performer_id = Column(UUID(as_uuid=True),ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    event_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    related_id = Column(UUID(as_uuid=True), nullable=True)  # id của command/schedule/...
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    sensor_data_id = Column(UUID(as_uuid=True), nullable=True)
    type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


# Hàm lấy database session (dùng cho FastAPI dependency)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Tạo tất cả các bảng (chỉ dùng khi cần khởi tạo lần đầu)
def create_tables():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    print("Initial PostgreSQL Database ...")
    # create_tables()  # Uncomment nếu muốn tạo bảng tự động khi chạy file
    print("Done. Database now ready.")