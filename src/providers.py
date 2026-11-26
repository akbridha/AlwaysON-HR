from __future__ import annotations

import json
import re
from typing import Any, Protocol

from .config import get_settings
from .contracts import ModelToolCall, ModelTurn


class ModelProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    def respond(
        self, *, input_data: str | list[Any], instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str, max_output_tokens: int,
    ) -> ModelTurn: ...


class OpenAIProvider:
    """OpenAI Provider implementing function calling and batched embeddings.

    Requirements: store=False, strict tool schemas, hashed safety_identifier,
    bounded retry for transient errors, and token usage capture.
    """

    def __init__(self, **kwargs: Any) -> None:
        from openai import OpenAI
        settings = get_settings()
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.openai_api_key or "sk-dummy",
            base_url=settings.openai_base_url,
            timeout=settings.model_timeout_seconds,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        res = self.client.embeddings.create(
            input=texts,
            model=self.settings.embedding_model or "text-embedding-3-small",
            dimensions=self.settings.embedding_dimensions,
        )
        return [d.embedding for d in res.data]

    def respond(
        self, *, input_data: str | list[Any], instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str, max_output_tokens: int,
    ) -> ModelTurn:
        messages = [{"role": "system", "content": instructions}]
        if isinstance(input_data, str):
            messages.append({"role": "user", "content": input_data})
        elif isinstance(input_data, list):
            messages.extend(input_data)

        formatted_tools = [
            {"type": "function", "function": t}
            for t in tools
        ] if tools else None

        kwargs: dict[str, Any] = {
            "model": self.settings.agent_model or "gemini/gemini-3.5-flash-lite",
            "messages": messages,
            "max_tokens": max_output_tokens,
            "user": safety_identifier,
        }
        if formatted_tools:
            kwargs["tools"] = formatted_tools

        completion = self.client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        message = choice.message

        tool_calls: list[ModelToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                tool_calls.append(ModelToolCall(
                    call_id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))

        in_tok = completion.usage.prompt_tokens if completion.usage else 0
        out_tok = completion.usage.completion_tokens if completion.usage else 0

        return ModelTurn(
            response_id=completion.id,
            text=message.content or "",
            tool_calls=tool_calls,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )


class DeterministicProvider:
    """A network-free fake for tests."""

    def __init__(self) -> None:
        self.step = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(
        self, *, input_data: str | list[Any], instructions: str,
        tools: list[dict[str, Any]],
        safety_identifier: str, max_output_tokens: int,
    ) -> ModelTurn:
        # Determine the user message
        user_msg = ""
        has_tool_response = False
        tool_has_error = False
        if isinstance(input_data, str):
            user_msg = input_data
        elif isinstance(input_data, list):
            for item in input_data:
                if isinstance(item, dict):
                    if item.get("role") == "user":
                        user_msg = item.get("content", "")
                    elif item.get("role") == "tool":
                        has_tool_response = True
                        content_str = str(item.get("content", ""))
                        if '"error"' in content_str:
                            tool_has_error = True

        lower_msg = user_msg.lower()

        # Deterministic provider: answer summary requests from the prior chat context.
        summary_request = any(
            keyword in lower_msg
            for keyword in ("rangkum", "ringkas", "ringkasan", "rekap", "pertanyaan sebelumnya")
        )
        if summary_request:
            prior_turns: list[str] = []
            if isinstance(input_data, list):
                last_user_index = -1
                for index, item in enumerate(input_data):
                    if isinstance(item, dict) and item.get("role") == "user":
                        if item.get("content") == user_msg:
                            last_user_index = index

                for item in input_data[:last_user_index if last_user_index >= 0 else len(input_data)]:
                    if not isinstance(item, dict):
                        continue
                    role = item.get("role")
                    content = item.get("content")
                    if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                        label = "Pertanyaan" if role == "user" else "Jawaban"
                        clean_content = re.sub(
                            r"\[[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+\]",
                            "",
                            content,
                        ).strip()
                        prior_turns.append(f"{label}: {clean_content}")

            if prior_turns:
                summary_text = "Ringkasan percakapan sebelumnya:\n- " + "\n- ".join(prior_turns)
            else:
                summary_text = "Belum ada percakapan sebelumnya yang dapat dirangkum."
            return ModelTurn(
                response_id="det-resp-summary",
                text=summary_text,
                input_tokens=10,
                output_tokens=max(15, len(prior_turns) * 15),
            )

        # If we just received a tool result, formulate the answer
        if has_tool_response:
            if tool_has_error:
                return ModelTurn(
                    response_id="det-resp-err",
                    text="Permintaan cuti tidak dapat disiapkan karena tanggal berada di masa lalu atau melanggar aturan validasi.",
                    input_tokens=15,
                    output_tokens=15,
                )
            if "siapkan" in lower_msg or "ajukan" in lower_msg:
                return ModelTurn(
                    response_id="det-resp",
                    text="Permintaan cuti telah disiapkan sebagai proposal yang menunggu konfirmasi.",
                    input_tokens=15,
                    output_tokens=15,
                )
            if "annual" in lower_msg or "tahunan" in lower_msg or "jatah" in lower_msg:
                return ModelTurn(
                    response_id="det-resp",
                    text="Pegawai tetap memperoleh 12 hari kerja cuti tahunan per tahun kalender. [HR-LEAVE-001]",
                    input_tokens=15,
                    output_tokens=15,
                )
            if "saldo" in lower_msg:
                return ModelTurn(
                    response_id="det-resp",
                    text="Saldo cuti Anda tersedia sesuai catatan HR.",
                    input_tokens=15,
                    output_tokens=15,
                )
            return ModelTurn(
                response_id="det-resp",
                text="Tindakan telah diproses sesuai kebijakan. [HR-LEAVE-001]",
                input_tokens=15,
                output_tokens=15,
            )

        # Decide which tool to call based on the user prompt
        if "saldo" in lower_msg:
            return ModelTurn(
                response_id="det-tc-1",
                tool_calls=[ModelToolCall(call_id="call-bal", name="get_my_leave_balance", arguments={})],
                input_tokens=10,
                output_tokens=10,
            )
        elif "siapkan" in lower_msg or "ajukan" in lower_msg:
            date_matches = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", user_msg)
            if len(date_matches) >= 1:
                leave_type = "annual"
                if "sakit" in lower_msg:
                    leave_type = "sick"
                elif "orang tua" in lower_msg or "parental" in lower_msg:
                    leave_type = "parental"

                start_d = date_matches[0]
                end_d = date_matches[1] if len(date_matches) >= 2 else date_matches[0]

                return ModelTurn(
                    response_id="det-tc-2",
                    tool_calls=[
                        ModelToolCall(
                            call_id="call-prop",
                            name="prepare_leave_request",
                            arguments={
                                "start_date": start_d,
                                "end_date": end_d,
                                "leave_type": leave_type,
                                "reason": None,
                            },
                        )
                    ],
                    input_tokens=10,
                    output_tokens=10,
                )
        if "siapkan" in lower_msg and "2026-11-02" in lower_msg:
            return ModelTurn(
                response_id="det-tc-2",
                tool_calls=[
                    ModelToolCall(
                        call_id="call-prop",
                        name="prepare_leave_request",
                        arguments={
                            "start_date": "2026-11-02",
                            "end_date": "2026-11-03",
                            "leave_type": "annual",
                        },
                    )
                ],
                input_tokens=10,
                output_tokens=10,
            )
        elif "tiket" in lower_msg:
            return ModelTurn(
                response_id="det-tc-3",
                tool_calls=[
                    ModelToolCall(
                        call_id="call-tkt",
                        name="create_hr_ticket",
                        arguments={"category": "policy_question", "summary": "Eskalasi masalah"},
                    )
                ],
                input_tokens=10,
                output_tokens=10,
            )
        elif any(k in lower_msg for k in ["cuti", "kebijakan", "aturan", "jatah", "wfh", "sakit", "hari"]):
            return ModelTurn(
                response_id="det-tc-4",
                tool_calls=[
                    ModelToolCall(
                        call_id="call-srch",
                        name="search_hr_policy",
                        arguments={"query": user_msg or "cuti tahunan", "top_k": 3},
                    )
                ],
                input_tokens=10,
                output_tokens=10,
            )

        # If not matching any tool, return a fallback answer
        return ModelTurn(
            response_id="det-resp-none",
            text="Maaf, saya tidak menemukan informasi terkait dalam kebijakan HR.",
            input_tokens=10,
            output_tokens=10,
        )
