import asyncio
import json
import os
import uuid
from contextlib import suppress
from typing import Optional
from app.models import PlayerInfo

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
        self._stopping = False  # New flag to prevent race conditions

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

            # Wait for IPC socket with timeout
            for _ in range(50):  # Increased from 20 to 50
                if os.path.exists(self.ipc_path):
                    break
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("IPC socket not created in time.")

            # Verify the process is still running
            if self.process.returncode is not None:
                raise RuntimeError(f"MPV process exited with code {self.process.returncode}")

            self._monitor_task = asyncio.create_task(self._monitor_cache())
            print(f"✅ MPV started successfully for: {self.url}")

        except Exception as e:
            print(f"❌ Failed to start mpv: {e}")
            await self.cleanup()
            raise

    async def _send_ipc_command(self, command: dict):
        if self._cleaned_up or self._stopping or not self.is_running() or not os.path.exists(self.ipc_path):
            print("⚠️ Cannot send IPC command: player is stopped or cleaning up")
            return False
        
        try:
            # Add timeout to prevent hanging
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.ipc_path), 
                timeout=2.0
            )
            
            command_str = json.dumps(command) + '\n'
            writer.write(command_str.encode('utf-8'))
            await asyncio.wait_for(writer.drain(), timeout=1.0)
            
            writer.close()
            await writer.wait_closed()
            return True
            
        except asyncio.TimeoutError:
            print("⚠️ IPC command timed out")
            return False
        except Exception as e:
            print(f"⚠️ IPC command failed: {e}")
            return False

    async def play(self):
        if self._stopping or self._cleaned_up:
            print("⚠️ Cannot play: player is stopping or cleaned up")
            return
        await self._send_ipc_command({"command": ["set_property", "pause", False]})

    async def pause(self):
        if self._stopping or self._cleaned_up:
            print("⚠️ Cannot pause: player is stopping or cleaned up")
            return
        await self._send_ipc_command({"command": ["set_property", "pause", True]})

    async def stop(self):
        if self._cleaned_up or self._stopping:
            return

        self._stopping = True
        print(f"🛑 Stopping MPV player for: {self.url}")

        # Cancel monitor task first
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._monitor_task

        # Try graceful quit first
        if self.is_running():
            try:
                print("🔄 Sending quit command to MPV...")
                await self._send_ipc_command({"command": ["quit"]})
                
                # Wait for process to exit gracefully
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                    print("✅ MPV quit gracefully")
                except asyncio.TimeoutError:
                    print("⚠️ MPV didn't quit gracefully, terminating...")
                    self.process.terminate()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=3)
                        print("✅ MPV terminated")
                    except asyncio.TimeoutError:
                        print("⚠️ MPV didn't terminate, killing...")
                        self.process.kill()
                        await self.process.wait()
                        print("✅ MPV killed")
                        
            except Exception as e:
                print(f"⚠️ Error during MPV shutdown: {e}")
                if self.process and self.process.returncode is None:
                    self.process.kill()
                    await self.process.wait()

        await self.cleanup()

    def is_running(self):
        return (self.process is not None and 
                self.process.returncode is None and 
                not self._cleaned_up and 
                not self._stopping)

    async def _monitor_cache(self):
        MAX_CACHE = 1073741824  # 1GB
        try:
            while self.is_running() and not self._stopping:
                cache_size = await self._get_property("demuxer-cache-state", subkey="cache-size")
                if cache_size and int(cache_size) > MAX_CACHE:
                    print("⚠️ Cache too big. Stopping...")
                    await self.stop()
                    break
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            print("🔄 Cache monitor cancelled")
        except Exception as e:
            print(f"⚠️ Cache monitor error: {e}")

    async def _get_property(self, prop, subkey=None):
        if self._cleaned_up or self._stopping or not self.is_running():
            return None
            
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.ipc_path),
                timeout=2.0
            )
            
            command = {"command": ["get_property", prop]}
            writer.write((json.dumps(command) + '\n').encode('utf-8'))
            await writer.drain()
            
            response = await asyncio.wait_for(reader.readline(), timeout=2.0)
            writer.close()
            await writer.wait_closed()
            
            data = json.loads(response)
            if subkey:
                return data.get("data", {}).get(subkey)
            return data.get("data")
            
        except Exception:
            return None

    async def cleanup(self):
        if self._cleaned_up:
            return
            
        self._cleaned_up = True
        print(f"🧹 Cleaning up MPV for: {self.url}")
        
        if os.path.exists(self.ipc_path):
            with suppress(FileNotFoundError, PermissionError):
                os.remove(self.ipc_path)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.stop()

    async def get_state(self):
        if self._cleaned_up or self._stopping:
            return PlayerInfo(
                status="stopped",
                current_media_type="audio",
                volume=0,
                is_paused=True,
                cache_size=0,
                media_name="",
                media_uploader="",
                media_duration=0,
                media_progress=0,
                media_url="",
                is_live=False,
            )
            
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
                
                status = "paused" if paused else "playing" if self.is_running() else "stopped"
                current_media_type = "audio" # fix this later FIXME
            else:
                status = "stopped"
                current_media_type = "audio"
            
            return PlayerInfo(
                status=status,
                current_media_type=current_media_type,
                volume=volume,
                is_paused=(status.lower() != "playing"),
                cache_size=cache,
                media_name=self.info.get("title") or "Unknown",
                media_uploader=self.info.get("uploader") or self.info.get("channel") or "Unknown",
                media_duration=self.info.get("duration") or 0,
                media_progress=progress,
                media_url=self.info.get("webpage_url") or self.url,
                is_live=self.info.get("is_live") or False,
            )
            
        except Exception as e:
            print(f"⚠️ Failed to get MPV state: {e}")
            return PlayerInfo(status="error")

    # Add unload method for compatibility
    async def unload(self):
        await self.stop()
