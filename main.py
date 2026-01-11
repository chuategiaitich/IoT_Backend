from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import uvicorn
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, inspect
from typing import Dict, List
import asyncio

from db import get_db, Base, engine
from mqtt import mqtt_handler
from api import router
from bridge import broadcast_worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    print("Starting up...")
    from db import create_tables
    create_tables()

    # Khởi tạo bridge worker
    loop = asyncio.get_running_loop()
    mqtt_handler.loop = loop
    asyncio.create_task(broadcast_worker())

    mqtt_handler.connect()
    print("Application started successfully!")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    mqtt_handler.disconnect()
    print("Application shutdown complete!")

def get_database_schema(db) -> Dict[str, List[Dict]]:
    """
    Lấy thông tin schema từ SQLAlchemy metadata và inspect database
    Trả về dict dạng: {table_name: [column_info, ...]}
    """
    schema_info = {}

    # 1. Lấy từ SQLAlchemy models (metadata)
    for table_name, table in Base.metadata.tables.items():
        columns = []
        for column in table.columns:
            col_info = {
                "name": column.name,
                "type": str(column.type),
                "nullable": column.nullable,
                "primary_key": column.primary_key,
                "default": str(column.default) if column.default else None,
                "foreign_keys": [fk.target_fullname for fk in column.foreign_keys]
            }
            columns.append(col_info)
        schema_info[table_name] = columns

    # 2. (Tùy chọn) Inspect thực tế database để lấy thêm constraint, index...
    # Cần dùng sync connection vì inspect thường dùng với sync engine
    inspector = inspect(engine)

    for table_name in inspector.get_table_names():
        if table_name not in schema_info:
            # Trường hợp bảng tồn tại trong DB nhưng không có trong models
            schema_info[table_name] = [{"name": "—", "type": "— (không trong model)", "note": "Bảng tồn tại trong DB nhưng không khai báo trong SQLAlchemy"}]

        # Thêm foreign keys từ inspector (đôi khi metadata không đủ)
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            for col in schema_info[table_name]:
                if col["name"] in fk["constrained_columns"]:
                    col["foreign_keys"] = col.get("foreign_keys", []) + [f"{fk['referred_table']}.{fk['referred_columns'][0]}"]

    return schema_info

# Khởi tạo FastAPI app
app = FastAPI(
    title="IoT Backend API",
    description="Backend API for IoT devices with MQTT integration",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs"
)

env = Environment(loader=FileSystemLoader("templates"))

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong production nên chỉ định cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
# app.include_router(router, prefix="/api", tags=["API"])
app.include_router(router)

# @app.get("/")
# def root():
#     """Root endpoint"""
#     return {
#         "message": "IoT Backend API",
#         "version": "1.0.0",
#         "docs": "/docs",
#         "status": "running"
#     }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "mqtt": "connected"
    }

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Backend Dashboard</title>
        <style>
            body {
                font-family: Arial;
                background: #0f172a;
                color: white;
                display: flex;
                height: 100vh;
                align-items: center;
                justify-content: center;
            }
            .card {
                background: #1e293b;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 10px 30px rgba(0,0,0,.4);
                text-align: center;
            }
            a {
                color: #38bdf8;
                text-decoration: none;
                font-weight: bold;
                display: block;
                margin-top: 12px;
            }
            a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>FastAPI Backend</h1>
            <p>Server is running</p>
            <a href="/docs">Go to API Docs</a>
            <a href="/docs/table">Go to DB's Metadata</a>
        </div>
    </body>
    </html>
    """

@app.get("/docs/table", response_class=HTMLResponse)
async def database_table_docs():
    """
    Hiển thị schema database dưới dạng HTML đẹp
    Không cần db session vì dùng metadata + inspector
    """
    try:
        schema = get_database_schema(None)  # truyền None vì dùng engine sync
    except Exception as e:
        return f"<h1>Lỗi khi lấy schema</h1><pre>{str(e)}</pre>"

    # Tạo HTML
    html = """
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Database Schema - IoT Project</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #0f172a;
                color: #e2e8f0;
                margin: 0;
                padding: 20px;
                line-height: 1.6;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            h1 {
                color: #38bdf8;
                text-align: center;
                margin-bottom: 30px;
            }
            .table-card {
                background: #1e293b;
                border-radius: 12px;
                overflow: hidden;
                margin-bottom: 30px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.4);
            }
            .table-header {
                background: #334155;
                padding: 15px 20px;
                font-size: 1.4em;
                font-weight: bold;
                color: #7dd3fc;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 12px 15px;
                text-align: left;
            }
            th {
                background: #475569;
                color: #94a3b8;
                font-weight: 600;
            }
            tr:nth-child(even) {
                background: #1e293b;
            }
            tr:hover {
                background: #334155;
            }
            .pk {
                color: #facc15;
                font-weight: bold;
            }
            .fk {
                color: #a78bfa;
            }
            .nullable {
                color: #f87171;
            }
            .not-null {
                color: #4ade80;
            }
            .code {
                font-family: 'Consolas', monospace;
                background: #111827;
                padding: 2px 6px;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Database Schema - IoT Project</h1>
            
            <p style="text-align: center; color: #94a3b8; margin-bottom: 40px;">
                Ngày cập nhật: 27/12/2025 • Tự động sinh từ SQLAlchemy Metadata
            </p>
    """

    if not schema:
        html += "<h2 style='text-align:center;color:#f87171;'>Không tìm thấy bảng nào trong metadata</h2>"
    else:
        for table_name, columns in sorted(schema.items()):
            html += f"""
            <div class="table-card">
                <div class="table-header">Table: {table_name}</div>
                <table>
                    <thead>
                        <tr>
                            <th>Cột</th>
                            <th>Kiểu dữ liệu</th>
                            <th>Nullable</th>
                            <th>Primary Key</th>
                            <th>Foreign Key</th>
                            <th>Default</th>
                        </tr>
                    </thead>
                    <tbody>
            """

            for col in columns:
                nullable_class = "not-null" if not col["nullable"] else "nullable"
                nullable_text = "NO" if not col["nullable"] else "YES"
                pk_text = '<span class="pk">PK</span>' if col["primary_key"] else "—"
                fk_text = "<br>".join([f'<span class="fk">→ {fk}</span>' for fk in col.get("foreign_keys", [])]) or "—"
                default_text = f'<span class="code">{col["default"]}</span>' if col["default"] else "—"

                html += f"""
                        <tr>
                            <td><strong>{col["name"]}</strong></td>
                            <td><code>{col["type"]}</code></td>
                            <td class="{nullable_class}">{nullable_text}</td>
                            <td>{pk_text}</td>
                            <td>{fk_text}</td>
                            <td>{default_text}</td>
                        </tr>
                """

            html += """
                    </tbody>
                </table>
            </div>
            """

    html += """
        </div>
    </body>
    </html>
    """

    return html
    

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=10000,
        reload=True,
        log_level="info"
    )