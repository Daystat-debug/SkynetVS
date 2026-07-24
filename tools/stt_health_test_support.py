from __future__ import annotations

from modules.stt_vosk import STTLifecycleSnapshot


class FakeSTTService:
    def __init__(
        self,
        snapshot: STTLifecycleSnapshot | None,
        *,
        error: Exception | None = None,
        samplerate: int = 16000,
        blocksize: int = 1024,
        device: int | None = 1,
        active_model_path: str = "models/model_large",
    ):
        self._snapshot = snapshot
        self._error = error
        self.samplerate = int(samplerate)
        self.blocksize = int(blocksize)
        self.device = device
        self.active_model_path = str(
            active_model_path
        )

    def get_lifecycle_telemetry(
        self,
    ) -> STTLifecycleSnapshot:
        if self._error is not None:
            raise self._error

        if self._snapshot is None:
            raise RuntimeError(
                "missing fake STT lifecycle"
            )

        return self._snapshot


def build_stt_lifecycle_snapshot(
    *,
    stream_started: bool = False,
    stream_active: bool = False,
    stream_generation: int = 0,
    stream_phase: str = "not_started",
    paused: bool = False,
    last_stream_started_at: float | None = None,
    last_stream_stopped_at: float | None = None,
    last_audio_block_at: float | None = None,
    audio_block_count: int = 0,
    audio_bytes_total: int = 0,
    last_processed_audio_block_at: float | None = None,
    processed_audio_block_count: int = 0,
    queue_size: int = 0,
    last_phrase_at: float | None = None,
    phrase_count: int = 0,
    last_callback_status_at: float | None = None,
    last_callback_status: str = "",
    callback_status_count: int = 0,
    last_error_at: float | None = None,
    last_error: str = "",
    failure_count: int = 0,
    consecutive_failures: int = 0,
) -> STTLifecycleSnapshot:
    return STTLifecycleSnapshot(
        stream_started=stream_started,
        stream_active=stream_active,
        stream_generation=stream_generation,
        stream_phase=stream_phase,
        paused=paused,
        last_stream_started_at=last_stream_started_at,
        last_stream_stopped_at=last_stream_stopped_at,
        last_audio_block_at=last_audio_block_at,
        audio_block_count=audio_block_count,
        audio_bytes_total=audio_bytes_total,
        last_processed_audio_block_at=(
            last_processed_audio_block_at
        ),
        processed_audio_block_count=(
            processed_audio_block_count
        ),
        queue_size=queue_size,
        last_phrase_at=last_phrase_at,
        phrase_count=phrase_count,
        last_callback_status_at=(
            last_callback_status_at
        ),
        last_callback_status=last_callback_status,
        callback_status_count=callback_status_count,
        last_error_at=last_error_at,
        last_error=last_error,
        failure_count=failure_count,
        consecutive_failures=consecutive_failures,
    )


def healthy_stt_service(
    now_value: float = 1000.0,
) -> FakeSTTService:
    now_value = float(now_value)

    return FakeSTTService(
        build_stt_lifecycle_snapshot(
            stream_started=True,
            stream_active=True,
            stream_generation=1,
            stream_phase="active",
            last_stream_started_at=now_value - 60.0,
            last_audio_block_at=now_value - 0.05,
            audio_block_count=100,
            audio_bytes_total=204800,
            last_processed_audio_block_at=(
                now_value - 0.02
            ),
            processed_audio_block_count=90,
            queue_size=0,
            last_phrase_at=now_value - 5.0,
            phrase_count=2,
        )
    )