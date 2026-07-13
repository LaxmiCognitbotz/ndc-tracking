from pydantic import BaseModel


class EmailRecipientSchema(BaseModel):
    id: str | None = None
    name: str
    email: str
    department: str
    role: str | None = None

    model_config = {"from_attributes": True}


class FnfEmailRequest(BaseModel):
    email: str
    record_id: int
