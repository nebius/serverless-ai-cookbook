import httpx
import pytest

from collect_lifecycle import event_pages


def test_event_pagination_preserves_order_and_does_not_count_reads_as_calls():
    seen = []
    def handle(request):
        seen.append(request)
        after = int(request.url.params["after_sequence"])
        end = 1000 if after == 0 else 1002
        return httpx.Response(200, json={"data": [{"sequence": n} for n in range(after + 1, end + 1)]})
    with httpx.Client(base_url="https://unit.test", transport=httpx.MockTransport(handle)) as client:
        values = event_pages(client, "operation")
    assert len(values) == 1002
    assert [r.method for r in seen] == ["GET", "GET"]
    assert seen[1].url.params["after_sequence"] == "1000"


@pytest.mark.parametrize("sequences", [[2, 1], [1, 1], [0]])
def test_non_advancing_event_page_is_reported(sequences):
    with httpx.Client(base_url="https://unit.test", transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"data": [{"sequence": n} for n in sequences]})
    )) as client:
        with pytest.raises(ValueError, match="advance uniquely"):
            event_pages(client, "operation")
