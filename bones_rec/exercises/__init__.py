"""
Пакет упражнений.
Экспортирует все доступные классы упражнений.
"""

from exercises.push_ups import PushUps
from exercises.squats import Squats
from exercises.bicep_curls import BicepCurls
from exercises.shoulder_press import ShoulderPress
from exercises.lunges import Lunges
from exercises.jumping_jacks import JumpingJacks
from exercises.sit_ups import SitUps
from exercises.high_knees import HighKnees

# Реестр всех упражнений: ключ → класс
EXERCISE_REGISTRY = {
    1: PushUps,
    2: Squats,
    3: BicepCurls,
    4: ShoulderPress,
    5: Lunges,
    6: JumpingJacks,
    7: SitUps,
    8: HighKnees,
}

__all__ = [
    "PushUps",
    "Squats",
    "BicepCurls",
    "ShoulderPress",
    "Lunges",
    "JumpingJacks",
    "SitUps",
    "HighKnees",
    "EXERCISE_REGISTRY",
]
