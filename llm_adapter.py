#!/usr/bin/env python3
# SPDX-License-Identifier: 0BSD

# Copyright (C) 2024-2025 by Forest Crossman <cyrozap@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for
# any purpose with or without fee is hereby granted.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
# WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
# AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL
# DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR
# PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.


import json
import os
import time
from typing import Any, Iterator

import requests  # type: ignore
from flask import Flask, request, Response


APP = Flask(__name__)

SOURCEGRAPH_DOMAIN = os.getenv("SOURCEGRAPH_DOMAIN", "sourcegraph.com")
STREAM_URL: str = f"https://{SOURCEGRAPH_DOMAIN}/.api/completions/stream"
MODEL_CONFIG_URL: str = f"https://{SOURCEGRAPH_DOMAIN}/.api/modelconfig/supported-models.json"

PARAMS: dict[str, str] = {
    "api-version": "2",
    "client-name": "web",
    "client-version": "0.0.1",
}

HEADERS_TEMPLATE: dict[str, str] = {
    "cache-control": "no-cache",
    "x-sourcegraph-client": f"https://{SOURCEGRAPH_DOMAIN}",
    "x-requested-with": "Sourcegraph",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "accept": "text/event-stream",
    "content-type": "application/json; charset=utf-8",
}


def transform_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    transformed_messages: list[dict[str, str]] = []
    for msg in messages:
        APP.logger.debug(msg)

        speaker: str = msg.get("role", "")
        if speaker == "developer":
            speaker = "system"
        elif speaker == "user":
            speaker = "human"

        text: str = msg.get("content", "")
        transformed_message: dict[str, str] = {"text": text, "speaker": speaker}

        APP.logger.debug(transformed_message)

        transformed_messages.append(transformed_message)

    return transformed_messages

@APP.route("/v1/chat/completions", methods=["POST"])
def chat_completions() -> Response:
    headers: dict[str, str] = HEADERS_TEMPLATE.copy()

    auth_token: str = request.headers.get("Authorization", "").strip()
    if auth_token.startswith("Bearer "):
        headers["cookie"] = "sgs={};".format(auth_token.split()[1])

    request_data: dict[str, Any] = request.get_json()

    APP.logger.debug("{} | {}".format(request.headers, request_data))

    if not request_data or "model" not in request_data or "messages" not in request_data:
        raise Exception

    model: str = request_data["model"]
    messages: list[dict[str, str]] = request_data["messages"]

    max_tokens_original: int | None = request_data.get("max_tokens")
    max_tokens: int = 4000
    if isinstance(max_tokens_original, int) and max_tokens_original < max_tokens:
        max_tokens = max_tokens_original

    transformed_messages: list[dict[str, str]] = transform_messages(messages)

    data: dict[str, Any] = {
        "temperature": 0.2,
        "topK": -1,
        "topP": -1,
        "maxTokensToSample": max_tokens,
        "model": model,
        "messages": transformed_messages,
    }

    def event_stream() -> Iterator[str]:
        APP.logger.debug(data)

        response: requests.Response = requests.post(STREAM_URL, headers=headers, params=PARAMS, json=data, stream=True)

        message_id: str = "chatcmpl-123"
        system_fingerprint: str = "fp_44709d6fcb"

        response_data: dict[str, Any]

        if not response.ok:
            response_data = {
                "id": message_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "system_fingerprint": system_fingerprint,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": f"# Error {response.status_code}\n\nGot the following response:\n\n```\n{response.text.strip()}\n```\n",
                    },
                    "logprobs": None,
                    "finish_reason": None
                }]
            }

            APP.logger.debug(response_data)

            yield "data: {}\n\n".format(json.dumps(response_data))

            response_data = {
                "id": message_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "system_fingerprint": system_fingerprint,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "logprobs": None,
                    "finish_reason": "error",
                }]
            }

            APP.logger.debug(response_data)

            yield "data: {}\n\ndata: [DONE]\n\n".format(json.dumps(response_data))

            return

        response_content_type: str | None = response.headers.get("content-type")
        if response_content_type != "text/event-stream":
            response_data = {
                "id": message_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "system_fingerprint": system_fingerprint,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "logprobs": None,
                    "finish_reason": f"# Error\n\nUnexpected content type: `{response_content_type}`\n",
                }]
            }

            APP.logger.debug(response_data)

            yield "data: {}\n\ndata: [DONE]\n\n".format(json.dumps(response_data))

            return

        for line in response.iter_lines(decode_unicode=True):
            if line.startswith("data:"):
                event_data: str = line[5:].strip()
                if event_data:
                    created_at: int = int(time.time())
                    try:
                        json_data: dict[str, Any] = json.loads(event_data)
                        if "deltaText" in json_data:
                            delta_text: str = json_data["deltaText"]
                            response_data = {
                                "id": message_id,
                                "object": "chat.completion.chunk",
                                "created": created_at,
                                "model": model,
                                "system_fingerprint": system_fingerprint,
                                "choices": [{
                                    "index": 0,
                                    "delta": {
                                        "role": "assistant",
                                        "content": delta_text,
                                    },
                                    "logprobs": None,
                                    "finish_reason": None,
                                }]
                            }

                            APP.logger.debug(response_data)

                            yield "data: {}\n\n".format(json.dumps(response_data))

                        elif "stopReason" in json_data and json_data["stopReason"] == "end_turn":
                            response_data = {
                                "id": message_id,
                                "object": "chat.completion.chunk",
                                "created": created_at,
                                "model": model,
                                "system_fingerprint": system_fingerprint,
                                "choices": [{
                                    "index": 0,
                                    "delta": {},
                                    "logprobs": None,
                                    "finish_reason": "stop",
                                }]
                            }

                            APP.logger.debug(response_data)

                            yield "data: {}\n\ndata: [DONE]\n\n".format(json.dumps(response_data))

                            break

                    except json.JSONDecodeError as e:
                        response_data = {
                            "id": message_id,
                            "object": "chat.completion.chunk",
                            "created": created_at,
                            "model": model,
                            "system_fingerprint": system_fingerprint,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "logprobs": None,
                                "finish_reason": f"# Error\n\n```\n{str(e)}\n```\n",
                            }]
                        }

                        APP.logger.debug(response_data)

                        yield "data: {}\n\ndata: [DONE]\n\n".format(json.dumps(response_data))

                        break

    return Response(event_stream(), mimetype="text/event-stream")

@APP.route("/v1/models", methods=["GET"])
def list_models() -> Response:
    headers = HEADERS_TEMPLATE.copy()

    auth_token: str = request.headers.get("Authorization", "").strip()
    if auth_token.startswith("Bearer "):
        headers["cookie"] = "sgs={};".format(auth_token.split()[1])

    response: requests.Response = requests.get(MODEL_CONFIG_URL, headers=headers)

    if not response.ok:
        error_response_data = {
            "error": f"Failed to fetch models from {MODEL_CONFIG_URL}. Status code: {response.status_code}",
            "message": response.text.strip(),
        }
        APP.logger.error(error_response_data)
        return Response(json.dumps(error_response_data), status=response.status_code, mimetype="application/json")

    try:
        model_config = response.json()

        models_list = []
        for model in model_config.get("models", []):
            model_ref = model.get("modelRef")
            owned_by = model_ref.split('::')[0] if '::' in model_ref else "unknown"

            models_list.append({
                "id": model_ref,
                "object": "model",
                "created": int(time.time()),
                "owned_by": owned_by,
            })

        return Response(json.dumps({"object": "list", "data": models_list}), mimetype="application/json")

    except json.JSONDecodeError as e:
        error_response_data = {
            "error": f"Failed to decode JSON response from {MODEL_CONFIG_URL}",
            "message": str(e),
        }
        APP.logger.error(error_response_data)
        return Response(json.dumps(error_response_data), status=500, mimetype="application/json")


if __name__ == "__main__":
    APP.run(debug=True)
