# filename: media_stubs.py
"""Placeholders for UDP Voice/Video. Wire these to GUI toggles later.
- Voice: capture mic (PyAudio) → encode (e.g., PCM/Opus) → UDP to server → relay.
- Video: capture frames (OpenCV) → JPEG encode → MTU-split → UDP.
Add sequence numbers and drop/repair strategy for out-of-order/ lost packets.
"""

class VoiceClient:
    def start(self):
        print("[voice] start (stub)")
    def stop(self):
        print("[voice] stop (stub)")

class VideoClient:
    def start(self):
        print("[video] start (stub)")
    def stop(self):
        print("[video] stop (stub)")
