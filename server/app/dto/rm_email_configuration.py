from pydantic import BaseModel


class RmEmailCreate(BaseModel):
    rm_name: str
    email: str


class RmEmailUpdate(BaseModel):
    rm_name: str
    email: str
