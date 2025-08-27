from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from passlib.context import CryptContext
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import socketio

from database import SessionLocal, get_db, Base, engine
from models import User, Message

# ==== Database ====
Base.metadata.create_all(bind=engine)

# ==== FastAPI + Socket.IO ====
app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app.mount("/socket.io", socketio.ASGIApp(sio))
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# ==== Timezone ====
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
def hms_local(dt):
    if not dt:
        return ""
    # nếu datetime lấy từ DB không có tzinfo thì giả sử UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).strftime("%H:%M:%S")

templates.env.filters["hms_local"] = hms_local
# ==== Password ====
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==== Current user ====
def get_current_user(request: Request):
    username = request.cookies.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username

# ==== Pages ====
@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse("/login")

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username đã tồn tại"})
    user = User(username=username, password=pwd_context.hash(password))
    db.add(user)
    db.commit()
    return RedirectResponse("/login", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd_context.verify(password, user.password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Username hoặc password sai"})
    resp = RedirectResponse("/chat", status_code=303)
    resp.set_cookie("username", username, httponly=True, max_age=3600)
    return resp

@app.get("/logout")
async def logout(request: Request):
    username = request.cookies.get("username")

    resp = RedirectResponse("/login")
    resp.delete_cookie("username")

    if username:
        await sio.emit("chat_message", {
            "time": datetime.now(timezone.utc).astimezone(LOCAL_TZ).strftime("%H:%M:%S"),
            "username": "System",
            "message": f"⚠️ {username} đã rời phòng chat",
            "sender_id": 0
        })

    return resp

@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, username: str = Depends(get_current_user), db: Session = Depends(get_db)):
    messages = (
        db.query(Message)
        .options(
            joinedload(Message.sender),
            joinedload(Message.receiver),
            joinedload(Message.group),
        )
        .order_by(Message.timestamp.asc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse(
        "chat.html", {"request": request, "username": username, "messages": messages}
    )

# ==== Socket.IO ====
@sio.event
async def connect(sid, environ):
    print("Client connected:", sid)

@sio.event
async def disconnect(sid):
    print("Client disconnected:", sid)
    # Nếu muốn thông báo rời phòng ở đây:
    session = await sio.get_session(sid)
    username = session.get("username")
    if username:
        await sio.emit("chat_message", {
            "time": datetime.now(timezone.utc).astimezone(LOCAL_TZ).strftime("%H:%M:%S"),
            "username": "System",
            "message": f"⚠️ {username} đã mất kết nối",
            "sender_id": 0
        })

@sio.event
async def join_chat(sid, data):
    username = data.get("username")
    await sio.save_session(sid, {"username": username})
    await sio.emit("chat_message", {
        "time": datetime.now(timezone.utc).astimezone(LOCAL_TZ).strftime("%H:%M:%S"),
        "username": "System",
        "message": f"⚡ {username} đã tham gia phòng chat",
        "sender_id": 0
    })

@sio.event
async def send_message(sid, data):
    session = await sio.get_session(sid)
    username = session.get("username")
    content = data.get("message")

    db = SessionLocal()
    try:
        user_obj = db.query(User).filter(User.username == username).first()
        if user_obj:
            msg = Message(sender_id=user_obj.id, content=content, timestamp=datetime.now(timezone.utc))
            db.add(msg)
            db.commit()

            await sio.emit("chat_message", {
                "time": datetime.now(timezone.utc).astimezone(LOCAL_TZ).strftime("%H:%M:%S"),
                "username": username,
                "message": content,
                "sender_id": user_obj.id
            })
    finally:
        db.close()
