import os
import asyncio
import subprocess
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

API_ID = int(os.environ["36142099"])
API_HASH = os.environ["d027b3aa54141f95958a55b9b92d3735"]
BOT_TOKEN = os.environ["8752861657:AAHcq4QRUHrTy5dmwg_HYRQs7mjJpOLsjnI"]

app = Client(
    "vc_audio_relay_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)
calls = PyTgCalls(app)

# chat_id -> settings
states = {}
active_vcs = set()
sudo_users = set()

DEFAULTS = {
    "volume": 200,
    "gain": 30,
    "bass": 10,
    "treble": 40,
    "voice": "normal",
    "muted": False,
    "automute": False,
    "recording": False,
}

def state(chat_id):
    if chat_id not in states:
        states[chat_id] = DEFAULTS.copy()
    return states[chat_id]

def is_sudo(message: Message):
    return message.from_user and (
        message.from_user.id in sudo_users
        or message.from_user.id == int(os.getenv("OWNER_ID", "0"))
    )

def parse_value(text, low, high):
    try:
        value = int(text)
        if low <= value <= high:
            return value
    except Exception:
        pass
    return None

def ffmpeg_filter(s):
    # Generic tone shaping only; no identity/voice cloning.
    vol = s["volume"] / 100.0
    gain = s["gain"] / 10.0
    bass = (s["bass"] - 50) / 5.0
    treble = (s["treble"] - 50) / 5.0

    filters = [
        f"volume={vol:.2f}",
        f"bass=g={bass:.1f}",
        f"treble=g={treble:.1f}",
        f"volume={gain:.2f}",
    ]

    if s["voice"] == "female":
        filters += ["highpass=f=140", "asetrate=48000*1.08", "aresample=48000"]
    elif s["voice"] == "male":
        filters += ["lowpass=f=5000", "asetrate=48000*0.92", "aresample=48000"]

    return ",".join(filters)

async def play_source(chat_id, source):
    s = state(chat_id)
    if s["muted"]:
        return

    # FFmpeg creates a processed PCM stream. Replace source with your
    # live audio input/relay endpoint when connecting the capture layer.
    filt = ffmpeg_filter(s)
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-i", source,
        "-af", filt,
        "-f", "s16le", "-ar", "48000", "-ac", "2", "pipe:1",
        stdout=asyncio.subprocess.PIPE,
    )
    return proc

@app.on_message(filters.command("join") & filters.group)
async def join(_, m: Message):
    if not is_sudo(m):
        return await m.reply_text("❌ Sudo only.")
    if len(m.command) != 2:
        return await m.reply_text("Usage: /join -100xxxxxxxx")
    try:
        chat_id = int(m.command[1])
        await calls.play(
            chat_id,
            MediaStream(
                "https://example.invalid/audio"
            )
        )
        active_vcs.add(chat_id)
        state(chat_id)
        await m.reply_text(f"🎧 VC joined: `{chat_id}`\n⚠️ Connect your live audio source to `play_source()`.")
    except Exception as e:
        await m.reply_text(f"❌ VC join failed:\n`{e}`")

@app.on_message(filters.command("leave") & filters.group)
async def leave(_, m):
    if not is_sudo(m):
        return await m.reply_text("❌ Sudo only.")
    try:
        chat_id = m.chat.id
        await calls.leave_call(chat_id)
        active_vcs.discard(chat_id)
        await m.reply_text("👋 Left the VC.")
    except Exception as e:
        await m.reply_text(f"❌ `{e}`")

@app.on_message(filters.command("volume") & filters.group)
async def volume(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    if len(m.command) != 2:
        return await m.reply_text("Usage: /volume 0-400")
    v = parse_value(m.command[1], 0, 400)
    if v is None: return await m.reply_text("❌ Range: 0–400")
    state(m.chat.id)["volume"] = v
    await m.reply_text(f"🔊 Volume: {v}%")

@app.on_message(filters.command("gain") & filters.group)
async def gain(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    if len(m.command) != 2:
        return await m.reply_text("Usage: /gain 0-150")
    v = parse_value(m.command[1], 0, 150)
    if v is None: return await m.reply_text("❌ Range: 0–150")
    state(m.chat.id)["gain"] = v
    await m.reply_text(f"🎚 Gain: {v}%")

@app.on_message(filters.command("bass") & filters.group)
async def bass(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    if len(m.command) != 2:
        return await m.reply_text("Usage: /bass 0-100")
    v = parse_value(m.command[1], 0, 100)
    if v is None: return await m.reply_text("❌ Range: 0–100")
    state(m.chat.id)["bass"] = v
    await m.reply_text(f"🎵 Bass: {v}")

@app.on_message(filters.command("treble") & filters.group)
async def treble(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    if len(m.command) != 2:
        return await m.reply_text("Usage: /treble 0-100")
    v = parse_value(m.command[1], 0, 100)
    if v is None: return await m.reply_text("❌ Range: 0–100")
    state(m.chat.id)["treble"] = v
    await m.reply_text(f"✨ Treble: {v}")

@app.on_message(filters.command("voice") & filters.group)
async def voice(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    if len(m.command) != 2 or m.command[1].lower() not in ("female", "male", "normal"):
        return await m.reply_text("Usage: /voice female|male|normal")
    s = state(m.chat.id)
    s["voice"] = m.command[1].lower()
    presets = {
        "female": "sharp/bright generic effect",
        "male": "deep/heavy generic effect",
        "normal": "balanced",
    }
    await m.reply_text(f"🎙 Voice preset: {s['voice']}\n{presets[s['voice']]}")

@app.on_message(filters.command("mute") & filters.group)
async def mute(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    state(m.chat.id)["muted"] = True
    await m.reply_text("🔇 Master mute ON")

@app.on_message(filters.command("unmute") & filters.group)
async def unmute(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    state(m.chat.id)["muted"] = False
    await m.reply_text("🔊 Master mute OFF")

@app.on_message(filters.command("automute") & filters.group)
async def automute(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    if len(m.command) != 2 or m.command[1] not in ("on", "off"):
        return await m.reply_text("Usage: /automute on|off")
    state(m.chat.id)["automute"] = m.command[1] == "on"
    await m.reply_text(f"🤫 Auto-mute: {m.command[1]}")

@app.on_message(filters.command("status") & filters.group)
async def status(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    s = state(m.chat.id)
    await m.reply_text(
        "🎧 **VC Audio Relay**\n\n"
        f"Active VCs: `{len(active_vcs)}`\n"
        f"Muted: `{s['muted']}`\n"
        f"Auto-mute: `{s['automute']}`\n"
        f"Volume: `{s['volume']}%`\n"
        f"Gain: `{s['gain']}%`\n"
        f"Bass: `{s['bass']}`\n"
        f"Treble: `{s['treble']}`\n"
        f"Voice: `{s['voice']}`"
    )

@app.on_message(filters.command("listvc") & filters.group)
async def listvc(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    if not active_vcs:
        return await m.reply_text("No active VCs.")
    await m.reply_text("🎧 Active VCs:\n" + "\n".join(f"• `{x}`" for x in active_vcs))

@app.on_message(filters.command("sudoadd") & filters.group)
async def sudoadd(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    target = m.from_user.id if not m.reply_to_message else m.reply_to_message.from_user.id
    sudo_users.add(target)
    await m.reply_text(f"👑 Added sudo: `{target}`")

@app.on_message(filters.command("sudodel") & filters.group)
async def sudodel(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    target = m.from_user.id if not m.reply_to_message else m.reply_to_message.from_user.id
    sudo_users.discard(target)
    await m.reply_text(f"🗑 Removed sudo: `{target}`")

@app.on_message(filters.command("sudolist") & filters.group)
async def sudolist(_, m):
    if not is_sudo(m): return await m.reply_text("❌ Sudo only.")
    text = "\n".join(f"• `{x}`" for x in sudo_users) or "No sudo users."
    await m.reply_text("👑 Sudo users:\n" + text)

print("Starting VC Audio Relay Bot...")
app.start()
calls.start()
asyncio.get_event_loop().run_forever()
