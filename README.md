# VC Audio Relay Bot

This is a control/processing core for a Telegram VC audio relay bot.

## Install
```bash
pkg update
pkg install python ffmpeg
pip install -r requirements.txt
```

Set environment variables:
```bash
export API_ID="..."
export API_HASH="..."
export BOT_TOKEN="..."
export OWNER_ID="..."
```

Run:
```bash
python bot.py
```

## Important
`/join` contains a placeholder media URL because PyTgCalls needs an actual media source.
A Telegram group-call receiver/capture layer must feed the bot's `play_source()` pipeline for true
live microphone -> processing -> VC relay. Android/Termux cannot simply read another participant's
Telegram VC microphone stream through the Bot API.

The FFmpeg filter provides generic tone shaping (volume/gain/bass/treble and male/female-style
pitch/tone presets); it is not an identity/voice clone.
