import contextlib
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
import base64
import websocket
from samsungtvws import SamsungTVWS
from samsungtvws.exceptions import ConnectionFailure
from const import CONNECTION_NAME
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        logger.warning("Invalid value for %s, falling back to %s", name, default)
        return default


DEFAULT_PORT = 8002
# Socket-level timeout handed to samsungtvws (covers connect and single reads).
DEFAULT_TIMEOUT = _env_int("FRAME_TV_SOCKET_TIMEOUT", 8)
# Wall-clock cap for a whole TV operation, see _tv_call().
TV_CALL_DEADLINE = _env_int("FRAME_TV_CALL_DEADLINE", 20)
# Uploads push the whole image over the websocket, so they get a longer budget.
TV_UPLOAD_DEADLINE = _env_int("FRAME_TV_UPLOAD_DEADLINE", 120)
# Pairing waits for someone to accept the prompt on the TV, so it needs room too.
TV_PAIRING_TIMEOUT = _env_int("FRAME_TV_PAIRING_TIMEOUT", 45)
# How long a TV is skipped after it failed to answer, so one dead set cannot
# turn a page full of thumbnails into a page full of stuck requests.
TV_DOWN_COOLDOWN = _env_int("FRAME_TV_DOWN_COOLDOWN", 30)
# How long a deliberate action queues behind another operation on the same TV. A page
# of thumbnails holds the TV for far longer than one call's deadline, and someone who
# pressed a button would rather wait for their turn than be told the TV is busy.
TV_BUSY_WAIT = _env_int("FRAME_TV_BUSY_WAIT", 90)
# How many thumbnails are asked for in one request. The TV streams the whole answer
# down one socket before the call returns, so a large batch is a single long transfer
# that is lost in full if it does not finish.
TV_THUMBNAIL_BATCH = _env_int("FRAME_TV_THUMBNAIL_BATCH", 8)
# Fetching a page of thumbnails is several of those transfers, so it gets its own
# budget rather than a single call's.
TV_THUMBNAIL_DEADLINE = _env_int("FRAME_TV_THUMBNAIL_DEADLINE", 120)
# How many images in a row may die at the connection level before the rest of the
# gallery is left for next time. Each one costs a socket timeout, and the TV is locked
# for the whole walk, so this bounds how long one page load can hold it.
TV_THUMBNAIL_GIVE_UP = _env_int("FRAME_TV_THUMBNAIL_GIVE_UP", 3)
# How long the walk may go without a single thumbnail before it stops. Counting failures
# is not enough on its own: one request to the art channel can run far longer than the
# socket timeout, because samsungtvws reads frames until it sees the one it asked for
# and each read restarts the clock. A set that has gone quiet would otherwise spend the
# whole budget to return nothing, with its art channel busy the entire time.
TV_THUMBNAIL_FIRST_ANSWER = _env_int("FRAME_TV_THUMBNAIL_FIRST_ANSWER", 25)
# How long one request to the TV may go without the library returning from it before
# its connection is closed from the outside. Guards that sit between calls cannot help
# here: samsungtvws reads frames until it sees the one it asked for, so a single call
# can outlast any budget while nothing around it gets a chance to run.
TV_STALL_TIMEOUT = _env_int("FRAME_TV_STALL_TIMEOUT", 25)
# Simple in-memory cache to reduce repeated TV requests
# Structure: { (ip, 'gallery'): (timestamp, value), (ip, content_id): (timestamp, bytes) }
_CACHE: dict = {}
_CACHE_TTL = 60  # seconds

def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        try:
            del _CACHE[key]
        except KeyError:
            pass
        return None
    return value

def _cache_set(key, value):
    _CACHE[key] = (time.time(), value)


# Disk-backed thumbnail cache — store under the project's data directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Match app.py's DATA_DIR behavior: use FRAME_TV_DATA env or default to 'data'
_DATA_DIR = Path(os.environ.get('FRAME_TV_DATA', 'data'))
if not _DATA_DIR.is_absolute():
    _DATA_DIR = PROJECT_ROOT.joinpath(_DATA_DIR)
TV_THUMB_DIR = _DATA_DIR.joinpath('instance', 'tv_thumbnails')
TV_THUMB_DIR.mkdir(parents=True, exist_ok=True)

# The gallery listing, held just long enough that reloading a page does not have to
# queue behind whatever else is talking to the TV. Anything here that changes the set's
# contents drops it, so a delete or an upload is still seen immediately; only a change
# made elsewhere — the TV's own remote — can be up to this stale.
TV_GALLERY_TTL = _env_int("FRAME_TV_GALLERY_TTL", 15)
_GALLERY_CACHE: Dict[str, tuple] = {}


def _cached_gallery(ip: str) -> Optional[List[Dict]]:
    entry = _GALLERY_CACHE.get(ip)
    if entry is None:
        return None
    cached_at, images = entry
    if time.time() - cached_at > TV_GALLERY_TTL:
        _GALLERY_CACHE.pop(ip, None)
        return None
    return images


def _remember_gallery(ip: str, images: List[Dict]) -> None:
    _GALLERY_CACHE[ip] = (time.time(), images)


def forget_gallery(ip: str) -> None:
    """Drop the cached listing for a TV whose contents just changed."""
    _GALLERY_CACHE.pop(ip, None)


def _thumb_disk_path(ip: str, content_id: str) -> Path:
    safe_ip = ip.replace(':', '_')
    return TV_THUMB_DIR.joinpath(safe_ip, content_id)

def _thumb_disk_get(ip: str, content_id: str) -> Optional[bytes]:
    p = _thumb_disk_path(ip, content_id)
    if p.is_file():
        try:
            return p.read_bytes()
        except Exception:
            return None
    return None

def _thumb_disk_set(ip: str, content_id: str, data: bytes) -> None:
    p = _thumb_disk_path(ip, content_id)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    except Exception:
        logger.exception("Failed to write thumbnail to disk for %s %s", ip, content_id)

class FrameTVError(Exception):
    """Base exception for Frame TV operations."""
    pass

class FrameTVConnectionError(FrameTVError):
    """Exception for connection errors to the Frame TV."""
    pass


class FrameTVTimeoutError(FrameTVConnectionError):
    """Exception for timeouts while talking to the Frame TV."""
    pass


class FrameTVUnavailableError(FrameTVConnectionError):
    """Raised instead of contacting a TV that just failed, while its cooldown lasts.

    This is the circuit breaker doing its job, not an incident: callers should report
    it without a stack trace, since one page of thumbnails raises it many times over.
    """
    pass

class FrameTVUploadError(FrameTVError):
    """Exception for upload errors to the Frame TV."""
    pass


def _is_timeout_error(err: Exception) -> bool:
    return (
        isinstance(err, (TimeoutError, socket.timeout))
        or getattr(err, "winerror", None) == 10060
        or "10060" in str(err)
        or "timed out" in str(err).lower()
    )


def _is_connection_error(err: Exception) -> bool:
    """True when the error means "the TV is not talking to us" rather than "the TV said no"."""
    return isinstance(
        err, (OSError, ConnectionFailure, FrameTVConnectionError, websocket.WebSocketException)
    ) or _is_timeout_error(err)


def _raise_tv_connection_error(ip: str, action_description: str, err: Exception) -> None:
    if _is_timeout_error(err):
        raise FrameTVTimeoutError(f"Timeout while {action_description} TV {ip}") from err
    raise FrameTVConnectionError(f"Error while {action_description} TV {ip}") from err


# --- Bounded TV calls ---
#
# samsungtvws has no overall timeout: art requests wait in a `while True` loop on
# recv() until the TV answers the right frame. A set that accepts the socket but
# stops answering therefore blocks the request forever — long enough for gunicorn
# to kill the worker, respawn it, and hit the same wall on the next thumbnail.
# Every TV call runs in a worker thread with a hard deadline, and the sockets are
# closed from the outside on expiry, which is what makes the pending recv() fail.

_TV_EXECUTOR = ThreadPoolExecutor(
    max_workers=_env_int("FRAME_TV_MAX_PARALLEL_CALLS", 8),
    thread_name_prefix="frametv",
)

# The cooldown is shared between gunicorn workers through a marker file whose mtime is
# when the TV last failed. Keeping it in memory would only teach one worker out of four,
# so a page full of thumbnails would still stall once per worker.
TV_DOWN_DIR = _DATA_DIR.joinpath('instance', 'tv_down')


def _safe_ip(ip: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in ip)


def _tv_down_marker(ip: str) -> Path:
    return TV_DOWN_DIR.joinpath(f"tv-{_safe_ip(ip)}")


def _tv_cooldown_remaining(ip: str) -> float:
    try:
        failed_at = _tv_down_marker(ip).stat().st_mtime
    except OSError:
        return 0.0
    return max(0.0, TV_DOWN_COOLDOWN - (time.time() - failed_at))


def _mark_tv_down(ip: str) -> None:
    try:
        TV_DOWN_DIR.mkdir(parents=True, exist_ok=True)
        _tv_down_marker(ip).touch()
    except OSError:
        logger.debug("Could not record TV %s as unreachable", ip, exc_info=True)


def _mark_tv_up(ip: str) -> None:
    try:
        _tv_down_marker(ip).unlink()
    except OSError:
        pass


# A Frame TV serves a single art channel. Opening a second one while another is still
# connecting makes the set announce `ms.channel.clientConnect`, which samsungtvws raises
# as a connection failure — so parallel requests to one TV do not queue, they break each
# other. gunicorn runs several workers, hence a file lock on top of the in-process one.
try:
    import fcntl  # POSIX only; the published image runs Linux
except ImportError:  # pragma: no cover - Windows development
    fcntl = None

TV_LOCK_DIR = _DATA_DIR.joinpath('instance', 'tv_locks')
_LOCAL_TV_LOCKS: Dict[str, threading.Lock] = {}
_LOCAL_TV_LOCKS_GUARD = threading.Lock()


def _local_tv_lock(ip: str) -> threading.Lock:
    with _LOCAL_TV_LOCKS_GUARD:
        lock = _LOCAL_TV_LOCKS.get(ip)
        if lock is None:
            lock = threading.Lock()
            _LOCAL_TV_LOCKS[ip] = lock
        return lock


@contextlib.contextmanager
def _tv_exclusive(ip: str, wait: float):
    """Hold a TV for one operation at a time, across threads and gunicorn workers."""
    give_up_at = time.monotonic() + wait
    busy = FrameTVUnavailableError(
        f"TV {ip} stayed busy with another request for more than {wait:.0f}s"
    )

    local = _local_tv_lock(ip)
    if not local.acquire(timeout=max(0.0, wait)):
        raise busy

    handle = None
    try:
        if fcntl is not None:
            TV_LOCK_DIR.mkdir(parents=True, exist_ok=True)
            handle = open(TV_LOCK_DIR.joinpath(f"tv-{_safe_ip(ip)}"), "w")
            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= give_up_at:
                        raise busy
                    time.sleep(0.1)
        yield
    finally:
        if handle is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()
        local.release()


# Notified as observer(ip, token) whenever a TV hands back a token that differs from
# the one it was given. Registered once by the app, which is what owns the database;
# this module stays unaware of where tokens are kept.
_token_observer: Optional[Callable[[str, str], None]] = None


def set_token_observer(observer: Optional[Callable[[str, str], None]]) -> None:
    global _token_observer
    _token_observer = observer


# --- Reaching a connection that is still being established ---
#
# samsungtvws only records a websocket on the channel object once the handshake has
# fully succeeded: `open()` builds it in a local, then loops on recv() waiting for the
# TV's connect frame, and only assigns `self.connection` afterwards. Its `close()` acts
# on `self.connection`, so a call abandoned while still inside `open()` closes nothing.
# The worker thread stays in that recv, holding the one art channel a Frame TV has, and
# the next request finds the set busy with a call nobody is waiting for any more.
#
# The socket exists by then — it is simply out of reach. So the create_connection the
# library calls is wrapped to note the websocket against the thread that made it, which
# gives close() something to act on. Only samsungtvws sees the wrapper.

_INFLIGHT_SOCKETS: Dict[int, Any] = {}
# Which TV each worker thread is talking to, so a connection left behind can be traced
# back to the set it is still holding.
_INFLIGHT_TV: Dict[int, str] = {}
_INFLIGHT_GUARD = threading.Lock()

# What each worker thread has heard from its TV: [frames, bytes]. Watching traffic at
# the socket is what separates a set that has gone quiet from one still streaming a
# long answer — a check between calls cannot tell the two apart.
_TRAFFIC: Dict[int, List[int]] = {}
_INFLIGHT_PROGRESS: Dict[int, Callable[[], None]] = {}


def _note_traffic(thread_id: int, data) -> None:
    with _INFLIGHT_GUARD:
        traffic = _TRAFFIC.get(thread_id)
        if traffic is not None:
            traffic[0] += 1
            traffic[1] += len(data) if data else 0
        hook = _INFLIGHT_PROGRESS.get(thread_id)
    if hook is not None:
        hook()


def _traffic_snapshot(thread_id: int) -> str:
    with _INFLIGHT_GUARD:
        traffic = _TRAFFIC.get(thread_id)
    if traffic is None:
        return "no traffic recorded"
    return f"{traffic[0]} frame(s), {traffic[1]} byte(s) received"


def _traffic_frames(thread_id: int) -> int:
    with _INFLIGHT_GUARD:
        traffic = _TRAFFIC.get(thread_id)
    return traffic[0] if traffic is not None else 0


class _ConnectionTracker:
    """The websocket module as samsungtvws sees it, noting each connection it opens."""

    def __init__(self, real_module):
        self._real = real_module

    def __getattr__(self, name):
        return getattr(self._real, name)

    def create_connection(self, *args, **kwargs):
        connection = self._real.create_connection(*args, **kwargs)
        thread_id = threading.get_ident()
        real_recv = connection.recv

        def recv(*recv_args, **recv_kwargs):
            data = real_recv(*recv_args, **recv_kwargs)
            _note_traffic(thread_id, data)
            return data

        # Instance attribute, not a subclass: callers and tests keep the very object
        # the real module handed back, only its reads are observed.
        connection.recv = recv
        with _INFLIGHT_GUARD:
            _INFLIGHT_SOCKETS[thread_id] = connection
        return connection


def _install_connection_tracker() -> None:
    from samsungtvws import connection as _samsung_connection

    if not isinstance(_samsung_connection.websocket, _ConnectionTracker):
        _samsung_connection.websocket = _ConnectionTracker(_samsung_connection.websocket)


def _forget_inflight(thread_id: int) -> None:
    with _INFLIGHT_GUARD:
        _INFLIGHT_SOCKETS.pop(thread_id, None)
        _INFLIGHT_TV.pop(thread_id, None)
        _INFLIGHT_PROGRESS.pop(thread_id, None)
        _TRAFFIC.pop(thread_id, None)


def _claim_inflight(thread_id: int, ip: str, on_progress: Optional[Callable[[], None]] = None) -> None:
    with _INFLIGHT_GUARD:
        _INFLIGHT_TV[thread_id] = ip
        _TRAFFIC[thread_id] = [0, 0]
        if on_progress is not None:
            _INFLIGHT_PROGRESS[thread_id] = on_progress


def reset_connections(ip: str) -> int:
    """Close every connection still recorded against a TV. Returns how many.

    Only safe to call while holding that TV's lock: nothing else may be talking to it,
    so anything still open belongs to a call that was abandoned and is doing nothing
    but occupying the one art channel the set has.
    """
    with _INFLIGHT_GUARD:
        stale = [tid for tid, owner in _INFLIGHT_TV.items() if owner == ip]
        connections = [(tid, _INFLIGHT_SOCKETS.pop(tid, None)) for tid in stale]

    closed = 0
    for thread_id, connection in connections:
        if connection is None:
            continue
        try:
            connection.close()
            closed += 1
        except Exception:
            logger.debug("Error closing a stale connection to TV %s", ip, exc_info=True)
    return closed


def _close_inflight(thread_id: int) -> bool:
    """Close whatever connection that thread last opened. True if there was one."""
    with _INFLIGHT_GUARD:
        connection = _INFLIGHT_SOCKETS.pop(thread_id, None)
    if connection is None:
        return False
    try:
        connection.close()
    except Exception:
        logger.debug("Error closing an in-flight connection", exc_info=True)
    return True


_install_connection_tracker()


class _TVSession:
    """A TV connection (remote channel + art channel) closable from another thread.

    samsungtvws opens a fresh art channel on every `tv.art()` call, so the object is
    kept here: one channel per operation instead of one per call, and a handle the
    caller can close to unblock a read that is stuck in the worker thread.
    """

    def __init__(self, ip: str, token: Optional[str], timeout: int):
        self.ip = ip
        self._tv = SamsungTVWS(
            host=ip, port=DEFAULT_PORT, token=token, name=CONNECTION_NAME, timeout=timeout
        )
        self._art = None
        self._worker_thread_id: Optional[int] = None
        self._last_progress = time.monotonic()
        self._context = ""

    def note_progress(self) -> None:
        """Called each time the library comes back from the TV, however it came back.

        A call that neither returns nor raises is the one thing nothing else can see.
        """
        self._last_progress = time.monotonic()

    def note_context(self, description: str) -> None:
        """What the worker is currently asking the TV for, for the stall log."""
        self._context = description

    def describe_traffic(self) -> str:
        """Frames and bytes heard on this worker's connection, if it claimed one."""
        if self._worker_thread_id is None:
            return "no traffic recorded"
        return _traffic_snapshot(self._worker_thread_id)

    def frames_received(self) -> int:
        """How many frames this worker's connection has delivered so far."""
        if self._worker_thread_id is None:
            return 0
        return _traffic_frames(self._worker_thread_id)

    def idle_for(self) -> float:
        return time.monotonic() - self._last_progress

    def claim_worker(self) -> None:
        """Called from the thread that will talk to the TV, so close() can reach it."""
        self._worker_thread_id = threading.get_ident()
        _claim_inflight(self._worker_thread_id, self.ip, on_progress=self.note_progress)

    def release_worker(self) -> None:
        if self._worker_thread_id is not None:
            _forget_inflight(self._worker_thread_id)

    @property
    def tv(self) -> SamsungTVWS:
        return self._tv

    def art(self):
        if self._art is None:
            self._art = self._tv.art()
        return self._art

    def current_token(self) -> Optional[str]:
        """The freshest token these channels hold.

        A Frame TV issues a new token on connect, and samsungtvws keeps it on whichever
        channel received it. `tv.art()` is handed a copy of the token as it stood then,
        so the art channel — opened last — carries the newest one.
        """
        for channel in (self._art, self._tv):
            token = getattr(channel, "token", None)
            if token:
                return str(token)
        return None

    def close(self) -> None:
        for channel in (self._art, self._tv):
            if channel is None:
                continue
            try:
                channel.close()
            except Exception:
                logger.debug("Error closing channel for TV %s", self.ip, exc_info=True)

        # Whatever the worker was still opening when it was abandoned. Closing it is
        # what makes its recv() raise, so the thread lets go of the TV's art channel
        # instead of sitting on it until the operating system gives up.
        if self._worker_thread_id is not None and _close_inflight(self._worker_thread_id):
            logger.info("Closed a half-open connection to TV %s", self.ip)


def _tv_call(
    ip: str,
    action_description: str,
    action: Callable[["_TVSession"], Any],
    *,
    token: Optional[str] = None,
    deadline: Optional[int] = None,
    open_remote: bool = True,
    skip_when_down: bool = True,
    stall_timeout: Optional[int] = None,
) -> Any:
    """Run `action(session)` against the TV, never blocking longer than `deadline`.

    Raises FrameTVTimeoutError when the deadline expires and FrameTVConnectionError
    when the TV is unreachable; errors coming from the TV itself (a rejected
    request, a bad content id) are re-raised untouched so callers can tell the two
    apart. A TV that fails is skipped for TV_DOWN_COOLDOWN seconds.

    `skip_when_down` is what the cooldown protects against: bursts of background
    reads, above all the one request per thumbnail a gallery page fires. Deliberate
    actions pass False — someone pressing play is waiting for that TV specifically,
    and would rather wait for a real answer than be told to come back later.
    """
    if deadline is None:
        deadline = TV_CALL_DEADLINE

    cooldown = _tv_cooldown_remaining(ip) if skip_when_down else 0
    if cooldown > 0:
        raise FrameTVUnavailableError(
            f"TV {ip} did not answer recently; skipping {action_description} it for another {cooldown:.0f}s"
        )

    # One operation at a time per TV: concurrent art channels corrupt each other. The
    # same split as the cooldown applies to the queue: a background read gives up as
    # soon as its own deadline is gone, a deliberate action waits for its turn.
    busy_wait = deadline if skip_when_down else max(deadline, TV_BUSY_WAIT)
    with _tv_exclusive(ip, wait=busy_wait):
        # Holding the lock means nothing else may be talking to this TV, so anything
        # still recorded against it is a call that was abandoned and never let go. It
        # would otherwise keep the set's one art channel busy while this request tried
        # to open a second — which the TV answers by refusing both.
        stale = reset_connections(ip)
        if stale:
            logger.info("Closed %d stale connection(s) to TV %s before starting", stale, ip)

        session = _TVSession(ip, token, DEFAULT_TIMEOUT)
        phases: Dict[str, float] = {}

        def run():
            session.claim_worker()
            started = time.monotonic()
            try:
                if open_remote:
                    session.tv.open()
                phases['open'] = time.monotonic() - started
                acting = time.monotonic()
                try:
                    return action(session)
                finally:
                    phases['action'] = time.monotonic() - acting
            finally:
                # Whether it finished or raised, nothing here is half-open any more.
                session.release_worker()

        def keep_any_new_token():
            """A token the TV issued is worth keeping even if the call then failed.

            It is handed over during the connect handshake, so a request that dies
            later still learned the one the set expects next time.
            """
            if _token_observer is None:
                return
            fresh = session.current_token()
            if fresh and fresh != token:
                try:
                    _token_observer(ip, fresh)
                except Exception:
                    logger.warning("Could not hand on the new token for TV %s", ip, exc_info=True)

        # A stall is a call that never comes back, so no check placed between calls can
        # see it. This watches from outside and closes the connection, which is what
        # makes the blocked read raise and hands the TV back. Progress is noted on
        # every frame the socket delivers, so a set still streaming a long answer is
        # left alone — only real silence trips this.
        finished = threading.Event()
        if stall_timeout:
            def watch_for_a_stall():
                while not finished.wait(1):
                    idle = session.idle_for()
                    if idle >= stall_timeout:
                        logger.warning(
                            "TV %s sent nothing for %.0fs while %s%s; closing the connection (%s)",
                            ip, idle, action_description,
                            f" ({session._context})" if session._context else "",
                            session.describe_traffic(),
                        )
                        session.close()
                        return

            threading.Thread(
                target=watch_for_a_stall, name="frametv-stall", daemon=True
            ).start()

        future = _TV_EXECUTOR.submit(run)
        try:
            try:
                result = future.result(timeout=deadline)
            finally:
                finished.set()
        except FutureTimeoutError as err:
            # cancel() succeeds only while the call is still queued; otherwise close the
            # sockets so the recv() blocking the worker thread raises and lets it go.
            if not future.cancel():
                session.close()
            keep_any_new_token()
            _mark_tv_down(ip)
            # Which step ran out of road. An absent phase never finished, which is the
            # useful half: "open: unfinished" says the set never let us in at all.
            logger.warning(
                "TV %s timed out %s — open: %s, action: %s",
                ip, action_description,
                f"{phases['open']:.1f}s" if 'open' in phases else 'unfinished',
                f"{phases['action']:.1f}s" if 'action' in phases else 'unfinished',
            )
            raise FrameTVTimeoutError(
                f"Timeout after {deadline}s while {action_description} TV {ip}"
            ) from err
        except Exception as err:
            session.close()
            keep_any_new_token()
            if _is_connection_error(err):
                _mark_tv_down(ip)
                _raise_tv_connection_error(ip, action_description, err)
            raise

        _mark_tv_up(ip)
        keep_any_new_token()
        session.close()
        return result


def _fetch_matte_list(art) -> Optional[Dict]:
    try:
        return art.get_matte_list()
    except Exception:  # pylint: disable=broad-except
        logger.exception("Error getting matte list")
        return None


def _matte_kwargs(art, matte: Optional[str]) -> Dict[str, str]:
    if matte is None:
        return {}
    available_mattes = _fetch_matte_list(art)
    if available_mattes and 'matte_types' in available_mattes:
        matte_types = available_mattes['matte_types']
        # Extract matte_type values from the list of dicts
        available_matte_names = [m.get('matte_type') for m in matte_types if isinstance(m, dict)]
        if matte not in available_matte_names:
            logger.warning("Requested matte '%s' not in available mattes: %s", matte, available_matte_names)
    return {'matte': matte, 'portrait_matte': matte}


def upload_artwork(
    ip: str,
    art_path: str,
    brightness: Optional[int] = None,
    display: bool = True,
    delete_others: bool = False,
    token: Optional[str] = None,
    matte: Optional[str] = "none",
    **kwargs
) -> Optional[str]:
    """
    Upload an artwork image to the Frame TV, optionally set brightness, and display it.
    Args:
        ip (str): IP address of the TV.
        art_path (str): Path to the artwork image file.
        brightness (Optional[int]): Brightness level to set after upload.
        display (bool): Whether to display the uploaded image immediately.
        delete_others (bool): Whether to delete every other artwork on the TV.
        token (Optional[str]): Token string to use for authentication.
        matte (Optional[str]): Matte/frame style to use (e.g., 'shadowbox_polar', 'shadowbox_modern', 'none' (no matte)).
    Returns:
        Optional[str]: Content ID of the uploaded image, or None if failed.
    """
    with open(art_path, "rb") as f:
        payload = f.read()

    def action(session: _TVSession) -> Optional[str]:
        art = session.art()
        content_id = art.upload(payload, **_matte_kwargs(art, matte))
        if brightness is not None:
            art.set_brightness(brightness)
        if display and content_id:
            art.select_image(content_id, show=True)
        if delete_others:
            _delete_other_images(art, content_id, debug=True)
        return content_id

    content_id = _tv_call(ip, "uploading artwork to", action, token=token, deadline=TV_UPLOAD_DEADLINE, skip_when_down=False)
    forget_gallery(ip)
    return content_id

def _delete_other_images(art, keep_content_id: str, *, debug: bool) -> None:
    available = []
    try:
        # art.available() returns a content list
        available = art.available() or []
    except Exception as err:  # pylint: disable=broad-except
        logger.exception("Could not enumerate TV gallery")
        return

    deletions = [item.get("content_id") for item in available if item.get("content_id") and item.get("content_id") != keep_content_id]

    kept = [item.get("content_id") for item in available if item.get("content_id") == keep_content_id]
    if len(kept) > 1:
        logger.warning("Found %d copies of active image %s; keeping all to avoid accidental deletion.", len(kept), keep_content_id)

    if not deletions:
        logger.debug("No other images to delete")
        return
    logger.info("Deleting %d old images: %s", len(deletions), deletions)
    art.delete_list(deletions)
    if debug:
        logger.debug("Deleted %d old images", len(deletions))

def delete_all_images_from_tv(ip: str, token: Optional[str] = None) -> None:
    """
    Delete all uploaded images from the Frame TV.
    Args:
        ip (str): IP address of the TV.
        token (Optional[str]): Token string to use for authentication.
    """
    def action(session: _TVSession) -> None:
        art = session.art()
        available = art.available() or []
        content_ids = [item.get("content_id") for item in available if item.get("content_id")]
        if content_ids:
            art.delete_list(content_ids)
            logger.info("Deleted %d images from TV %s", len(content_ids), ip)
        else:
            logger.info("No images found on TV %s to delete", ip)

    _tv_call(ip, "deleting images from", action, token=token, skip_when_down=False)
    forget_gallery(ip)

def play_uploaded_content(ip: str, content_id: str, token: Optional[str] = None) -> None:
    """
    Play an already uploaded image on the Frame TV using its content_id.
    Args:
        ip (str): IP address of the TV.
        content_id (str): Content ID of the uploaded image.
        token (Optional[str]): Token string to use for authentication.
    """
    _tv_call(
        ip,
        f"playing image {content_id} on",
        lambda session: session.art().select_image(content_id, show=True),
        token=token,
        skip_when_down=False,
    )

def set_brightness(ip: str, brightness: int, token: Optional[str] = None) -> None:
    """
    Set the brightness of the Frame TV in art mode.
    Args:
        ip (str): IP address of the TV.
        brightness (int): Brightness level to set.
        token (Optional[str]): Token string to use for authentication.
    """
    _tv_call(
        ip,
        "setting brightness on",
        lambda session: session.art().set_brightness(brightness),
        token=token,
        skip_when_down=False,
    )

def is_art_mode_on(ip: str, token: Optional[str] = None) -> bool:
    """
    Check if the Frame TV is currently in art mode.
    Args:
        ip (str): IP address of the TV.
        token (Optional[str]): Token string to use for authentication.
    Returns:
        bool: True if art mode is enabled, False otherwise.
    """
    status = _tv_call(
        ip,
        "reading art mode from",
        lambda session: session.art().get_artmode(),
        token=token,
    )
    return status == "on"

def is_tv_reachable(ip: str, token: Optional[str] = None) -> bool:
    """
    Check if the Frame TV is reachable on the network.
    Args:
        ip (str): IP address of the TV.
        token (Optional[str]): Token string to use for authentication.
    Returns:
        bool: True if the TV is reachable, False otherwise.
    """
    try:
        _tv_call(ip, "reaching", lambda session: True, token=token)
        return True
    except Exception:
        return False

def _magic_packet(mac: str) -> bytes:
    """Six 0xFF bytes followed by the MAC repeated sixteen times."""
    cleaned = "".join(ch for ch in mac if ch.isalnum())
    if len(cleaned) != 12:
        raise ValueError(f"Invalid MAC address: {mac!r}")
    try:
        address = bytes.fromhex(cleaned)
    except ValueError as err:
        raise ValueError(f"Invalid MAC address: {mac!r}") from err
    return b"\xff" * 6 + address * 16


def power_on(ip: str, mac: Optional[str], token: Optional[str] = None) -> None:
    """
    Power on the Frame TV using Wake-on-LAN.

    The TV has no network stack to talk to while it is off, so this is a broadcast
    magic packet rather than a request: it cannot be acknowledged, and a TV that
    ignores it stays off. Wake-on-LAN also has to be enabled on the set itself.

    Args:
        ip (str): IP address of the TV, used to aim the directed broadcast.
        mac (Optional[str]): MAC address of the TV. Required.
        token (Optional[str]): Unused, kept for interface consistency.
    """
    if not mac:
        raise FrameTVError(
            f"No MAC address stored for TV {ip}; Wake-on-LAN needs one to reach a TV that is off"
        )

    packet = _magic_packet(mac)

    # The global broadcast is what usually works; the subnet-directed one helps when a
    # router forwards it and the host has several interfaces.
    targets = ["255.255.255.255"]
    octets = ip.split(".")
    if len(octets) == 4 and all(o.isdigit() for o in octets):
        targets.append(".".join(octets[:3] + ["255"]))

    sent = False
    for target in targets:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(DEFAULT_TIMEOUT)
                for port in (7, 9):
                    sock.sendto(packet, (target, port))
            sent = True
        except OSError:
            logger.debug("Wake-on-LAN broadcast to %s failed", target, exc_info=True)

    if not sent:
        raise FrameTVConnectionError(f"Could not send the Wake-on-LAN packet for TV {ip}")
    logger.info("Sent Wake-on-LAN packet for TV %s (%s)", ip, mac)

def power_off(ip: str, token: Optional[str] = None) -> None:
    """
    Power off the Frame TV.
    Args:
        ip (str): IP address of the TV.
        token (Optional[str]): Token string to use for authentication.
    """
    _tv_call(ip, "powering off", lambda session: session.tv.send_key("KEY_POWER"), token=token, skip_when_down=False)

def enable_art_mode(ip: str, token: Optional[str] = None) -> None:
    """
    Enable art mode on the Frame TV.
    Args:
        ip (str): IP address of the TV.
        token (Optional[str]): Token string to use for authentication.
    """
    _tv_call(
        ip,
        "enabling art mode on",
        lambda session: session.art().set_artmode(True),
        token=token,
        skip_when_down=False,
    )

def remove_token(ip: str) -> None:
    """
    Delete the authentication token file for the specified TV IP.
    Args:
        ip (str): IP address of the TV.
    """
    pass

def get_available_mattes(ip: str, token: Optional[str] = None) -> Optional[Dict]:
    """
    Get the list of available matte styles and colors on the Frame TV.
    Args:
        ip (str): IP address of the TV.
        token (Optional[str]): Token string to use for authentication.
    Returns:
        Optional[Dict]: Dictionary with 'matte_types' and 'matte_colors' keys, or None if failed.
    """
    try:
        return _tv_call(
            ip,
            "getting matte list from",
            lambda session: _fetch_matte_list(session.art()),
            token=token,
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception("Error getting matte list from TV %s", ip)
        return None

def change_matte(ip: str, matte: str, token: Optional[str] = None) -> None:
    """
    Change the matte style on the Frame TV.
    Args:
        ip (str): IP address of the TV.
        matte (str): Matte style to set.
        token (Optional[str]): Token string to use for authentication.
    """
    try:
        _tv_call(
            ip,
            "changing matte on",
            lambda session: session.art().change_matte(matte),
            token=token,
            skip_when_down=False,
        )
    except Exception:  # pylint: disable=broad-except
        logger.exception("Error changing matte on TV %s", ip)

def _content_date(item: Dict) -> str:
    """The date a TV content entry carries, as ISO 8601.

    Firmware reports it as `image_date` in EXIF form ("2026:08:10 14:24:23"), which no
    date parser in a browser accepts. The older key names are kept as a fallback in
    case another firmware uses them.
    """
    raw = item.get("image_date") or item.get("date_added") or item.get("created_at")
    if not raw or not isinstance(raw, str):
        return ""
    try:
        return datetime.strptime(raw.strip(), "%Y:%m:%d %H:%M:%S").isoformat()
    except ValueError:
        # Already ISO, or a shape we do not know: hand it over untouched.
        return raw


def _cached_thumbnail(ip: str, content_id: str) -> Optional[bytes]:
    cached = _cache_get((ip, content_id))
    if cached is not None:
        return cached
    disk = _thumb_disk_get(ip, content_id)
    if disk is not None:
        _cache_set((ip, content_id), disk)
    return disk


# Content the TV has no preview for at all — some of the art it ships with. Asking
# again on every page load costs a round trip each time and always gets the same
# nothing, so the answer is remembered; the window is short enough that a firmware
# that starts answering is picked up on its own.
_NO_THUMBNAIL_TTL = _env_int("FRAME_TV_NO_THUMBNAIL_TTL", 3600)
_NO_THUMBNAIL: Dict[tuple, float] = {}


def _remember_no_thumbnail(ip: str, content_id: str) -> None:
    _NO_THUMBNAIL[(ip, content_id)] = time.time()


def _known_to_have_no_thumbnail(ip: str, content_id: str) -> bool:
    seen_at = _NO_THUMBNAIL.get((ip, content_id))
    if seen_at is None:
        return False
    if time.time() - seen_at > _NO_THUMBNAIL_TTL:
        del _NO_THUMBNAIL[(ip, content_id)]
        return False
    return True


def _content_id_of(name: str, wanted: List[str]) -> Optional[str]:
    """The content id a batch thumbnail belongs to.

    samsungtvws keys the batch answer by `fileID.fileType` — "MY_F0440.jpg", not
    "MY_F0440" — because that is how the TV labels each file on the D2D socket. Keeping
    the key verbatim meant every thumbnail was filed under a name nothing ever looked
    up, so a gallery stayed blank while the bytes were arriving perfectly well.
    """
    if name in wanted:
        return name
    stem = name.rsplit('.', 1)[0]
    return stem if stem in wanted else None


def _single_thumbnail(art, ip: str, content_id: str) -> Tuple[Optional[bytes], bool]:
    """One thumbnail through the single-image endpoint.

    Returns (payload, still_talking). `still_talking` is False only when the call died
    at the connection level: the difference between "this image has no preview" and
    "the TV has stopped answering" is what tells the caller whether to keep walking the
    gallery or to stop. Getting that wrong costs a socket timeout per remaining image.
    """
    try:
        thumbnail = art.get_thumbnail(content_id)
    except Exception as err:
        if _is_connection_error(err):
            return None, False
        logger.debug("TV %s declined %s: %s", ip, content_id, err)
        return None, True
    if isinstance(thumbnail, (bytes, bytearray)) and thumbnail:
        return bytes(thumbnail), True
    return None, True


def _collect_thumbnails(
    art, ip: str, content_ids: List[str], fetch_missing: bool = True,
    on_progress: Optional[Callable[[], None]] = None,
    on_batch: Optional[Callable[[List[str]], None]] = None,
    frames_received: Optional[Callable[[], int]] = None,
) -> Dict[str, bytes]:
    """Thumbnails for `content_ids`: cache first, then whatever is left, in batches.

    Serving the cache keeps a TV that has gone quiet from blanking a gallery it has
    already answered for once.

    The TV streams every thumbnail of a request down one D2D socket before the call
    returns, so asking for a whole gallery at once is a single transfer that either
    finishes or is lost entirely — a set with forty 4K images never finished. Asking
    in batches means each one is saved as it lands, so a gallery fills in over a few
    visits instead of staying blank forever.

    One unservable image takes its whole batch down with it: the TV closes the socket
    rather than skipping the entry. So a refused batch is asked for again one at a
    time, which isolates the offender and saves the rest of it.
    """
    found: Dict[str, bytes] = {}
    missing: List[str] = []
    for cid in content_ids:
        cached = _cached_thumbnail(ip, cid)
        if cached is not None:
            found[cid] = cached
        elif _known_to_have_no_thumbnail(ip, cid):
            # Remembered as previewless: asking again is a round trip for the same
            # nothing — and for a poisoned entry, another stall.
            continue
        else:
            missing.append(cid)

    if not missing or not fetch_missing:
        return found

    def keep(cid: str, data) -> bool:
        if not isinstance(data, (bytes, bytearray)) or not data:
            return False
        payload = bytes(data)
        found[cid] = payload
        _thumb_disk_set(ip, cid, payload)
        _cache_set((ip, cid), payload)
        return True

    # A refusal only says something about the image if the TV goes on to answer for
    # another one. A set that stops mid-gallery would otherwise have every image left
    # in the list written off as previewless, and a page of placeholders is worse than
    # a slow one. So refusals are noted and judged at the end.
    refusals: List[tuple] = []
    answered = 0
    dead_in_a_row = 0
    started = time.monotonic()

    def nothing_is_coming() -> bool:
        """True once the walk has run a while with nothing at all to show for it."""
        return answered == 0 and time.monotonic() - started > TV_THUMBNAIL_FIRST_ANSWER

    for start in range(0, len(missing), TV_THUMBNAIL_BATCH):
        if nothing_is_coming():
            logger.warning(
                "TV %s gave nothing in %ds; leaving its thumbnails for next time",
                ip, TV_THUMBNAIL_FIRST_ANSWER,
            )
            return found

        batch = missing[start:start + TV_THUMBNAIL_BATCH]
        if on_batch:
            # Which images the blocked call was asking for, if it never comes back.
            on_batch(batch)
        try:
            frames_before = frames_received() if frames_received else None
            call_started = time.monotonic()
            thumb_map = art.get_thumbnail_list(batch) or {}
            if on_progress:
                on_progress()
        except Exception as err:
            if on_progress:
                on_progress()
            stalled = (
                frames_received is not None
                and frames_before is not None
                and frames_received() > frames_before
                and time.monotonic() - call_started >= TV_STALL_TIMEOUT - 2
            )
            if stalled:
                # The set answered during this very call, then stopped and held the
                # socket open until the watchdog cut it: it was alive, so the batch
                # itself is the problem — an entry whose transfer starts and never
                # finishes. A refusal arrives fast, a dead TV says nothing at all;
                # only a long call that still delivered frames is a stall.
                # Remembering these as previewless is what stops every page load
                # paying another stall for the same image.
                for cid in batch:
                    logger.warning(
                        "TV %s stalled serving %s mid-transfer; treating it as previewless",
                        ip, cid,
                    )
                    _remember_no_thumbnail(ip, cid)
            else:
                logger.info(
                    "TV %s refused a batch of %d thumbnails (%s); asking one at a time",
                    ip, len(batch), err,
                )
            thumb_map = {}

        if isinstance(thumb_map, dict):
            for name, data in thumb_map.items():
                cid = _content_id_of(name, batch)
                if cid is None:
                    logger.debug("TV %s answered with an unexpected thumbnail %r", ip, name)
                    continue
                if keep(cid, data):
                    answered += 1

        for cid in batch:
            if cid in found or _known_to_have_no_thumbnail(ip, cid):
                continue
            if nothing_is_coming():
                logger.warning(
                    "TV %s gave nothing in %ds; leaving its thumbnails for next time",
                    ip, TV_THUMBNAIL_FIRST_ANSWER,
                )
                return found
            if on_batch:
                on_batch([cid])
            payload, still_talking = _single_thumbnail(art, ip, cid)
            if on_progress:
                on_progress()
            if payload is None:
                refusals.append((cid, answered))
                # A set that will not serve an image closes the socket on it, exactly
                # as a set that has gone away does, so the two cannot be told apart
                # from one call. What separates them is how many in a row: a handful
                # of unservable images is normal, a wall of them is a TV that stopped
                # talking. Walking the rest at a socket timeout apiece is what had a
                # page load holding the TV for two minutes.
                dead_in_a_row += 1 if not still_talking else 0
                if dead_in_a_row >= TV_THUMBNAIL_GIVE_UP:
                    logger.warning(
                        "TV %s went quiet after %d thumbnails; leaving the rest for next time",
                        ip, answered,
                    )
                    return found
                continue
            dead_in_a_row = 0
            if keep(cid, payload):
                answered += 1

        if answered == 0:
            # A whole batch, then every one of its images on its own, and not a single
            # answer: the set is away rather than out of previews. Walking the rest of
            # the gallery one dead call at a time would only make the page slower.
            logger.warning("TV %s is not answering for thumbnails; giving up", ip)
            return found

    for cid, answered_before in refusals:
        if answered > answered_before:
            # The TV kept working after refusing this one, so it is the image that has
            # no preview, not the connection. Asking again every visit would cost a
            # round trip to be told the same nothing.
            logger.info("TV %s has no preview for %s", ip, cid)
            _remember_no_thumbnail(ip, cid)
    return found


def get_tv_gallery_thumbnails(
    ip: str, content_ids: List[str], token: Optional[str] = None
) -> Dict[str, bytes]:
    """Fetch several thumbnails in a single round trip to the TV.

    One request beats one per image: the TV only serves a single art channel, so the
    parallel requests a gallery page used to fire were rejecting each other.
    """
    cached = {}
    missing = []
    for cid in content_ids:
        hit = _cached_thumbnail(ip, cid)
        if hit is not None:
            cached[cid] = hit
        else:
            missing.append(cid)

    if not missing:
        return cached

    try:
        fetched = _tv_call(
            ip,
            "fetching thumbnails from",
            lambda session: _collect_thumbnails(
                session.art(), ip, missing, on_progress=session.note_progress,
                on_batch=lambda batch: session.note_context(f"batch {batch}"),
                frames_received=session.frames_received,
            ),
            token=token,
            deadline=TV_THUMBNAIL_DEADLINE,
            stall_timeout=TV_STALL_TIMEOUT,
        )
    except FrameTVError as err:
        # Hand back whatever was cached rather than blanking a whole page because one
        # image was missing from it. One line: the cooldown is already recorded.
        logger.warning("Serving %d cached thumbnails for TV %s: %s", len(cached), ip, err)
        return cached

    cached.update(fetched or {})
    return cached


def get_tv_gallery_images(ip: str, token: Optional[str] = None) -> List[Dict]:
    """
    Fetch the list of images currently on the Frame TV.
    Args:
        ip (str): IP address of the TV.
        token (Optional[str]): Token string to use for authentication.
    Returns:
        List[Dict]: List of image dictionaries with metadata (content_id, filename, date_added).
    """
    # Briefly cached, and dropped the moment anything here changes the TV's contents.
    # Without it, reloading the page while a walk of thumbnails still holds the TV
    # queued behind it and then failed, reporting a set that was answering perfectly
    # well. The listing is what the page needs first, so it must not wait on the
    # slowest thing running.
    listing = _cached_gallery(ip)
    if listing is not None:
        return listing

    def action(session: _TVSession) -> List[Dict]:
        art = session.art()
        available = art.available() or []

        images = []
        seen_content_ids = []
        for item in available:
            content_id = item.get("content_id")
            if content_id and content_id not in seen_content_ids:
                images.append({
                    "content_id": content_id,
                    "filename": item.get("file_name") or item.get("filename") or "",
                    "date_added": _content_date(item),
                    "width": item.get("width"),
                    "height": item.get("height"),
                    "matte": item.get("matte_id"),
                    "thumbnail": None,
                })
                seen_content_ids.append(content_id)

        # Cached thumbnails only: the listing has to come back quickly, and the page
        # asks for whatever is still missing in its own request afterwards.
        by_content_id = {img["content_id"]: img for img in images}
        thumbnails = _collect_thumbnails(art, ip, list(by_content_id), fetch_missing=False)
        for cid, data in thumbnails.items():
            img = by_content_id.get(cid)
            if img is not None:
                img["thumbnail"] = base64.b64encode(data).decode("ascii")

        return images

    images = _tv_call(
        ip, "fetching gallery images from", action, token=token,
        stall_timeout=TV_STALL_TIMEOUT,
    )
    _remember_gallery(ip, images)
    return images

def delete_tv_image(ip: str, content_id: str, token: Optional[str] = None) -> bool:
    """
    Delete a specific image from the Frame TV by content_id.
    Args:
        ip (str): IP address of the TV.
        content_id (str): Content ID of the image to delete.
        token (Optional[str]): Token string to use for authentication.
    Returns:
        bool: True if deletion was successful.
    """
    _tv_call(
        ip,
        f"deleting image {content_id} from",
        lambda session: session.art().delete(content_id),
        token=token,
        skip_when_down=False,
    )
    forget_gallery(ip)
    return True

def delete_tv_images(ip: str, content_ids: List[str], token: Optional[str] = None) -> int:
    """Delete several images from the TV in a single round trip.

    The TV takes a list, so this is one connection rather than one per image — which
    matters given it only serves a single art channel.

    Returns:
        int: how many content ids were sent for deletion.
    """
    wanted = [cid for cid in content_ids if cid]
    if not wanted:
        return 0

    _tv_call(
        ip,
        f"deleting {len(wanted)} images from",
        lambda session: session.art().delete_list(wanted),
        token=token,
        skip_when_down=False,
    )
    for content_id in wanted:
        _CACHE.pop((ip, content_id), None)
    forget_gallery(ip)
    return len(wanted)


def get_tv_device_info(ip: str, token: Optional[str] = None) -> Dict:
    """Whatever the TV reports about itself, plus one raw content entry.

    There is no storage endpoint in the art API. `tv_flash_size` gives the total
    capacity but nothing reports what is used, so the content list is sampled here:
    if entries carry a per-image size, occupancy can be summed from them.
    """
    def action(session: _TVSession) -> Dict:
        art = session.art()
        info = art.get_device_info() or {}
        sample = None
        try:
            available = art.available() or []
            if available:
                sample = available[0]
        except Exception:
            logger.debug("Could not sample the content list of TV %s", ip, exc_info=True)
        return {'device_info': info, 'sample_content': sample}

    return _tv_call(ip, "reading device info from", action, token=token)


def get_tv_gallery_thumbnail(ip: str, content_id: str, token: Optional[str] = None) -> Optional[bytes]:
    """
    Fetch the thumbnail bytes for a TV gallery image.
    Args:
        ip (str): IP address of the TV.
        content_id (str): Content ID of the image.
        token (Optional[str]): Token string to use for authentication.
    Returns:
        Optional[bytes]: Thumbnail image bytes, or None if unavailable.
    """
    cached = _cached_thumbnail(ip, content_id)
    if cached is not None:
        return cached

    def action(session: _TVSession) -> Optional[bytes]:
        # The batch endpoint is the reliable path on recent firmware and already falls
        # back to the single call for content it skips.
        return _collect_thumbnails(session.art(), ip, [content_id],
                                   on_batch=lambda batch: session.note_context(f"batch {batch}"),
                                   frames_received=session.frames_received,
                                   ).get(content_id)

    thumbnail_bytes = _tv_call(ip, f"fetching thumbnail {content_id} from", action, token=token)
    if thumbnail_bytes is not None:
        _thumb_disk_set(ip, content_id, thumbnail_bytes)
        _cache_set((ip, content_id), thumbnail_bytes)
    return thumbnail_bytes
