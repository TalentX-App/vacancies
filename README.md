# vacancies

# TalentX Vacancies API

API для управления и поиска вакансий с удаленной работой. API предоставляет возможности создания, чтения, обновления и удаления вакансий, а также расширенного поиска с фильтрацией.

## Технологический стек

- Python 3.9+
- FastAPI
- MongoDB (с использованием motor)
- Pydantic для валидации данных
- Prometheus для метрик

## Установка и запуск

### Предварительные требования

- Python 3.9 или выше
- MongoDB
- Poetry (опционально)

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Настройка окружения

Создайте файл `.env` в корневой директории проекта:

```env
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=vacancies_db
```

### Запуск приложения

```bash
python main.py
```

По умолчанию API будет доступен по адресу: `http://localhost:10000`

## API Endpoints

### Получение списка вакансий

```http
GET /api/vacancies
```

#### Параметры запроса

| Параметр       | Тип    | Описание                                          | По умолчанию   |
| -------------- | ------ | ------------------------------------------------- | -------------- |
| skip           | int    | Количество пропускаемых записей                   | 0              |
| limit          | int    | Количество записей на странице (max: 100)         | 10             |
| company        | string | Фильтр по названию компании                       | null           |
| specialization | string | Поиск по специализации в заголовке/описании       | null           |
| salary_min     | int    | Минимальная зарплата                              | null           |
| salary_max     | int    | Максимальная зарплата                             | null           |
| sort_by        | string | Поле для сортировки (published_date/title)        | published_date |
| sort_order     | int    | Порядок сортировки (-1: убывание, 1: возрастание) | -1             |

#### Пример ответа

```json
{
	"vacancies": [
		{
			"id": "507f1f77bcf86cd799439011",
			"title": "Senior Python Developer",
			"published_date": "2024-01-01T12:00:00Z",
			"work_format": "remote",
			"salary": {
				"amount": "5000-7000",
				"currency": "USD",
				"range": {
					"min": 5000,
					"max": 7000
				}
			},
			"location": "Remote",
			"company": "TechCorp",
			"description": "...",
			"contacts": {
				"type": "email",
				"value": "hr@techcorp.com"
			},
			"parsed_at": "2024-01-01T12:05:00Z"
		}
	],
	"total": 1
}
```

### Получение вакансии по ID

```http
GET /api/vacancies/{vacancy_id}
```

#### Параметры пути

| Параметр   | Тип    | Описание                       |
| ---------- | ------ | ------------------------------ |
| vacancy_id | string | ID вакансии (MongoDB ObjectId) |

#### Пример ответа

```json
{
	"id": "507f1f77bcf86cd799439011",
	"title": "Senior Python Developer",
	"published_date": "2024-01-01T12:00:00Z",
	"work_format": "remote",
	"salary": {
		"amount": "5000-7000",
		"currency": "USD",
		"range": {
			"min": 5000,
			"max": 7000
		}
	},
	"location": "Remote",
	"company": "TechCorp",
	"description": "...",
	"contacts": {
		"type": "email",
		"value": "hr@techcorp.com"
	},
	"parsed_at": "2024-01-01T12:05:00Z"
}
```

### Создание вакансии

```http
POST /api/vacancies
```

#### Тело запроса

```json
{
	"title": "Senior Python Developer",
	"published_date": "2024-01-01T12:00:00Z",
	"work_format": "remote",
	"salary": {
		"amount": "5000-7000",
		"currency": "USD",
		"range": {
			"min": 5000,
			"max": 7000
		}
	},
	"location": "Remote",
	"company": "TechCorp",
	"description": "...",
	"contacts": {
		"type": "email",
		"value": "hr@techcorp.com"
	}
}
```

### Обновление вакансии

```http
PUT /api/vacancies/{vacancy_id}
```

#### Параметры пути

| Параметр   | Тип    | Описание                       |
| ---------- | ------ | ------------------------------ |
| vacancy_id | string | ID вакансии (MongoDB ObjectId) |

#### Тело запроса

Все поля опциональны. Обновляются только переданные поля.

```json
{
	"title": "Updated Senior Python Developer",
	"salary": {
		"amount": "6000-8000",
		"currency": "USD",
		"range": {
			"min": 6000,
			"max": 8000
		}
	}
}
```

### Удаление вакансии

```http
DELETE /api/vacancies/{vacancy_id}
```

#### Параметры пути

| Параметр   | Тип    | Описание                       |
| ---------- | ------ | ------------------------------ |
| vacancy_id | string | ID вакансии (MongoDB ObjectId) |

#### Пример ответа

```json
{
	"status": "Vacancy deleted successfully"
}
```

## Мониторинг

API включает интеграцию с Prometheus для мониторинга. Метрики доступны по эндпоинту:

```http
GET /metrics
```

## Схемы данных

### Vacancy

| Поле           | Тип      | Описание                  | Обязательное |
| -------------- | -------- | ------------------------- | ------------ |
| title          | string   | Заголовок вакансии        | Да           |
| published_date | datetime | Дата публикации           | Да           |
| work_format    | string   | Формат работы             | Да           |
| salary         | object   | Информация о зарплате     | Нет          |
| location       | string   | Местоположение            | Да           |
| company        | string   | Название компании         | Нет          |
| description    | string   | Описание вакансии         | Да           |
| contacts       | object   | Контактная информация     | Да           |
| parsed_at      | datetime | Дата добавления в систему | Авто         |

### SalaryInfo

| Поле     | Тип    | Описание                   |
| -------- | ------ | -------------------------- |
| amount   | string | Текстовое представление    |
| currency | string | Валюта                     |
| range    | object | Минимальная и максимальная |

### ContactInfo

| Поле  | Тип    | Описание          |
| ----- | ------ | ----------------- |
| type  | string | Тип контакта      |
| value | string | Значение контакта |

## Обработка ошибок

API использует стандартные HTTP коды состояния:

- 200: Успешный запрос
- 400: Некорректный запрос
- 404: Ресурс не найден
- 500: Внутренняя ошибка сервера

При ошибке возвращается JSON с описанием:

```json
{
	"detail": "Error description"
}
```

## Лицензия

MIT
