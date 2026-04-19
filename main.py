#!/usr/bin/env python3
"""
🔥 EXACT @JERRY_HOSTING_bot CLONE 🔥
Auto-approve | 24/7 hosting | Error fix button | Multi-language
Credit: ADIL
"""

import os
import subprocess
import time
import resource
import asyncio
from pathlib import Path
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)

# ---------- CONFIG ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8762654526:AAFvVEJsFhVJeCCSmlSI6dxLVDNtbe41sTQ)
DATA_DIR = "./user_data"
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
TIMEOUT_SEC = 300                  # max run time per script (5 min)
MAX_MEMORY_MB = 256                # 256 MB RAM limit

os.makedirs(DATA_DIR, exist_ok=True)

# Store running processes: {user_id: {"proc": Popen, "file": name, "start": timestamp, "log": []}}
running_procs = {}

def set_limits():
    """Apply resource limits to child process."""
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SEC, TIMEOUT_SEC))
    mem_bytes = MAX_MEMORY_MB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def get_command(file_path: Path):
    """Return shell command based on file extension."""
    ext = file_path.suffix.lower()
    if ext == '.py':
        return ['python3', str(file_path)]
    elif ext == '.js':
        return ['node', str(file_path)]
    elif ext == '.sh':
        return ['bash', str(file_path)]
    elif ext == '.rb':
        return ['ruby', str(file_path)]
    elif ext == '.pl':
        return ['perl', str(file_path)]
    elif ext == '.cpp':
        # Compile then run
        out = file_path.with_suffix('.out')
        subprocess.run(['g++', str(file_path), '-o', str(out)], check=False)
        return [str(out)] if out.exists() else None
    elif ext == '.go':
        return ['go', 'run', str(file_path)]
    else:
        # Assume executable binary
        os.chmod(file_path, 0o755)
        return [str(file_path)]

def run_script(user_id: int, file_path: Path):
    """Start user script with resource limits."""
    cmd = get_command(file_path)
    if not cmd:
        raise ValueError("Unsupported file type or compilation failed")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        preexec_fn=set_limits
    )
    running_procs[user_id] = {
        "proc": proc,
        "file": file_path.name,
        "start": time.time(),
        "log": []
    }
    return proc

def get_logs(user_id: int, lines: int = 50) -> str:
    """Return last N lines of output."""
    info = running_procs.get(user_id)
    if not info:
        return "No running process."
    try:
        stdout, stderr = info["proc"].communicate(timeout=0.01)
        if stdout:
            info["log"].extend(stdout.splitlines())
        if stderr:
            info["log"].extend(stderr.splitlines())
    except subprocess.TimeoutExpired:
        pass
    if len(info["log"]) > 200:
        info["log"] = info["log"][-200:]
    return "\n".join(info["log"][-lines:])

def process_has_error(user_id: int) -> bool:
    """Check if process exited with error or stderr contains error keywords."""
    info = running_procs.get(user_id)
    if not info:
        return False
    proc = info["proc"]
    poll = proc.poll()
    if poll is not None and poll != 0:
        return True
    _, stderr = proc.communicate(timeout=0.1)
    if stderr:
        error_keywords = ["Error", "Exception", "Traceback", "SyntaxError", "FAILED", "Fatal"]
        if any(kw in stderr for kw in error_keywords):
            return True
    return False

async def monitor_process(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Background task: wait a few seconds, then check for errors and send fix button."""
    await asyncio.sleep(5)
    if process_has_error(user_id):
        keyboard = [[InlineKeyboardButton("🛠️ Fix Error", callback_data=f"fix_{user_id}")]]
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ *Error detected* in your running script.\nClick below to upload a corrected version.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

def make_process_keyboard(user_id: int):
    """Create inline keyboard for a running process."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Status", callback_data=f"status_{user_id}"),
            InlineKeyboardButton("📜 Logs", callback_data=f"logs_{user_id}")
        ],
        [
            InlineKeyboardButton("🛑 Stop", callback_data=f"stop_{user_id}"),
            InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------- Bot Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 *EXACT @JERRY_HOSTING_bot CLONE* 🔥\n"
        "Credit: ADIL\n\n"
        "*Send me any script file* (`.py`, `.js`, `.sh`, `.rb`, `.pl`, `.cpp`, `.go`)\n"
        "I will run it **24/7** with resource limits.\n\n"
        "*Commands:*\n"
        "/start – this message\n"
        "/status – current process status\n"
        "/logs – show last 50 lines\n"
        "/stop – kill your process\n\n"
        "*Inline buttons* appear after upload.\n"
        "If an error occurs, a **Fix Error** button will appear – click it and upload corrected file.",
        parse_mode="Markdown"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    doc = update.message.document

    # Check if this is a "fix" upload
    if context.user_data.get("awaiting_fix"):
        context.user_data["awaiting_fix"] = False
        # Stop existing process
        if user_id in running_procs:
            running_procs[user_id]["proc"].terminate()
            time.sleep(1)
            if running_procs[user_id]["proc"].poll() is None:
                running_procs[user_id]["proc"].kill()
            del running_procs[user_id]
    else:
        # Normal first-time upload – stop any previous process
        if user_id in running_procs:
            running_procs[user_id]["proc"].terminate()
            time.sleep(1)
            if running_procs[user_id]["proc"].poll() is None:
                running_procs[user_id]["proc"].kill()
            del running_procs[user_id]

    if doc.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(f"❌ File too large. Max {MAX_FILE_SIZE//(1024*1024)} MB.")
        return

    status_msg = await update.message.reply_text("📥 Downloading your file...")
    file = await context.bot.get_file(doc.file_id)
    user_dir = Path(DATA_DIR) / str(user_id)
    user_dir.mkdir(exist_ok=True)
    file_path = user_dir / doc.file_name
    await file.download_to_drive(file_path)

    try:
        run_script(user_id, file_path)
        await status_msg.edit_text(
            f"✅ *Script started successfully!*\n\n"
            f"📄 `{doc.file_name}`\n"
            f"⏱️ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Use the buttons below to manage it.",
            parse_mode="Markdown",
            reply_markup=make_process_keyboard(user_id)
        )
        asyncio.create_task(monitor_process(user_id, context))
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed to start: {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("fix_"):
        target_user = int(data.split("_")[1])
        if target_user != user_id:
            await query.edit_message_text("❌ You can only fix your own process.")
            return
        context.user_data["awaiting_fix"] = True
        await query.edit_message_text(
            "🛠️ *Upload the corrected file.*\nIt will replace the current one and restart automatically.",
            parse_mode="Markdown"
        )
        return

    if user_id not in running_procs:
        await query.edit_message_text("❌ No running process for you.")
        return

    if data.startswith("status_"):
        proc_info = running_procs[user_id]
        poll = proc_info["proc"].poll()
        status = "🟢 running" if poll is None else f"🔴 exited with code {poll}"
        uptime = int(time.time() - proc_info["start"])
        text = f"*Process status:* {status}\n*File:* `{proc_info['file']}`\n*Uptime:* {uptime}s"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=make_process_keyboard(user_id))

    elif data.startswith("logs_"):
        logs = get_logs(user_id, 50)
        if not logs:
            logs = "No output yet."
        if len(logs) > 4000:
            logs = logs[:4000] + "\n... (truncated)"
        await query.edit_message_text(f"📄 *Logs:*\n```\n{logs}\n```", parse_mode="Markdown", reply_markup=make_process_keyboard(user_id))

    elif data.startswith("stop_"):
        proc = running_procs[user_id]["proc"]
        proc.terminate()
        time.sleep(1)
        if proc.poll() is None:
            proc.kill()
        del running_procs[user_id]
        await query.edit_message_text("🛑 Process stopped.\nYou can upload a new file.", reply_markup=None)

    elif data.startswith("restart_"):
        proc_info = running_procs[user_id]
        file_path = Path(DATA_DIR) / str(user_id) / proc_info["file"]
        # Kill old
        proc_info["proc"].terminate()
        time.sleep(1)
        if proc_info["proc"].poll() is None:
            proc_info["proc"].kill()
        # Start new
        try:
            run_script(user_id, file_path)
            await query.edit_message_text(
                f"🔄 *Restarted* `{proc_info['file']}`",
                parse_mode="Markdown",
                reply_markup=make_process_keyboard(user_id)
            )
            asyncio.create_task(monitor_process(user_id, context))
        except Exception as e:
            await query.edit_message_text(f"❌ Restart failed: {str(e)}")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in running_procs:
        proc_info = running_procs[user_id]
        poll = proc_info["proc"].poll()
        status = "running" if poll is None else f"exited with code {poll}"
        await update.message.reply_text(
            f"🟢 Status: {status}\nFile: `{proc_info['file']}`",
            parse_mode="Markdown",
            reply_markup=make_process_keyboard(user_id)
        )
    else:
        await update.message.reply_text("❌ No running process. Upload a file to start.")

async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logs = get_logs(user_id, 50)
    if not logs:
        logs = "No output yet."
    if len(logs) > 4000:
        logs = logs[:4000] + "\n... (truncated)"
    await update.message.reply_text(f"📄 *Logs:*\n```\n{logs}\n```", parse_mode="Markdown")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in running_procs:
        running_procs[user_id]["proc"].terminate()
        time.sleep(1)
        if running_procs[user_id]["proc"].poll() is None:
            running_procs[user_id]["proc"].kill()
        del running_procs[user_id]
        await update.message.reply_text("🛑 Process stopped.")
    else:
        await update.message.reply_text("No running process.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(status_|logs_|stop_|restart_|fix_)"))

    print("🤖 Bot started (exact @JERRY_HOSTING_bot clone). Credit: ADIL")
    app.run_polling()

if __name__ == "__main__":
    main()
