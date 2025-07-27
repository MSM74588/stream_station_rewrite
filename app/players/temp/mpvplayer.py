import asyncio
import json
import os
import uuid
from contextlib import suppress
from typing import Optional

class MPVMediaPlayer:
    def __init__(self, url):
        if not url:
            raise ValueError("A valid URL must be provided to initialize MPVMediaPlayer.")

        self.url = url
        self.info = {}
        self.type = "mpv"
        self.ipc_path = f"/tmp/mpv_socket_{uuid.uuid4().hex[:8]}"
        self.process: Optional[asyncio.subprocess.Process] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._cleaned_up = False

    async def start(self):
        try:
            self.process = await asyncio.create_subprocess_exec(
                'mpv',
                self.url,
                '--no-terminal',
                '--no-video',
                '--force-window=no',
                '--player-operation-mode=pseudo-gui',
                f'--input-ipc-server={self.ipc_path}'
            )

            for _ in range(20):
                if os.path.exists(self.ipc_path):
                    break
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("IPC socket not created in time.")

            self._monitor_task = asyncio.create_task(self._monitor_cache())

        except Exception as e:
            print(f"❌ Failed to start mpv: {e}")

    async def _send_ipc_command(self, command: dict):
        if self._cleaned_up or not self.is_running() or not os.path.exists(self.ipc_path):
            return False
        try:
            reader, writer = await asyncio.open_unix_connection(self.ipc_path)
            writer.write((json.dumps(command) + '\n').encode('utf-8'))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return True
        except Exception as e:
            print(f"⚠️ IPC command failed: {e}")
            return False

    async def play(self):
        await self._send_ipc_command({"command": ["set_property", "pause", False]})

    async def pause(self):
        await self._send_ipc_command({"command": ["set_property", "pause", True]})

    async def stop(self):
        if self._cleaned_up:
            return

        if self._monitor_task:
            self._monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitor_task

        if self.is_running():
            try:
                await self._send_ipc_command({"command": ["quit"]})
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except asyncio.TimeoutError:
                print("⚠️ MPV didn't quit gracefully, terminating...")
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    print("⚠️ MPV didn't terminate, killing...")
                    self.process.kill()
        self.cleanup()

    def is_running(self):
        return self.process is not None and self.process.returncode is None

    async def _monitor_cache(self):
        MAX_CACHE = 1073741824
        try:
            while self.is_running():
                cache_size = await self._get_property("demuxer-cache-state", subkey="cache-size")
                paused = await self._get_property("pause")
                if cache_size and int(cache_size) > MAX_CACHE:
                    print("⚠️ Cache too big. Stopping...")
                    await self.stop()
                    break
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"⚠️ Cache monitor error: {e}")

    async def _get_property(self, prop, subkey=None):
        try:
            reader, writer = await asyncio.open_unix_connection(self.ipc_path)
            command = {"command": ["get_property", prop]}
            writer.write((json.dumps(command) + '\n').encode('utf-8'))
            await writer.drain()
            response = await reader.readline()
            writer.close()
            await writer.wait_closed()
            data = json.loads(response)
            if subkey:
                return data.get("data", {}).get(subkey)
            return data.get("data")
        except Exception:
            return None

    def cleanup(self):
        self._cleaned_up = True
        if os.path.exists(self.ipc_path):
            with suppress(FileNotFoundError):
                os.remove(self.ipc_path)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def get_state(self):
        try:
            volume = -1
            progress = 0
            paused = False
            cache = 0

            if self.is_running():
                volume = await self._get_property("volume")
                volume = int(round(volume)) if volume is not None else -1

                progress = await self._get_property("playback-time")
                progress = int(progress) if progress is not None else 0

                paused = await self._get_property("pause") or False

                cache = await self._get_property("demuxer-cache-state", subkey="cache-size")
                cache = cache if cache is not None else 0

            return {
                "status": "paused" if paused else "playing" if self.is_running() else "stopped",
                "current_media_type": "audio" if "--no-video" in self.process.args else "video",
                "volume": volume,
                "is_paused": paused,
                "cache_size": cache,
                "media_name": self.info.get("title") or "Unknown",
                "media_uploader": self.info.get("uploader") or self.info.get("channel") or "Unknown",
                "media_duration": self.info.get("duration") or 0,
                "media_progress": progress,
                "is_live": self.info.get("is_live") or False,
                "media_url": self.info.get("webpage_url") or self.url,
            }
        except Exception as e:
            print(f"⚠️ Failed to get MPV state: {e}")

# Example async usage
async def main():
    url = 'https://www.youtube.com/watch?v=jfKfPfyJRdk'
    async with MPVMediaPlayer(url) as player:
        await asyncio.sleep(5)
        await player.pause()
        await asyncio.sleep(2)
        await player.play()
        await asyncio.sleep(5)
        await player.stop()

if __name__ == '__main__':
    asyncio.run(main())
