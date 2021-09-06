from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class NewCustomerData:
    org_name: str
    country_code: str
    date_start: datetime
    date_end: datetime
    aggregation_layer_id: int
    cloud_percentage: int
    use_sentinel1: bool
    use_sentinel2: bool
    user_ids: List[int]

    project_name: str = None


@dataclass
class NewUserData:
    first_name: str
    last_name: str
    email: str
    create_token: bool
    language: str


@dataclass
class UpgradeTestGroupData:
    test_group_id: int
    users_data: List[NewUserData]
