import logging
import sys

# Создаем форматтер с подробной информацией
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Создаем обработчик для вывода в консоль
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

# Настраиваем корневой логгер
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

# Настраиваем логгер для нашего приложения
app_logger = logging.getLogger('vacancy_monitor')
app_logger.setLevel(logging.INFO)

# Убираем дублирование логов
app_logger.propagate = False
app_logger.addHandler(console_handler)
