import os
import platform
from typing import List

import paddle
from paddleocr import PaddleOCR


class PaddleOCREngine:
    def __init__(
        self,
        device: str = "auto",
        lang: str = "ch",
        use_textline_orientation: bool = True,
        enable_mkldnn: bool = False,
        logger=None,
    ) -> None:
        self.logger = logger
        self.device = self._resolve_device(device)

        # Avoid repeated host checks in restricted network environments.
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

        if self.logger:
            self.logger.info(f"Initialize PaddleOCR with device={self.device}, lang={lang}")

        self._ocr = PaddleOCR(
            lang=lang,
            use_textline_orientation=use_textline_orientation,
            device=self.device,
            enable_mkldnn=enable_mkldnn,
        )

    def _resolve_device(self, requested: str) -> str:
        req = (requested or "auto").strip().lower()

        if req not in {"auto", "cpu", "gpu"} and not req.startswith("gpu:"):
            if self.logger:
                self.logger.warning(f"Unknown device='{requested}', fallback to auto.")
            req = "auto"

        if req == "cpu":
            return "cpu"

        if req == "auto":
            # Project requirement: Mac defaults to CPU.
            if platform.system() == "Darwin":
                return "cpu"
            if self._gpu_available():
                return "gpu:0"
            return "cpu"

        # req == "gpu" or req.startswith("gpu:")
        if self._gpu_available():
            return "gpu:0" if req == "gpu" else req

        if self.logger:
            self.logger.warning("GPU requested but unavailable. Fallback to CPU.")
        return "cpu"

    @staticmethod
    def _gpu_available() -> bool:
        try:
            return bool(paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0)
        except Exception:
            return False

    def extract_text(self, image_paths: List[str]) -> List[str]:
        """
        Return flattened text lines from all images.
        """
        outputs: List[str] = []

        for image_path in image_paths:
            try:
                result = self._ocr.predict(image_path)
            except Exception as exc:
                if self.logger:
                    self.logger.error(f"OCR failed for image={image_path}: {exc}")
                continue

            if not result:
                continue

            record = result[0]
            texts = []
            if hasattr(record, "get"):
                rec_texts = record.get("rec_texts") or []
                texts = [str(t).strip() for t in rec_texts if str(t).strip()]

            if self.logger:
                self.logger.info(f"OCR image done: {image_path}, lines={len(texts)}")
            outputs.extend(texts)

        return outputs
