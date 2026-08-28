"""
Hybrid LLM router: cheap/fast local Ollama model for simple turns, cloud
model for complex reasoning/booking logic/long context. This is also the
exact component swapped out during simulation training (Section:
agent-vs-agent).
"""
import os
import ollama
import httpx


SIMPLE_INTENT_MARKERS = ("hours", "address", "yes", "no", "hello", "hi", "thanks")


class LLMEngine:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.local_model = os.getenv("OLLAMA_LOCAL_MODEL", "llama3:8b")
        self.cloud_model = os.getenv("CLOUD_LLM_MODEL", "gpt-5")
        self.cloud_key = os.getenv("CLOUD_LLM_API_KEY")

    def _looks_simple(self, user_text: str) -> bool:
        t = user_text.lower()
        return len(t.split()) < 8 and any(m in t for m in SIMPLE_INTENT_MARKERS)

    async def respond(self, system_prompt: str, context: str, user_text: str,
                       tier: str = "hybrid") -> str:
        prompt = self._build_prompt(system_prompt, context, user_text)

        use_local = tier == "local" or (tier == "hybrid" and self._looks_simple(user_text))
        if use_local:
            try:
                return await self._call_local(prompt)
            except Exception:
                pass  # fall through to cloud on local failure
        return await self._call_cloud(prompt)

    def _build_prompt(self, system_prompt: str, context: str, user_text: str) -> str:
        parts = [system_prompt]
        if context:
            parts.append(f"Relevant knowledge:\n{context}")
        parts.append(f"Caller said: {user_text}")
        parts.append("Respond in one or two short spoken sentences.")
        return "\n\n".join(parts)

    async def _call_local(self, prompt: str) -> str:
        client = ollama.AsyncClient(host=self.ollama_host)
        result = await client.generate(model=self.local_model, prompt=prompt)
        return result["response"].strip()

    async def _call_cloud(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.cloud_key}"},
                json={
                    "model": self.cloud_model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
