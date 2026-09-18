import ast
import asyncio
import json
from pathlib import Path


def test_prediction_cell_runs_with_jupyter_event_loop():
    notebook = json.loads(
        (Path(__file__).parents[1] / "notebooks/bir_boltz2_tutorial.ipynb").read_text()
    )
    source = next(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code" and "rows =" in "".join(cell["source"])
    )

    async def stage():
        return [{"output_path": "test.cif"}]

    def processor(records):
        assert records == [{"record": {"input_id": "test"}, "__record_id": "test"}]
        # Public BioIR's synchronous processor runs each async stage this way.
        return asyncio.run(stage())

    namespace = {"processor": processor, "request": {"input_id": "test"}}

    async def execute_cell():
        code = compile(
            source, "notebook-cell", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT
        )
        await eval(code, namespace)

    asyncio.run(execute_cell())
    assert namespace["row"] == {"output_path": "test.cif"}
