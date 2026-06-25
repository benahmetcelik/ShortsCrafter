from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scene:
    scene: int
    text: str
    prompt: str

    @classmethod
    def from_dict(cls, data: dict) -> Scene:
        return cls(
            scene=int(data["scene"]),
            text=str(data["text"]).strip(),
            prompt=str(data.get("prompt", data["text"])).strip(),
        )

    def to_dict(self) -> dict:
        return {"scene": self.scene, "text": self.text, "prompt": self.prompt}
