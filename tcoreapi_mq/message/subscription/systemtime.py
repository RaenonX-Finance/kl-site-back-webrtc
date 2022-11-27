from datetime import datetime, timedelta, timezone

from .common import CommonData


def time_round_second_to_min(dt: datetime) -> datetime:
    if dt.second > 30:
        dt += timedelta(minutes=1)
        dt = dt.replace(second=0)

    return dt


class SystemTimeData:
    def __init__(self, timestamp: datetime):
        self.timestamp: datetime = time_round_second_to_min(timestamp.replace(tzinfo=timezone.utc))
        self.epoch_sec: float = self.timestamp.timestamp()

    @staticmethod
    def from_common_data(data: CommonData) -> "SystemTimeData":
        return SystemTimeData(datetime.strptime(
            f"{data.body['Date']} {data.body['Time']:>06}",
            "%Y%m%d %H%M%S"
        ))

    @staticmethod
    def from_datetime(dt: datetime) -> "SystemTimeData":
        return SystemTimeData(dt)
