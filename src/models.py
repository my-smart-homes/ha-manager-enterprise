from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict


def convert_datetime_to_gmt(dt: datetime) -> str:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


class ZPModel(BaseModel):
    model_config = ConfigDict(
        json_encoders={datetime: convert_datetime_to_gmt},
        populate_by_name=True,
    )

    # @model_validator(mode="before")
    # @classmethod
    # def set_null_microseconds(cls, data: dict[str, Any]) -> dict[str, Any]:
    #     datetime_fields = {
    #         k: v.replace(microsecond=0)
    #         for k, v in data.items()
    #         if isinstance(k, datetime)
    #     }
    #
    #     return {**data, **datetime_fields}

    def serializable_dict(self, **kwargs):
        """Return a dict which contains only serializable fields."""
        default_dict = self.model_dump()

        return jsonable_encoder(default_dict)