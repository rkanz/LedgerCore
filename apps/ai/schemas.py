from enum import Enum

from pydantic import BaseModel, Field


class TransactionCategory(str, Enum):
    FOOD = "FOOD"
    SHOPPING = "SHOPPING"
    TRANSPORT = "TRANSPORT"
    BILLS = "BILLS"
    HEALTH = "HEALTH"
    HOME = "HOME"
    ENTERTAINMENT = "ENTERTAINMENT"
    TRAVEL = "TRAVEL"
    SALARY = "SALARY"
    TRANSFER = "TRANSFER"
    OTHER = "OTHER"


class TransactionCategoryOutput(BaseModel):
    category:TransactionCategory
    confidence:float=Field(ge=0,le=1)
    tags:list[str] = Field(min_length=0,max_length=3)

class FinancialSummaryOutput(BaseModel):
    summary:str
    insights:list[str]=Field(min_length=1,max_length=4)
    recommendations:list[str]=Field(min_length=1,max_length=3)