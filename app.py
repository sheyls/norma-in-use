"""Entry point for a Hugging Face Space: serves the explorer (web/app.py) on 0.0.0.0:7860.

Free Gradio Spaces run on ZeroGPU, which only starts an app that declares at
least one @spaces.GPU function and launches Gradio (that is when the function
is reported). The explorer needs no GPU: the function below is never called,
and the Gradio app listens only on an internal port. Outside a Space (no
`spaces`/`gradio` installed) both steps are skipped.

Locally, run the explorer directly instead: cd web && ../.venv/bin/python app.py
"""
import os
import runpy
import sys
from pathlib import Path

PORT = os.environ.get("PORT", "7860")

try:
    import spaces  # must come before anything that could initialise CUDA
    import gradio as gr
except ImportError:
    spaces = gr = None

if spaces is not None:
    @spaces.GPU
    def _unused():
        """Declared for ZeroGPU; never called."""

    with gr.Blocks() as _placeholder:
        gr.Markdown("The NORMA-O explorer is served on the Space's main port.")
    _placeholder.launch(server_name="127.0.0.1", server_port=7861, prevent_thread_lock=True)

web = Path(__file__).resolve().parent / "web" / "app.py"
sys.argv = [str(web), "--host", "0.0.0.0", "--port", PORT]
runpy.run_path(str(web), run_name="__main__")
