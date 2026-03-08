"""
LLM Engine — GGUF inference via llama-cpp-python for RTX 5060 Ti.

Loads a quantized Arkady model (GGUF Q4_K_M) with full GPU offload
and Flash Attention 2 for minimal VRAM usage during JSON analysis.

Hardware target:
  - NVIDIA RTX 5060 Ti (8GB or 16GB VRAM)
  - CUDA 12.x + Tensor Cores
  - Q4_K_M quantization: ~15GB model → ~8.5GB in VRAM

Usage:
    engine = LLMEngine()
    response = engine.generate(
        prompt="Analyze this trade...",
        max_tokens=512,
        temperature=0.1,
    )
"""

import os
import json
import time
from typing import Optional, Dict, Any

# Default model path (override via env or constructor)
DEFAULT_MODEL_PATH = os.environ.get(
    "LLM_MODEL_PATH",
    os.path.expanduser("~/models/arkady-reasoning-27b-Q4_K_M.gguf"),
)

# RTX 5060 Ti optimized defaults
DEFAULT_CONFIG = {
    # Context & generation
    "n_ctx": 4096,           # 4K context window (sufficient for JSON analysis)
    "n_batch": 512,          # Batch size for prompt processing
    "n_threads": 4,          # CPU threads for non-GPU ops
    "max_tokens": 1024,      # Max generation length

    # GPU offload
    "n_gpu_layers": -1,      # -1 = offload ALL layers to VRAM
    "main_gpu": 0,           # Primary GPU index

    # Flash Attention 2 (reduces VRAM for long contexts)
    "flash_attn": True,

    # Quantization-aware sampling
    "temperature": 0.1,      # Low temp for deterministic trade decisions
    "top_p": 0.9,
    "repeat_penalty": 1.1,

    # Memory optimization
    "use_mmap": True,        # Memory-map the model file
    "use_mlock": False,      # Don't lock in RAM (we want VRAM)
    "offload_kqv": True,     # Offload KV-cache to GPU
}


class LLMEngine:
    """
    Quantized LLM inference engine for trade risk analysis.

    Wraps llama-cpp-python with RTX 5060 Ti optimized settings.
    The model is loaded lazily on first generate() call.

    Parameters
    ----------
    model_path : str
        Path to the GGUF model file.
    config : dict
        Override any DEFAULT_CONFIG keys.
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.model_path = model_path
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._llm = None  # Lazy-loaded
        self._load_time: float = 0.0

    def _ensure_loaded(self):
        """Lazy-load the model on first use."""
        if self._llm is not None:
            return

        try:
            from llama_cpp import Llama  # type: ignore[import-untyped]
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python not installed. Install with CUDA support:\n"
                "  CMAKE_ARGS='-DGGML_CUDA=on' pip install llama-cpp-python"
            )

        if not os.path.isfile(self.model_path):
            raise FileNotFoundError(
                f"GGUF model not found: {self.model_path}\n"
                f"Download a Q4_K_M quantized model and set LLM_MODEL_PATH."
            )

        print(f"🔧 Loading GGUF model: {os.path.basename(self.model_path)}")
        print(f"   n_gpu_layers={self.config['n_gpu_layers']} | "
              f"n_ctx={self.config['n_ctx']} | "
              f"flash_attn={self.config['flash_attn']}")

        t0 = time.time()
        self._llm = Llama(
            model_path=self.model_path,
            n_ctx=self.config["n_ctx"],
            n_batch=self.config["n_batch"],
            n_threads=self.config["n_threads"],
            n_gpu_layers=self.config["n_gpu_layers"],
            main_gpu=self.config["main_gpu"],
            flash_attn=self.config["flash_attn"],
            use_mmap=self.config["use_mmap"],
            use_mlock=self.config["use_mlock"],
            offload_kqv=self.config["offload_kqv"],
            verbose=False,
        )
        self._load_time = time.time() - t0
        print(f"   ✅ Model loaded in {self._load_time:.1f}s")

    def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a quantitative trade risk analyst. Respond ONLY in valid JSON.",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[list] = None,
    ) -> str:
        """
        Generate a completion from the quantized model.

        Parameters
        ----------
        prompt : str
            The user prompt (trade data for analysis).
        system_prompt : str
            System instruction (default: JSON-only output).
        max_tokens : int
            Override max generation length.
        temperature : float
            Override sampling temperature.
        stop : list[str]
            Stop sequences.

        Returns
        -------
        str
            The raw model output text.
        """
        self._ensure_loaded()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens or self.config["max_tokens"],
            temperature=temperature or self.config["temperature"],
            top_p=self.config["top_p"],
            repeat_penalty=self.config["repeat_penalty"],
            stop=stop or ["\n\n\n"],
        )

        text = response["choices"][0]["message"]["content"]
        return text.strip()

    def generate_json(
        self,
        prompt: str,
        system_prompt: str = "You are a quantitative trade risk analyst. Respond ONLY in valid JSON.",
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """
        Generate and parse a JSON response from the model.

        Raises ValueError if the model output is not valid JSON.
        """
        raw = self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"LLM returned invalid JSON:\n{raw[:500]}\nError: {e}"
            )

    def unload(self):
        """Free VRAM by unloading the model."""
        if self._llm is not None:
            del self._llm
            self._llm = None
            print("🗑️ LLM model unloaded from VRAM")

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def get_info(self) -> Dict[str, Any]:
        """Return engine diagnostics."""
        return {
            "model_path": self.model_path,
            "loaded": self.is_loaded,
            "load_time_sec": self._load_time,
            "config": self.config,
        }
