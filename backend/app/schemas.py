from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Slug = Annotated[str, Field(min_length=1, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


def check_options(v: dict[str, str]) -> dict[str, str]:
    if len(v) > 5:
        raise ValueError("at most 5 option types per variant")
    for k, val in v.items():
        if not k.strip() or len(k) > 30:
            raise ValueError("option names must be 1-30 characters")
        if not val.strip() or len(val) > 50:
            raise ValueError("option values must be 1-50 characters")
    return v


def check_specs(v: Optional[dict]) -> Optional[dict]:
    """Specification rule: flat object, <=30 keys, keys <=50 chars, values str/int/float/bool."""
    if v is None:
        return v
    if len(v) > 30:
        raise ValueError("specifications allow at most 30 keys")
    for k, val in v.items():
        if not k.strip() or len(k) > 50:
            raise ValueError("specification keys must be 1-50 characters")
        if not isinstance(val, (str, int, float, bool)) or (isinstance(val, str) and len(val) > 200):
            raise ValueError("specification values must be flat str/number/bool (max 200 chars)")
    return v


class CategoryCreate(BaseModel):
    name: Name
    slug: Slug
    parent_id: Optional[int] = None


class CategoryUpdate(BaseModel):
    name: Optional[Name] = None
    slug: Optional[Slug] = None
    parent_id: Optional[int] = None  # send null explicitly to move to root
    is_active: Optional[bool] = None


class ProductCreate(BaseModel):
    name: Name
    slug: Slug
    description: str = Field(default="", max_length=5000)
    category_id: int
    specifications: Optional[dict] = None
    _specs = field_validator("specifications")(check_specs)


class ProductUpdate(BaseModel):
    name: Optional[Name] = None
    slug: Optional[Slug] = None
    description: Optional[str] = Field(default=None, max_length=5000)
    category_id: Optional[int] = None
    status: Optional[Literal["draft", "published", "archived"]] = None
    specifications: Optional[dict] = None
    _specs = field_validator("specifications")(check_specs)


class VariantCreate(BaseModel):
    option_values: dict[str, str]
    _opts = field_validator("option_values")(check_options)


class SkuCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{2,39}$")
    price: Money
    stock_quantity: int = Field(default=0, ge=0)
    is_active: bool = True
    variant_id: Optional[int] = None
    option_values: Optional[dict[str, str]] = None

    @field_validator("option_values")
    @classmethod
    def _opts(cls, v):
        return check_options(v) if v is not None else v

    @model_validator(mode="after")
    def _one_target(self):
        if self.variant_id is not None and self.option_values is not None:
            raise ValueError("send either variant_id or option_values, not both")
        return self


class SkuUpdate(BaseModel):
    price: Optional[Money] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class LoginRequest(BaseModel):
    email: str
    password: str
