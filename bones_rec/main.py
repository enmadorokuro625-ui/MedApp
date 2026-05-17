"""
Точка входа: выбор упражнения и сложности через консольное меню.
"""

import sys
from exercises import EXERCISE_REGISTRY
from base_exercise import BaseExercise
from exercise_tracker import ExerciseTracker


def print_menu():
    """Выводит меню выбора упражнения."""
    print("\n" + "=" * 50)
    print("  ТРЕКЕР УПРАЖНЕНИЙ — MedApp")
    print("=" * 50)
    print("\nДоступные упражнения:\n")
    for num, exercise_cls in EXERCISE_REGISTRY.items():
        # Создаём временный экземпляр для получения имени
        temp = exercise_cls.__new__(exercise_cls)
        print(f"  {num}. {temp.name}")
    print(f"\n  0. Выход")


def choose_difficulty() -> str:
    """Запрашивает у пользователя уровень сложности."""
    print("\nУровень сложности:\n")
    print("  1. Лёгкий   — мягкие углы, для начинающих")
    print("  2. Средний   — стандартные углы")
    print("  3. Сложный   — строгие углы, полная амплитуда")
    print()

    mapping = {
        "1": BaseExercise.DIFFICULTY_EASY,
        "2": BaseExercise.DIFFICULTY_MEDIUM,
        "3": BaseExercise.DIFFICULTY_HARD,
    }

    while True:
        choice = input("Выберите сложность (1-3): ").strip()
        if choice in mapping:
            return mapping[choice]
        print("  ✗ Неверный ввод. Попробуйте ещё раз.")


def main():
    while True:
        print_menu()
        choice = input("\nВыберите упражнение (0-8): ").strip()

        if choice == "0":
            print("\nДо свидания!\n")
            sys.exit(0)

        if not choice.isdigit() or int(choice) not in EXERCISE_REGISTRY:
            print("  ✗ Неверный ввод. Попробуйте ещё раз.")
            continue

        exercise_cls = EXERCISE_REGISTRY[int(choice)]
        difficulty = choose_difficulty()

        # Создаём экземпляр упражнения
        exercise = exercise_cls(difficulty=difficulty)

        print(f"\n→ Запуск: {exercise.name} ({exercise.get_difficulty_label()})")
        print("  ESC — выход  |  R — сброс счётчика\n")

        # Запуск трекера
        tracker = ExerciseTracker(exercise=exercise)
        tracker.run()


if __name__ == "__main__":
    main()
