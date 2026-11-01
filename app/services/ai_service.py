import os
import io
import re
import json
import base64
import logging
from typing import Optional, Tuple, List, Dict
import requests
from app.utils.errors import ValidationError

logger = logging.getLogger(__name__)


class AIProviderNotConfiguredError(Exception):
    """Raised when the configured AI provider credentials are missing."""
    pass


def optimize_image_bytes(image_bytes: bytes, max_dim: int = 1200) -> Tuple[str, str]:
    """Compress and downscale image bytes for AI vision inference, returning (base64_str, mime_type)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(image_bytes))
        w, h = im.size
        # Minimum dimension of 32px for vision API constraints
        if w < 32 or h < 32:
            im = im.resize((max(w, 32), max(h, 32)), Image.Resampling.LANCZOS)
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGB")
        im.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=80, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"
    except Exception as e:
        logger.warning("Could not optimize image via PIL: %s", e)
        return base64.b64encode(image_bytes).decode("utf-8"), "image/jpeg"


def optimize_base64_image(b64_str: str, max_dim: int = 1200) -> Tuple[str, str]:
    """Parse raw base64 (with or without data URI header) and return optimized (base64_str, mime_type)."""
    mime_type = "image/jpeg"
    clean_b64 = b64_str.strip()
    if "," in clean_b64:
        header, body = clean_b64.split(",", 1)
        if "image/" in header:
            mime_type = header.split(";")[0].replace("data:", "")
        clean_b64 = body
    raw_bytes = base64.b64decode(clean_b64)
    return optimize_image_bytes(raw_bytes, max_dim=max_dim)


SYSTEM_REPORT_INSTRUCTION = """
You are an expert academic documentation assistant for CUestIC, the Department of Electronics and Communication Engineering at CHRIST (Deemed to be University), Bangalore.
Your task is to help the Documentation Team prepare official Activity Reports according to the formal university template.

CRITICAL GUIDELINES:
1. Tone: Formal, professional, concise, academic documentation language.
2. Facts: Use ONLY the factual information supplied by the user or visible in attached reference posters. Do NOT invent dates, timings, venues, attendance figures, statistics, or speaker credentials.
3. If essential details are missing for the section, mark them clearly with `[Insert ...]` or `[Verify ...]`.
4. Output format: Return only the drafted content for the requested field/section without meta-commentary, markdown backticks, or greetings.
"""

POSTER_EXTRACTION_PROMPT = """
You are an expert academic documentation assistant for CUestIC, Department of Electronics and Communication Engineering at CHRIST (Deemed to be University), Bangalore.

Carefully inspect and analyze the attached event poster / brochure / flyer image.
Extract all details from the poster and return a valid JSON object matching this exact schema:
{
  "title_of_activity": "Exact official title of the event / workshop / seminar",
  "type_of_activity": "One of: Workshop, Seminar, Guest Lecture, Technical Talk, Hackathon, Symposium, Conference, Panel Discussion, Hands-on Training, Department Club Activity, Other",
  "date": "Date of the event as shown (e.g. DD-MM-YYYY or DD Month YYYY)",
  "time": "Time or duration (e.g. 10:00 AM - 1:00 PM)",
  "venue": "Campus / auditorium / room / lab / platform name",
  "collaborators": "Student chapters, clubs, or external collaborators (e.g. CUestIC & IEEE Student Branch)",
  "speakers": [
    {
      "name": "Full name of Resource Person / Speaker / Guest",
      "title": "Designation / Role",
      "organization": "Institution / Company / Department",
      "contact": ""
    }
  ],
  "type_of_participants": "Target audience (e.g. UG / PG Students & Faculty)",
  "highlights": "Topics covered, workshop modules or activities mentioned on the poster",
  "summary": "Formal 2-3 sentence overview of the event based strictly on the poster",
  "key_takeaways": "Expected outcomes or learnings highlighted on the poster",
  "speaker_profile": "Speaker credentials or bio if visible on the poster"
}

CRITICAL RULES:
1. Return ONLY the raw JSON object. Do NOT wrap in markdown backticks or preface with conversational text.
2. The `type_of_activity` must strictly be one of:
   ['Workshop', 'Seminar', 'Guest Lecture', 'Technical Talk', 'Hackathon', 'Symposium', 'Conference', 'Panel Discussion', 'Hands-on Training', 'Department Club Activity', 'Other']
3. If any detail is not present on the poster, set its value to "" (or [] for speakers).
4. Do NOT hallucinate or guess details that do not exist on the poster.
"""


class BaseAIProvider:
    """Abstract base class for AI Providers."""
    provider_name: str = "base"
    model_name: str = "default"

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        raise NotImplementedError


class GeminiProvider(BaseAIProvider):
    """Google Gemini AI Provider with Multimodal Vision."""
    provider_name = "gemini"

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        parts = []
        if image_base64:
            parts.append({
                "inline_data": {
                    "mime_type": image_mime_type or "image/jpeg",
                    "data": image_base64,
                }
            })

        full_prompt = f"System Guidelines:\n{system_instruction}\n\nTask:\n{prompt}" if system_instruction else prompt
        parts.append({"text": full_prompt})

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            }
        }

        # Try primary model, retry on 503 (high demand), and fall back to alternative flash if needed
        models_to_try = [self.model_name]
        if "3.1-flash-lite" not in self.model_name:
            models_to_try.append("gemini-3.1-flash-lite")

        last_error_text = ""
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            try:
                resp = requests.post(url, json=payload, timeout=22)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts_out = candidates[0].get("content", {}).get("parts", [])
                        if parts_out:
                            text_res = parts_out[0].get("text", "").strip()
                            if text_res:
                                return text_res
                elif resp.status_code in (503, 429):
                    import time
                    time.sleep(0.5)
                    last_error_text = resp.text
                    continue
                else:
                    last_error_text = resp.text
            except requests.RequestException as e:
                logger.warning("Gemini network error on model %s: %s", model, e)
                last_error_text = str(e)

        raise ValidationError(f"Gemini API error: {last_error_text}")


class GrokProvider(BaseAIProvider):
    """Grok / Groq AI Provider (supports Groq LPU and xAI Grok with vision support)."""
    provider_name = "grok"

    def __init__(self, api_key: str, model_name: Optional[str] = None):
        self.api_key = api_key
        self.is_groq = api_key.startswith("gsk_")

        if self.is_groq:
            self.endpoint = "https://api.groq.com/openai/v1/chat/completions"
            self.model_name = model_name or os.environ.get("GROK_MODEL", "qwen/qwen3.8-27b")
        else:
            self.endpoint = "https://api.x.ai/v1/chat/completions"
            self.model_name = model_name or os.environ.get("GROK_MODEL", "grok-2-latest")

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        if image_base64:
            user_content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_mime_type or 'image/jpeg'};base64,{image_base64}"
                    }
                }
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
        }

        try:
            resp = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
            if resp.status_code != 200:
                logger.error("Grok API error: %d - %s", resp.status_code, resp.text)
                raise ValidationError(f"Grok API error ({resp.status_code}): {resp.text}")

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValidationError("Grok returned no response choices.")

            return choices[0].get("message", {}).get("content", "").strip()
        except requests.RequestException as e:
            logger.error("Grok network error: %s", e)
            raise ValidationError(f"Could not reach Grok service: {str(e)}")


class AIService:
    """Service facade for AI Copilot assistance with multi-provider dynamic switching."""

    @classmethod
    def get_default_provider_name(cls) -> str:
        return os.environ.get("AI_PROVIDER", "gemini").lower()

    @classmethod
    def get_available_models(cls) -> List[Dict]:
        """Return all available and configured AI models for the frontend model switcher."""
        models = []

        # Gemini
        gemini_key = os.environ.get("GEMINI_API_KEY")
        gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        models.append({
            "provider": "gemini",
            "name": "Google Gemini",
            "model": gemini_model,
            "is_configured": bool(gemini_key),
            "description": "Google Gemini 3.5 Flash Multimodal Intelligence",
            "is_default": cls.get_default_provider_name() == "gemini",
        })

        # Grok / Groq
        grok_key = os.environ.get("GROK_API_KEY")
        grok_model = os.environ.get("GROK_MODEL", "qwen/qwen3.8-27b")
        is_groq = bool(grok_key and grok_key.startswith("gsk_"))
        models.append({
            "provider": "grok",
            "name": "Grok (Groq LPU)" if is_groq else "xAI Grok",
            "model": grok_model,
            "is_configured": bool(grok_key),
            "description": "Ultra-fast Groq LPU inference" if is_groq else "xAI Grok-2 Intelligence",
            "is_default": cls.get_default_provider_name() == "grok",
        })

        return models

    @classmethod
    def is_configured(cls, provider_name: Optional[str] = None) -> bool:
        provider = (provider_name or cls.get_default_provider_name()).lower()
        if provider == "gemini":
            return bool(os.environ.get("GEMINI_API_KEY"))
        elif provider in ("grok", "groq"):
            return bool(os.environ.get("GROK_API_KEY"))
        return False

    @classmethod
    def get_provider(
        cls,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Tuple[BaseAIProvider, str, str]:
        """
        Instantiate and return the requested AI provider.
        Returns: (provider_instance, resolved_provider_key, resolved_model_name)
        """
        target = (provider_name or cls.get_default_provider_name()).lower()

        if target == "gemini":
            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise AIProviderNotConfiguredError(
                    "Gemini AI provider is selected but GEMINI_API_KEY is not configured in the environment."
                )
            model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
            return GeminiProvider(api_key=key, model_name=model), "gemini", model

        elif target in ("grok", "groq"):
            key = os.environ.get("GROK_API_KEY")
            if not key:
                raise AIProviderNotConfiguredError(
                    "Grok AI provider is selected but GROK_API_KEY is not configured in the environment."
                )
            default_model = "qwen/qwen3.8-27b" if key.startswith("gsk_") else "grok-2-latest"
            model = model_name or os.environ.get("GROK_MODEL", default_model)
            return GrokProvider(api_key=key, model_name=model), "grok", model

        else:
            raise ValidationError(f"Unknown AI provider '{target}'. Supported options: 'gemini', 'grok'.")

    @classmethod
    def generate_with_resilient_fallback(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        """
        Executes AI generation with multi-provider resiliency and automatic fallback.
        Attempts primary provider first. If it encounters a timeout, network abort,
        or service outage (e.g. 503/429), it automatically falls back to the secondary
        configured provider (Groq / Gemini) so the user never experiences intermittent failures.
        """
        primary = (provider_name or cls.get_default_provider_name()).lower()
        if primary not in ("gemini", "grok", "groq"):
            primary = "gemini"

        secondary = "grok" if primary == "gemini" else "gemini"

        providers_to_try = []
        if cls.is_configured(primary):
            providers_to_try.append((primary, model_name))
        if cls.is_configured(secondary):
            providers_to_try.append((secondary, None))

        if not providers_to_try:
            raise AIProviderNotConfiguredError(
                "Neither Google Gemini nor Groq AI credentials are configured in the environment."
            )

        errors = []
        for prov_name, mod_name in providers_to_try:
            try:
                provider_instance, resolved_prov, resolved_mod = cls.get_provider(
                    provider_name=prov_name,
                    model_name=mod_name,
                )
                logger.info("Calling AI provider '%s' (model: %s)...", resolved_prov, resolved_mod)
                result = provider_instance.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    image_base64=image_base64,
                    image_mime_type=image_mime_type,
                )
                if result and result.strip():
                    return result, resolved_prov, resolved_mod
            except Exception as e:
                logger.warning("AI provider '%s' failed: %s. Attempting fallback if available...", prov_name, e)
                errors.append(f"{prov_name}: {str(e)}")

        # If image was supplied and providers failed with image payload, retry once with text-only prompt
        if image_base64:
            logger.info("Attempting AI generation fallback without image payload...")
            for prov_name, mod_name in providers_to_try:
                try:
                    provider_instance, resolved_prov, resolved_mod = cls.get_provider(
                        provider_name=prov_name,
                        model_name=mod_name,
                    )
                    result = provider_instance.generate(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        image_base64=None,
                        image_mime_type=None,
                    )
                    if result and result.strip():
                        return result, resolved_prov, resolved_mod
                except Exception as e:
                    errors.append(f"{prov_name} (text-only): {str(e)}")

        raise ValidationError(f"All configured AI providers failed. Details: {'; '.join(errors)}")

    @classmethod
    def extract_poster_context(
        cls,
        image_base64: str,
        image_mime_type: str = "image/jpeg",
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Tuple[Dict, str, str]:
        """
        Analyze an event poster/flyer image using multimodal AI vision with automatic fallback.
        Returns: (extracted_data_dict, resolved_provider, resolved_model)
        """
        raw, resolved_provider, resolved_model = cls.generate_with_resilient_fallback(
            prompt=POSTER_EXTRACTION_PROMPT,
            system_instruction=SYSTEM_REPORT_INSTRUCTION,
            image_base64=image_base64,
            image_mime_type=image_mime_type,
            provider_name=provider_name,
            model_name=model_name,
        )

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except Exception as e:
            logger.warning("Failed to parse AI poster JSON directly: %s. Response was: %s", e, raw)
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(0))
                except Exception:
                    data = {"summary": cleaned}
            else:
                data = {"summary": cleaned}

        if not isinstance(data, dict):
            data = {"summary": str(data)}

        # Normalize speakers array
        if "speakers" not in data or not isinstance(data["speakers"], list):
            data["speakers"] = []
        else:
            normalized_speakers = []
            for s in data["speakers"]:
                if isinstance(s, dict):
                    normalized_speakers.append({
                        "name": str(s.get("name", "")).strip(),
                        "title": str(s.get("title", "")).strip(),
                        "organization": str(s.get("organization", "")).strip(),
                        "contact": str(s.get("contact", "")).strip(),
                    })
                elif isinstance(s, str) and s.strip():
                    normalized_speakers.append({
                        "name": s.strip(),
                        "title": "",
                        "organization": "",
                        "contact": "",
                    })
            data["speakers"] = normalized_speakers

        return data, resolved_provider, resolved_model

    @classmethod
    def assist_field(
        cls,
        field_key: str,
        field_label: str,
        user_instruction: str,
        current_content: Optional[str] = None,
        report_context: Optional[dict] = None,
        action: str = "draft",
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
        poster_context: Optional[dict] = None,
    ) -> Tuple[str, str, str]:
        """
        Provide contextual field assistance for the AI Copilot with multi-provider fallback.
        Can consume both structured event context and visual reference poster image.
        Returns: (generated_text, resolved_provider, resolved_model)
        """
        ctx_summary = []
        if report_context:
            if report_context.get("title_of_activity"):
                ctx_summary.append(f"Activity Title: {report_context['title_of_activity']}")
            if report_context.get("type_of_activity"):
                ctx_summary.append(f"Activity Type: {report_context['type_of_activity']}")
            if report_context.get("date"):
                ctx_summary.append(f"Date: {report_context['date']}")
            if report_context.get("time"):
                ctx_summary.append(f"Time: {report_context['time']}")
            if report_context.get("venue"):
                ctx_summary.append(f"Venue: {report_context['venue']}")
            if report_context.get("collaborators"):
                ctx_summary.append(f"Collaborators: {report_context['collaborators']}")

        if poster_context and isinstance(poster_context, dict):
            poster_lines = []
            for k, v in poster_context.items():
                if v and isinstance(v, str):
                    poster_lines.append(f"- {k.replace('_', ' ').title()}: {v}")
                elif v and isinstance(v, list) and k == "speakers":
                    for spk in v:
                        if isinstance(spk, dict) and spk.get("name"):
                            desc = f"{spk.get('name')}"
                            if spk.get('title'):
                                desc += f", {spk.get('title')}"
                            if spk.get('organization'):
                                desc += f" ({spk.get('organization')})"
                            poster_lines.append(f"- Resource Person: {desc}")
            if poster_lines:
                ctx_summary.append("\nReference Poster Context (Extracted from attached poster):\n" + "\n".join(poster_lines))

        context_block = "\n".join(ctx_summary) if ctx_summary else "General University Event"

        prompt = f"""
Field to Assist: {field_label} (Key: {field_key})
Action: {action.upper()}

Context of the Event:
{context_block}

Current Field Content:
{current_content or '[Empty]'}

User Instruction / Notes:
{user_instruction}

Please provide the content specifically tailored for '{field_label}'.
"""
        generated, resolved_provider, resolved_model = cls.generate_with_resilient_fallback(
            prompt=prompt,
            system_instruction=SYSTEM_REPORT_INSTRUCTION,
            image_base64=image_base64,
            image_mime_type=image_mime_type,
            provider_name=provider_name,
            model_name=model_name,
        )
        return generated, resolved_provider, resolved_model
