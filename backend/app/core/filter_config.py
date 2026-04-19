# backend/app/core/filter_config.py

from typing import Dict, List, Optional

"""
SCBR V3.0 通用過濾規則配置 (Universal Filter Configuration)
[Update] 切換為「白名單 (Allow List)」模式，實作分區封鎖法 (Zone Blocking)。
"""

# 定義臟腑關係網 (ZangFu Network) - 白名單
# 當主病位是 Key 時，只允許 Value 中的病位進入 Top-N
ZANGFU_ALLOW_LIST: Dict[str, List[str]] = {
    "肺系": ["肺系", "脾胃", "心系", "外感", "氣血津液"],  # 脾為生痰之源，心肺同居上焦，外感常犯肺，氣血津液包含虛勞
    "心系": ["心系", "肺系", "脾胃", "肝膽", "氣血津液"],  # 肝木生心火
    "脾胃": ["脾胃", "肺系", "心系", "肝膽", "大腸", "氣血津液"],
    "肝膽": ["肝膽", "心系", "脾胃", "腎系", "氣血津液"],
    "腎系": ["腎系", "肝膽", "肺系", "膀胱", "氣血津液"],  # 肺腎金水相生
    "肢體經絡": ["肢體經絡", "肝膽", "腎系", "氣血津液"], # 肝主筋，腎主骨
    "婦科": ["婦科", "肝膽", "腎系", "脾胃", "氣血津液"], # 婦科常與肝脾腎相關
    # "氣血津液" 本身通常作為通用類別，或依據具體症狀歸類，這裡暫不設限或允許所有
}

def get_allowed_categories(primary_location: str) -> Optional[List[str]]:
    """
    指令層過濾器：只回傳「白名單」內的類別
    """
    return ZANGFU_ALLOW_LIST.get(primary_location, [])