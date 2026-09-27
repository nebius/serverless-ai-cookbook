import pytest

from fs2_speech.contracts import ENGLISH_ID, RuntimeProfile
from fs2_speech.probe_job import render_job


def inputs():
    return dict(name="fs2-speech-probe-test", namespace="test", image="registry.example/speech@sha256:" + "a" * 64,
                profile=RuntimeProfile(model=ENGLISH_ID), gpu_class="test-gpu")


def test_bounded_task_owned_job_without_cluster_privileges():
    job = render_job(**inputs())
    assert job["spec"]["backoffLimit"] == 0
    assert job["spec"]["activeDeadlineSeconds"] == 1800
    pod = job["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["nodeSelector"]["nebius.com/preemptible"] == "true"
    assert pod["containers"][0]["resources"]["limits"]["nvidia.com/gpu"] == "1"
    assert not pod.get("hostNetwork")


@pytest.mark.parametrize("image", ["registry.example/speech:latest", "registry.example/speech:stable", "x@sha256:123"])
def test_unpinned_images_rejected(image):
    kwargs = inputs()
    kwargs["image"] = image
    with pytest.raises(ValueError, match="digest"):
        render_job(**kwargs)


def test_not_a_general_cluster_mutation_tool():
    kwargs = inputs()
    kwargs["name"] = "existing-customer-model"
    with pytest.raises(ValueError, match="diagnostic"):
        render_job(**kwargs)


def test_gpu_is_configurable_not_hardcoded():
    job = render_job(**inputs(), preemptible=False)
    assert job["spec"]["template"]["spec"]["nodeSelector"] == {"accelerator.fs2.nebius/class": "test-gpu"}


def test_unimplemented_cli_options_are_not_ignored():
    kwargs = inputs()
    kwargs["profile"] = RuntimeProfile(model=ENGLISH_ID, confidence=True)
    with pytest.raises(ValueError, match="baseline"):
        render_job(**kwargs)
