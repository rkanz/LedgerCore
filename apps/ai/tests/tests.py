from django.test import SimpleTestCase

from apps.ai.client import CloudflareAIClient
from apps.ai.schemas import TransactionCategory, TransactionCategoryOutput


class CloudflareAIClientTests(SimpleTestCase):
    def test_chat_completion(self):
        client=CloudflareAIClient()
        response=client.chat(
            [
                {
                    "role": "user",
                    "content": "Say hello in Persian.",
                }
            ]
        )
        print(response)
        self.assertIn("choices", response)
        self.assertEqual(response["choices"][0]["message"]["role"], "assistant")
        self.assertIsNotNone(response["choices"][0]["message"]["content"])

    def test_structured_output(self):
        client = CloudflareAIClient()

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "transaction_category",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": [
                                "Food",
                                "Transport",
                                "Bills",
                                "Shopping",
                                "Salary",
                                "Transfer",
                                "Other",
                            ],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                    },
                    "required": ["category", "confidence"],
                    "additionalProperties": False,
                },
            },
        }

        response = client.chat(
            [
                {
                    "role": "user",
                    "content": "خرید نان و شیر از فروشگاه",
                }
            ],
            response_format=response_format,
        )

        data = client.parse_json_response(response)
        validated_data = TransactionCategoryOutput.model_validate(data)

        print(validated_data)

        self.assertIsInstance(validated_data.category, TransactionCategory)
        self.assertGreaterEqual(validated_data.confidence, 0)
        self.assertLessEqual(validated_data.confidence, 1)      