import json
import logging

from apps.ai.client import CloudflareAIClient
from apps.ai.schemas import FinancialSummaryOutput, TransactionCategoryOutput
from apps.analytics.services import get_financial_summary
from apps.transactions.models import Tag, Transaction

logger = logging.getLogger(__name__)

def categorize_transaction(transaction):
    if not transaction.description.strip():
        return None  
    available_tags=list(Tag.objects.values_list("name",flat=True))
    messages=[
        {
            "role":"system",
            "content":(
                "You categorize financial transactions.\n"
                "Choose exactly one category.\n"
                "Choose between 1 and 3 tags.\n"
                "Prefer using relevant tags from the existing tag list.\n"
                "If a relevant existing tag is available, use it instead of "
                "creating a new tag.\n"
                "Only suggest a new tag when none of the existing tags are relevant.\n"
                "New tags must be short, meaningful, and lowercase.\n"
                "Return existing tags exactly as they appear in the provided list.\n"
                "Do not rename, pluralize, translate, or change the case of existing tags.\n"
                "If the transaction description does not contain enough meaningful\n"
                "information to determine a category, choose OTHER and use a low confidence."
            )
        },
            {
            "role":"user",
            "content":(
                "Transaction description: "
                f"{transaction.description}\n"
                f"Existing tags: {', '.join(available_tags)}"
            )
        }
    ]
    client=CloudflareAIClient()
    response=client.chat(
        messages=messages,
        response_format={
            "type":"json_schema",
            "json_schema":{
                "name":"transaction.category",
                "schema":{
                    "type":"object",
                    "properties":{
                        "category":{
                            "type":"string",
                            "enum": [
                                "FOOD",
                                "SHOPPING",
                                "TRANSPORT",
                                "BILLS",
                                "HEALTH",
                                "HOME",
                                "ENTERTAINMENT",
                                "TRAVEL",
                                "SALARY",
                                "TRANSFER",
                                "OTHER",
                            ],
                        },
                        "confidence":{
                            "type":"number",
                            "minimum":0,
                            "maximum":1
                        },
                        "tags":{
                            "type":"array",
                            "items":{
                                "type":"string"
                            },
                            "minItems":0,
                            "maxItems":3
                        },
                    },
                    "required":[
                        "category",
                        "confidence",
                        "tags"
                    ],
                    "additionalProperties": False
                },
            },
        },
    )

    result=client.parse_json_response(response)
    validated_result=TransactionCategoryOutput.model_validate(result) # type: ignore
    normalized_tags=[]
    for tag_name in validated_result.tags:
        tag_name=tag_name.strip().lower()
        tag,_=Tag.objects.get_or_create(name=tag_name)
        normalized_tags.append(tag.name)
    transaction.category=validated_result.category.value
    transaction.save(update_fields=["category"])
    transaction.tags.set(
        Tag.objects.filter(name__in=normalized_tags)
    )
    validated_result.tags = normalized_tags
    return validated_result

def safe_categorize_transaction(transaction_id):
    try:
        transaction=Transaction.objects.get(pk=transaction_id)
        categorize_transaction(transaction)
        logger.info(
            "Transaction categorized by AI: transaction_id=%s ",
            transaction_id,
        )
    except Exception:
        logger.exception(
            "AI transaction categorization failed: transaction_id=%s",
            transaction_id,
        )

def generate_financial_summary(financial_data):
    messages=[
        {
        "role":"system",
        "content": (
            "You are a financial analysis assistant.\n"
            "Analyze only the financial data provided to you.\n"
            "Use the data to identify meaningful financial patterns and observations.\n"
            "Do not invent or assume information that is not provided.\n"
            "Do not simply repeat the provided numbers.\n"
            "Base recommendations only on meaningful observations from the data.\n"
            "If the data is insufficient for a meaningful conclusion, do not speculate.\n"
            "Return one summary, 1 to 4 insights, and 1 to 3 recommendations."
        )               
        },{
        "role":"user",
        "content":(
            "Financial summary:\n"
            f"{json.dumps(financial_data, default=str)}"
            )
        }
    ]
    
    client=CloudflareAIClient()
    response=client.chat(
        messages=messages,
        response_format={
                    "type":"json_schema",
                    "json_schema": {
                "type": "object",
                "properties": {
                "summary": {
                    "type": "string",
                },
                "insights": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "minItems": 1,
                    "maxItems": 4,
                },
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "minItems": 1,
                    "maxItems": 3,
                },
            },
            "required": [
                "summary",
                "insights",
                "recommendations",
            ],
            "additionalProperties": False,
        }
            }
    )
    print("\nRAW CONTENT:")
    print(response["choices"][0]["message"]["content"])
    result=client.parse_json_response(response)
    print("\nRAW AI RESULT:")
    print(result)
    validated_result=FinancialSummaryOutput.model_validate(result)
    return validated_result