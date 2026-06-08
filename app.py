"""Gradio UI for the ASU Freshman Unofficial Guide RAG.

Usage: python3 app.py   (needs GROQ_API_KEY in .env and a built index: scripts.build_index)
"""
import gradio as gr
from rag.generate import answer


def _respond(query: str):
    if not query or not query.strip():
        return "Ask a question about thriving at ASU as a freshman.", ""
    out = answer(query.strip(), k=5)
    seen = []
    for h in out["sources"]:
        line = f"- [{h.get('source_type')}] {h.get('source_url')}"
        if line not in seen:
            seen.append(line)
    return out["answer"], "\n".join(seen)


with gr.Blocks(title="ASU Freshman Unofficial Guide") as demo:
    gr.Markdown("# ASU Freshman Unofficial Guide\nAsk about studying, housing, transport, professors, finals.")
    q = gr.Textbox(label="Your question", placeholder="How long should I study before a break?")
    btn = gr.Button("Ask")
    ans = gr.Markdown(label="Answer")
    srcs = gr.Markdown(label="Sources")
    btn.click(_respond, inputs=q, outputs=[ans, srcs])
    q.submit(_respond, inputs=q, outputs=[ans, srcs])


if __name__ == "__main__":
    demo.launch()
