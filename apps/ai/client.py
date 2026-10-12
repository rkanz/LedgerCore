import json

import httpx
from django.conf import settings


class CloudflareAIClient:
    def __init__(self):
        self.account_id=settings.CLOUDFLARE_ACCOUNT_ID
        self.api_token=settings.CLOUDFLARE_API_TOKEN
        self.model=settings.CLOUDFLARE_AI_MODEL

        self.url=(
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{self.account_id}/ai/v1/chat/completions"
        )
    def chat(self,messages,response_format=None):
        headers={
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        payload= {
            "model":self.model,
            "messages":messages,
        }
        print("PAYLOAD:", payload)
        if response_format is not None:
            payload["response_format"] = response_format
        with httpx.Client(timeout=30.0) as client:
            response=client.post(
                self.url,
                headers=headers,
                json=payload
            )
            if not response.is_success:
                print("Cloudflare status:", response.status_code)
                print("Cloudflare response:", response.text)

            response.raise_for_status()

            return response.json()
    def parse_json_response(self, response):
        content = response["choices"][0]["message"]["content"]

        return json.loads(content)