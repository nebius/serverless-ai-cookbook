import subprocess
import sys
from types import SimpleNamespace

import pytest

from fs2_speech import capacity_observation as observation

UUID = "42ad5794-fb58-416a-bf98-0123456789ab"
ROW = "GPU-" + UUID + ", 580.95.05, 72, 41\n"


def test_smi_exact_uuid_fixed_arguments_and_measured_values(monkeypatch):
    commands = []
    monkeypatch.setattr(observation.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(observation, "_bounded_smi", lambda command: commands.append(command) or ROW.encode())
    driver, rates = observation._smi_observation([{"uuid": UUID}])
    assert driver == "580.95.05" and rates == {"GPU-" + UUID: (72, 41)}
    assert commands == [["/usr/bin/nvidia-smi", "--id=GPU-" + UUID,
                         "--query-gpu=uuid,driver_version,utilization.gpu,utilization.memory",
                         "--format=csv,noheader,nounits"]]


@pytest.mark.parametrize("uuid", [None, "", "0", "--id=0", UUID + ";echo secret", "MIG-" + UUID])
def test_unsupported_or_injected_identity_never_calls_utility(monkeypatch, uuid):
    monkeypatch.setattr(observation, "_bounded_smi", lambda _: pytest.fail("query not authorized"))
    assert observation._smi_observation([{"uuid": uuid}]) == (None, {})


def test_absent_binary_stays_unknown(monkeypatch):
    monkeypatch.setattr(observation.shutil, "which", lambda name: None)
    monkeypatch.setattr(observation, "_bounded_smi", lambda _: pytest.fail("no binary"))
    assert observation._smi_observation([{"uuid": UUID}]) == (None, {})


@pytest.mark.parametrize("raw", [
    b"", b"N/A", ROW.replace("72", "N/A").encode(), ROW.replace("72", "101").encode(),
    ROW.replace("72", "nan").encode(), ROW.replace(UUID, "00000000-0000-0000-0000-000000000000").encode(),
    (ROW + ROW).encode(), ROW.replace("580.95.05", "private-error").encode(), b"x" * 16385,
])
def test_malformed_mismatch_or_unsupported_rates_are_unknown(monkeypatch, raw):
    monkeypatch.setattr(observation.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(observation, "_bounded_smi", lambda _: raw)
    assert observation._smi_observation([{"uuid": UUID}]) == (None, {})


@pytest.mark.parametrize("error", [FileNotFoundError, TimeoutError, subprocess.SubprocessError])
def test_utility_errors_stay_unknown_and_are_not_logged(monkeypatch, capsys, error):
    monkeypatch.setattr(observation.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    def failure(_):
        raise error("private exception must not be printed")
    monkeypatch.setattr(observation, "_bounded_smi", failure)
    assert observation._smi_observation([{"uuid": UUID}]) == (None, {})
    captured = capsys.readouterr()
    assert not captured.out and not captured.err


def test_bounded_query_reaps_timeout_and_rejects_large_stdout():
    # Local controlled children only, no nvidia-smi/GPU or external requests.
    with pytest.raises(TimeoutError):
        observation._bounded_smi([sys.executable, "-c", "import time; time.sleep(10)"])
    with pytest.raises(ValueError, match="query_size"):
        observation._bounded_smi([sys.executable, "-c", "import sys; sys.stdout.write('x'*20000)"])
    assert observation._bounded_smi([sys.executable, "-c", "print('bounded')"]) == b"bounded\n"


def mock_cuda(monkeypatch):
    cuda = SimpleNamespace(
        is_available=lambda: True, device_count=lambda: 1,
        get_device_properties=lambda _: SimpleNamespace(name="unit GPU", uuid=UUID),
        mem_get_info=lambda _: (10, 20), memory_allocated=lambda _: 2,
        memory_reserved=lambda _: 3,
        synchronize=lambda: pytest.fail("telemetry must not synchronize CUDA"),
    )
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=cuda, version=SimpleNamespace(cuda="unit")))


def test_successful_nvml_does_not_run_fallback(monkeypatch):
    mock_cuda(monkeypatch)
    requested_uuids = []
    nvml = SimpleNamespace(
        nvmlInit=lambda: None, nvmlShutdown=lambda: None,
        nvmlSystemGetDriverVersion=lambda: b"580.95.05",
        nvmlDeviceGetHandleByUUID=lambda value: requested_uuids.append(value) or value,
        nvmlDeviceGetUtilizationRates=lambda _: SimpleNamespace(gpu=12, memory=34),
    )
    monkeypatch.setitem(sys.modules, "pynvml", nvml)
    monkeypatch.setattr(observation, "_smi_observation", lambda _: pytest.fail("NVML already succeeded"))
    result = observation.hardware_snapshot()
    assert requested_uuids == ["GPU-" + UUID]
    assert result["driver_version"] == "580.95.05"
    assert result["devices"][0]["utilization_percent"] == 12
    assert result["devices"][0]["memory_utilization_percent"] == 34


@pytest.mark.parametrize("mode", ["absent", "failed", "partial"])
def test_fallback_fills_only_missing_nvml_measurements(monkeypatch, mode):
    mock_cuda(monkeypatch)
    def failed():
        raise RuntimeError("private device error")
    nvml = SimpleNamespace(
        nvmlInit=failed if mode == "failed" else lambda: None,
        nvmlShutdown=lambda: None,
        nvmlSystemGetDriverVersion=lambda: "580.95.04",
        nvmlDeviceGetHandleByUUID=lambda _: failed(),
    )
    monkeypatch.setitem(sys.modules, "pynvml", None if mode == "absent" else nvml)
    calls = []
    monkeypatch.setattr(observation, "_smi_observation", lambda devices:
                        calls.append(devices[0]["uuid"]) or ("580.95.05", {"GPU-" + UUID: (72, 41)}))
    result = observation.hardware_snapshot()
    assert calls == [UUID]
    assert result["driver_version"] == ("580.95.04" if mode == "partial" else "580.95.05")
    assert result["devices"][0]["uuid"] == UUID
    assert result["devices"][0]["utilization_percent"] == 72
    assert result["devices"][0]["memory_utilization_percent"] == 41
