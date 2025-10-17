from pydantic import BaseModel


class Base(BaseModel):
    class Config:
        populate_by_name = True
        extra = "ignore"

