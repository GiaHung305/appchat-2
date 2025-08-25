from fastapi import FastAPI, Request, Form, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # nếu Windows: pip install tzdata
from database import SessionLocal, get_db
from models import User, Message

app = FastAPI()

# Mount static và template
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==== TIMEZONE: UTC -> Asia/Ho_Chi_Minh ====
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def hms_local(dt: datetime, fmt: str = "%H:%M:%S") -> str:
    """Format giờ địa phương từ datetime UTC/naive."""
    if dt is None:
        return ""
    # Nếu datetime không có tzinfo, coi như UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).strftime(fmt)

# đăng ký filter cho Jinja
templates.env.filters["hms_local"] = hms_local

# Mã hóa password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dependency xác thực user
def get_current_user(request: Request):
    username = request.cookies.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username

# -------------------- ĐĂNG KÝ --------------------
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username đã tồn tại"})
    hashed_password = pwd_context.hash(password)
    new_user = User(username=username, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return RedirectResponse("/login", status_code=303)

# -------------------- ĐĂNG NHẬP --------------------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Username hoặc password sai"})
    
    response = RedirectResponse("/chat", status_code=303)
    response.set_cookie(key="username", value=username, httponly=True, max_age=3600)
    return response

# -------------------- LOGOUT --------------------
@app.get("/logout")
def logout():
    response = RedirectResponse("/login")
    response.delete_cookie("username")
    return response

# -------------------- CHAT --------------------
@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, username: str = Depends(get_current_user), db: Session = Depends(get_db)):
    # Lấy 50 tin nhắn gần nhất theo thứ tự cũ -> mới
    messages = (
        db.query(Message)
        .order_by(Message.timestamp.asc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "chat.html",
        {"request": request, "username": username, "messages": messages}
    )

# -------------------- WEBSOCKET CHAT --------------------
connected_users = {}

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    username = websocket.cookies.get("username")
    if not username:
        await websocket.close(code=403)
        return

    await websocket.accept()

    # Nếu user đã connect trước đó, đóng kết nối cũ để tránh xung đột khi reload
    if username in connected_users:
        try:
            await connected_users[username].close()
        except Exception:
            pass

    # Thêm user vào danh sách kết nối
    connected_users[username] = websocket

    # (Tuỳ chọn) Nếu không muốn thông báo join/leave, comment 2 khối dưới:
    join_msg = f"⚡ {username} đã tham gia phòng chat ({hms_local(datetime.now(timezone.utc))})"
    for ws in connected_users.values():
        if ws.client_state.value == 1 and ws is not websocket:
            await ws.send_text(join_msg)

    try:
        while True:
            data = await websocket.receive_text()

            # ----- Lưu tin nhắn vào DB (UTC aware) -----
            db = SessionLocal()
            try:
                user_obj = db.query(User).filter(User.username == username).first()
                if user_obj:
                    msg = Message(
                        sender_id=user_obj.id,
                        receiver_id=None,
                        group_id=None,
                        content=data,
                        type="text",
                        # Lưu UTC để chuẩn hoá
                        timestamp=datetime.now(timezone.utc)
                    )
                    db.add(msg)
                    db.commit()
            finally:
                db.close()
            # -------------------------------------------

            # Broadcast tin nhắn (hiển thị giờ VN)
            time_str = hms_local(datetime.now(timezone.utc))
            out = f"[{time_str}] {username}: {data}"
            for user, ws in connected_users.items():
                if ws.client_state.value == 1:
                    await ws.send_text(out)

    except WebSocketDisconnect:
        connected_users.pop(username, None)
        # (Tuỳ chọn) Không muốn thông báo leave thì comment khối dưới
        leave_msg = f"⚠️ {username} đã rời phòng chat ({hms_local(datetime.now(timezone.utc))})"
        for ws in connected_users.values():
            if ws.client_state.value == 1:
                await ws.send_text(leave_msg)
