from __future__ import annotations

import json
import random
import time
from pathlib import Path

import requests
from huggingface_hub import InferenceClient

from auto_video.config import DATA_DIR, Settings
from auto_video.models import Scene
from auto_video.utils import log

SECTORS_SEEN_FILE = DATA_DIR / "sectors_seen.json"
INPUT_FILE = DATA_DIR / "input.json"
SECTOR_FILE = DATA_DIR / "sector.txt"


def _load_seen_sectors() -> list[str]:
    if not SECTORS_SEEN_FILE.exists():
        return []
    try:
        data = json.loads(SECTORS_SEEN_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(item) for item in data]
    except (json.JSONDecodeError, OSError) as exc:
        log(f"Seen sectors okunamadi: {exc}")
    return []


def save_seen_sector(sector: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    seen = _load_seen_sectors()
    if sector not in seen:
        seen.append(sector)
        SECTORS_SEEN_FILE.write_text(
            json.dumps(seen, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def reset_seen_sectors() -> None:
    if SECTORS_SEEN_FILE.exists():
        SECTORS_SEEN_FILE.unlink()
    log("Kullanilmis sektor listesi sifirlandi.")


def _pick_sector(candidates: list[str], settings: Settings) -> str:
    chosen = _ai_select_sector(candidates, settings)
    if chosen:
        log(f"AI tarafindan secilen sektor: {chosen}")
        return chosen
    sector = random.choice(candidates)
    log(f"AI secim basarisiz, rastgele secilen sektor: {sector}")
    return sector


def _ai_select_sector(candidates: list[str], settings: Settings) -> str | None:
    prompt = (
        "Asagidaki Turkiye'deki is sektorleri hariç Türkiye'deki bütün is sektorlerinden yalnizca birini sec. "
        "Sadece sektor adini tek satirda Turkce yaz.\n"
        + "\n".join(f"- {sector}" for sector in candidates)
    )

    if settings.use_openrouter:
        try:
            log("OpenRouter ile sektor seciliyor...")
            text = _generate_openrouter(prompt, settings, max_tokens=60)
            if text:
                return text.strip().splitlines()[0].strip()

        except Exception as exc:
            log(f"OpenRouter secim hatasi: {exc}")

    try:
        log("HF Inference ile sektor seciliyor...")
        client = InferenceClient("gpt2", token=settings.hf_token)
        response = client.text_generation(prompt, max_new_tokens=40)
        text = response if isinstance(response, str) else str(response)
        return _match_candidate(text.strip().splitlines()[0].strip(), candidates)
    except Exception as exc:
        log(f"HF secim hatasi: {exc}")
        return None


def _match_candidate(answer: str, candidates: list[str]) -> str | None:
    normalized = answer.lower()
    for candidate in candidates:
        if candidate.lower() == normalized:
            return candidate
    for candidate in candidates:
        if normalized in candidate.lower() or candidate.lower() in normalized:
            return candidate
    return None


def _generate_openrouter(prompt: str, settings: Settings, max_tokens: int = 1000) -> str | None:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json={
            "model": settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        },
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://github.com/auto-video",
            "X-Title": "Auto Video Generator",
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _generate_hf(prompt: str, settings: Settings) -> str | None:
    models = [
        "meta-llama/Llama-2-7b-chat-hf",
        "tiiuae/falcon-7b-instruct",
        "NousResearch/Nous-Hermes-2-Mistral-7B-DPO",
    ]
    for model in models:
        try:
            log(f"Model deneniyor: {model}")
            client = InferenceClient(model, token=settings.hf_token)
            response = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            if response and response.choices and response.choices[0].message:
                log(f"Basarili: {model}")
                return response.choices[0].message.content
        except Exception as exc:
            log(f"Model basarisiz ({model}): {str(exc)[:120]}")
            time.sleep(2)
    return None


def _build_script_prompt(sector: str, scene_count: int) -> str:
    return f"""
Asagidaki sektor hakkinda tam olarak {scene_count} sahnelik bir video senaryosu yaz: {sector}
Bu videoyu izleyen kisiler, {sector} sektoründeki girişimciler ne kadar kazanıyor, giderleri ve gelirleri nelerdir gibi sorularin cevabini alacak ve calisma sartlari hakkinda bilgi sahibi olacak.
Verdiğin veriler 2026 yılındaki veriler olmalıdır. Türk lirası cinsinden veriler olmalıdır. Giderler ve kazançlar ayrı ayrı verilmeli.
prompt alani sahnelerin her biri icin kisa ve net bir gorsel tasvir icermelidir. Her sahne icin Ingilizce anlat ama gorsel icinde metin bulunacaksa bu metin mutlaka Turkce olmalidir.
Gorsel tasvirlerde hintli tasvir etme; sadece Turk/Avrupa vatandaslarini tasvir et.

text alaninda Turkce metin olmali ve o sektor ile ilgili bilgi vermelidir. Bu alana gelen metin seslendirilecegi icin sohbet tadinda ve dogal olmalidir.
son sahne de cümlenin en sonuna kullanıcıya daha fazla bu tarz video için takip etmesini söyle.
JSON formatinda dondur. Yapi:
[
  {{"scene": 1, "text": "Turkce metin", "prompt": "English visual description"}},
  ...
]

Sadece valid JSON don, baska bir sey yazma!
""".strip()


def _parse_scenes(response_text: str, min_scenes: int = 4) -> list[Scene]:
    start_idx = response_text.find("[")
    end_idx = response_text.rfind("]") + 1
    if start_idx == -1 or end_idx <= 0:
        raise ValueError("JSON array bulunamadi")

    payload = json.loads(response_text[start_idx:end_idx])
    if not isinstance(payload, list) or len(payload) < min_scenes:
        raise ValueError(f"JSON en az {min_scenes} sahne icermeli")

    return [Scene.from_dict(item) for item in payload]


def generate_script(settings: Settings, *, reset_seen: bool = False) -> list[Scene]:
    if reset_seen:
        reset_seen_sectors()

    seen = _load_seen_sectors()
    candidates = [sector for sector in settings.sectors if sector not in seen]
    if not candidates:
        raise RuntimeError(
            "Tum sektorler daha once kullanilmis. Yeni sektor ekleyin (data/sectors.json), "
            "veya 'python run.py script --reset-seen' komutunu calistirin."
        )

    sector = _pick_sector(candidates, settings)
    prompt = _build_script_prompt(sector, settings.scene_count)

    response_text = None
    if settings.use_openrouter:
        log("OpenRouter API kullaniliyor...")
        response_text = _generate_openrouter(prompt, settings)
    if not response_text:
        log("HF Inference API kullaniliyor...")
        response_text = _generate_hf(prompt, settings)
    if not response_text:
        raise RuntimeError("Tum API'ler basarisiz oldu. Lutfen daha sonra tekrar deneyin.")

    try:
        scenes = _parse_scenes(response_text, min_scenes=min(4, settings.scene_count))
    except (json.JSONDecodeError, ValueError) as exc:
        log(f"JSON parse hatasi: {exc}")
        log(f"Yanit: {response_text[:200]}")
        raise

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INPUT_FILE.write_text(
        json.dumps([scene.to_dict() for scene in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    SECTOR_FILE.write_text(sector, encoding="utf-8")
    save_seen_sector(sector)
    log(f"Senaryo kaydedildi: {INPUT_FILE}")
    return scenes
