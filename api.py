from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, UUID4, EmailStr, constr, ConfigDict
from typing import List, Optional, Annotated
from datetime import datetime, timedelta
import uuid

from db import get_db, User, Device, SensorData, Command, Schedule, History, Alert
from mqtt import mqtt_handler
from auth import (
    get_current_user,
    get_current_active_user,
    create_access_token,
    authenticate_user,
    get_password_hash,
    Token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    OAuth2PasswordRequestForm
)

from websocket_manager import manager
from fastapi import WebSocket

# router = APIRouter(prefix="/api", tags=["API"])
router = APIRouter()

@router.websocket("/ws/sensor_data")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)

# =================== SCHEMAS ===================

# User Schemas
class UserBase(BaseModel):
    email: str
    name: str

class UserCreate(UserBase):
    password: constr(min_length=8)

class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    password: Optional[constr(min_length=8)] = None  # Chỉ cập nhật nếu có

class UserSchema(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    # class Config:
        # from_attributes = True

# Device Schemas
class DeviceBase(BaseModel):
    user_id: UUID4
    name: str
    type: Optional[str] = "feeder"
    status: Optional[str] = "offline"

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    user_id: Optional[UUID4] = None
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None

class DeviceSchema(DeviceBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # class Config:
        # from_attributes = True

# SensorData Schemas
class SensorDataBase(BaseModel):
    device_id: UUID4
    type: str
    value_number: Optional[float] = None
    value_string: Optional[str] = None
    unit: Optional[str] = None

class SensorDataCreate(SensorDataBase):
    pass

class SensorDataUpdate(BaseModel):
    device_id: Optional[UUID4] = None
    type: Optional[str] = None
    value_number: Optional[float] = None
    value_string: Optional[str] = None
    unit: Optional[str] = None

class SensorDataSchema(SensorDataBase):
    id: UUID4
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

    # class Config:
        # from_attributes = True

# Command Schemas
class CommandBase(BaseModel):
    device_id: UUID4
    performer_id: UUID4
    action: str
    params: Optional[dict] = {}
    status: Optional[str] = "pending"

class CommandCreate(CommandBase):
    pass

class CommandUpdate(BaseModel):
    device_id: Optional[UUID4] = None
    performer_id: Optional[UUID4] = None
    action: Optional[str] = None
    params: Optional[dict] = None
    status: Optional[str] = None
    executed_at: Optional[datetime] = None

class CommandSchema(CommandBase):
    id: UUID4
    created_at: datetime
    executed_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)
    # class Config:
        # from_attributes = True

# Schedule Schemas
class ScheduleBase(BaseModel):
    device_id: UUID4
    performer_id: UUID4
    action: str
    params: Optional[dict] = {}
    cron: str
    active: Optional[bool] = True

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleUpdate(BaseModel):
    device_id: Optional[UUID4] = None
    performer_id: Optional[UUID4] = None
    action: Optional[str] = None
    params: Optional[dict] = None
    cron: Optional[str] = None
    active: Optional[bool] = None

class ScheduleSchema(ScheduleBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    # class Config:
        # from_attributes = True

# History Schemas
class HistoryBase(BaseModel):
    device_id: Optional[UUID4] = None
    performer_id: Optional[UUID4] = None
    event_type: str
    description: str
    related_id: Optional[UUID4] = None

class HistoryCreate(HistoryBase):
    pass

class HistoryUpdate(BaseModel):
    device_id: Optional[UUID4] = None
    performer_id: Optional[UUID4] = None
    event_type: Optional[str] = None
    description: Optional[str] = None
    related_id: Optional[UUID4] = None

class HistorySchema(HistoryBase):
    id: UUID4
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)
    # class Config:
        # from_attributes = True

# Alert Schemas
class AlertBase(BaseModel):
    device_id: UUID4
    sensor_data_id: Optional[UUID4] = None
    type: str
    message: str

class AlertCreate(AlertBase):
    pass

class AlertUpdate(BaseModel):
    device_id: Optional[UUID4] = None
    sensor_data_id: Optional[UUID4] = None
    type: Optional[str] = None
    message: Optional[str] = None

class AlertSchema(AlertBase):
    id: UUID4
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)
    # class Config:
        # from_attributes = True

# =================== ENDPOINTS ===================

# Users
@router.get("/users", response_model=List[UserSchema])
def get_users(db: Session = Depends(get_db)):
    stmt = select(User)
    return db.scalars(stmt).all()

@router.get("/users/me", response_model=UserSchema)
def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    """Lấy thông tin người dùng đang đăng nhập"""
    return current_user

@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    """Đăng ký người dùng mới"""
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(
            status_code=400,
            detail="Email này đã được sử dụng"
        )

    hashed_password = get_password_hash(user.password)

    db_user = User(
        email=user.email,
        name=user.name,
        password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # Log history
    db_history = History(
        performer_id=db_user.id,
        event_type="USER_REGISTER",
        description=f"User {db_user.name} ({db_user.email}) registered",
        related_id=db_user.id
    )
    db.add(db_history)
    db.commit()

    return db_user

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Đăng nhập và nhận JWT token"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.put("/users/{user_id}", response_model=UserSchema)
def update_user(user_id: str, user_update: UserUpdate, db: Session = Depends(get_db)):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_user = db.get(User, user_uuid)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_user = db.get(User, user_uuid)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return None

# Devices
@router.get("/devices", response_model=List[DeviceSchema])
def get_devices(db: Session = Depends(get_db)):
    stmt = select(Device)
    return db.scalars(stmt).all()

@router.get("/devices/{device_id}", response_model=DeviceSchema)
def get_device(device_id: str, db: Session = Depends(get_db)):
    try:
        device_uuid = uuid.UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    device = db.get(Device, device_uuid)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.post("/devices", response_model=DeviceSchema, status_code=status.HTTP_201_CREATED)
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    db_device = Device(**device.dict())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: str, db: Session = Depends(get_db)):
    try:
        device_uuid = uuid.UUID(device_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_device = db.get(Device, device_uuid)
    if not db_device:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(db_device)
    db.commit()
    return None

# Sensor Data
@router.get("/sensor_data", response_model=List[SensorDataSchema])
def get_sensor_data(db: Session = Depends(get_db)):
    stmt = select(SensorData)
    return db.scalars(stmt).all()

@router.get("/sensor_data/{sensor_id}", response_model=SensorDataSchema)
def get_sensor_datum(sensor_id: str, db: Session = Depends(get_db)):
    try:
        sensor_uuid = uuid.UUID(sensor_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    sensor = db.get(SensorData, sensor_uuid)
    if not sensor:
        raise HTTPException(status_code=404, detail="Sensor data not found")
    return sensor

# Commands
@router.get("/commands", response_model=List[CommandSchema])
def get_commands(db: Session = Depends(get_db)):
    stmt = select(Command)
    return db.scalars(stmt).all()

@router.get("/commands/{command_id}", response_model=CommandSchema)
def get_command(command_id: str, db: Session = Depends(get_db)):
    try:
        command_uuid = uuid.UUID(command_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    command = db.get(Command, command_uuid)
    if not command:
        raise HTTPException(status_code=404, detail="Command not found")
    return command

@router.post("/commands", response_model=CommandSchema, status_code=status.HTTP_201_CREATED)
def create_command(command: CommandCreate, db: Session = Depends(get_db)):
    db_command = Command(**command.dict())
    db.add(db_command)
    db.commit()
    db.refresh(db_command)

    # Log history
    db_history = History(
        device_id=db_command.device_id,
        performer_id=db_command.performer_id,
        event_type="COMMAND_CREATE",
        description=f"Command '{db_command.action}' created for device {db_command.device_id}",
        related_id=db_command.id
    )
    db.add(db_history)
    db.commit()

    # Publish command to MQTT
    mqtt_handler.publish_command(str(db_command.device_id), db_command.params)

    return db_command

@router.put("/commands/{command_id}", response_model=CommandSchema)
def update_command(command_id: str, command_update: CommandUpdate, db: Session = Depends(get_db)):
    try:
        command_uuid = uuid.UUID(command_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_command = db.get(Command, command_uuid)
    if not db_command:
        raise HTTPException(status_code=404, detail="Command not found")
    update_data = command_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_command, key, value)
    db.commit()
    db.refresh(db_command)
    return db_command

@router.delete("/commands/{command_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_command(command_id: str, db: Session = Depends(get_db)):
    try:
        command_uuid = uuid.UUID(command_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_command = db.get(Command, command_uuid)
    if not db_command:
        raise HTTPException(status_code=404, detail="Command not found")
    db.delete(db_command)
    db.commit()
    return None

# Schedules
@router.get("/schedules", response_model=List[ScheduleSchema])
def get_schedules(db: Session = Depends(get_db)):
    stmt = select(Schedule)
    return db.scalars(stmt).all()

@router.get("/schedules/{schedule_id}", response_model=ScheduleSchema)
def get_schedule(schedule_id: str, db: Session = Depends(get_db)):
    try:
        schedule_uuid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    schedule = db.get(Schedule, schedule_uuid)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule

@router.post("/schedules", response_model=ScheduleSchema, status_code=status.HTTP_201_CREATED)
def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    db_schedule = Schedule(**schedule.dict())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)

    # Log history
    db_history = History(
        device_id=db_schedule.device_id,
        performer_id=db_schedule.performer_id,
        event_type="SCHEDULE_CREATE",
        description=f"Schedule '{db_schedule.action}' created for device {db_schedule.device_id} with cron '{db_schedule.cron}'",
        related_id=db_schedule.id
    )
    db.add(db_history)
    db.commit()

    return db_schedule

@router.put("/schedules/{schedule_id}", response_model=ScheduleSchema)
def update_schedule(schedule_id: str, schedule_update: ScheduleUpdate, db: Session = Depends(get_db)):
    try:
        schedule_uuid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_schedule = db.get(Schedule, schedule_uuid)
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    update_data = schedule_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_schedule, key, value)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule

@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    try:
        schedule_uuid = uuid.UUID(schedule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_schedule = db.get(Schedule, schedule_uuid)
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(db_schedule)
    db.commit()
    return None

# History
@router.get("/history", response_model=List[HistorySchema])
def get_history(db: Session = Depends(get_db)):
    stmt = select(History)
    return db.scalars(stmt).all()

@router.get("/history/{history_id}", response_model=HistorySchema)
def get_history_item(history_id: str, db: Session = Depends(get_db)):
    try:
        history_uuid = uuid.UUID(history_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    history = db.get(History, history_uuid)
    if not history:
        raise HTTPException(status_code=404, detail="History not found")
    return history

@router.delete("/history/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(history_id: str, db: Session = Depends(get_db)):
    try:
        history_uuid = uuid.UUID(history_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_history = db.get(History, history_uuid)
    if not db_history:
        raise HTTPException(status_code=404, detail="History not found")
    db.delete(db_history)
    db.commit()
    return None

# Alerts
@router.get("/alerts", response_model=List[AlertSchema])
def get_alerts(db: Session = Depends(get_db)):
    stmt = select(Alert)
    return db.scalars(stmt).all()

@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: str, db: Session = Depends(get_db)):
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
    db_alert = db.get(Alert, alert_uuid)
    if not db_alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    db.delete(db_alert)
    db.commit()
    return None