from __future__ import annotations

import math
import threading
import time

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AudioState:
    volume: int
    muted: bool


@dataclass(frozen=True)
class AudioControlProbe:
    device_id: str
    device_name: str
    volume: int
    muted: bool


@dataclass(frozen=True)
class AudioEndpointBinding:
    device: Any
    endpoint: Any
    device_id: str
    device_name: str


class AudioControlError(RuntimeError):
    def __init__(
        self,
        operation: str,
        detail: str,
        *,
        retry_attempted: bool = False,
    ):
        self.operation = str(operation or "audio_control").strip()
        self.detail = str(detail or "Unknown audio control failure").strip()
        self.retry_attempted = bool(retry_attempted)

        suffix = " after endpoint refresh" if self.retry_attempted else ""
        super().__init__(f"Audio control {self.operation} failed{suffix}: {self.detail}")


class AudioControlUnavailableError(AudioControlError):
    pass


class AudioControlOperationError(AudioControlError):
    pass


class AudioControlVerificationError(AudioControlError):
    pass


EndpointProvider = Callable[[], AudioEndpointBinding]


class AudioControl:
    """
    Управление громкостью текущего default playback endpoint Windows.

    Каждая операция получает актуальное системное устройство. Это позволяет
    корректно работать после переключения между колонками и наушниками.
    """

    def __init__(
        self,
        *,
        endpoint_provider: EndpointProvider | None = None,
        verification_tolerance: int = 1,
        retry_delay_sec: float = 0.05,
        validate_on_init: bool = True,
    ):
        tolerance = int(verification_tolerance)
        retry_delay = float(retry_delay_sec)

        if tolerance < 0 or tolerance > 5:
            raise ValueError("Audio volume verification tolerance must be between 0 and 5")

        if not math.isfinite(retry_delay) or retry_delay < 0.0 or retry_delay > 1.0:
            raise ValueError("Audio endpoint retry delay must be between 0 and 1 second")

        self._endpoint_provider = endpoint_provider or self._default_endpoint_provider
        self._verification_tolerance = tolerance
        self._retry_delay_sec = retry_delay
        self._lock = threading.RLock()

        if validate_on_init:
            with self._lock:
                self._run_idempotent("initialize", self._read_state)

    def _default_endpoint_provider(self) -> AudioEndpointBinding:
        try:
            from pycaw.pycaw import AudioUtilities

            device = AudioUtilities.GetSpeakers()

            if device is None:
                raise AudioControlUnavailableError(
                    "bind",
                    "Current default audio endpoint is unavailable",
                )

            endpoint = getattr(device, "EndpointVolume", None)

            if endpoint is None:
                raise AudioControlUnavailableError(
                    "bind",
                    "Current audio device does not expose EndpointVolume",
                )

            device_id = str(
                getattr(device, "id", "")
                or getattr(device, "Id", "")
                or ""
            )
            device_name = str(
                getattr(device, "FriendlyName", "")
                or ""
            )

            return AudioEndpointBinding(
                device=device,
                endpoint=endpoint,
                device_id=device_id,
                device_name=device_name,
            )
        except AudioControlError:
            raise
        except Exception as e:
            raise AudioControlUnavailableError(
                "bind",
                str(e).strip() or type(e).__name__,
            ) from e

    def _resolve_binding(self) -> AudioEndpointBinding:
        binding = self._endpoint_provider()

        if not isinstance(binding, AudioEndpointBinding):
            raise AudioControlUnavailableError(
                "bind",
                "Endpoint provider returned an invalid binding",
            )

        if binding.device is None:
            raise AudioControlUnavailableError(
                "bind",
                "Current default audio device is unavailable",
            )

        if binding.endpoint is None:
            raise AudioControlUnavailableError(
                "bind",
                "Current default audio endpoint is unavailable",
            )

        return binding

    def _clone_error(
        self,
        error: BaseException,
        operation: str,
        *,
        retry_attempted: bool,
    ) -> AudioControlError:
        if isinstance(error, AudioControlError):
            error_type = type(error)
            detail = error.detail
        else:
            error_type = AudioControlOperationError
            detail = str(error).strip() or type(error).__name__

        return error_type(
            operation,
            detail,
            retry_attempted=retry_attempted,
        )

    def _sleep_before_retry(self) -> None:
        if self._retry_delay_sec > 0.0:
            time.sleep(self._retry_delay_sec)

    def _run_idempotent(
        self,
        operation: str,
        action: Callable[[AudioEndpointBinding], Any],
    ) -> Any:
        last_error: BaseException | None = None

        for attempt in range(2):
            try:
                return action(self._resolve_binding())
            except Exception as e:
                last_error = e

                if attempt == 0:
                    self._sleep_before_retry()

        if last_error is None:
            last_error = RuntimeError("Unknown audio control failure")

        raise self._clone_error(
            last_error,
            operation,
            retry_attempted=True,
        ) from last_error

    def _read_mute(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value

        try:
            number = int(value)
        except (TypeError, ValueError) as e:
            raise AudioControlOperationError(
                "read",
                "Mute state is invalid",
            ) from e

        if number not in (0, 1):
            raise AudioControlOperationError(
                "read",
                "Mute state is invalid",
            )

        return bool(number)

    def _read_state(self, binding: AudioEndpointBinding) -> AudioState:
        try:
            volume_scalar = float(binding.endpoint.GetMasterVolumeLevelScalar())
            muted = self._read_mute(binding.endpoint.GetMute())
        except AudioControlError:
            raise
        except Exception as e:
            raise AudioControlOperationError(
                "read",
                str(e).strip() or type(e).__name__,
            ) from e

        if not math.isfinite(volume_scalar):
            raise AudioControlOperationError(
                "read",
                "Volume scalar is not finite",
            )

        if volume_scalar < -0.001 or volume_scalar > 1.001:
            raise AudioControlOperationError(
                "read",
                "Volume scalar is outside the valid range",
            )

        volume_scalar = max(0.0, min(1.0, volume_scalar))

        return AudioState(
            volume=int(round(volume_scalar * 100.0)),
            muted=muted,
        )

    def _check_result(self, result: Any, operation: str) -> None:
        if result not in (None, 0):
            raise AudioControlOperationError(
                operation,
                f"CoreAudio returned {result}",
            )

    def _set_volume_on_binding(
        self,
        binding: AudioEndpointBinding,
        target: int,
        *,
        operation: str,
    ) -> AudioState:
        try:
            result = binding.endpoint.SetMasterVolumeLevelScalar(target / 100.0, None)
        except Exception as e:
            raise AudioControlOperationError(
                operation,
                str(e).strip() or type(e).__name__,
            ) from e

        self._check_result(result, operation)
        state = self._read_state(binding)

        if abs(state.volume - target) > self._verification_tolerance:
            raise AudioControlVerificationError(
                operation,
                f"Expected volume {target}, got {state.volume}",
            )

        return state

    def _set_mute_on_binding(
        self,
        binding: AudioEndpointBinding,
        target: bool,
    ) -> AudioState:
        operation = "mute" if target else "unmute"

        try:
            result = binding.endpoint.SetMute(1 if target else 0, None)
        except Exception as e:
            raise AudioControlOperationError(
                operation,
                str(e).strip() or type(e).__name__,
            ) from e

        self._check_result(result, operation)
        state = self._read_state(binding)

        if state.muted != target:
            raise AudioControlVerificationError(
                operation,
                f"Expected muted={target}, got muted={state.muted}",
            )

        return state

    def _clamp_percent(self, value: int) -> int:
        return max(0, min(100, int(value)))

    def _binding_identity(self, binding: AudioEndpointBinding) -> tuple[str, str]:
        device_id = str(binding.device_id or "").strip().lower()

        if device_id:
            return "id", device_id

        device_name = " ".join(str(binding.device_name or "").lower().split())

        if device_name:
            return "name", device_name

        return "unknown", ""

    def probe(self) -> AudioControlProbe:
        with self._lock:
            def probe_binding(binding: AudioEndpointBinding) -> AudioControlProbe:
                state = self._read_state(binding)

                return AudioControlProbe(
                    device_id=binding.device_id,
                    device_name=binding.device_name,
                    volume=state.volume,
                    muted=state.muted,
                )

            return self._run_idempotent("probe", probe_binding)

    def get_state(self) -> AudioState:
        with self._lock:
            return self._run_idempotent("get_state", self._read_state)

    def set_volume(self, value_0_100: int) -> AudioState:
        if isinstance(value_0_100, bool):
            raise ValueError("Volume must be an integer from 0 to 100")

        try:
            target = int(value_0_100)
        except (TypeError, ValueError) as e:
            raise ValueError("Volume must be an integer from 0 to 100") from e

        target = self._clamp_percent(target)

        with self._lock:
            return self._run_idempotent(
                "set_volume",
                lambda binding: self._set_volume_on_binding(
                    binding,
                    target,
                    operation="set_volume",
                ),
            )

    def change_volume(self, delta_0_100: int) -> AudioState:
        if isinstance(delta_0_100, bool):
            raise ValueError("Volume delta must be an integer")

        try:
            delta = int(delta_0_100)
        except (TypeError, ValueError) as e:
            raise ValueError("Volume delta must be an integer") from e

        with self._lock:
            first_identity: tuple[str, str] | None = None
            first_target: int | None = None
            last_error: BaseException | None = None

            for attempt in range(2):
                try:
                    binding = self._resolve_binding()
                    identity = self._binding_identity(binding)
                    state = self._read_state(binding)

                    if attempt == 0 or first_target is None:
                        target = self._clamp_percent(state.volume + delta)
                        first_identity = identity
                        first_target = target
                    elif identity == first_identity:
                        target = first_target
                    else:
                        target = self._clamp_percent(state.volume + delta)

                    return self._set_volume_on_binding(
                        binding,
                        target,
                        operation="change_volume",
                    )
                except Exception as e:
                    last_error = e

                    if attempt == 0:
                        self._sleep_before_retry()

            if last_error is None:
                last_error = RuntimeError("Unknown audio control failure")

            raise self._clone_error(
                last_error,
                "change_volume",
                retry_attempted=True,
            ) from last_error

    def mute(self) -> AudioState:
        with self._lock:
            return self._run_idempotent(
                "mute",
                lambda binding: self._set_mute_on_binding(binding, True),
            )

    def unmute(self) -> AudioState:
        with self._lock:
            return self._run_idempotent(
                "unmute",
                lambda binding: self._set_mute_on_binding(binding, False),
            )